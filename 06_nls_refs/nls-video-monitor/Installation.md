# Installation

Setup guide for **nls-video-monitor** (source) and **GravityDesktop** (runtime).

## Directory layout

| Path | Role |
|------|------|
| `~/Downloads/nls-video-monitor/` | Source repo — Java, Python, docs |
| `~/Downloads/GravityDesktop/` | Run directory — bundled yt-dlp, `run.sh` |
| `~/.local/bin/nls-video` | CLI symlink (optional) |
| `~/.config/gravity-desktop/` | Cookies, remote-nav.tsv |
| `~/.config/nls-video/` | Pipeline config.json |
| `~/.local/share/interlaterus-desktop/` | Blockcode DB + catalogs |
| `~/.local/share/nls-video/` | Job DB + visualist catalog |

## System requirements

| Package | Required | Notes |
|---------|----------|-------|
| Java JDK | ✓ | `javac` + `java` for GravityDesktop |
| Python 3.10+ | ✓ | interlaterus, nls-video |
| ffmpeg | ✓ | libx264, libvpx (VP56), aac |
| ffprobe | ✓ | Usually bundled with ffmpeg |
| yt-dlp | ✓ | Bundled in GravityDesktop preferred |
| Deno | ✓ for YouTube | `~/.deno/bin/deno` |
| rich | optional | `pip install rich` — TUI polish |
| python3-secretstorage | optional | Browser cookie decrypt |
| notify-send | optional | Desktop notifications |

## Step 1 — Clone / sync source

```bash
cd ~/Downloads/nls-video-monitor
chmod +x nls_video_pipe.py install.sh
./install.sh
```

Creates `~/.local/bin/nls-video` → `nls_video_pipe.py`.

Verify:

```bash
nls-video --help
```

## Step 2 — GravityDesktop run directory

If not already present:

```bash
mkdir -p ~/Downloads/GravityDesktop
cd ~/Downloads/GravityDesktop

# Copy or symlink core files from source
for f in GravityDesktop.java interlaterus_desktop.py blockcode_nft_client.py; do
  ln -sf ~/Downloads/nls-video-monitor/"$f" .
done

# Optional pipeline tools
ln -sf ~/Downloads/nls-video-monitor/nls_video_pipe.py .
ln -sf ~/Downloads/nls-video-monitor/hierarchy_interpreter.py .

# Bundled yt-dlp (recommended)
curl -fsSL -o yt-dlp https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp
chmod +x yt-dlp

# Launch scripts (copy from repo or create)
chmod +x run.sh check-paths.sh run-interlaterus.sh
```

## Step 3 — Deno (JS runtime)

```bash
curl -fsSL https://deno.land/install.sh | sh
export PATH="$HOME/.deno/bin:$PATH"
```

GravityDesktop `run.sh` adds Deno to PATH automatically.

## Step 4 — Dependency check

```bash
~/Downloads/GravityDesktop/check-paths.sh
```

Expected: 0 failures. Warnings acceptable for optional items (gravity-server not listening, nls-video not linked).

### Common failures

| Failure | Fix |
|---------|-----|
| bundled yt-dlp missing `--js-runtimes` | Re-download latest yt-dlp binary |
| deno simulate failed | Reinstall Deno; check PATH |
| libx264 missing | `sudo apt install ffmpeg` |
| python3-secretstorage | `sudo apt install python3-secretstorage` or use cookies.txt |
| java/javac missing | `sudo apt install default-jdk` |

## Step 5 — Cookies (age-restricted / private)

**Option A — Netscape file (recommended):**

```bash
mkdir -p ~/.config/gravity-desktop
# Export from browser extension → cookies.txt
```

**Option B — Browser DB:**

```bash
export GRAVITY_COOKIES_BROWSER=brave   # or chromium, chrome, firefox
```

Requires `python3-secretstorage` on Linux.

## Step 6 — Launch

### GravityDesktop only

```bash
~/Downloads/GravityDesktop/run.sh
```

### With gravity-server (live jobs in UI)

Terminal 1:

```bash
nls-video worker          # optional: processes queued jobs
```

Terminal 2:

```bash
nls-video gravity-server --port 4242
```

Terminal 3:

```bash
~/Downloads/GravityDesktop/run.sh
```

### Interlaterus watch (background mint)

```bash
~/Downloads/GravityDesktop/run-interlaterus.sh watch
```

### Web dashboard

```bash
nls-video serve --port 8765
# Open http://127.0.0.1:8765
```

### Terminal gravity client

```bash
nls-video gravity-client --port 4242
```

## Environment variables

Set in `run.sh` or shell profile:

```bash
export YTDLP_PATH="$HOME/Downloads/GravityDesktop/yt-dlp"
export FFMPEG_PATH="/usr/bin/ffmpeg"
export FFPROBE_PATH="/usr/bin/ffprobe"
export GRAVITY_COOKIES_BROWSER=brave
export GRAVITY_MIN_SLEEP_INTERVAL=3
export GRAVITY_MAX_SLEEP_INTERVAL=12
# export GRAVITY_PROXY=socks5://127.0.0.1:1080
# export GRAVITY_REMOTE_BASE=https://example.com/videos/
# export INTERLATERUS_SKIP_MINT=1
```

## ffplay (optional preview)

```bash
sudo apt install ffmpeg   # includes ffplay
ffplay -autoexit ~/Downloads/direct-h264-*.mp4
```

## VLC note

If older downloads were AV1-in-WebM mislabeled as `direct-h264-*.webm`, VLC may fail. New GravityDesktop downloads use H.264 MP4. Re-download or transcode:

```bash
ffmpeg -i broken.webm -c:v libx264 -c:a aac fixed.mp4
```

## First download test

1. Start `run.sh`
2. Paste `https://www.youtube.com/watch?v=jNQXAC9IVRw` (short test video)
3. Confirm `~/Downloads/direct-h264-jNQXAC9IVRw.mp4`
4. Confirm mint: `run-interlaterus.sh list`

## Troubleshooting

| Symptom | Cause | Action |
|---------|-------|--------|
| `finished (rc=2)` | Stale system yt-dlp | Use bundled `$APP_DIR/yt-dlp` |
| `finished (rc=1)` | 403, cookies, geo | Enable cookies; VPN/proxy; wait cooldown |
| Cookie decrypt error | No secretstorage | Install package or cookies.txt |
| Empty jobs panel | No gravity-server | `nls-video gravity-server --port 4242` |
| No mint after download | Script missing | Symlink interlaterus_desktop.py to APP_DIR |
| `already_minted` | Same file re-hashed | Expected; dedup by sha256 |

## gitignore

The repo `.gitignore` excludes `*.class`, `__pycache__`, local DBs, cookies, and download artifacts. Do not commit secrets or mint registries.

## Documentation index

- [README.md](README.md) — overview
- [ARCHITECTURE.md](ARCHITECTURE.md) — diagrams
- [GRAVITYDESKTOP_JAVA.md](GRAVITYDESKTOP_JAVA.md) — UI details
- [INTERLATERUS.md](INTERLATERUS.md) — mint flow
- [BLOCKCODE_NFT_CLIENT.md](BLOCKCODE_NFT_CLIENT.md) — NFT API
- [AnalogOnAnalog.md](AnalogOnAnalog.md) — theory