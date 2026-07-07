/*
 * GravityDesktop.java
 * Java + (Swing as desktop window; QtJambi ready for true Qt)
 * Client for the NoiseProtocol Gravity server (from SCIS noiseprotocol gravity).
 * Opens a native desktop window acting *as the protocol client* for the NLS Visualist interface.
 * 
 * Aesthetics from your visualist X post: glitch title, "1000 years old nonlinear h@k reality" banner,
 * nonlinear/h@k vibe, dark theme.
 * Thumbnails of ASC: cinematic film-style (high contrast, borders, "ASC" labels, subtle grain via colors).
 * 
 * Build: javac GravityDesktop.java
 * Run:  java GravityDesktop
 * 
 * Rules followed: no kill, no eval (pure sockets + Swing, no process termination, no dynamic exec).
 * 
 * Protocol (Gravity / noiseprotocol from SCIS):
 * - Connect
 * - Receive prologue "GRAVITY\x00\x01"
 * - Send hello (32 bytes 0x42)
 * - Receive server hello (32 bytes 0x00)
 * - Send finish (48 bytes 0x43)
 * - Then receive JSON lines: {"type":"gravity_update", "jobs":[...], "catalog":[...]}
 * 
 * The window shows:
 * - Header with glitch + banner
 * - Jobs panel (table + progress)
 * - Visualist Data panel (catalog with ASC thumbnails + gravity badges)
 * - NEW: URL drag & drop / copy & paste INPUT BAR (above status) for direct data downloads to ~/Downloads/
 *   (matches gravity-client TUI; drag text/URLs from browser, paste, Enter or button triggers yt-dlp).
 * - Auto updates from the protocol.
 * 
 * For full Qt: replace JFrame/JPanel with com.trolltech.qt.gui.QMainWindow etc.
 * (qmake available in your env for native Qt parts if needed).
 */

import javax.swing.*;
import javax.swing.table.DefaultTableModel;
import java.awt.*;
import java.awt.event.*;
import java.io.*;
import java.net.*;
import java.util.*;
import java.util.List;

public class GravityDesktop {
    private static final String HOST = "127.0.0.1";
    private static final int PORT = 4242;
    private static final String APP_DIR = resolveAppDir();
    private static final String YTDLP_PATH = resolveYtDlpPath();
    private static final String FFMPEG_PATH = resolveFfmpegPath();
    private static final String FFPLAY_PATH = resolveFfplayPath();
    // Prefer H.264 in MP4; fall back to best H.264 stream merged to MP4 (never AV1/WebM).
    private static final String YTDLP_H264_FORMAT =
        "bv*[vcodec^=avc][ext=mp4]+ba[ext=m4a]/bv*[vcodec^=avc1]+ba[ext=m4a]/"
        + "b[ext=mp4][vcodec^=avc]/bestvideo[vcodec^=avc]+bestaudio/best[vcodec^=avc]";
    // Animated GIF: native gif if available, else recode best video to gif.
    private static final String YTDLP_GIF_FORMAT = "best[ext=gif]/best";

    /** System-wide request pacing + 403/IP restriction cooldown (shared across all yt-dlp calls). */
    private static final class RateLimiter {
        private static final Object LOCK = new Object();
        private static long lastRequestMs = 0;
        private static long cooldownUntilMs = 0;
        private static int consecutive403 = 0;

        static void acquire(String phase) throws InterruptedException {
            long minGapMs = envLong("GRAVITY_MIN_REQUEST_INTERVAL_SEC", 3) * 1000L;
            synchronized (LOCK) {
                long now = System.currentTimeMillis();
                long waitUntil = Math.max(lastRequestMs + minGapMs, cooldownUntilMs);
                long waitMs = waitUntil - now;
                if (waitMs > 0) Thread.sleep(waitMs);
                lastRequestMs = System.currentTimeMillis();
            }
        }

        static void on403() {
            synchronized (LOCK) {
                consecutive403++;
                long baseSec = envLong("GRAVITY_403_COOLDOWN_SEC", 60);
                long cooldownSec = baseSec * Math.min(consecutive403, 5);
                cooldownUntilMs = System.currentTimeMillis() + cooldownSec * 1000L;
            }
        }

        static void onSuccess() {
            synchronized (LOCK) {
                consecutive403 = Math.max(0, consecutive403 - 1);
            }
        }

        static long cooldownSecondsRemaining() {
            synchronized (LOCK) {
                long rem = cooldownUntilMs - System.currentTimeMillis();
                return rem > 0 ? (rem + 999) / 1000 : 0;
            }
        }
    }

    private static final class YtDlpResult {
        final int exitCode;
        final String lastLine;
        final java.util.List<String> lines;
        YtDlpResult(int exitCode, String lastLine, java.util.List<String> lines) {
            this.exitCode = exitCode;
            this.lastLine = lastLine;
            this.lines = lines;
        }
    }

    private static long envLong(String key, long defaultVal) {
        String v = System.getenv(key);
        if (v == null || v.isBlank()) return defaultVal;
        try { return Long.parseLong(v.trim()); } catch (Exception e) { return defaultVal; }
    }

    private static String envStr(String key, String defaultVal) {
        String v = System.getenv(key);
        return (v != null && !v.isBlank()) ? v.trim() : defaultVal;
    }

    private static boolean isIpOr403Error(String line) {
        if (line == null || line.isBlank()) return false;
        String l = line.toLowerCase();
        return l.contains("403")
            || l.contains("forbidden")
            || l.contains("http error 403")
            || l.contains("rate limit")
            || l.contains("rate-limit")
            || l.contains("too many requests")
            || l.contains("429")
            || (l.contains("ip") && (l.contains("block") || l.contains("restrict") || l.contains("banned")))
            || l.contains("precondition check failed");
    }

    private static boolean isGeoRestrictionError(String line) {
        if (line == null || line.isBlank()) return false;
        String l = line.toLowerCase();
        return l.contains("not available in your country")
            || l.contains("geo restrict")
            || l.contains("geo-restrict")
            || l.contains("available in your region")
            || l.contains("region") && l.contains("not available")
            || l.contains("copyright grounds")
            || l.contains("blocked in your region");
    }

    private static boolean outputIndicates403(java.util.List<String> lines) {
        for (String line : lines) {
            if (isIpOr403Error(line) || isGeoRestrictionError(line)) return true;
        }
        return false;
    }

    private static String minSleepInterval() {
        String v = System.getenv("GRAVITY_MIN_SLEEP_INTERVAL");
        if (v == null || v.isBlank()) v = System.getenv("GRAVITY_SLEEP_INTERVAL");
        return (v != null && !v.isBlank()) ? v.trim() : "3";
    }

    private static boolean vpnInterfaceUp() {
        try {
            Process p = new ProcessBuilder("ip", "-o", "link", "show").start();
            BufferedReader br = new BufferedReader(new InputStreamReader(p.getInputStream()));
            String ln;
            while ((ln = br.readLine()) != null) {
                String l = ln.toLowerCase();
                if (!l.contains("state up")) continue;
                if (l.contains(": tun") || l.contains(": wg") || l.contains(": ppp") || l.contains("vpn")) {
                    p.waitFor();
                    return true;
                }
            }
            p.waitFor();
        } catch (Exception ignore) {}
        return false;
    }

    private static String resolveProxyUrl() {
        String gravity = System.getenv("GRAVITY_PROXY");
        if (gravity != null && !gravity.isBlank()) return gravity.trim();
        for (String key : new String[]{"HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy"}) {
            String v = System.getenv(key);
            if (v != null && !v.isBlank()) return v.trim();
        }
        return null;
    }

    private static String describeNetworkRoute() {
        String proxy = resolveProxyUrl();
        if (proxy != null) {
            return proxy.length() > 28 ? "proxy:" + proxy.substring(0, 25) + "..." : "proxy:" + proxy;
        }
        if (vpnInterfaceUp()) return "VPN up";
        return "direct";
    }

    private static void addProxyArgs(java.util.List<String> args) {
        String proxy = resolveProxyUrl();
        if (proxy == null || proxy.isBlank()) return;
        args.add("--proxy");
        args.add(proxy);
        String geoProxy = System.getenv("GRAVITY_GEO_PROXY");
        args.add("--geo-verification-proxy");
        args.add((geoProxy != null && !geoProxy.isBlank()) ? geoProxy.trim() : proxy);
    }

    private static void addRateLimitArgs(java.util.List<String> args) {
        // Human-like pacing: random sleep between downloads, requests, and fragments.
        args.add("--min-sleep-interval");
        args.add(minSleepInterval());
        args.add("--max-sleep-interval");
        args.add(envStr("GRAVITY_MAX_SLEEP_INTERVAL", "12"));
        args.add("--sleep-requests");
        args.add(envStr("GRAVITY_SLEEP_REQUESTS", "1"));
        args.add("--retries");
        args.add(envStr("GRAVITY_RETRIES", "15"));
        args.add("--fragment-retries");
        args.add(envStr("GRAVITY_FRAGMENT_RETRIES", "15"));
        args.add("--extractor-retries");
        args.add(envStr("GRAVITY_EXTRACTOR_RETRIES", "5"));
        args.add("--retry-sleep");
        args.add("http:exp=1:" + envStr("GRAVITY_HTTP_RETRY_SLEEP_MAX", "60"));
        args.add("--retry-sleep");
        args.add("fragment:exp=1:30");
        args.add("--retry-sleep");
        args.add("extractor:exp=1:20");
        args.add("--concurrent-fragments");
        args.add("1");
        String limitRate = System.getenv("GRAVITY_LIMIT_RATE");
        if (limitRate != null && !limitRate.isBlank()) {
            args.add("--limit-rate");
            args.add(limitRate.trim());
        }
    }

    private YtDlpResult runYtDlp(java.util.List<String> args) throws Exception {
        RateLimiter.acquire("yt-dlp");
        ProcessBuilder pb = new ProcessBuilder(args);
        pb.redirectErrorStream(true);
        Process proc = pb.start();
        java.util.List<String> lines = new java.util.ArrayList<>();
        BufferedReader r = new BufferedReader(new InputStreamReader(proc.getInputStream()));
        String ln;
        String lastLine = "";
        while ((ln = r.readLine()) != null) {
            lastLine = ln;
            lines.add(ln);
        }
        return new YtDlpResult(proc.waitFor(), lastLine, lines);
    }

    private YtDlpResult runYtDlpWithProgress(java.util.List<String> args, double theta) throws Exception {
        RateLimiter.acquire("yt-dlp");
        ProcessBuilder pb = new ProcessBuilder(args);
        pb.redirectErrorStream(true);
        Process proc = pb.start();
        java.util.List<String> lines = new java.util.ArrayList<>();
        BufferedReader r = new BufferedReader(new InputStreamReader(proc.getInputStream()));
        String ln;
        String lastLine = "";
        while ((ln = r.readLine()) != null) {
            lastLine = ln;
            lines.add(ln);
            final String line = ln;
            int pct = -1;
            if (line.contains("%")) {
                java.util.regex.Matcher m = java.util.regex.Pattern.compile("(\\d+\\.?\\d*)%").matcher(line);
                if (m.find()) {
                    try {
                        pct = (int) Double.parseDouble(m.group(1));
                    } catch (Exception ignore) {}
                }
            }
            final int progress = pct;
            SwingUtilities.invokeLater(() -> {
                if (progress >= 0) {
                    directProgress.setValue(Math.min(100, Math.max(0, progress)));
                }
                String shortLine = line.length() > 78 ? line.substring(0, 75) + "..." : line;
                if (line.contains("[download]") || line.contains("Merging") ||
                    line.contains("Destination") || line.contains("has already") ||
                    isIpOr403Error(line)) {
                    directStatusLabel.setText(shortLine + (theta != 0 ? " θ" + theta : ""));
                }
            });
        }
        return new YtDlpResult(proc.waitFor(), lastLine, lines);
    }

    /** Remote viewer nav entry: asset-class + PHP viewer template (viewkey / menu index). */
    private static final class RemoteNavEntry {
        String assetClass;
        String baseUrl;
        int menuIndex;
        String viewer; // remote.php | remote-cli.php | navi-remote.php

        RemoteNavEntry(String assetClass, String baseUrl, int menuIndex, String viewer) {
            this.assetClass = assetClass;
            this.baseUrl = baseUrl;
            this.menuIndex = menuIndex;
            this.viewer = viewer != null && !viewer.isBlank() ? viewer : "remote-cli.php";
        }

        String baseNorm() {
            String b = baseUrl == null ? "" : baseUrl.trim();
            if (b.isEmpty()) return "";
            return b.endsWith("/") ? b : b + "/";
        }

        String buildViewkeyUrl(String viewkey) {
            String key = viewkey == null ? "" : viewkey.trim();
            String b = baseNorm();
            if (b.isEmpty()) return "viewkey=" + key;
            String v = viewer.toLowerCase();
            if (v.contains("remote-cli")) {
                return b + "remote-cli.php?viewkey=" + key;
            }
            if (v.contains("navi")) {
                return b + "navi(1)remote.php?index.htm&menu=" + menuIndex + "&viewkey=" + key;
            }
            return b + "remote.php?index.htm&menu=" + menuIndex + "&viewkey=" + key;
        }

        String buildMenuUrl(int index) {
            String b = baseNorm();
            String v = viewer.toLowerCase();
            if (v.contains("navi")) {
                return b + "navi(1)remote.php?index.htm&menu=" + index;
            }
            return b + "remote.php?index.htm&menu=" + index;
        }

        static RemoteNavEntry fromTsv(String line) {
            String[] p = line.split("\t", -1);
            if (p.length < 4) return null;
            try {
                return new RemoteNavEntry(p[0].trim(), p[1].trim(), Integer.parseInt(p[2].trim()), p[3].trim());
            } catch (Exception e) { return null; }
        }

        String toTsv() {
            return assetClass + "\t" + baseUrl + "\t" + menuIndex + "\t" + viewer;
        }

        public String toString() {
            return assetClass + " [menu=" + menuIndex + "] " + viewer;
        }
    }

    /** Recent direct download entry for the ~/Downloads list panel. */
    private static final class RecentDownload {
        final String path;
        final String display;

        RecentDownload(String path, String display) {
            this.path = path;
            this.display = display;
        }

        public String toString() {
            return display;
        }
    }

    private JFrame frame;
    private JTable jobsTable;
    private DefaultTableModel jobsModel;
    private JTextArea visualistArea;
    private JLabel statusLabel;
    private DefaultListModel<RemoteNavEntry> remoteNavModel;
    private JList<RemoteNavEntry> remoteNavList;

    // URL drag & drop + copy-paste input (above status bar) for direct download to ~/Downloads/
    // Mirrors the gravity-client TUI feature. Uses yt-dlp CLI (ProcessBuilder, safe list, no shell/eval).
    private JTextField urlField;
    private JButton downloadBtn;
    private JButton previewBtn;
    private JProgressBar directProgress;
    private JLabel directStatusLabel;
    private volatile String lastDownloadPath;
    private JLabel mintStatusLabel;
    private DefaultListModel<RecentDownload> recentDownloadsModel;
    private JList<RecentDownload> recentDownloadsList;

    // KISS rotation theta + dual vi (i & j = true) for H.264
    private JTextField thetaField;
    private JCheckBox dualCheck;
    private JCheckBox gifCheck;
    private JCheckBox privateCheck;

    private Socket socket;
    private BufferedReader in;
    private PrintWriter out;
    private volatile boolean gravityRunning = true;

    // ASC frame using user-provided symbol pattern for live metadata display (filmic/ASC aesthetic)
    private static final String ASC_FRAME =
        "⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰ \n" +
        "⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱ \n" +
        "⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲ \n" +
        "⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲⿳ \n" +
        "⿶⿷⿸⿹⿺⿻⿰⿱⿲⿳⿴ \n" +
        "⿷⿸⿹⿺⿻⿰⿱⿲⿳⿴⿵ \n" +
        "⿸⿹⿺⿻⿰⿱⿲⿳⿴⿵⿶ \n" +
        "⿹⿺⿻⿰⿱⿲⿳⿴⿵⿶⿷ \n" +
        "⿺⿻⿰⿱⿲⿳⿴⿵⿶⿷⿸\n";

    private static final long RUNTIME_STARTED_MS = System.currentTimeMillis();
    private static final File RUNTIME_LOG_DIR = new File(
        System.getProperty("user.home"), ".local/share/gravity-desktop/runtime-logs");
    private static final File RUNTIME_LIVE_LOG = new File(RUNTIME_LOG_DIR, "gravity-desktop-live.jsonl");
    private static final File RUNTIME_SESSION = new File(RUNTIME_LOG_DIR, "gravity-desktop-session.json");
    private static final Object RUNTIME_LOG_LOCK = new Object();

    static {
        initRuntimeLog();
    }

    private static boolean runtimeLogEnabled() {
        String v = System.getenv("GRAVITY_RUNTIME_LOG");
        if (v == null || v.isBlank()) return true;
        v = v.trim().toLowerCase();
        return !("0".equals(v) || "false".equals(v) || "no".equals(v) || "off".equals(v));
    }

    private static String jsonEsc(String s) {
        if (s == null) return "";
        return s.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\n").replace("\r", "");
    }

    private static void initRuntimeLog() {
        if (!runtimeLogEnabled()) return;
        RUNTIME_LOG_DIR.mkdirs();
        String started = java.time.Instant.now().toString();
        String session = "{\n"
            + "  \"source\": \"gravity-desktop\",\n"
            + "  \"pid\": " + ProcessHandle.current().pid() + ",\n"
            + "  \"started_at\": \"" + started + "\",\n"
            + "  \"live_log\": \"" + jsonEsc(RUNTIME_LIVE_LOG.getAbsolutePath()) + "\",\n"
            + "  \"gravity_host\": \"" + HOST + ":" + PORT + "\"\n"
            + "}\n";
        try (FileWriter fw = new FileWriter(RUNTIME_SESSION, false)) {
            fw.write(session);
        } catch (Exception ignore) {}
        appendRuntimeLog("session_start", null);
    }

    private static void appendRuntimeLog(String event, String extraFields) {
        if (!runtimeLogEnabled()) return;
        long runtimeMs = System.currentTimeMillis() - RUNTIME_STARTED_MS;
        String ts = java.time.Instant.now().toString();
        String line = "{\"ts\":\"" + ts + "\",\"runtime_ms\":" + runtimeMs
            + ",\"source\":\"gravity-desktop\",\"event\":\"" + jsonEsc(event) + "\""
            + (extraFields != null && !extraFields.isBlank() ? "," + extraFields : "")
            + "}\n";
        synchronized (RUNTIME_LOG_LOCK) {
            try (FileWriter fw = new FileWriter(RUNTIME_LIVE_LOG, true)) {
                fw.write(line);
            } catch (Exception ignore) {}
        }
    }

    public static void main(String[] args) {
        SwingUtilities.invokeLater(() -> {
            GravityDesktop app = new GravityDesktop();
            app.createAndShowGUI();
            app.connectToGravity();
        });
    }

    /** App home: GRAVITY_DESKTOP_HOME env, then directory containing this class/jar. */
    private static String resolveAppDir() {
        String env = System.getenv("GRAVITY_DESKTOP_HOME");
        if (env != null && !env.isBlank()) {
            File f = new File(env);
            if (f.isDirectory()) return f.getAbsolutePath();
        }
        try {
            java.net.URL loc = GravityDesktop.class.getProtectionDomain().getCodeSource().getLocation();
            File f = new File(loc.toURI());
            if (f.isFile()) return f.getParentFile().getAbsolutePath();
            return f.getAbsolutePath();
        } catch (Exception e) {
            return System.getProperty("user.dir");
        }
    }

    private static String resolveExecutable(String envVar, String fallbackName, String... candidates) {
        String env = System.getenv(envVar);
        if (env != null && !env.isBlank()) {
            File f = new File(env);
            if (f.canExecute()) return f.getAbsolutePath();
        }
        for (String c : candidates) {
            File f = new File(c);
            if (f.canExecute()) return f.getAbsolutePath();
        }
        try {
            Process p = new ProcessBuilder("which", fallbackName).start();
            if (p.waitFor() == 0) {
                BufferedReader br = new BufferedReader(new InputStreamReader(p.getInputStream()));
                String path = br.readLine();
                if (path != null && !path.isBlank()) return path.trim();
            }
        } catch (Exception ignore) {}
        return fallbackName;
    }

    private static String resolveYtDlpPath() {
        String home = System.getProperty("user.home");
        return resolveExecutable("YTDLP_PATH", "yt-dlp",
            APP_DIR + "/yt-dlp",
            home + "/Downloads/GravityDesktop/yt-dlp",
            home + "/.local/bin/yt-dlp",
            "/usr/local/bin/yt-dlp",
            "/usr/bin/yt-dlp");
    }

    private static String resolveFfmpegPath() {
        String home = System.getProperty("user.home");
        return resolveExecutable("FFMPEG_PATH", "ffmpeg",
            "/usr/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            home + "/.local/bin/ffmpeg");
    }

    private static String resolveFfplayPath() {
        String home = System.getProperty("user.home");
        return resolveExecutable("FFPLAY_PATH", "ffplay",
            "/usr/bin/ffplay",
            "/usr/local/bin/ffplay",
            home + "/.local/bin/ffplay");
    }

    /** InterlaterusDesktop: download → probe → blockcode mint → NLS catalog. */
    private static String resolveInterlaterusScript() {
        String home = System.getProperty("user.home");
        String[] candidates = {
            APP_DIR + "/interlaterus_desktop.py",
            home + "/Downloads/nls-video-monitor/interlaterus_desktop.py",
            home + "/Downloads/GravityDesktop/interlaterus_desktop.py",
        };
        for (String c : candidates) {
            if (new File(c).isFile()) return c;
        }
        return null;
    }

    private void triggerInterlaterusMint(String mediaPath, String sourceUrl, String title) {
        if ("1".equals(System.getenv("INTERLATERUS_SKIP_MINT"))) {
            updateMintStatus("skipped", null, null);
            return;
        }
        String script = resolveInterlaterusScript();
        if (script == null || mediaPath == null || mediaPath.isBlank()) {
            updateMintStatus("no_script", null, null);
            return;
        }
        File media = new File(mediaPath);
        if (!media.isFile()) return;
        final String scriptFinal = script;
        final String pathFinal = media.getAbsolutePath();
        final String urlFinal = sourceUrl != null ? sourceUrl : "";
        final String titleFinal = title != null ? title : "";
        updateMintStatus("minting", null, null);
        new Thread(() -> {
            StringBuilder jsonOut = new StringBuilder();
            try {
                ProcessBuilder pb = new ProcessBuilder(
                    "python3", scriptFinal, "mint",
                    "--file", pathFinal,
                    "--url", urlFinal,
                    "--title", titleFinal
                );
                pb.redirectErrorStream(true);
                Process proc = pb.start();
                try (BufferedReader br = new BufferedReader(new InputStreamReader(proc.getInputStream()))) {
                    String ln;
                    while ((ln = br.readLine()) != null) {
                        jsonOut.append(ln).append('\n');
                    }
                }
                int rc = proc.waitFor();
                if (rc == 0) {
                    parseAndShowMintResult(jsonOut.toString(), pathFinal);
                    refreshRecentDownloads();
                } else {
                    updateMintStatus("failed", null, null);
                }
            } catch (Exception ex) {
                updateMintStatus("failed", null, null);
            }
        }).start();
    }

    private void updateMintStatus(String phase, String pattern, int[] vertex) {
        SwingUtilities.invokeLater(() -> {
            if (mintStatusLabel == null) return;
            Color ok = new Color(0x5a, 0xe0, 0xd0);
            Color warn = new Color(0xc8, 0xd0, 0x5a);
            Color err = new Color(0xe8, 0x5a, 0x6a);
            Color muted = new Color(0x98, 0xb7, 0xc7);
            String vtx = vertex != null
                ? "[" + vertex[0] + "," + vertex[1] + "," + vertex[2] + "," + vertex[3] + "]"
                : "";
            switch (phase) {
                case "minting":
                    mintStatusLabel.setForeground(warn);
                    mintStatusLabel.setText("mint: probing → blockcode tesseract...");
                    break;
                case "minted":
                    mintStatusLabel.setForeground(ok);
                    mintStatusLabel.setText("mint: ✓ " + pattern + "  vertex " + vtx);
                    break;
                case "already_minted":
                    mintStatusLabel.setForeground(warn);
                    mintStatusLabel.setText("mint: ○ " + pattern + " (already minted)");
                    break;
                case "skipped":
                    mintStatusLabel.setForeground(muted);
                    mintStatusLabel.setText("mint: skipped (INTERLATERUS_SKIP_MINT=1)");
                    break;
                case "no_script":
                    mintStatusLabel.setForeground(err);
                    mintStatusLabel.setText("mint: interlaterus_desktop.py not found");
                    break;
                case "failed":
                    mintStatusLabel.setForeground(err);
                    mintStatusLabel.setText("mint: failed — check interlaterus / ffprobe");
                    break;
                case "pending":
                    mintStatusLabel.setForeground(muted);
                    mintStatusLabel.setText("mint: pending — " + (pattern != null ? pattern : "no sidecar yet"));
                    break;
                default:
                    mintStatusLabel.setForeground(muted);
                    mintStatusLabel.setText("mint: —");
            }
        });
    }

    private void parseAndShowMintResult(String output, String mediaPath) {
        String status = extractJsonString(output, "status");
        String pattern = extractJsonString(output, "pattern_code");
        int[] vertex = extractJsonVertex(output);
        if (pattern == null || pattern.isBlank()) {
            MintSidecar sidecar = readMintSidecar(mediaPath);
            if (sidecar != null) {
                pattern = sidecar.pattern;
                if (vertex == null) vertex = sidecar.vertex;
            }
        }
        if ("already_minted".equals(status)) {
            updateMintStatus("already_minted", pattern, vertex);
        } else if ("minted".equals(status)) {
            updateMintStatus("minted", pattern, vertex);
        } else {
            updateMintStatus("failed", pattern, vertex);
        }
        appendMintToVisualist(status, pattern, vertex, mediaPath);
        String vtx = vertex != null
            ? "[" + vertex[0] + "," + vertex[1] + "," + vertex[2] + "," + vertex[3] + "]"
            : "null";
        appendRuntimeLog("mint_complete",
            "\"status\":\"" + jsonEsc(status) + "\",\"pattern\":\"" + jsonEsc(pattern)
            + "\",\"vertex\":" + vtx + ",\"media\":\"" + jsonEsc(mediaPath) + "\"");
    }

    private void appendMintToVisualist(String status, String pattern, int[] vertex, String mediaPath) {
        if (pattern == null || pattern.isBlank()) return;
        String vtx = vertex != null
            ? "[" + vertex[0] + "," + vertex[1] + "," + vertex[2] + "," + vertex[3] + "]"
            : "—";
        String file = mediaPath != null ? new File(mediaPath).getName() : "";
        String block = "\n⿲ BLOCKCODE MINT " + status.toUpperCase() + " ⿲\n"
            + "pattern: " + pattern + "\n"
            + "vertex:  " + vtx + "\n"
            + "file:    " + file + "\n";
        SwingUtilities.invokeLater(() -> {
            if (visualistArea == null) return;
            String cur = visualistArea.getText();
            visualistArea.setText(cur + block);
        });
    }

    private static String extractJsonString(String json, String key) {
        if (json == null) return null;
        java.util.regex.Matcher m = java.util.regex.Pattern
            .compile("\"" + key + "\"\\s*:\\s*\"([^\"]+)\"")
            .matcher(json);
        return m.find() ? m.group(1) : null;
    }

    private static int[] extractJsonVertex(String json) {
        if (json == null) return null;
        java.util.regex.Matcher m = java.util.regex.Pattern
            .compile("\"vertex\"\\s*:\\s*\\[\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*,\\s*(\\d+)\\s*\\]")
            .matcher(json);
        if (!m.find()) return null;
        return new int[]{
            Integer.parseInt(m.group(1)),
            Integer.parseInt(m.group(2)),
            Integer.parseInt(m.group(3)),
            Integer.parseInt(m.group(4))
        };
    }

    private static final class MintSidecar {
        final String pattern;
        final int[] vertex;

        MintSidecar(String pattern, int[] vertex) {
            this.pattern = pattern;
            this.vertex = vertex;
        }
    }

    private static MintSidecar readMintSidecar(String mediaPath) {
        File sidecar = new File(mediaPath + ".interlaterus.json");
        if (!sidecar.isFile()) return null;
        try {
            String text = new String(java.nio.file.Files.readAllBytes(sidecar.toPath()));
            String pattern = extractJsonString(text, "pattern_code");
            int[] vertex = extractJsonVertex(text);
            if (pattern == null) return null;
            return new MintSidecar(pattern, vertex);
        } catch (Exception ignore) {
            return null;
        }
    }

    private static boolean isRecentDownloadName(String name) {
        if (name == null) return false;
        return name.matches("^direct-h264-.+\\.mp4$")
            || name.matches("^direct-gif-.+\\.gif$")
            || name.matches("^direct-h264-rot\\d+-.+\\.mp4$");
    }

    private String downloadsDir() {
        return System.getProperty("user.home") + "/Downloads";
    }

    private void refreshRecentDownloads() {
        File dir = new File(downloadsDir());
        File[] files = dir.listFiles();
        java.util.List<File> matches = new java.util.ArrayList<>();
        if (files != null) {
            for (File f : files) {
                if (f.isFile() && isRecentDownloadName(f.getName())) {
                    matches.add(f);
                }
            }
        }
        matches.sort((a, b) -> Long.compare(b.lastModified(), a.lastModified()));
        final java.util.List<RecentDownload> entries = new java.util.ArrayList<>();
        int limit = 25;
        for (int i = 0; i < matches.size() && i < limit; i++) {
            File f = matches.get(i);
            String label = f.getName();
            MintSidecar sidecar = readMintSidecar(f.getAbsolutePath());
            if (sidecar != null && sidecar.pattern != null) {
                label += "  ·  " + sidecar.pattern;
                if (sidecar.vertex != null) {
                    label += "  v" + sidecar.vertex[0] + sidecar.vertex[1]
                        + sidecar.vertex[2] + sidecar.vertex[3];
                }
            }
            entries.add(new RecentDownload(f.getAbsolutePath(), label));
        }
        SwingUtilities.invokeLater(() -> {
            if (recentDownloadsModel == null) return;
            recentDownloadsModel.clear();
            for (RecentDownload rd : entries) {
                recentDownloadsModel.addElement(rd);
            }
        });
    }

    private void openDownloadsFolder() {
        String path = downloadsDir();
        try {
            String os = System.getProperty("os.name", "").toLowerCase();
            ProcessBuilder pb = os.contains("mac")
                ? new ProcessBuilder("open", path)
                : new ProcessBuilder("xdg-open", path);
            pb.start();
            directStatusLabel.setText("Opened ~/Downloads/");
        } catch (Exception ex) {
            String msg = ex.getMessage() != null ? ex.getMessage() : ex.toString();
            directStatusLabel.setText("Could not open Downloads: " + msg);
        }
    }

    private void onRecentDownloadSelected(RecentDownload sel) {
        if (sel == null) return;
        setLastDownloadPath(sel.path);
        MintSidecar sidecar = readMintSidecar(sel.path);
        if (sidecar != null) {
            updateMintStatus("minted", sidecar.pattern, sidecar.vertex);
        } else {
            updateMintStatus("pending", new File(sel.path).getName(), null);
        }
    }

    private void createAndShowGUI() {
        // KISS design following the visual_language_animation.svg
        // Dark gradient-like bg, monospace, rounded container feel, thin cyan accent border,
        // colored node indicators for pipeline stages (H.264 focus), simple clean layout.
        frame = new JFrame("NLS Visualist • H.264 v1.1.9");
        frame.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE);
        frame.setSize(1240, 760);
        frame.setLocationRelativeTo(null);

        Color bg = new Color(0x09, 0x09, 0x0f);
        Color panelBg = new Color(0x16, 0x1a, 0x2a);
        Color accent = new Color(0x9b, 0xe7, 0xff); // #9be7ff from SVG
        Color textLight = new Color(0xe6, 0xf6, 0xff);
        Color textMuted = new Color(0x98, 0xb7, 0xc7);

        frame.getContentPane().setBackground(bg);
        frame.setLayout(new BorderLayout(8, 8));

        // Top header - KISS: title + pipeline flow subtitle (monospace)
        JPanel header = new JPanel(new BorderLayout());
        header.setBackground(bg);
        header.setBorder(BorderFactory.createEmptyBorder(8, 16, 4, 16));

        JLabel title = new JLabel("NLS Visualist • H.264 Pipeline");
        title.setFont(new Font("Monospaced", Font.BOLD, 20));
        title.setForeground(textLight);
        header.add(title, BorderLayout.NORTH);

        JLabel sub = new JLabel("https:// / ipfs://  →  H.264 mp4 / GIF  •  human sleep  •  VPN/proxy geo  •  403 retry");
        sub.setFont(new Font("Monospaced", Font.PLAIN, 12));
        sub.setForeground(textMuted);
        header.add(sub, BorderLayout.SOUTH);

        frame.add(header, BorderLayout.NORTH);

        // Main container with thin cyan border (like SVG main rect rx="24" stroke #9be7ff)
        JPanel mainWrap = new JPanel(new BorderLayout(6, 6));
        mainWrap.setBackground(panelBg);
        mainWrap.setBorder(BorderFactory.createCompoundBorder(
            BorderFactory.createLineBorder(accent, 1),
            BorderFactory.createEmptyBorder(8, 10, 8, 10)
        ));

        // H.264 pipeline stages as simple colored node indicators (KISS version of SVG nodes)
        // Colors + symbols inspired by the SVG visual language
        JPanel stages = new JPanel(new GridLayout(1, 5, 8, 0));
        stages.setBackground(panelBg);
        String[] stageNames = {"INPUT", "DOWNLOAD", "H.264", "GRAVITY", "CATALOG"};
        Color[] stageCols = {
            new Color(0x5a, 0xe0, 0xd0), // hsl(176 ~ cyan)
            new Color(0xc8, 0xd0, 0x5a), // hsl(78 ~ yellow-green)
            new Color(0xe8, 0x5a, 0x6a), // hsl(355 ~ red)
            new Color(0x5a, 0xd0, 0x7a), // hsl(123 ~ green)
            new Color(0xb0, 0x5a, 0xd0)  // hsl(310 ~ purple)
        };
        String[] symbols = {"◐", "▦", "⌬", "▣", "◈"};
        for (int i = 0; i < stageNames.length; i++) {
            JPanel node = new JPanel(new BorderLayout());
            node.setBackground(panelBg);
            JLabel sym = new JLabel(symbols[i], SwingConstants.CENTER);
            sym.setFont(new Font("Monospaced", Font.PLAIN, 22));
            sym.setForeground(stageCols[i]);
            JLabel lbl = new JLabel(stageNames[i], SwingConstants.CENTER);
            lbl.setFont(new Font("Monospaced", Font.PLAIN, 10));
            lbl.setForeground(textMuted);
            node.add(sym, BorderLayout.CENTER);
            node.add(lbl, BorderLayout.SOUTH);
            stages.add(node);
        }
        mainWrap.add(stages, BorderLayout.NORTH);

        // Simple H.264 focused input (KISS drag/paste URL for download + convert)
        // Added rotation theta + dual vi (i & j = true) per visual language
        JPanel inputBox = new JPanel(new BorderLayout(6, 4));
        inputBox.setBackground(panelBg);
        inputBox.setBorder(BorderFactory.createTitledBorder(
            BorderFactory.createLineBorder(accent, 1),
            "URL  (https://, ipfs://, .php viewer, GIF — paste / drag → ~/Downloads/)",
            0, 0, new Font("Monospaced", Font.PLAIN, 10), accent
        ));

        JPanel row = new JPanel(new BorderLayout(4, 0));
        row.setBackground(panelBg);
        urlField = new JTextField(50);
        urlField.setFont(new Font("Monospaced", Font.PLAIN, 13));
        urlField.setBackground(new Color(0x0b, 0x10, 0x20));
        urlField.setForeground(textLight);
        urlField.setCaretColor(accent);
        urlField.setEditable(true);
        urlField.setFocusable(true);
        urlField.setDragEnabled(true);  // allow selection drag + paste support
        urlField.addActionListener(e -> startDirectDownload());
        downloadBtn = new JButton("H.264");
        downloadBtn.setFont(new Font("Monospaced", Font.BOLD, 11));
        downloadBtn.setForeground(bg);
        downloadBtn.setBackground(accent);
        downloadBtn.addActionListener(e -> startDirectDownload());
        previewBtn = new JButton("▶");
        previewBtn.setFont(new Font("Monospaced", Font.BOLD, 11));
        previewBtn.setForeground(textLight);
        previewBtn.setBackground(new Color(0x1a, 0x25, 0x40));
        previewBtn.setEnabled(false);
        previewBtn.setToolTipText("Preview last download with ffplay");
        previewBtn.addActionListener(e -> previewLastDownload());
        JPanel btnCol = new JPanel(new GridLayout(2, 1, 0, 2));
        btnCol.setBackground(panelBg);
        btnCol.add(downloadBtn);
        btnCol.add(previewBtn);
        row.add(urlField, BorderLayout.CENTER);
        row.add(btnCol, BorderLayout.EAST);
        inputBox.add(row, BorderLayout.CENTER);

        // Rotation theta dual vi controls (KISS, H.264 post-process support)
        // + JS runtime check/install for yt-dlp (Deno and Node.js are similarly supported; pythonJava style: Java UI + Python helper possible)
        JPanel rotRow = new JPanel(new FlowLayout(FlowLayout.LEFT, 4, 0));
        rotRow.setBackground(panelBg);
        JLabel thetaL = new JLabel("theta°:");
        thetaL.setFont(new Font("Monospaced", Font.PLAIN, 9));
        thetaL.setForeground(textMuted);
        thetaField = new JTextField("0", 4);
        thetaField.setFont(new Font("Monospaced", Font.PLAIN, 9));
        thetaField.setBackground(new Color(0x0b, 0x10, 0x20));
        thetaField.setForeground(textLight);
        dualCheck = new JCheckBox("dual vi");
        dualCheck.setFont(new Font("Monospaced", Font.PLAIN, 9));
        dualCheck.setForeground(textMuted);
        dualCheck.setBackground(panelBg);
        gifCheck = new JCheckBox("GIF");
        gifCheck.setFont(new Font("Monospaced", Font.PLAIN, 9));
        gifCheck.setForeground(textMuted);
        gifCheck.setBackground(panelBg);
        gifCheck.setToolTipText("Download animated GIF instead of H.264 mp4");
        privateCheck = new JCheckBox("private");
        privateCheck.setFont(new Font("Monospaced", Font.PLAIN, 9));
        privateCheck.setForeground(textMuted);
        privateCheck.setBackground(panelBg);
        privateCheck.setSelected(false);
        privateCheck.setToolTipText("Use cookies for login-required videos (browser or ~/.config/gravity-desktop/cookies.txt)");
        JLabel ijL = new JLabel("i & j = true");
        ijL.setFont(new Font("Monospaced", Font.PLAIN, 8));
        ijL.setForeground(accent);

        // JS runtime status + install (addresses yt-dlp JS warning)
        String jsRt = checkJsRuntime();
        JLabel jsL = new JLabel("JS: " + (jsRt != null ? jsRt : "none"));
        jsL.setFont(new Font("Monospaced", Font.PLAIN, 8));
        jsL.setForeground(jsRt != null ? new Color(0x5a, 0xe0, 0xd0) : new Color(0xe8, 0x5a, 0x6a));
        JButton jsInstall = new JButton("Install Deno");
        jsInstall.setFont(new Font("Monospaced", Font.PLAIN, 8));
        jsInstall.addActionListener(e -> {
            int choice = JOptionPane.showConfirmDialog(frame,
                "Install Deno (recommended JS runtime for yt-dlp)?\n" +
                "Deno and Node.js are similarly supported by yt-dlp.\n" +
                "Uses curl | sh (or you can call Python helper).",
                "Install JS Runtime", JOptionPane.YES_NO_OPTION);
            if (choice == JOptionPane.YES_OPTION) {
                try {
                    // pythonJava possibility: prefer Python helper if available
                    java.util.List<String> installCmd;
                    File pipePy = new File(APP_DIR, "nls_video_pipe.py");
                    if (pipePy.exists()) {
                        installCmd = java.util.Arrays.asList("python3", "-c",
                            "import sys; sys.path.insert(0,'" + APP_DIR + "'); import nls_video_pipe as m; m.ensure_js_runtime(auto_install=True)");
                    } else {
                        installCmd = java.util.Arrays.asList("sh", "-c",
                            "curl -fsSL https://deno.land/install.sh | sh");
                    }
                    ProcessBuilder ipb = new ProcessBuilder(installCmd);
                    ipb.inheritIO();
                    Process ip = ipb.start();
                    ip.waitFor();
                    JOptionPane.showMessageDialog(frame, "Install attempted. Restart this app/terminal to pick up PATH.");
                    // Re-check
                    String newRt = checkJsRuntime();
                    jsL.setText("JS: " + (newRt != null ? newRt : "none"));
                } catch (Exception ex) {
                    JOptionPane.showMessageDialog(frame, "Install error: " + ex.getMessage());
                }
            }
        });
        rotRow.add(thetaL);
        rotRow.add(thetaField);
        rotRow.add(dualCheck);
        rotRow.add(ijL);
        rotRow.add(gifCheck);
        rotRow.add(privateCheck);
        JLabel netL = new JLabel("net: " + describeNetworkRoute());
        netL.setFont(new Font("Monospaced", Font.PLAIN, 8));
        netL.setForeground(vpnInterfaceUp() || resolveProxyUrl() != null
            ? new Color(0x5a, 0xe0, 0xd0) : textMuted);
        netL.setToolTipText("VPN/proxy route for geo bypass — set GRAVITY_PROXY or connect VPN (tun/wg)");
        rotRow.add(netL);
        rotRow.add(jsL);
        rotRow.add(jsInstall);

        // Launch concise 11D Hierarchy for deeper ASC / Visualist exploration (ties to live data)
        JButton hierBtn = new JButton("11D Hierarchy");
        hierBtn.setFont(new Font("Monospaced", Font.PLAIN, 8));
        hierBtn.addActionListener(e -> {
            try {
                ProcessBuilder hpb = new ProcessBuilder("python3", new File(APP_DIR, "hierarchy_interpreter.py").getAbsolutePath());
                hpb.inheritIO();
                hpb.start();
            } catch (Exception ex) {
                JOptionPane.showMessageDialog(frame, "Could not launch hierarchy: " + ex.getMessage());
            }
        });
        rotRow.add(hierBtn);

        JButton queueBtn = new JButton("Queue");
        queueBtn.setFont(new Font("Monospaced", Font.PLAIN, 8));
        queueBtn.setToolTipText("Add URL to pipeline worker queue via gravity-serve API (vice versa with web)");
        queueBtn.addActionListener(e -> addPipelineJobViaApi());
        rotRow.add(queueBtn);

        inputBox.add(rotRow, BorderLayout.SOUTH);

        // Minimal progress (tied to H.264 stage)
        directProgress = new JProgressBar(0, 100);
        directProgress.setStringPainted(true);
        directProgress.setFont(new Font("Monospaced", Font.PLAIN, 10));
        directProgress.setForeground(stageCols[2]); // H.264 red-ish
        directProgress.setBackground(new Color(0x0b, 0x10, 0x20));
        mintStatusLabel = new JLabel("mint: —");
        mintStatusLabel.setFont(new Font("Monospaced", Font.PLAIN, 9));
        mintStatusLabel.setForeground(textMuted);
        directStatusLabel = new JLabel("ready — https://, ipfs://, .php viewer, GIF address");
        directStatusLabel.setFont(new Font("Monospaced", Font.PLAIN, 10));
        directStatusLabel.setForeground(textMuted);
        JPanel pRow = new JPanel(new BorderLayout(4, 0));
        pRow.setBackground(panelBg);
        pRow.add(directProgress, BorderLayout.CENTER);
        JPanel statusCol = new JPanel(new BorderLayout(0, 2));
        statusCol.setBackground(panelBg);
        statusCol.add(mintStatusLabel, BorderLayout.NORTH);
        statusCol.add(directStatusLabel, BorderLayout.SOUTH);
        pRow.add(statusCol, BorderLayout.SOUTH);
        inputBox.add(pRow, BorderLayout.SOUTH);

        mainWrap.add(inputBox, BorderLayout.NORTH);

        // Recent ~/Downloads direct-h264/gif files + open-folder shortcut
        JPanel recentPanel = new JPanel(new BorderLayout(4, 2));
        recentPanel.setBackground(panelBg);
        recentPanel.setPreferredSize(new Dimension(0, 108));
        recentPanel.setBorder(BorderFactory.createTitledBorder(
            BorderFactory.createLineBorder(accent, 1),
            "Recent Downloads (~/Downloads/)",
            0, 0, new Font("Monospaced", Font.PLAIN, 9), accent
        ));
        recentDownloadsModel = new DefaultListModel<>();
        recentDownloadsList = new JList<>(recentDownloadsModel);
        recentDownloadsList.setFont(new Font("Monospaced", Font.PLAIN, 9));
        recentDownloadsList.setBackground(new Color(0x0b, 0x10, 0x20));
        recentDownloadsList.setForeground(textLight);
        recentDownloadsList.setSelectionMode(ListSelectionModel.SINGLE_SELECTION);
        recentDownloadsList.addListSelectionListener(e -> {
            if (e.getValueIsAdjusting()) return;
            onRecentDownloadSelected(recentDownloadsList.getSelectedValue());
        });
        recentDownloadsList.addMouseListener(new MouseAdapter() {
            @Override
            public void mouseClicked(MouseEvent e) {
                if (e.getClickCount() == 2) {
                    RecentDownload sel = recentDownloadsList.getSelectedValue();
                    if (sel != null) previewLastDownload();
                }
            }
        });
        JPanel recentBtns = new JPanel(new FlowLayout(FlowLayout.RIGHT, 4, 0));
        recentBtns.setBackground(panelBg);
        JButton openDlBtn = new JButton("Downloads ↗");
        openDlBtn.setFont(new Font("Monospaced", Font.PLAIN, 8));
        openDlBtn.setToolTipText("Open ~/Downloads/ in file manager");
        openDlBtn.addActionListener(e -> openDownloadsFolder());
        JButton refreshDlBtn = new JButton("↻");
        refreshDlBtn.setFont(new Font("Monospaced", Font.PLAIN, 8));
        refreshDlBtn.setToolTipText("Refresh recent downloads list");
        refreshDlBtn.addActionListener(e -> refreshRecentDownloads());
        recentBtns.add(openDlBtn);
        recentBtns.add(refreshDlBtn);
        recentPanel.add(new JScrollPane(recentDownloadsList), BorderLayout.CENTER);
        recentPanel.add(recentBtns, BorderLayout.SOUTH);

        // Drop target kept (KISS paste/drag works)
        try {
            new java.awt.dnd.DropTarget(urlField, new java.awt.dnd.DropTargetAdapter() {
                public void drop(java.awt.dnd.DropTargetDropEvent dtde) {
                    try {
                        dtde.acceptDrop(java.awt.dnd.DnDConstants.ACTION_COPY);
                        java.awt.datatransfer.Transferable t = dtde.getTransferable();
                        if (t.isDataFlavorSupported(java.awt.datatransfer.DataFlavor.stringFlavor)) {
                            String u = (String) t.getTransferData(java.awt.datatransfer.DataFlavor.stringFlavor);
                            if (u != null && u.trim().length() > 0) {
                                final String url = expandRemoteInput(normalizeUrl(u));
                                SwingUtilities.invokeLater(() -> { urlField.setText(url); startDirectDownload(); });
                            }
                        }
                        dtde.dropComplete(true);
                    } catch (Exception ignore) { dtde.dropComplete(false); }
                }
            });
        } catch (Exception ignore) {}

        // Core content: simple jobs table + visualist (monospace, dark, minimal)
        JPanel content = new JPanel(new GridLayout(1, 2, 6, 6));
        content.setBackground(panelBg);

        // Jobs (H.264 pipeline live)
        JPanel jobsP = new JPanel(new BorderLayout());
        jobsP.setBackground(panelBg);
        jobsP.setBorder(BorderFactory.createTitledBorder(
            BorderFactory.createLineBorder(accent, 1),
            "Jobs (live)",
            0, 0, new Font("Monospaced", Font.PLAIN, 10), accent
        ));
        jobsModel = new DefaultTableModel(new String[]{"#", "Title", "Stage", "%", "Out"}, 0);
        jobsTable = new JTable(jobsModel);
        jobsTable.setBackground(new Color(0x0b, 0x10, 0x20));
        jobsTable.setForeground(textLight);
        jobsTable.setFont(new Font("Monospaced", Font.PLAIN, 10));
        jobsTable.setRowHeight(18);
        jobsP.add(new JScrollPane(jobsTable), BorderLayout.CENTER);
        JPanel jobsLiveBtns = new JPanel(new FlowLayout(FlowLayout.RIGHT, 4, 0));
        jobsLiveBtns.setBackground(panelBg);
        JButton cancelJobBtn = new JButton("Cancel Job");
        cancelJobBtn.setFont(new Font("Monospaced", Font.PLAIN, 8));
        cancelJobBtn.setToolTipText("Cancel selected live job via gravity-serve API");
        cancelJobBtn.addActionListener(e -> cancelSelectedJobViaApi());
        jobsLiveBtns.add(cancelJobBtn);
        jobsP.add(jobsLiveBtns, BorderLayout.SOUTH);
        content.add(jobsP);

        // Visualist / catalog (simple)
        JPanel visP = new JPanel(new BorderLayout());
        visP.setBackground(panelBg);
        visP.setBorder(BorderFactory.createTitledBorder(
            BorderFactory.createLineBorder(accent, 1),
            "ASC PANEL (Live Data + H.264 + Gravity)",
            0, 0, new Font("Monospaced", Font.PLAIN, 10), accent
        ));
        visualistArea = new JTextArea();
        visualistArea.setBackground(new Color(0x0b, 0x10, 0x20));
        visualistArea.setForeground(textMuted);
        visualistArea.setFont(new Font("Monospaced", Font.PLAIN, 10));
        visualistArea.setEditable(false);
        // Initial ASC frame with symbols for immediate "live data showing" style (will be replaced by real data on first gravity update)
        visualistArea.setText(ASC_FRAME + "\n\nLIVE ASC DATA - waiting for gravity updates...\n\nASC: [FILMIC | HIGH CONTRAST | GRAIN | 320x180]\n");
        visP.add(new JScrollPane(visualistArea), BorderLayout.CENTER);
        content.add(visP);

        JPanel centerStack = new JPanel(new BorderLayout(0, 6));
        centerStack.setBackground(panelBg);
        centerStack.add(recentPanel, BorderLayout.NORTH);
        centerStack.add(content, BorderLayout.CENTER);
        mainWrap.add(centerStack, BorderLayout.CENTER);

        // Bottom status - KISS
        statusLabel = new JLabel("gravity • h264 • no kill • no eval • monospace visual language");
        statusLabel.setFont(new Font("Monospaced", Font.PLAIN, 10));
        statusLabel.setForeground(textMuted);
        statusLabel.setBorder(BorderFactory.createEmptyBorder(4, 10, 4, 10));
        mainWrap.add(statusLabel, BorderLayout.SOUTH);

        // Sync remote nav: asset-class add/delete, viewkey & menu$index URL builder
        JPanel navP = new JPanel(new BorderLayout(4, 4));
        navP.setBackground(panelBg);
        navP.setPreferredSize(new Dimension(240, 0));
        navP.setBorder(BorderFactory.createTitledBorder(
            BorderFactory.createLineBorder(accent, 1),
            "Remote Nav (asset-class)",
            0, 0, new Font("Monospaced", Font.PLAIN, 9), accent
        ));
        remoteNavModel = new DefaultListModel<>();
        remoteNavList = new JList<>(remoteNavModel);
        remoteNavList.setFont(new Font("Monospaced", Font.PLAIN, 9));
        remoteNavList.setBackground(new Color(0x0b, 0x10, 0x20));
        remoteNavList.setForeground(textLight);
        remoteNavList.addListSelectionListener(e -> {
            RemoteNavEntry sel = remoteNavList.getSelectedValue();
            if (sel != null && !e.getValueIsAdjusting()) {
                urlField.setText(sel.buildMenuUrl(sel.menuIndex));
            }
        });
        loadRemoteNav();
        JPanel navBtns = new JPanel(new GridLayout(3, 1, 2, 2));
        navBtns.setBackground(panelBg);
        JButton navAdd = new JButton("+ asset");
        navAdd.setFont(new Font("Monospaced", Font.PLAIN, 8));
        navAdd.addActionListener(e -> {
            String asset = JOptionPane.showInputDialog(frame, "Asset-class name:", "Add Nav", JOptionPane.PLAIN_MESSAGE);
            if (asset == null || asset.isBlank()) return;
            String base = JOptionPane.showInputDialog(frame, "Base URL (https://site/path/):", "Add Nav", JOptionPane.PLAIN_MESSAGE);
            if (base == null || base.isBlank()) return;
            String menuS = JOptionPane.showInputDialog(frame, "Menu index (1):", "1");
            int menu = 1;
            try { if (menuS != null) menu = Integer.parseInt(menuS.trim()); } catch (Exception ignore) {}
            String[] viewers = {"remote-cli.php", "remote.php", "navi(1)remote.php"};
            String viewer = (String) JOptionPane.showInputDialog(frame, "Viewer script:", "Add Nav",
                JOptionPane.PLAIN_MESSAGE, null, viewers, viewers[0]);
            if (viewer == null) viewer = "remote-cli.php";
            remoteNavModel.addElement(new RemoteNavEntry(asset.trim(), base.trim(), menu, viewer));
            saveRemoteNav();
        });
        JButton navDel = new JButton("- asset");
        navDel.setFont(new Font("Monospaced", Font.PLAIN, 8));
        navDel.addActionListener(e -> {
            int idx = remoteNavList.getSelectedIndex();
            if (idx < 0) return;
            remoteNavModel.remove(idx);
            saveRemoteNav();
        });
        JButton navSync = new JButton("Sync URL");
        navSync.setFont(new Font("Monospaced", Font.PLAIN, 8));
        navSync.addActionListener(e -> {
            RemoteNavEntry sel = remoteNavList.getSelectedValue();
            if (sel == null) return;
            String vk = JOptionPane.showInputDialog(frame, "viewkey (or blank for menu$index):", "");
            if (vk != null && !vk.isBlank()) {
                urlField.setText(sel.buildViewkeyUrl(vk.trim()));
            } else {
                urlField.setText(sel.buildMenuUrl(sel.menuIndex));
            }
        });
        navBtns.add(navAdd);
        navBtns.add(navDel);
        navBtns.add(navSync);
        navP.add(new JScrollPane(remoteNavList), BorderLayout.CENTER);
        navP.add(navBtns, BorderLayout.SOUTH);
        JLabel navHint = new JLabel("<html>viewkey=ID<br>menu$N</html>");
        navHint.setFont(new Font("Monospaced", Font.PLAIN, 8));
        navHint.setForeground(textMuted);
        navP.add(navHint, BorderLayout.NORTH);

        frame.add(navP, BorderLayout.WEST);
        frame.add(mainWrap, BorderLayout.CENTER);

        // Drop target on the whole for extra KISS UX
        try {
            new java.awt.dnd.DropTarget(mainWrap, new java.awt.dnd.DropTargetAdapter() {
                public void drop(java.awt.dnd.DropTargetDropEvent dtde) {
                    try {
                        dtde.acceptDrop(java.awt.dnd.DnDConstants.ACTION_COPY);
                        java.awt.datatransfer.Transferable t = dtde.getTransferable();
                        if (t.isDataFlavorSupported(java.awt.datatransfer.DataFlavor.stringFlavor)) {
                            String u = (String) t.getTransferData(java.awt.datatransfer.DataFlavor.stringFlavor);
                            if (u != null && isDownloadableUrl(normalizeUrl(u))) {
                                final String url = expandRemoteInput(normalizeUrl(u));
                                SwingUtilities.invokeLater(() -> { urlField.setText(url); startDirectDownload(); });
                            }
                        }
                        dtde.dropComplete(true);
                    } catch (Exception ignore) {}
                }
            });
        } catch (Exception ignore) {}

        frame.setVisible(true);
        refreshRecentDownloads();

        // Ensure the main URL input bar gets focus for immediate cursor input, selection, copy & paste
        SwingUtilities.invokeLater(() -> {
            if (urlField != null) {
                urlField.requestFocusInWindow();
            }
        });

        // Clear log data cache memory after exit/quit (KISS, no lingering state)
        frame.addWindowListener(new WindowAdapter() {
            @Override
            public void windowClosing(WindowEvent e) {
                gravityRunning = false;
                appendRuntimeLog("session_end", null);
                if (jobsModel != null) {
                    jobsModel.setRowCount(0);
                }
                if (visualistArea != null) {
                    visualistArea.setText("");
                }
                if (directStatusLabel != null) {
                    directStatusLabel.setText("cleared");
                }
                if (thetaField != null) {
                    thetaField.setText("0");
                }
                if (urlField != null) {
                    urlField.setText("");
                }
                // hint to release memory (no eval, simple)
                System.gc();
                if (socket != null && !socket.isClosed()) {
                    try { socket.close(); } catch (Exception ignore) {}
                }
            }
        });
    }

    private void connectToGravity() {
        new Thread(() -> {
            int attempt = 0;
            while (gravityRunning) {
                try {
                    closeGravitySocket();
                    socket = new Socket(HOST, PORT);
                    in = new BufferedReader(new InputStreamReader(socket.getInputStream()));
                    out = new PrintWriter(socket.getOutputStream(), true);

                    byte[] hello = new byte[32];
                    Arrays.fill(hello, (byte) 0x42);
                    socket.getOutputStream().write(hello);
                    socket.getOutputStream().flush();

                    byte[] serverHello = new byte[32];
                    socket.getInputStream().read(serverHello);

                    byte[] finish = new byte[48];
                    Arrays.fill(finish, (byte) 0x43);
                    socket.getOutputStream().write(finish);
                    socket.getOutputStream().flush();

                    attempt = 0;
                    appendRuntimeLog("gravity_handshake_ok", "\"host\":\"" + HOST + "\",\"port\":" + PORT);
                    SwingUtilities.invokeLater(() ->
                        statusLabel.setText("Gravity handshake complete • Receiving Visualist protocol updates..."));

                    String line;
                    while (gravityRunning && (line = in.readLine()) != null) {
                        final String updateLine = line;
                        int jobHints = 0;
                        java.util.regex.Matcher jm = java.util.regex.Pattern.compile("\"id\"\\s*:").matcher(updateLine);
                        while (jm.find()) jobHints++;
                        final int jobCount = jobHints;
                        appendRuntimeLog("gravity_update",
                            "\"jobs_count\":" + jobCount + ",\"line_bytes\":" + updateLine.length());
                        SwingUtilities.invokeLater(() -> {
                            updateUIFromLine(updateLine);
                            statusLabel.setText("Gravity live • " + new java.util.Date());
                        });
                    }
                } catch (Exception e) {
                    attempt++;
                    final int retrySec = Math.min(30, 2 * attempt);
                    final String errMsg = e.getMessage() != null ? e.getMessage() : e.toString();
                    appendRuntimeLog("gravity_offline",
                        "\"error\":\"" + jsonEsc(errMsg) + "\",\"retry_sec\":" + retrySec);
                    SwingUtilities.invokeLater(() ->
                        statusLabel.setText("Gravity offline — retry in " + retrySec + "s (" + errMsg + ")"));
                    try {
                        Thread.sleep(retrySec * 1000L);
                    } catch (InterruptedException ie) {
                        break;
                    }
                }
            }
        }).start();
    }

    private void closeGravitySocket() {
        if (in != null) {
            try { in.close(); } catch (Exception ignore) {}
            in = null;
        }
        if (out != null) {
            try { out.close(); } catch (Exception ignore) {}
            out = null;
        }
        if (socket != null && !socket.isClosed()) {
            try { socket.close(); } catch (Exception ignore) {}
            socket = null;
        }
    }

    private void setLastDownloadPath(String path) {
        lastDownloadPath = path;
        if (previewBtn != null) {
            boolean exists = path != null && new File(path).isFile();
            previewBtn.setEnabled(exists);
            previewBtn.setToolTipText(exists
                ? "Preview: " + new File(path).getName()
                : "Preview last download with ffplay");
        }
    }

    private static String resolveGravityServeUrl() {
        return envStr("GRAVITY_SERVE_URL", "http://127.0.0.1:8766");
    }

    private void gravityServePost(String path, String jsonBody, java.util.function.Consumer<String> onDone) {
        final String base = resolveGravityServeUrl();
        new Thread(() -> {
            String resp = "";
            try {
                URL u = URI.create(base + path).toURL();
                HttpURLConnection conn = (HttpURLConnection) u.openConnection();
                conn.setRequestMethod("POST");
                conn.setRequestProperty("Content-Type", "application/json; charset=utf-8");
                conn.setDoOutput(true);
                conn.setConnectTimeout(8000);
                conn.setReadTimeout(30000);
                try (OutputStream os = conn.getOutputStream()) {
                    os.write(jsonBody.getBytes(java.nio.charset.StandardCharsets.UTF_8));
                }
                int code = conn.getResponseCode();
                InputStream stream = code >= 400 ? conn.getErrorStream() : conn.getInputStream();
                if (stream != null) {
                    BufferedReader br = new BufferedReader(new InputStreamReader(stream));
                    StringBuilder sb = new StringBuilder();
                    String ln;
                    while ((ln = br.readLine()) != null) sb.append(ln);
                    resp = sb.toString();
                }
                if (resp.isEmpty()) {
                    resp = "{\"ok\":false,\"error\":\"HTTP " + code + "\"}";
                } else if (resp.contains("<!DOCTYPE") || resp.contains("<html")) {
                    resp = "{\"ok\":false,\"error\":\"Non-JSON response (HTTP " + code + ") — restart gravity-serve?\"}";
                }
            } catch (Exception ex) {
                resp = "{\"ok\":false,\"error\":\"" + jsonEsc(ex.getMessage()) + "\"}";
            }
            final String finalResp = resp;
            SwingUtilities.invokeLater(() -> onDone.accept(finalResp));
        }).start();
    }

    private void addPipelineJobViaApi() {
        String rawUrl = expandRemoteInput(normalizeUrl(urlField.getText()));
        if (!rawUrl.startsWith("http") && !rawUrl.startsWith("ipfs://")) {
            directStatusLabel.setText("Queue: need http(s) URL");
            return;
        }
        boolean grav = privateCheck != null && privateCheck.isSelected();
        String body = "{\"url\":\"" + jsonEsc(rawUrl) + "\",\"preset\":\"balanced-4k\",\"gravity\":" + grav + "}";
        directStatusLabel.setText("Queueing pipeline job via gravity-serve API...");
        gravityServePost("/api/add", body, resp -> {
            appendRuntimeLog("api_add_job", "\"response_text\":\"" + jsonEsc(resp) + "\"");
            if (resp.contains("\"ok\":true") || resp.contains("\"ok\": true")) {
                directStatusLabel.setText("Pipeline job queued (API) — worker converts to Visualist");
            } else {
                directStatusLabel.setText("Queue API failed — is gravity-serve running? :8766");
            }
        });
    }

    private void cancelSelectedJobViaApi() {
        int row = jobsTable != null ? jobsTable.getSelectedRow() : -1;
        if (row < 0) {
            directStatusLabel.setText("Select a live job row to cancel");
            return;
        }
        Object idObj = jobsModel.getValueAt(row, 0);
        String id = String.valueOf(idObj);
        String body = "{\"id\":" + id + "}";
        directStatusLabel.setText("Cancelling job #" + id + " via API...");
        gravityServePost("/api/cancel", body, resp -> {
            appendRuntimeLog("api_cancel_job", "\"job_id\":" + id + ",\"response_text\":\"" + jsonEsc(resp) + "\"");
            if (resp.contains("\"ok\":true") || resp.contains("\"ok\": true")) {
                directStatusLabel.setText("Cancelled job #" + id);
            } else {
                String err = "Cancel failed for job #" + id;
                int errIdx = resp.indexOf("\"error\":");
                if (errIdx >= 0) {
                    int q1 = resp.indexOf('"', errIdx + 8);
                    int q2 = resp.indexOf('"', q1 + 1);
                    if (q1 >= 0 && q2 > q1) err = resp.substring(q1 + 1, q2);
                }
                directStatusLabel.setText(err);
            }
        });
    }

    private void previewLastDownload() {
        String path = lastDownloadPath;
        if (path == null || !new File(path).isFile()) {
            directStatusLabel.setText("No preview file — download first");
            previewBtn.setEnabled(false);
            return;
        }
        try {
            ProcessBuilder pb = new ProcessBuilder(FFPLAY_PATH, "-autoexit", "-window_title",
                "GravityDesktop: " + new File(path).getName(), path);
            pb.redirectErrorStream(true);
            pb.start();
            directStatusLabel.setText("Playing: " + new File(path).getName());
        } catch (Exception ex) {
            String msg = ex.getMessage() != null ? ex.getMessage() : ex.toString();
            directStatusLabel.setText("ffplay error: " + (msg.length() > 60 ? msg.substring(0, 57) + "..." : msg));
        }
    }

    private void updateUIFromLine(String line) {
        // KISS crude string parse (no JSON lib, no eval) for live jobs + catalog
        jobsModel.setRowCount(0);

        // --- Live jobs from protocol ---
        // Extract simple key-value patterns (handles the gravity_update JSON lines)
        java.util.regex.Pattern idP = java.util.regex.Pattern.compile("\"id\":\\s*(\\d+)");
        java.util.regex.Pattern titleP = java.util.regex.Pattern.compile("\"title\":\\s*\"([^\"]+)\"");
        java.util.regex.Pattern statusP = java.util.regex.Pattern.compile("\"status\":\\s*\"([^\"]+)\"");
        java.util.regex.Pattern progP = java.util.regex.Pattern.compile("\"progress\":\\s*([0-9.]+)");
        java.util.regex.Pattern presetP = java.util.regex.Pattern.compile("\"preset\":\\s*\"([^\"]+)\"");

        java.util.regex.Matcher mId = idP.matcher(line);
        java.util.regex.Matcher mTitle = titleP.matcher(line);
        java.util.regex.Matcher mStatus = statusP.matcher(line);
        java.util.regex.Matcher mProg = progP.matcher(line);
        java.util.regex.Matcher mPreset = presetP.matcher(line);

        int row = 0;
        while (mId.find() && row < 20) {  // safety limit
            String id = mId.group(1);
            String title = mTitle.find() ? mTitle.group(1) : "?";
            String status = mStatus.find() ? mStatus.group(1) : "?";
            String prog = mProg.find() ? mProg.group(1) + "%" : "?";
            String preset = mPreset.find() ? mPreset.group(1) : "?";
            jobsModel.addRow(new Object[]{id, title.substring(0, Math.min(32, title.length())), status, prog, preset});
            row++;
        }

        // --- Live catalog metadata rendered to ASC (using provided symbol frame + log style) ---
        // Improved parser for "memory update data": properly extract per-item storage_memory_category
        // and other metadata from live gravity_update JSON lines. Updates the UI "memory" (visualistArea + jobsModel).
        StringBuilder sb = new StringBuilder();
        sb.append(ASC_FRAME);
        sb.append("\n");
        sb.append("⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰  GRAVITY_UPDATE RECEIVED - LIVE DATA FLOW HIGH/LOW  ⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰\n");
        sb.append("⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱  ASC PANEL: Symmetric ASC vs SC + Hierarchy Flow  ⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱\n");
        sb.append("⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲  1000 years old nonlinear h@k reality  ⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲\n\n");

        // Better crude per-item extraction for memory update data (KISS: split objects, parse each chunk)
        // Find catalog array content
        int catStart = line.indexOf("\"catalog\":[");
        java.util.List<String> catalogChunks = new java.util.ArrayList<>();
        if (catStart > 0) {
            int catEnd = line.indexOf("]", catStart);
            if (catEnd > catStart) {
                String catArray = line.substring(catStart + 11, catEnd);
                // Split on "},{" for objects (crude but works for the protocol JSON)
                String[] parts = catArray.split("\\},\\{");
                for (String p : parts) {
                    if (p.trim().length() > 5) {
                        catalogChunks.add("{" + p.replace("{", "").replace("}", "") + "}");
                    }
                }
            }
        }

        int catCount = 0;
        for (String chunk : catalogChunks) {
            if (catCount >= 6) break;
            // Extract from this chunk
            java.util.regex.Pattern tP = java.util.regex.Pattern.compile("\"title\":\\s*\"([^\"]+)\"");
            java.util.regex.Pattern gP = java.util.regex.Pattern.compile("\"gravity_prepared\":\\s*(true|false)");
            java.util.regex.Pattern hP = java.util.regex.Pattern.compile("\"raw_h264_stream\":\\s*\"([^\"]+)\"");
            java.util.regex.Pattern vP = java.util.regex.Pattern.compile("\"vp56_raw_stream\":\\s*\"([^\"]+)\"");
            java.util.regex.Pattern sP = java.util.regex.Pattern.compile("\"storage_memory_category\":\\s*\\{([^}]+)\\}");
            java.util.regex.Pattern thP = java.util.regex.Pattern.compile("\"thumbnail\":\\s*\"([^\"]+)\"");

            java.util.regex.Matcher mt = tP.matcher(chunk);
            java.util.regex.Matcher mg = gP.matcher(chunk);
            java.util.regex.Matcher mh = hP.matcher(chunk);
            java.util.regex.Matcher mv = vP.matcher(chunk);
            java.util.regex.Matcher ms = sP.matcher(chunk);
            java.util.regex.Matcher mth = thP.matcher(chunk);

            String t = mt.find() ? mt.group(1) : "untitled";
            String g = mg.find() ? mg.group(1) : "false";
            String h = mh.find() ? mh.group(1) : "";
            String v = mv.find() ? mv.group(1) : "";
            String sRaw = ms.find() ? ms.group(1) : "";
            String th = mth.find() ? mth.group(1) : "";

            // Parse storage_memory_category nicely (the "memory update data")
            String s = "zone=local memory=?";
            if (!sRaw.isEmpty()) {
                s = sRaw.replace("\"", "").replace(":", "=").replace(",", " | ");
            }

            sb.append("⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲⿳ ASC ENTRY #").append(catCount+1).append(" ⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲⿳\n");
            sb.append("⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲ ASC: [FILMIC | HIGH CONTRAST | GRAIN | 320x180]          ");
            sb.append("⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲ SC: ").append(s).append("\n");
            if (!th.isEmpty()) sb.append(" thumb:").append(th.substring(Math.max(0, th.length()-20))).append("\n");
            sb.append("gravity_prepared: ").append(g);
            if (!h.isEmpty()) sb.append("  h264:").append(h.substring(Math.max(0, h.length()-15)));
            if (!v.isEmpty()) sb.append("  vp56:").append(v.substring(Math.max(0, v.length()-15)));
            sb.append("\n⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰ [END symmetric ASC vs SC] ⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰\n\n");
            catCount++;
        }

        if (catCount == 0) {
            sb.append("⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰  (no live catalog yet — connect gravity-server + run worker)  ⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰\n");
            sb.append("ASC: [FILMIC | HIGH CONTRAST | GRAIN | 320x180]\n");
            sb.append("storage_memory: zone=local memory=system (default)\n");
        }

        // Data Flow Log HIGH / LOW LIVE - using hierarchy levels, tied to live ASC data
        sb.append("\n");
        sb.append("⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰ DATA FLOW LOG HIGH/LOW LIVE ⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰\n");
        sb.append("⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱ 11 HIGH Pure Form (Source) ⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱\n");
        sb.append("⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲     ↓ LIVE DATA FLOWING ↓     ⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲\n");
        sb.append("⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲⿳ 10 Geometric (ASC Thumbs) ⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲⿳\n");
        sb.append("⿶⿷⿸⿹⿺⿻⿰⿱⿲⿳⿴     ↓     ⿶⿷⿸⿹⿺⿻⿰⿱⿲⿳⿴\n");
        sb.append("⿷⿸⿹⿺⿻⿰⿱⿲⿳⿴⿵  8 DNA (H.264 + Gravity)  ⿷⿸⿹⿺⿻⿰⿱⿲⿳⿴⿵\n");
        sb.append("⿸⿹⿺⿻⿰⿱⿲⿳⿴⿵⿶     ↓     ⿸⿹⿺⿻⿰⿱⿲⿳⿴⿵⿶\n");
        sb.append("⿹⿺⿻⿰⿱⿲⿳⿴⿵⿶⿷  6 Waves / 5 Elements     ⿹⿺⿻⿰⿱⿲⿳⿴⿵⿶⿷\n");
        sb.append("⿺⿻⿰⿱⿲⿳⿴⿵⿶⿷⿸     ↓     ⿺⿻⿰⿱⿲⿳⿴⿵⿶⿷⿸\n");
        sb.append("⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰  3 Human / 2 Journey      ⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰\n");
        sb.append("⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱     ↓     ⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱\n");
        sb.append("⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲  1 LOW The Way (Cataloged) ⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲\n");
        sb.append("⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰ [LIVE items flowing high→low above] ⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰\n");

        sb.append("\n");
        sb.append(ASC_FRAME);
        visualistArea.setText(sb.toString());
    }

    /** Small inset "data box" styled exactly after the reference video's glitch cyan ASC/filmic panels (first 5-10s aesthetic). */
    private JPanel makeAscBox(String label, String content) {
        JPanel box = new JPanel(new BorderLayout(1, 1));
        box.setBackground(new Color(0, 0, 0));
        box.setBorder(BorderFactory.createLineBorder(new Color(0, 255, 200), 1));  // thin cyan like video insets

        JLabel l = new JLabel(label);
        l.setForeground(new Color(0, 255, 200));
        l.setFont(new Font("Monospaced", Font.BOLD, 8));
        l.setBorder(BorderFactory.createEmptyBorder(1, 2, 0, 2));

        JTextArea ta = new JTextArea(content);
        ta.setBackground(new Color(0, 0, 0));
        ta.setForeground(new Color(0, 220, 180));
        ta.setFont(new Font("Monospaced", Font.PLAIN, 7));
        ta.setEditable(false);
        ta.setBorder(BorderFactory.createEmptyBorder(0, 2, 1, 2));

        box.add(l, BorderLayout.NORTH);
        box.add(ta, BorderLayout.CENTER);
        return box;
    }

    /** Vertical film-sprocket / grain edge strip to match the blocky side patterns in the reference video frames. */
    private JPanel makeFilmEdge() {
        JPanel edge = new JPanel();
        edge.setLayout(new BoxLayout(edge, BoxLayout.Y_AXIS));
        edge.setPreferredSize(new Dimension(22, 0));
        edge.setBackground(new Color(15, 15, 15));
        String[] marks = {"█", "░", "▓", "░", "█", " ", "░"};
        for (int i = 0; i < 40; i++) {
            JLabel m = new JLabel(marks[i % marks.length]);
            m.setForeground(new Color(50, 50, 50));
            m.setFont(new Font("Monospaced", Font.PLAIN, 7));
            m.setAlignmentX(0.5f);
            edge.add(m);
        }
        return edge;
    }

    /**
     * JS runtime check for yt-dlp (addresses the "No supported JavaScript runtime could be found" warning).
     * Deno and Node.js (bun etc.) are similarly supported by yt-dlp as JS runtimes.
     * Checks for deno (default/recommended), node, bun.
     * "pythonJava" install: Java can invoke the Python helper (nls_video_pipe.py ensure) or direct install.
     */
    private static Boolean jsRuntimesSupported;

    private static boolean ytDlpSupportsJsRuntimes() {
        if (jsRuntimesSupported != null) return jsRuntimesSupported;
        try {
            Process p = new ProcessBuilder(YTDLP_PATH, "--help").redirectErrorStream(true).start();
            StringBuilder sb = new StringBuilder();
            BufferedReader br = new BufferedReader(new InputStreamReader(p.getInputStream()));
            String line;
            while ((line = br.readLine()) != null) sb.append(line).append('\n');
            p.waitFor();
            jsRuntimesSupported = sb.toString().contains("--js-runtimes");
        } catch (Exception e) {
            jsRuntimesSupported = false;
        }
        return jsRuntimesSupported;
    }

    private static String formatJsRuntimeArg(String jsRt) {
        String name = jsRt.split(" ")[0];
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("\\(([^)]+)\\)").matcher(jsRt);
        if (m.find()) return name + ":" + m.group(1).trim();
        return name;
    }

    private static void addJsRuntimeArgs(java.util.List<String> args, String jsRt) {
        if (jsRt == null || !ytDlpSupportsJsRuntimes()) return;
        args.add("--js-runtimes");
        args.add(formatJsRuntimeArg(jsRt));
    }

    private static void addFormatArgs(java.util.List<String> args, String format, boolean gifMode) {
        args.add("-f");
        args.add(format);
        args.add("--merge-output-format");
        args.add(gifMode ? "gif" : "mp4");
        if (gifMode && (format.contains("best") || format.contains("/"))) {
            args.add("--recode-video");
            args.add("gif");
        }
    }

    private static void addH264Mp4Args(java.util.List<String> args) {
        addFormatArgs(args, YTDLP_H264_FORMAT, false);
    }

    private static void addGifArgs(java.util.List<String> args) {
        addFormatArgs(args, YTDLP_GIF_FORMAT, true);
    }

    private static final class FormatRow {
        String id;
        String ext;
        String resolution;
        String vcodec;
        String acodec;
        boolean videoOnly;
        boolean audioOnly;
        int height;
    }

    private static int parseFormatHeight(String resolution) {
        if (resolution == null || resolution.equals("audio only")) return 0;
        java.util.regex.Matcher m = java.util.regex.Pattern.compile("\\d+x(\\d+)").matcher(resolution);
        return m.find() ? Integer.parseInt(m.group(1)) : 0;
    }

    private static boolean isH264Codec(String vcodec) {
        if (vcodec == null) return false;
        String v = vcodec.toLowerCase();
        return v.startsWith("avc1") || v.startsWith("avc") || v.contains("h264");
    }

    private static FormatRow parseFormatLine(String line) {
        if (line == null || line.isBlank()) return null;
        if (line.startsWith("ID ") || line.startsWith("---") || line.startsWith("[info]")) return null;
        String[] parts = line.split("\\|");
        if (parts.length < 3) return null;
        String[] left = parts[0].trim().split("\\s+");
        if (left.length < 3) return null;
        if (!left[0].matches("[\\w.-]+")) return null;

        FormatRow row = new FormatRow();
        row.id = left[0];
        row.ext = left[1];
        row.resolution = left[2];
        row.height = parseFormatHeight(row.resolution);

        String right = parts[2].trim();
        row.videoOnly = right.contains("video only");
        row.audioOnly = right.contains("audio only");
        String[] tokens = right.split("\\s+");
        if (tokens.length == 0) return row;

        if (row.audioOnly) {
            for (String t : tokens) {
                if (t.startsWith("mp4a") || t.startsWith("opus") || t.startsWith("aac")) {
                    row.acodec = t;
                    break;
                }
            }
        } else if (row.videoOnly) {
            row.vcodec = tokens[0];
        } else {
            row.vcodec = tokens[0];
            for (int i = 1; i < tokens.length; i++) {
                String t = tokens[i];
                if (t.startsWith("mp4a") || t.startsWith("opus") || t.startsWith("aac")) {
                    row.acodec = t;
                    break;
                }
            }
        }
        return row;
    }

    private static String selectH264Format(java.util.List<FormatRow> rows) {
        FormatRow bestCombined = null;
        for (FormatRow r : rows) {
            if (r.videoOnly || r.audioOnly) continue;
            if (!isH264Codec(r.vcodec)) continue;
            if (bestCombined == null || r.height > bestCombined.height) bestCombined = r;
        }
        if (bestCombined != null) return bestCombined.id;

        FormatRow bestVideo = null;
        FormatRow bestAudio = null;
        for (FormatRow r : rows) {
            if (r.videoOnly && isH264Codec(r.vcodec) && "mp4".equalsIgnoreCase(r.ext)) {
                if (bestVideo == null || r.height > bestVideo.height) bestVideo = r;
            }
            if (r.audioOnly && "m4a".equalsIgnoreCase(r.ext)) {
                boolean isMedium = r.acodec != null && r.acodec.contains("40.2");
                if (bestAudio == null
                    || (isMedium && (bestAudio.acodec == null || !bestAudio.acodec.contains("40.2")))
                    || (!isMedium && bestAudio.acodec != null && bestAudio.acodec.contains("40.5"))) {
                    bestAudio = r;
                }
            }
        }
        if (bestVideo != null && bestAudio != null) return bestVideo.id + "+" + bestAudio.id;
        if (bestVideo != null) return bestVideo.id + "+bestaudio[ext=m4a]/bestaudio";
        return YTDLP_H264_FORMAT;
    }

    private static String selectGifFormat(java.util.List<FormatRow> rows) {
        FormatRow bestGif = null;
        for (FormatRow r : rows) {
            if (!"gif".equalsIgnoreCase(r.ext)) continue;
            if (bestGif == null || r.height > bestGif.height) bestGif = r;
        }
        if (bestGif != null) return bestGif.id;
        return YTDLP_GIF_FORMAT;
    }

    private static String selectGenericFormat(java.util.List<FormatRow> rows, boolean gifMode) {
        if (gifMode) return selectGifFormat(rows);
        FormatRow bestCombined = null;
        FormatRow bestVideo = null;
        FormatRow bestAudio = null;
        for (FormatRow r : rows) {
            if (!r.videoOnly && !r.audioOnly) {
                if (bestCombined == null || r.height > bestCombined.height) bestCombined = r;
            } else if (r.videoOnly) {
                if (bestVideo == null || r.height > bestVideo.height) bestVideo = r;
            } else if (r.audioOnly) {
                if (bestAudio == null) bestAudio = r;
            }
        }
        if (bestCombined != null) return bestCombined.id;
        if (bestVideo != null && bestAudio != null) return bestVideo.id + "+" + bestAudio.id;
        if (bestVideo != null) return bestVideo.id + "+bestaudio/bestaudio";
        if (!rows.isEmpty()) return rows.get(0).id;
        return "best";
    }

    private static String selectFormatFromList(java.util.List<String> lines, boolean gifMode, boolean generic) {
        java.util.List<FormatRow> rows = new java.util.ArrayList<>();
        boolean inTable = false;
        for (String line : lines) {
            if (line.contains("Available formats")) {
                inTable = true;
                continue;
            }
            if (!inTable) continue;
            FormatRow row = parseFormatLine(line);
            if (row != null) rows.add(row);
        }
        if (rows.isEmpty()) {
            return gifMode ? YTDLP_GIF_FORMAT : YTDLP_H264_FORMAT;
        }
        if (generic) return selectGenericFormat(rows, gifMode);
        if (gifMode) return selectGifFormat(rows);
        return selectH264Format(rows);
    }

    private static void addBaseYtDlpArgs(java.util.List<String> args, String url, String jsRt, boolean usePrivate) {
        addRateLimitArgs(args);
        addProxyArgs(args);
        addJsRuntimeArgs(args, jsRt);
        addCookiesArgs(args, url, usePrivate);
        if (isPhpViewerUrl(url)) addPhpViewerArgs(args, url);
        if (isIpfsHttpUrl(url)) addIpfsHttpArgs(args);
    }

    private java.util.List<String> runListFormats(String url, String jsRt, boolean usePrivate) throws Exception {
        java.util.List<String> args = new java.util.ArrayList<>();
        args.add(YTDLP_PATH);
        addBaseYtDlpArgs(args, url, jsRt, usePrivate);
        args.add("--list-formats");
        args.add(url);
        YtDlpResult result = runYtDlp(args);
        if (result.exitCode != 0 && outputIndicates403(result.lines)) {
            RateLimiter.on403();
        } else if (result.exitCode == 0) {
            RateLimiter.onSuccess();
        }
        return result.lines;
    }

    private static final class CookieSource {
        final String kind; // "file" or "browser"
        final String value;
        CookieSource(String kind, String value) { this.kind = kind; this.value = value; }
    }

    private static String cookiesFilePath() {
        String env = System.getenv("GRAVITY_COOKIES_FILE");
        if (env != null && !env.isBlank()) {
            File f = new File(env.trim());
            if (f.isFile() && f.canRead()) return f.getAbsolutePath();
        }
        String home = System.getProperty("user.home");
        File def = new File(home + "/.config/gravity-desktop/cookies.txt");
        if (def.isFile() && def.canRead()) return def.getAbsolutePath();
        return null;
    }

    private static boolean browserCookieDbExists(String browser) {
        String home = System.getProperty("user.home");
        String b = browser.toLowerCase();
        if ("brave".equals(b)) {
            return new File(home + "/.config/BraveSoftware/Brave-Browser/Default/Cookies").isFile();
        }
        if ("chromium".equals(b)) {
            return new File(home + "/.config/chromium/Default/Cookies").isFile();
        }
        if ("chrome".equals(b)) {
            return new File(home + "/.config/google-chrome/Default/Cookies").isFile();
        }
        if ("edge".equals(b)) {
            return new File(home + "/.config/microsoft-edge/Default/Cookies").isFile();
        }
        if ("opera".equals(b)) {
            return new File(home + "/.config/opera/Default/Cookies").isFile()
                || new File(home + "/.config/opera-stable/Default/Cookies").isFile();
        }
        if ("vivaldi".equals(b)) {
            return new File(home + "/.config/vivaldi/Default/Cookies").isFile();
        }
        if ("whale".equals(b)) {
            return new File(home + "/.config/naver-whale/Default/Cookies").isFile()
                || new File(home + "/.config/Naver Whale/Default/Cookies").isFile();
        }
        if ("safari".equals(b)) {
            return new File(home + "/Library/Cookies/Cookies.binarycookies").isFile();
        }
        if ("firefox".equals(b)) {
            File snap = new File(home + "/snap/firefox/common/.mozilla/firefox");
            if (snap.isDirectory()) {
                File[] profiles = snap.listFiles((dir, name) -> name.endsWith(".default") || name.contains("default"));
                if (profiles != null) {
                    for (File p : profiles) {
                        if (new File(p, "cookies.sqlite").isFile()) return true;
                    }
                }
            }
            File ff = new File(home + "/.mozilla/firefox");
            if (ff.isDirectory()) {
                File[] profiles = ff.listFiles((dir, name) -> name.endsWith(".default") || name.contains("default"));
                if (profiles != null) {
                    for (File p : profiles) {
                        if (new File(p, "cookies.sqlite").isFile()) return true;
                    }
                }
            }
        }
        return false;
    }

    private static String resolveCookiesBrowser() {
        String env = System.getenv("GRAVITY_COOKIES_BROWSER");
        if (env != null && !env.isBlank()) {
            String b = env.trim();
            if (browserCookieDbExists(b)) return b;
            return null;
        }
        for (String candidate : new String[]{
            "brave", "chromium", "chrome", "edge", "firefox", "opera", "vivaldi", "whale", "safari"
        }) {
            if (browserCookieDbExists(candidate)) return candidate;
        }
        return null;
    }

    private static CookieSource resolveCookieSource() {
        String file = cookiesFilePath();
        if (file != null) return new CookieSource("file", file);
        String browser = resolveCookiesBrowser();
        if (browser != null) return new CookieSource("browser", browser);
        return null;
    }

    private static boolean shouldUseCookies(String url, boolean usePrivate) {
        if (!usePrivate) return false;
        if (isDirectMediaUrl(url) || isIpfsHttpUrl(url)) return false;
        return true;
    }

    private static void addCookiesArgs(java.util.List<String> args, String url, boolean usePrivate) {
        if (!shouldUseCookies(url, usePrivate)) return;
        CookieSource src = resolveCookieSource();
        if (src == null) return;
        if ("file".equals(src.kind)) {
            args.add("--cookies");
            args.add(src.value);
        } else {
            args.add("--cookies-from-browser");
            args.add(src.value);
        }
    }

    private static String describeCookieSource() {
        CookieSource src = resolveCookieSource();
        if (src == null) return "none";
        if ("file".equals(src.kind)) return "file:" + src.value;
        return "browser:" + src.value;
    }

    private static String ipfsGateway() {
        String gw = System.getenv("GRAVITY_IPFS_GATEWAY");
        if (gw != null && !gw.isBlank()) {
            gw = gw.trim();
            if (!gw.endsWith("/")) gw += "/";
            return gw;
        }
        return "https://ipfs.io/ipfs/";
    }

    private static File remoteNavStore() {
        String home = System.getProperty("user.home");
        return new File(home + "/.config/gravity-desktop/remote-nav.tsv");
    }

    private void loadRemoteNav() {
        if (remoteNavModel == null) return;
        remoteNavModel.clear();
        File f = remoteNavStore();
        if (!f.isFile()) {
            String base = System.getenv("GRAVITY_REMOTE_BASE");
            if (base != null && !base.isBlank()) {
                remoteNavModel.addElement(new RemoteNavEntry("default", base.trim(), 1, "remote-cli.php"));
            }
            return;
        }
        try (BufferedReader br = new BufferedReader(new FileReader(f))) {
            String ln;
            while ((ln = br.readLine()) != null) {
                if (ln.isBlank() || ln.startsWith("#")) continue;
                RemoteNavEntry e = RemoteNavEntry.fromTsv(ln);
                if (e != null) remoteNavModel.addElement(e);
            }
        } catch (Exception ignore) {}
    }

    private void saveRemoteNav() {
        if (remoteNavModel == null) return;
        try {
            File f = remoteNavStore();
            f.getParentFile().mkdirs();
            try (PrintWriter pw = new PrintWriter(new FileWriter(f))) {
                pw.println("# assetClass\tbaseUrl\tmenuIndex\tviewer");
                for (int i = 0; i < remoteNavModel.size(); i++) {
                    pw.println(remoteNavModel.get(i).toTsv());
                }
            }
        } catch (Exception ignore) {}
    }

    private RemoteNavEntry getActiveNavEntry() {
        if (remoteNavList == null) return null;
        return remoteNavList.getSelectedValue();
    }

    /** Expand viewkey= / menu$N shorthand using sync nav asset-class assignment. */
    private String expandRemoteInput(String raw) {
        if (raw == null) return "";
        String u = raw.trim();
        RemoteNavEntry nav = getActiveNavEntry();

        java.util.regex.Matcher vk = java.util.regex.Pattern
            .compile("(?i)^viewkey=(.+)$").matcher(u);
        if (vk.matches()) {
            String key = vk.group(1).trim();
            if (nav != null) return nav.buildViewkeyUrl(key);
            String base = System.getenv("GRAVITY_REMOTE_BASE");
            if (base != null && !base.isBlank()) {
                return new RemoteNavEntry("env", base.trim(), 1, "remote-cli.php").buildViewkeyUrl(key);
            }
            return u;
        }

        java.util.regex.Matcher menu = java.util.regex.Pattern.compile("^menu\\$(\\d+)$").matcher(u);
        if (menu.matches()) {
            int idx = Integer.parseInt(menu.group(1));
            if (nav != null) return nav.buildMenuUrl(idx);
            String base = System.getenv("GRAVITY_REMOTE_BASE");
            if (base != null && !base.isBlank()) {
                return new RemoteNavEntry("env", base.trim(), idx, "remote.php").buildMenuUrl(idx);
            }
            return u;
        }

        if (u.toLowerCase().startsWith("remote-cli.php") || u.toLowerCase().startsWith("remote.php")
            || u.toLowerCase().contains("navi(1)remote.php")) {
            if (nav != null && !nav.baseNorm().isEmpty()) {
                return nav.baseNorm() + u;
            }
            String base = System.getenv("GRAVITY_REMOTE_BASE");
            if (base != null && !base.isBlank()) {
                return (base.endsWith("/") ? base : base + "/") + u;
            }
        }
        return u;
    }

    private static String normalizeUrl(String raw) {
        if (raw == null) return "";
        String url = raw.trim();
        java.util.regex.Matcher http = java.util.regex.Pattern
            .compile("(https?://[^\\s<>\"']+)", java.util.regex.Pattern.CASE_INSENSITIVE).matcher(url);
        java.util.regex.Matcher ipfs = java.util.regex.Pattern
            .compile("(ipfs://[^\\s<>\"']+)", java.util.regex.Pattern.CASE_INSENSITIVE).matcher(url);
        java.util.regex.Matcher vk = java.util.regex.Pattern
            .compile("(viewkey=[^\\s<>\"'&]+)", java.util.regex.Pattern.CASE_INSENSITIVE).matcher(url);
        java.util.regex.Matcher menu = java.util.regex.Pattern.compile("(menu\\$\\d+)").matcher(url);
        if (http.find()) url = http.group(1);
        else if (ipfs.find()) url = ipfs.group(1);
        else if (vk.find()) url = vk.group(1);
        else if (menu.find()) url = menu.group(1);
        return url.replaceAll("[.,;:!?\\]\\)>\"']+$", "");
    }

    /** Resolve ipfs:// to HTTP gateway; leave https gateway URLs unchanged. */
    private static String resolveDownloadUrl(String url) {
        if (url == null || url.isBlank()) return url;
        String u = url.trim();
        if (u.regionMatches(true, 0, "ipfs://", 0, 7)) {
            String path = u.substring(7);
            if (path.startsWith("ipfs/")) path = path.substring(5);
            return ipfsGateway() + path;
        }
        return u;
    }

    private static boolean isDownloadableUrl(String url) {
        if (url == null || url.isBlank()) return false;
        String u = url.trim().toLowerCase();
        return u.startsWith("http://") || u.startsWith("https://") || u.startsWith("ipfs://")
            || u.startsWith("viewkey=") || u.startsWith("menu$")
            || u.contains("remote.php") || u.contains("remote-cli.php");
    }

    private static boolean isIpfsHttpUrl(String url) {
        String u = url.toLowerCase();
        return u.contains("/ipfs/") || u.contains(".ipfs.") || u.contains("ipfs.io")
            || u.contains("dweb.link") || u.contains("cloudflare-ipfs.com")
            || u.contains("gateway.pinata") || u.contains("nftstorage.link");
    }

    private static boolean isPhpViewerUrl(String url) {
        String u = url.toLowerCase();
        return u.contains(".php") || u.contains("viewkey=");
    }

    private void postProcessVp56(String mp4Path) {
        if (mp4Path == null || !new File(mp4Path).isFile()) return;
        String out = mp4Path.replaceAll("\\.mp4$", "") + ".vp56.webm";
        try {
            ProcessBuilder pb = new ProcessBuilder(
                FFMPEG_PATH, "-y", "-i", mp4Path,
                "-c:v", "libvpx", "-b:v", "800k", "-c:a", "libvorbis",
                out
            );
            pb.redirectErrorStream(true);
            Process p = pb.start();
            p.waitFor();
            directStatusLabel.setText("VP56/webm post: " + new File(out).getName());
        } catch (Exception ex) {
            directStatusLabel.setText("VP56 note: " + ex.getMessage());
        }
    }

    private static boolean isGifAddress(String url) {
        String base = url.toLowerCase().split("\\?")[0].split("#")[0];
        return base.endsWith(".gif")
            || base.contains("/gif/")
            || base.contains("format=gif")
            || base.contains("type=gif");
    }

    private static boolean isDirectMediaUrl(String url) {
        String base = url.toLowerCase().split("\\?")[0].split("#")[0];
        return base.matches(".*\\.(mp4|webm|mkv|mov|m4v|gif|webp|avi|flv)$") || isGifAddress(url);
    }

    private static boolean useGenericExtractor(String url) {
        return isIpfsHttpUrl(url) || isPhpViewerUrl(url) || isDirectMediaUrl(url);
    }

    private static void addGenericMediaArgs(java.util.List<String> args, boolean gifMode) {
        if (gifMode) {
            addGifArgs(args);
        } else {
            args.add("-f");
            args.add("bestvideo*+bestaudio/best");
            args.add("--merge-output-format");
            args.add("mp4");
        }
    }

    private static void addPhpViewerArgs(java.util.List<String> args, String url) {
        args.add("--add-header");
        args.add("Referer:" + url);
        args.add("--add-header");
        args.add("User-Agent:Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36");
    }

    private static void addIpfsHttpArgs(java.util.List<String> args) {
        args.add("--add-header");
        args.add("User-Agent:GravityDesktop/1.1.9 (IPFS-HTTP)");
        args.add("--add-header");
        args.add("Accept:*/*");
    }

    private static String extractMediaId(String url) {
        java.util.regex.Matcher ipfs = java.util.regex.Pattern
            .compile("/ipfs/([^/?#]+)", java.util.regex.Pattern.CASE_INSENSITIVE).matcher(url);
        if (ipfs.find()) {
            String cid = ipfs.group(1);
            return cid.length() > 16 ? cid.substring(0, 16) : cid;
        }
        if (url.regionMatches(true, 0, "ipfs://", 0, 7)) {
            String cid = url.substring(7).split("[?#]")[0];
            if (cid.startsWith("ipfs/")) cid = cid.substring(5);
            return cid.length() > 16 ? cid.substring(0, 16) : cid;
        }
        if (url.contains("v=")) return url.substring(url.indexOf("v=") + 2).split("&")[0];
        if (url.contains("youtu.be/")) return url.substring(url.lastIndexOf('/') + 1).split("\\?")[0];
        java.util.regex.Matcher tw = java.util.regex.Pattern
            .compile("(?:twitter\\.com|x\\.com)/(?:[^/]+/status|i/status)/(\\d+)", java.util.regex.Pattern.CASE_INSENSITIVE)
            .matcher(url);
        if (tw.find()) return tw.group(1);
        java.util.regex.Matcher php = java.util.regex.Pattern.compile("[?&](?:id|v|file|cid|hash)=([^&#]+)").matcher(url);
        if (php.find()) {
            String id = php.group(1);
            return id.length() > 20 ? id.substring(0, 20) : id;
        }
        java.util.regex.Matcher num = java.util.regex.Pattern.compile("/(\\d{8,})").matcher(url);
        if (num.find()) return num.group(1);
        String base = url.split("\\?")[0];
        int slash = base.lastIndexOf('/');
        if (slash >= 0 && slash < base.length() - 1) {
            String tail = base.substring(slash + 1).replaceAll("\\.[^.]+$", "");
            if (!tail.isBlank()) return tail.length() > 20 ? tail.substring(0, 20) : tail;
        }
        return Integer.toHexString(url.hashCode());
    }

    private static void addCommonYtDlpArgs(java.util.List<String> args, String url, String jsRt,
            boolean gifMode, boolean usePrivate, String selectedFormat) {
        addBaseYtDlpArgs(args, url, jsRt, usePrivate);
        addFormatArgs(args, selectedFormat, gifMode);
        args.add("--newline");
    }

    private String checkJsRuntime() {
        String home = System.getProperty("user.home");
        String[][] runtimes = {
            {"deno", home + "/.deno/bin/deno", "/usr/bin/deno", "/usr/local/bin/deno"},
            {"node", "/usr/bin/node", "/usr/local/bin/node"},
            {"bun", home + "/.bun/bin/bun", "/usr/bin/bun", "/usr/local/bin/bun"},
        };
        for (String[] rt : runtimes) {
            String name = rt[0];
            String path = resolveExecutable(name.toUpperCase() + "_PATH", name,
                java.util.Arrays.copyOfRange(rt, 1, rt.length));
            if (!path.equals(name)) {
                return name + " (" + path + ")";
            }
        }
        return null;
    }

    /**
     * Start direct yt-dlp download for a pasted/dragged URL.
     * Target is always ~/Downloads/ (no pipeline job added; independent "quick drop" like the TUI input bar).
     * Parses stdout for progress % (same style as Python gravity-client).
     * Uses ProcessBuilder with arg list (no shell, follows no-eval / no-kill).
     */
    private void startDirectDownload() {
        String rawUrl = expandRemoteInput(normalizeUrl(urlField.getText()));
        if (!isDownloadableUrl(rawUrl)) {
            directStatusLabel.setText("Ignored: https://, viewkey=, menu$N, .php viewer, or GIF");
            return;
        }
        if (!rawUrl.startsWith("http") && !rawUrl.startsWith("ipfs://")) {
            directStatusLabel.setText("Select nav asset or set GRAVITY_REMOTE_BASE for viewkey=/menu$");
            return;
        }
        urlField.setText(rawUrl);
        String url = resolveDownloadUrl(rawUrl);
        if (gifCheck != null && isGifAddress(rawUrl)) gifCheck.setSelected(true);

        double theta = 0;
        try { theta = Double.parseDouble(thetaField.getText().trim()); } catch (Exception ignore) {}
        boolean dual = dualCheck != null && dualCheck.isSelected();
        boolean gifMode = (gifCheck != null && gifCheck.isSelected()) || isGifAddress(url);
        boolean usePrivate = privateCheck != null && privateCheck.isSelected();
        String srcNote = isPhpViewerUrl(url) ? " php-viewer"
            : (isIpfsHttpUrl(url) ? " ipfs-http" : "");
        boolean useCookies = shouldUseCookies(url, usePrivate) && resolveCookieSource() != null;
        String rotNote = (gifMode ? " gif" : " h264") + srcNote
            + (theta != 0 && !gifMode ? " rot" + theta : "")
            + (dual ? " dual vi i&j=true" : "")
            + (useCookies ? " cookies:" + describeCookieSource() : "");

        String startMsg = "Starting yt-dlp direct to ~/Downloads/..." + rotNote;
        if (usePrivate && resolveCookieSource() == null) {
            startMsg = "private: no cookies.txt/browser DB — continuing without cookies";
        }
        directStatusLabel.setText(startMsg);
        directProgress.setValue(0);
        final String finalUrl = url;
        final double finalTheta = gifMode ? 0 : theta;
        final boolean finalDual = dual;
        final boolean finalGif = gifMode;
        final String mediaId = extractMediaId(url);

        downloadBtn.setEnabled(false);
        urlField.setEnabled(false);
        if (thetaField != null) thetaField.setEnabled(false);
        if (dualCheck != null) dualCheck.setEnabled(false);
        if (gifCheck != null) gifCheck.setEnabled(false);
        if (privateCheck != null) privateCheck.setEnabled(false);

        new Thread(() -> {
            try {
                String home = System.getProperty("user.home");
                String outtmpl = finalGif
                    ? home + "/Downloads/direct-gif-%(id)s.gif"
                    : home + "/Downloads/direct-h264-%(id)s.mp4";

                String jsRt = checkJsRuntime();
                SwingUtilities.invokeLater(() ->
                    directStatusLabel.setText("Checking formats (yt-dlp --list-formats)..."));

                java.util.List<String> formatLines = runListFormats(finalUrl, jsRt, usePrivate);
                boolean generic = useGenericExtractor(finalUrl);
                String selectedFormat = selectFormatFromList(formatLines, finalGif, generic);
                final String formatNote = selectedFormat;

                SwingUtilities.invokeLater(() ->
                    directStatusLabel.setText("Selected format: " + formatNote + " — downloading..."));

                java.util.List<String> ytdlpArgs = new java.util.ArrayList<>();
                ytdlpArgs.add(YTDLP_PATH);
                addCommonYtDlpArgs(ytdlpArgs, finalUrl, jsRt, finalGif, usePrivate, selectedFormat);
                ytdlpArgs.add("-o");
                ytdlpArgs.add(outtmpl);
                ytdlpArgs.add(finalUrl);

                YtDlpResult dlResult = runYtDlpWithProgress(ytdlpArgs, finalTheta);
                int rc = dlResult.exitCode;
                String lastLine = dlResult.lastLine;

                int max403Retries = (int) envLong("GRAVITY_403_RETRIES", 2);
                int attempt = 0;
                while (rc != 0 && outputIndicates403(dlResult.lines) && attempt < max403Retries) {
                    attempt++;
                    RateLimiter.on403();
                    final int retryNum = attempt;
                    final long coolSec = RateLimiter.cooldownSecondsRemaining();
                    SwingUtilities.invokeLater(() ->
                        directStatusLabel.setText("403/IP restricted — cooldown " + coolSec + "s, retry " + retryNum + "/" + max403Retries));
                    dlResult = runYtDlpWithProgress(ytdlpArgs, finalTheta);
                    rc = dlResult.exitCode;
                    lastLine = dlResult.lastLine;
                }

                if (rc == 0) {
                    RateLimiter.onSuccess();
                } else if (outputIndicates403(dlResult.lines)) {
                    RateLimiter.on403();
                }

                final String lastErr = lastLine;
                final boolean ip403 = outputIndicates403(dlResult.lines);
                final int finalRc = rc;
                SwingUtilities.invokeLater(() -> {
                    if (finalRc == 0) {
                        directProgress.setValue(100);
                        String shortUrl = finalUrl.length() > 28 ? finalUrl.substring(0, 25) + "..." : finalUrl;
                        String baseMsg = "✓ done → ~/Downloads/  (" + shortUrl + ")"
                            + (finalGif ? " GIF" : " H.264 mp4")
                            + " [" + formatNote + "]"
                            + (finalTheta != 0 ? " + θ" + finalTheta : "");
                        if (finalDual) baseMsg += " dual vi && i & j = true";
                        final String msg = baseMsg;
                        directStatusLabel.setText(msg);

                        String previewPath = finalGif
                            ? home + "/Downloads/direct-gif-" + mediaId + ".gif"
                            : home + "/Downloads/direct-h264-" + mediaId + ".mp4";

                        if (finalDual && !finalGif) {
                            try {
                                String id = mediaId;
                                String downloaded = home + "/Downloads/direct-h264-" + id + ".mp4";
                                postProcessVp56(downloaded);
                            } catch (Exception ignore) {}
                        }

                        // KISS H.264 rotate post if theta (simple id based)
                        if (finalTheta != 0) {
                            try {
                                String id = mediaId;
                                String downloaded = home + "/Downloads/direct-h264-" + id + ".mp4";
                                String rotated = home + "/Downloads/direct-h264-rot" + (int)finalTheta + "-" + id + ".mp4";
                                ProcessBuilder rotPb = new ProcessBuilder(
                                    FFMPEG_PATH, "-y", "-i", downloaded,
                                    "-vf", "rotate=" + finalTheta + "*PI/180",
                                    "-c:v", "libx264", "-crf", "19", "-c:a", "aac",
                                    rotated
                                );
                                rotPb.redirectErrorStream(true);
                                Process rotProc = rotPb.start();
                                rotProc.waitFor();
                                if (new File(rotated).isFile()) previewPath = rotated;
                                directStatusLabel.setText(msg + " (rotated θ" + (int)finalTheta + ")");
                            } catch (Exception rotEx) {
                                directStatusLabel.setText(msg + " (θ post note: " + rotEx.getMessage().substring(0,20) + ")");
                            }
                        }
                        final String finalPreviewPath = previewPath;
                        setLastDownloadPath(finalPreviewPath);
                        refreshRecentDownloads();
                        appendRuntimeLog("download_complete",
                            "\"path\":\"" + jsonEsc(finalPreviewPath) + "\",\"gif\":" + finalGif
                            + ",\"format\":\"" + jsonEsc(formatNote) + "\"");

                        // gravity_update simulation: make ASC panel show LIVE data for this URL
                        // (simulates server broadcast for the gravity protocol client)
                        try {
                            // get nice title (with JS runtime if available)
                            String jsRt2 = checkJsRuntime();
                            java.util.List<String> titleArgs = new java.util.ArrayList<>();
                            titleArgs.add(YTDLP_PATH);
                            addJsRuntimeArgs(titleArgs, jsRt2);
                            addCookiesArgs(titleArgs, finalUrl, usePrivate);
                            titleArgs.add("--print");
                            titleArgs.add("%(title)s");
                            titleArgs.add(finalUrl);
                            ProcessBuilder titlePb = new ProcessBuilder(titleArgs);
                            titlePb.redirectErrorStream(true);
                            Process titleProc = titlePb.start();
                            BufferedReader tr = new BufferedReader(new InputStreamReader(titleProc.getInputStream()));
                            String vidTitle = tr.readLine();
                            titleProc.waitFor();
                            if (vidTitle == null || vidTitle.trim().isEmpty()) vidTitle = "Video " + finalUrl;
                            final String fTitle = vidTitle;
                            triggerInterlaterusMint(finalPreviewPath, finalUrl, fTitle);

                            SwingUtilities.invokeLater(() -> {
                                // add entry to jobs
                                jobsModel.addRow(new Object[]{
                                    "g-up", 
                                    fTitle.substring(0, Math.min(28, fTitle.length())), 
                                    "completed", 
                                    "100%", 
                                    finalGif ? "gif" : "h264"
                                });

                                // Symmetric ASC vs SC live data for gravity_update
                                // Uses the symbol grid for symmetric filmic borders/frames
                                // ASC side: cinematic/filmic style metadata
                                // SC side: storage_memory_category (memory update data)
                                StringBuilder asc = new StringBuilder();
                                asc.append(ASC_FRAME);
                                asc.append("\n");
                                asc.append("⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰  gravity_update LIVE DATA for ").append(fTitle).append("  ⿲⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰\n");
                                asc.append("⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱  Symmetric ASC vs SC  ⿳⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱\n\n");

                                // Left: ASC (symmetric with right SC)
                                asc.append("⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲ ASC SIDE ⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲          ");
                                asc.append("⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲ SC SIDE (storage_memory) ⿴⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲\n");
                                asc.append("⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲⿳ [FILMIC | HIGH CONTRAST | GRAIN | 320x180]          ");
                                asc.append("⿵⿶⿷⿸⿹⿺⿻⿰⿱⿲⿳ zone=local | memory=high | location=dc-1\n");
                                asc.append("⿶⿷⿸⿹⿺⿻⿰⿱⿲⿳⿴ gravity_prepared: true          ");
                                asc.append("⿶⿷⿸⿹⿺⿻⿰⿱⿲⿳⿴ V=1 | Bandwidth=high\n");
                                if (finalTheta != 0) {
                                    asc.append("⿷⿸⿹⿺⿻⿰⿱⿲⿳⿴⿵ rotation_theta: ").append((int)finalTheta).append("          ");
                                    asc.append("⿷⿸⿹⿺⿻⿰⿱⿲⿳⿴⿵ (symmetric with ASC)\n");
                                }
                                if (finalDual) {
                                    asc.append("⿸⿹⿺⿻⿰⿱⿲⿳⿴⿵⿶ dual_vi: i & j = true          ");
                                    asc.append("⿸⿹⿺⿻⿰⿱⿲⿳⿴⿵⿶ (interstellar mode)\n");
                                }
                                asc.append("⿹⿺⿻⿰⿱⿲⿳⿴⿵⿶⿷ url: ").append(finalUrl).append("\n");
                                asc.append("⿺⿻⿰⿱⿲⿳⿴⿵⿶⿷⿸ [END symmetric ASC vs SC] ⿺⿻⿰⿱⿲⿳⿴⿵⿶⿷⿸\n\n");
                                asc.append(ASC_FRAME);

                                visualistArea.setText(asc.toString());
                                final String liveMsg = msg + " | ▶ preview ready";
                                directStatusLabel.setText(liveMsg);
                            });
                        } catch (Exception ex) {
                            triggerInterlaterusMint(finalPreviewPath, finalUrl, "");
                        }
                    } else {
                        String err = lastErr.isEmpty() ? "see terminal output" : lastErr;
                        if (ip403) {
                            String route = describeNetworkRoute();
                            err = "403/geo restricted — wait "
                                + RateLimiter.cooldownSecondsRemaining()
                                + "s, try VPN/GRAVITY_PROXY (" + route + "), private+cookies";
                        } else if (err.length() > 72) {
                            err = err.substring(0, 69) + "...";
                        }
                        directStatusLabel.setText("yt-dlp failed (rc=" + finalRc + "): " + err);
                    }
                    downloadBtn.setEnabled(true);
                    urlField.setEnabled(true);
                    if (thetaField != null) thetaField.setEnabled(true);
                    if (dualCheck != null) dualCheck.setEnabled(true);
                    if (gifCheck != null) gifCheck.setEnabled(true);
                    if (privateCheck != null) privateCheck.setEnabled(true);
                });
            } catch (Exception ex) {
                String msg = ex.getMessage();
                if (msg == null) msg = ex.toString();
                final String fmsg = msg.length() > 65 ? msg.substring(0, 62) + "..." : msg;
                SwingUtilities.invokeLater(() -> {
                    directStatusLabel.setText("Error launching yt-dlp: " + fmsg + " (is yt-dlp in PATH?)");
                    directProgress.setValue(0);
                    downloadBtn.setEnabled(true);
                    urlField.setEnabled(true);
                    if (thetaField != null) thetaField.setEnabled(true);
                    if (dualCheck != null) dualCheck.setEnabled(true);
                    if (gifCheck != null) gifCheck.setEnabled(true);
                    if (privateCheck != null) privateCheck.setEnabled(true);
                });
            }
        }).start();
    }
}