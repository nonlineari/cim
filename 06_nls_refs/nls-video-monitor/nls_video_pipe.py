#!/usr/bin/env python3
"""
NLS Video Pipeline + Monitor
Integrates yt-dlp download + ffmpeg H.264 conversion with robust monitoring.

Desktop-friendly on Linux:
- Rich TUI monitor (`nls-video monitor`)
- Simple web dashboard (`nls-video serve`) - the "interface"
- Desktop notifications via notify-send
- Clean sidecar metadata + central catalog for "NLS Visualist data"

Usage:
  nls-video add "https://youtube.com/watch?v=..." --preset balanced-4k
  nls-video list
  nls-video monitor
  nls-video serve          # opens browser dashboard
  nls-video worker         # run the processor (in tmux or &)

Presets (tuned from real usage):
  balanced-4k   (veryfast, crf 19) - good speed/quality compromise
  hq-4k         (medium, crf 18)   - higher quality, slower
  fast-1080     (veryfast, crf 23, 1080p max) - quick turnaround

Data for NLS Visualist:
  On completion writes:
    <output>.mp4
    <output>.nlsvis.json   (per-item structured data)
  Also maintains:
    ~/.local/share/nls-video/visualist_catalog.json  (append-only index of all processed items)

Config: ~/.config/nls-video/config.json  (optional)
"""

import argparse
import hashlib
import json
import mimetypes
import os
import re
import shutil
import socket
import sqlite3
import subprocess
import sys
import select
import threading
import time
from dataclasses import dataclass, asdict
import signal
from datetime import datetime, timezone
try:
    from zoneinfo import ZoneInfo
except ImportError:
    ZoneInfo = None  # type: ignore
from http.server import HTTPServer, BaseHTTPRequestHandler
import socketserver
from pathlib import Path
from typing import Optional, Dict, Any, List
from urllib.parse import urlparse, parse_qs, unquote

# Optional integration of the 11D Hierarchy Interpreter (NLS Visualist edition)
try:
    import hierarchy_interpreter
    HIERARCHY_AVAILABLE = True
except ImportError:
    HIERARCHY_AVAILABLE = False

# Optional rich (beautiful TUI / tables). Falls back gracefully.
try:
    from rich.console import Console
    from rich.table import Table
    from rich.live import Live
    from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.text import Text
    from rich import print as rprint
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    rprint = print

# JS runtime check for yt-dlp (addresses "No supported JavaScript runtime" warning)
# Supports deno (default in recent yt-dlp), node, etc.
# "pythonJava" install path: Python drives the install, Java app can call this too.
def check_js_runtime():
    """Return name of first found JS runtime or None.
    Deno and Node.js (and bun etc.) are similarly supported as JS runtimes for yt-dlp YouTube extraction.
    """
    for rt in ("deno", "node", "bun", "qjs"):
        if shutil.which(rt):
            return rt
    return None

def ensure_js_runtime(interactive: bool = True, auto_install: bool = False) -> Optional[str]:
    """Check for JS runtime. Warn if missing. Deno and Node.js are treated similarly (both work for --js-runtimes).
    Optionally install Deno (lightweight, recommended by yt-dlp by default).
    """
    rt = check_js_runtime()
    if rt:
        return rt

    msg = "WARNING: No supported JavaScript runtime for yt-dlp. YouTube extraction may miss formats. Only deno is enabled by default in recent yt-dlp."
    if RICH_AVAILABLE:
        print_rich(msg, "yellow")
    else:
        print(msg)
    print("See https://github.com/yt-dlp/yt-dlp/wiki/EJS for details.")
    print("Deno and Node.js are similarly usable as runtimes (Deno is lighter and default-preferred for yt-dlp).")

    if not interactive and not auto_install:
        return None

    if auto_install or (interactive and input("Install Deno now via official script? [y/N]: ").strip().lower() == "y"):
        try:
            print("Installing Deno (curl | sh)...")
            # Note: shell=True is used only for the official install pipe (KISS, documented).
            # Equivalent safe list would be more complex.
            subprocess.check_call(
                'curl -fsSL https://deno.land/install.sh | sh',
                shell=True
            )
            print("Deno installed. You may need to restart your shell or `source` your rc file.")
            # Update PATH for current process
            deno_bin = os.path.expanduser("~/.deno/bin")
            if os.path.isdir(deno_bin):
                os.environ["PATH"] = deno_bin + os.pathsep + os.environ.get("PATH", "")
            return "deno"
        except Exception as e:
            print(f"Auto-install failed: {e}")
            print("Install manually or use your package manager (e.g. pacman -S deno, brew install deno).")
    return None

# Enable terminal line editing for the input bar (cursor arrows, backspace, basic paste support)
try:
    import readline
except ImportError:
    pass  # Windows or minimal env; paste+Enter still works

# ----------------------------- Paths & Defaults -----------------------------
APP_NAME = "nls-video"
XDG_DATA = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / APP_NAME
XDG_CONFIG = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
XDG_CACHE = Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / APP_NAME

DB_PATH = XDG_DATA / "jobs.db"
LOG_DIR = XDG_DATA / "logs"
CONFIG_PATH = XDG_CONFIG / "config.json"
CATALOG_PATH = XDG_DATA / "visualist_catalog.json"
INTERLATERUS_CATALOG = Path.home() / ".local" / "share" / "interlaterus-desktop" / "nls_media_catalog.json"
BLOCKCODE_DB = Path.home() / ".local" / "share" / "interlaterus-desktop" / "blockcode_registry.db"
POSITION_INDEX_PATH = XDG_DATA / "position_index.json"
PROOF_OF_SPATIO_PATH = XDG_DATA / "proof-of-spatio.json"
DOWNLOADS_DIR = Path.home() / "Downloads"

TIME_AXIOM = "utc"
DERIVED_TIMEZONES: Dict[str, str] = {
    "new_york": "America/New_York",
    "london": "Europe/London",
    "hong_kong": "Asia/Hong_Kong",
    "los_angeles": "America/Los_Angeles",
}
# Standard local timezone — override with GRAVITY_LOCAL_TIMEZONE or TZ (IANA name).
LOCAL_TIMEZONE: str = ""


def resolve_local_timezone() -> str:
    """Resolve standard local TZ var: env GRAVITY_LOCAL_TIMEZONE → TZ → system → London."""
    global LOCAL_TIMEZONE
    if LOCAL_TIMEZONE:
        return LOCAL_TIMEZONE
    for key in ("GRAVITY_LOCAL_TIMEZONE", "TZ"):
        v = os.environ.get(key, "").strip()
        if v and v.upper() not in ("UTC", "GMT", "GMT0"):
            LOCAL_TIMEZONE = v
            return LOCAL_TIMEZONE
    if ZoneInfo is not None:
        try:
            local = datetime.now().astimezone().tzinfo
            key = getattr(local, "key", None)
            if key:
                LOCAL_TIMEZONE = str(key)
                return LOCAL_TIMEZONE
        except Exception:
            pass
    LOCAL_TIMEZONE = "Europe/London"
    return LOCAL_TIMEZONE


def resolve_app_root() -> Path:
    """Project root — never ~/.local/bin (gravity-serve assets break under bin symlink)."""
    env = os.environ.get("NLS_VIDEO_HOME", "").strip()
    if env:
        root = Path(env).expanduser().resolve()
        if (root / "nls_video_pipe.py").is_file():
            return root
    script = Path(__file__).resolve()
    if script.name == "nls_video_pipe.py":
        return script.parent
    parent = script.parent
    if parent.name == "bin" or str(parent).endswith("/.local/bin"):
        for cand in (
            Path.home() / "Downloads" / "nls-video-monitor",
            Path.home() / "Downloads" / "GravityDesktop",
        ):
            if (cand / "nls_video_pipe.py").is_file():
                return cand.resolve()
    return parent


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def now_utc_iso() -> str:
    return now_utc().isoformat()


def format_utc_axiom(at: Optional[datetime] = None) -> Dict[str, str]:
    at = at or now_utc()
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    else:
        at = at.astimezone(timezone.utc)
    return {"axiom": TIME_AXIOM, "iso": at.isoformat(), "display": at.strftime("%Y-%m-%d %H:%M:%S UTC")}


def format_local_clock(at: Optional[datetime] = None, local_tz: Optional[str] = None) -> Dict[str, str]:
    """Local wall clock projected from UTC axiom via standard LOCAL_TIMEZONE var."""
    at = at or now_utc()
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    else:
        at = at.astimezone(timezone.utc)
    tz_name = local_tz or resolve_local_timezone()
    if ZoneInfo is not None:
        try:
            local = at.astimezone(ZoneInfo(tz_name))
            return {
                "tz": tz_name,
                "iso": local.isoformat(),
                "display": local.strftime("%Y-%m-%d %H:%M:%S %Z"),
            }
        except Exception:
            pass
    return {"tz": tz_name, "iso": at.isoformat(), "display": at.strftime("%Y-%m-%d %H:%M:%S UTC")}


def format_derived_clocks(at: Optional[datetime] = None) -> Dict[str, str]:
    at = at or now_utc()
    if at.tzinfo is None:
        at = at.replace(tzinfo=timezone.utc)
    else:
        at = at.astimezone(timezone.utc)
    out: Dict[str, str] = {}
    for key, tz_name in DERIVED_TIMEZONES.items():
        if ZoneInfo is not None:
            try:
                out[key] = at.astimezone(ZoneInfo(tz_name)).strftime("%Y-%m-%d %H:%M:%S %Z")
                continue
            except Exception:
                pass
        out[key] = at.isoformat()
    return out


def api_time() -> Dict[str, Any]:
    at = now_utc()
    axiom = format_utc_axiom(at)
    derived = format_derived_clocks(at)
    local = format_local_clock(at)
    local_tz = local["tz"]
    return {
        "ok": True,
        "axiom": TIME_AXIOM,
        "utc_iso": axiom["iso"],
        "utc": axiom["display"],
        "local_tz": local_tz,
        "local": local["display"],
        "local_iso": local["iso"],
        "derived": derived,
        "zones": {"axiom": "UTC", "local": local_tz, "derived": DERIVED_TIMEZONES},
        "clocks": {"utc": axiom["display"], "local": local["display"], **derived},
    }


_SCRIPT_DIR = resolve_app_root()
VERSION_PATH = _SCRIPT_DIR / "version.json"
GRAVITY_SERVE_HTML = _SCRIPT_DIR / "gravity_serve.html"
PLAN_HTML = _SCRIPT_DIR / "plan.html"
PLAN_MD = _SCRIPT_DIR / "plan.md"
PLAN_ORIGINAL_MD = _SCRIPT_DIR / "plan.original.md"
RUNTIME_LOG_DIR = Path.home() / ".local" / "share" / "gravity-desktop" / "runtime-logs"
GRAVITY_SERVE_RUNNING_PATH = XDG_DATA / "gravity-serve-running.json"
MM_NOTIFY_PATH = XDG_DATA / "mm-notify.json"
ARCHIVE_LATEST_LINK = XDG_DATA / "archives" / "gravity-serve-latest"


def load_version_manifest() -> Dict[str, Any]:
    try:
        return json.loads(VERSION_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"name": APP_NAME, "version": "0.0.0", "tag": "v0.0.0"}


__version__ = str(load_version_manifest().get("version", "0.0.0"))

# Default media root for NLS Visualist outputs
DEFAULT_VISUALIST_ROOT = Path.home() / "Videos" / "NLS-Visualist"

DEFAULT_PRESETS = {
    "balanced-4k": {
        "description": "Balanced 4K H.264 (veryfast + crf19) - recommended for most desktop work",
        "ffmpeg_extra": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"],
        "max_height": None,
    },
    "hq-4k": {
        "description": "Higher quality 4K (medium preset, crf18) - slower but better efficiency",
        "ffmpeg_extra": ["-c:v", "libx264", "-preset", "medium", "-crf", "18",
                         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "256k", "-movflags", "+faststart"],
        "max_height": None,
    },
    "fast-1080": {
        "description": "Fast 1080p (veryfast, crf23, scaled) - quick turnaround / editing proxies",
        "ffmpeg_extra": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23",
                         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"],
        "max_height": 1080,
    },
    "interstellar-nonlinear": {
        "description": "Interstellar|nonlineari Visualist: H.264 + VP56 via SCIS noiseprotocol-vcodec + FFMPEG origin transcode + gravity (noiseprotocol secure transport prep). For 1000 years old nonlinear h@k reality aesthetics.",
        "ffmpeg_extra": ["-c:v", "libx264", "-preset", "veryfast", "-crf", "19",
                         "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart"],
        "max_height": None,
        "vp56": True,
        "gravity": True,
    },
}

# ----------------------------- Data Model -----------------------------
@dataclass
class Job:
    id: int
    url: str
    title: str
    preset: str
    status: str  # pending, downloading, converting, completed, failed, cancelled
    progress: float  # 0-100
    stage: str       # download | convert | done
    output_path: Optional[str]
    log_path: str
    metadata: Dict[str, Any]
    created: str
    started: Optional[str] = None
    finished: Optional[str] = None
    error: Optional[str] = None
    source_file: Optional[str] = None  # for convert-only on existing local file

    def to_dict(self):
        d = asdict(self)
        if isinstance(d.get("metadata"), str):
            try:
                d["metadata"] = json.loads(d["metadata"])
            except Exception:
                pass
        return d


# ----------------------------- DB Helpers -----------------------------
def get_db():
    XDG_DATA.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            url TEXT NOT NULL,
            title TEXT,
            preset TEXT,
            status TEXT,
            progress REAL DEFAULT 0,
            stage TEXT,
            output_path TEXT,
            log_path TEXT,
            metadata TEXT,
            created TEXT,
            started TEXT,
            finished TEXT,
            error TEXT,
            source_file TEXT
        )
    """)
    try:
        conn.execute("ALTER TABLE jobs ADD COLUMN source_file TEXT")
    except sqlite3.OperationalError:
        pass
    conn.commit()
    return conn


def save_job(conn, job: Job):
    conn.execute("""
        INSERT OR REPLACE INTO jobs
        (id, url, title, preset, status, progress, stage, output_path, log_path, metadata,
         created, started, finished, error, source_file)
        VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        job.id, job.url, job.title, job.preset, job.status, job.progress, job.stage,
        job.output_path, job.log_path, json.dumps(job.metadata),
        job.created, job.started, job.finished, job.error, getattr(job, 'source_file', None)
    ))
    conn.commit()


def load_job(conn, job_id: int) -> Optional[Job]:
    row = conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        return None
    meta = json.loads(row["metadata"] or "{}")
    return Job(
        id=row["id"], url=row["url"], title=row["title"] or "", preset=row["preset"],
        status=row["status"], progress=row["progress"] or 0, stage=row["stage"] or "",
        output_path=row["output_path"], log_path=row["log_path"],
        metadata=meta, created=row["created"], started=row["started"],
        finished=row["finished"], error=row["error"],
        source_file=row["source_file"] if "source_file" in row.keys() else None
    )


def list_jobs(conn, status: Optional[str] = None) -> List[Job]:
    q = "SELECT * FROM jobs"
    params = []
    if status:
        q += " WHERE status = ?"
        params.append(status)
    q += " ORDER BY id DESC"
    rows = conn.execute(q, params).fetchall()
    jobs = []
    for r in rows:
        meta = json.loads(r["metadata"] or "{}")
        jobs.append(Job(
            id=r["id"], url=r["url"], title=r["title"] or "", preset=r["preset"],
            status=r["status"], progress=r["progress"] or 0, stage=r["stage"] or "",
            output_path=r["output_path"], log_path=r["log_path"],
            metadata=meta, created=r["created"], started=r["started"],
            finished=r["finished"], error=r["error"],
            source_file=r["source_file"] if "source_file" in r.keys() else None
        ))
    return jobs


# ----------------------------- Config & Visualist Data -----------------------------
def load_config() -> dict:
    XDG_CONFIG.mkdir(parents=True, exist_ok=True)
    if CONFIG_PATH.exists():
        try:
            return json.loads(CONFIG_PATH.read_text())
        except Exception:
            pass
    cfg = {
        "visualist_root": str(DEFAULT_VISUALIST_ROOT),
        "default_preset": "balanced-4k",
        "notify": True,
    }
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2))
    return cfg


def ensure_visualist_root(cfg: dict) -> Path:
    root = Path(cfg.get("visualist_root", DEFAULT_VISUALIST_ROOT))
    root.mkdir(parents=True, exist_ok=True)
    return root


def write_visualist_sidecar(video_path: Path, job: Job, cfg: dict):
    """Write per-file .nlsvis.json + update central catalog for NLS Visualist data."""
    sidecar = video_path.with_suffix(".nlsvis.json")
    data = {
        "id": job.id,
        "title": job.title,
        "source_url": job.url,
        "preset": job.preset,
        "output_path": str(video_path),
        "technical": job.metadata.get("technical", {}),
        "processed_at": job.finished,
        "tags": ["youtube", "h264", job.preset],
        "storage_memory_category": job.metadata.get("storage_memory_category", {}),
        "interstellar_nonlinear": job.metadata.get("interstellar_nonlinear", False),
        "gravity_prepared": job.metadata.get("gravity_prepared", False),
        "vp56_gravity_prepared": job.metadata.get("vp56_gravity_prepared", False),
    }
    sidecar.write_text(json.dumps(data, indent=2))

    # Append to central catalog (NLS Visualist data interface)
    catalog = []
    if CATALOG_PATH.exists():
        try:
            catalog = json.loads(CATALOG_PATH.read_text())
        except Exception:
            catalog = []
    catalog.append(data)
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2))

    # Also drop a copy in the Visualist root for easy ingestion
    try:
        root = ensure_visualist_root(cfg)
        dest = root / sidecar.name
        if not dest.exists():
            shutil.copy2(sidecar, dest)
        # Optionally copy the video too (or symlink). For now we just note the path.
    except Exception:
        pass


def desktop_notify(title: str, body: str):
    try:
        subprocess.run(["notify-send", "-a", "NLS Video", title, body], check=False)
    except Exception:
        pass


# ----------------------------- yt-dlp + ffmpeg logic -----------------------------
def sanitize_filename(name: str) -> str:
    return re.sub(r'[<>:"/\\|?*]', '_', name).strip()


YTDLP_H264_FORMAT = (
    "bv*[vcodec^=avc][ext=mp4]+ba[ext=m4a]/bv*[vcodec^=avc1]+ba[ext=m4a]/"
    "b[ext=mp4][vcodec^=avc]/bestvideo[vcodec^=avc]+bestaudio/best[vcodec^=avc]"
)
YTDLP_GIF_FORMAT = "best[ext=gif]/best"

_active_ffmpeg_procs: Dict[int, subprocess.Popen] = {}
_active_ffmpeg_lock = threading.Lock()

_direct_dl_lock = threading.Lock()
_direct_dl_state: Dict[str, Any] = {
    "status": "idle",
    "progress": 0.0,
    "message": "",
    "error": None,
    "url": None,
    "path": None,
}


class GravityRateLimiter:
    """Mirror GravityDesktop RateLimiter — pacing + 403 cooldown."""

    _lock = threading.Lock()
    _last_request_ms = 0.0
    _cooldown_until_ms = 0.0
    _consecutive_403 = 0

    @classmethod
    def acquire(cls, phase: str = "yt-dlp") -> None:
        min_gap_ms = float(os.environ.get("GRAVITY_MIN_REQUEST_INTERVAL_SEC", "3")) * 1000.0
        with cls._lock:
            now = time.time() * 1000.0
            wait_until = max(cls._last_request_ms + min_gap_ms, cls._cooldown_until_ms)
            wait_ms = wait_until - now
        if wait_ms > 0:
            time.sleep(wait_ms / 1000.0)
        with cls._lock:
            cls._last_request_ms = time.time() * 1000.0

    @classmethod
    def on_403(cls) -> None:
        with cls._lock:
            cls._consecutive_403 += 1
            base_sec = float(os.environ.get("GRAVITY_403_COOLDOWN_SEC", "60"))
            cooldown_sec = base_sec * min(cls._consecutive_403, 5)
            cls._cooldown_until_ms = time.time() * 1000.0 + cooldown_sec * 1000.0

    @classmethod
    def on_success(cls) -> None:
        with cls._lock:
            cls._consecutive_403 = max(0, cls._consecutive_403 - 1)

    @classmethod
    def cooldown_seconds_remaining(cls) -> int:
        with cls._lock:
            rem = cls._cooldown_until_ms - time.time() * 1000.0
            return int((rem + 999) // 1000) if rem > 0 else 0


def _env_str(key: str, default: str) -> str:
    v = os.environ.get(key)
    return v.strip() if v and v.strip() else default


def resolve_ytdlp_path() -> str:
    script_dir = _SCRIPT_DIR
    for cand in (
        os.environ.get("YTDLP_PATH"),
        str(script_dir / "yt-dlp"),
        str(Path.home() / "Downloads" / "GravityDesktop" / "yt-dlp"),
        str(Path.home() / ".local" / "bin" / "yt-dlp"),
        "/usr/local/bin/yt-dlp",
        "/usr/bin/yt-dlp",
    ):
        if cand and Path(cand).is_file():
            return cand
    found = shutil.which("yt-dlp")
    return found or "yt-dlp"


def _resolve_proxy_url() -> Optional[str]:
    gravity = os.environ.get("GRAVITY_PROXY")
    if gravity and gravity.strip():
        return gravity.strip()
    for key in ("HTTPS_PROXY", "https_proxy", "ALL_PROXY", "all_proxy", "HTTP_PROXY", "http_proxy"):
        v = os.environ.get(key)
        if v and v.strip():
            return v.strip()
    return None


def _cookies_file_path() -> Optional[str]:
    env = os.environ.get("GRAVITY_COOKIES_FILE")
    if env:
        p = Path(env.strip())
        if p.is_file():
            return str(p)
    default = Path.home() / ".config" / "gravity-desktop" / "cookies.txt"
    return str(default) if default.is_file() else None


def _browser_cookie_db_exists(browser: str) -> bool:
    home = Path.home()
    b = browser.lower().split(":")[0].split("+")[0]
    chromium_paths = {
        "brave": [home / ".config" / "BraveSoftware" / "Brave-Browser" / "Default" / "Cookies"],
        "chromium": [home / ".config" / "chromium" / "Default" / "Cookies"],
        "chrome": [home / ".config" / "google-chrome" / "Default" / "Cookies"],
        "edge": [home / ".config" / "microsoft-edge" / "Default" / "Cookies"],
        "opera": [
            home / ".config" / "opera" / "Default" / "Cookies",
            home / ".config" / "opera-stable" / "Default" / "Cookies",
        ],
        "vivaldi": [home / ".config" / "vivaldi" / "Default" / "Cookies"],
        "whale": [
            home / ".config" / "naver-whale" / "Default" / "Cookies",
            home / ".config" / "Naver Whale" / "Default" / "Cookies",
        ],
    }
    if b in chromium_paths:
        return any(p.is_file() for p in chromium_paths[b])
    if b == "safari":
        return (home / "Library" / "Cookies" / "Cookies.binarycookies").is_file()
    if b == "firefox":
        for base in (home / "snap" / "firefox" / "common" / ".mozilla" / "firefox",
                     home / ".mozilla" / "firefox"):
            if not base.is_dir():
                continue
            for prof in base.iterdir():
                if prof.is_dir() and ("default" in prof.name.lower()):
                    if (prof / "cookies.sqlite").is_file():
                        return True
    return False


def _resolve_cookies_browser() -> Optional[str]:
    env = os.environ.get("GRAVITY_COOKIES_BROWSER")
    if env and env.strip():
        return env.strip()
    for candidate in ("brave", "chromium", "chrome", "edge", "firefox", "opera", "vivaldi", "whale", "safari"):
        if _browser_cookie_db_exists(candidate):
            return candidate
    return None


def _resolve_cookie_source(use_private: bool = True) -> Optional[Dict[str, str]]:
    if not use_private:
        return None
    f = _cookies_file_path()
    if f:
        return {"kind": "file", "value": f}
    browser = _resolve_cookies_browser()
    if browser:
        return {"kind": "browser", "value": browser}
    return None


def _output_indicates_403(lines: List[str]) -> bool:
    for line in lines:
        if not line:
            continue
        l = line.lower()
        if any(x in l for x in (
            "403", "forbidden", "http error 403", "rate limit", "rate-limit",
            "too many requests", "429", "precondition check failed",
            "not available in your country", "geo restrict", "geo-restrict",
            "blocked in your region", "copyright grounds",
        )):
            return True
        if "ip" in l and any(x in l for x in ("block", "restrict", "banned")):
            return True
    return False


def _ytdlp_js_runtime() -> Optional[str]:
    rt = check_js_runtime()
    if rt:
        return rt
    deno = Path.home() / ".deno" / "bin" / "deno"
    if deno.is_file():
        return "deno"
    return None


def _build_ytdlp_cli_base(url: str, use_private: bool = True) -> List[str]:
    """CLI args shared with GravityDesktop addBaseYtDlpArgs."""
    args = [resolve_ytdlp_path()]
    args += [
        "--min-sleep-interval", _env_str("GRAVITY_MIN_SLEEP_INTERVAL", _env_str("GRAVITY_SLEEP_INTERVAL", "3")),
        "--max-sleep-interval", _env_str("GRAVITY_MAX_SLEEP_INTERVAL", "12"),
        "--sleep-requests", _env_str("GRAVITY_SLEEP_REQUESTS", "1"),
        "--retries", _env_str("GRAVITY_RETRIES", "15"),
        "--fragment-retries", _env_str("GRAVITY_FRAGMENT_RETRIES", "15"),
        "--extractor-retries", _env_str("GRAVITY_EXTRACTOR_RETRIES", "5"),
        "--retry-sleep", "http:exp=1:" + _env_str("GRAVITY_HTTP_RETRY_SLEEP_MAX", "60"),
        "--retry-sleep", "fragment:exp=1:30",
        "--retry-sleep", "extractor:exp=1:20",
        "--concurrent-fragments", "1",
    ]
    limit_rate = os.environ.get("GRAVITY_LIMIT_RATE")
    if limit_rate and limit_rate.strip():
        args += ["--limit-rate", limit_rate.strip()]
    proxy = _resolve_proxy_url()
    if proxy:
        args += ["--proxy", proxy]
        geo = os.environ.get("GRAVITY_GEO_PROXY") or proxy
        args += ["--geo-verification-proxy", geo.strip()]
    js_rt = _ytdlp_js_runtime()
    if js_rt:
        args += ["--js-runtimes", js_rt]
    cookie_src = _resolve_cookie_source(use_private)
    if cookie_src:
        if cookie_src["kind"] == "file":
            args += ["--cookies", cookie_src["value"]]
        else:
            args += ["--cookies-from-browser", cookie_src["value"]]
    return args


def _ytdlp_api_extra_opts(use_private: bool = True) -> Dict[str, Any]:
    """Python yt_dlp options mirroring GravityDesktop pacing/proxy/cookies."""
    opts: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "sleep_interval_requests": int(_env_str("GRAVITY_SLEEP_REQUESTS", "1")),
        "sleep_interval": int(_env_str("GRAVITY_MIN_SLEEP_INTERVAL", "3")),
        "max_sleep_interval": int(_env_str("GRAVITY_MAX_SLEEP_INTERVAL", "12")),
        "retries": int(_env_str("GRAVITY_RETRIES", "15")),
        "fragment_retries": int(_env_str("GRAVITY_FRAGMENT_RETRIES", "15")),
        "extractor_retries": int(_env_str("GRAVITY_EXTRACTOR_RETRIES", "5")),
        "concurrent_fragment_downloads": 1,
    }
    proxy = _resolve_proxy_url()
    if proxy:
        opts["proxy"] = proxy
        opts["geo_verification_proxy"] = (os.environ.get("GRAVITY_GEO_PROXY") or proxy).strip()
    limit_rate = os.environ.get("GRAVITY_LIMIT_RATE")
    if limit_rate and limit_rate.strip():
        opts["ratelimit"] = limit_rate.strip()
    js_rt = _ytdlp_js_runtime()
    if js_rt:
        opts["js_runtimes"] = [js_rt]
    cookie_src = _resolve_cookie_source(use_private)
    if cookie_src:
        if cookie_src["kind"] == "file":
            opts["cookiefile"] = cookie_src["value"]
        else:
            opts["cookiesfrombrowser"] = (cookie_src["value"],)
    return opts


def _run_ytdlp_cli(args: List[str], on_line: Optional[Any] = None) -> Dict[str, Any]:
    GravityRateLimiter.acquire("yt-dlp")
    proc = subprocess.Popen(
        args,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )
    lines: List[str] = []
    last_line = ""
    assert proc.stdout is not None
    for line in proc.stdout:
        line = line.rstrip("\n")
        last_line = line
        lines.append(line)
        if on_line:
            on_line(line)
    rc = proc.wait()
    return {"exit_code": rc, "last_line": last_line, "lines": lines}


def _parse_ytdlp_progress(line: str) -> Optional[float]:
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", line)
    if m:
        try:
            return float(m.group(1))
        except ValueError:
            pass
    return None


def _direct_dl_set(**kwargs: Any) -> None:
    with _direct_dl_lock:
        _direct_dl_state.update(kwargs)


def direct_download_status() -> Dict[str, Any]:
    with _direct_dl_lock:
        return dict(_direct_dl_state)


def _job_is_cancelled(job_id: int) -> bool:
    conn = get_db()
    job = load_job(conn, job_id)
    conn.close()
    return bool(job and job.status == "cancelled")


def _register_ffmpeg_proc(job_id: int, proc: subprocess.Popen) -> None:
    with _active_ffmpeg_lock:
        old = _active_ffmpeg_procs.get(job_id)
        if old and old.poll() is None:
            try:
                old.terminate()
            except Exception:
                pass
        _active_ffmpeg_procs[job_id] = proc


def _unregister_ffmpeg_proc(job_id: int) -> None:
    with _active_ffmpeg_lock:
        _active_ffmpeg_procs.pop(job_id, None)


def _stop_job_processes(job_id: int) -> None:
    with _active_ffmpeg_lock:
        proc = _active_ffmpeg_procs.pop(job_id, None)
    if proc and proc.poll() is None:
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


def run_download(job: Job, conn: sqlite3.Connection, cfg: dict) -> Path:
    """Download using yt_dlp Python API for clean progress hooks."""
    ensure_js_runtime(interactive=False)
    from yt_dlp.utils import DownloadCancelled
    import yt_dlp

    if _job_is_cancelled(job.id):
        raise DownloadCancelled("job cancelled before download")

    job.status = "downloading"
    job.stage = "download"
    job.progress = 0
    save_job(conn, job)

    out_dir = Path(job.output_path).parent if job.output_path else XDG_CACHE
    out_dir.mkdir(parents=True, exist_ok=True)

    base = sanitize_filename(job.title or f"video-{job.id}")
    temp_template = str(out_dir / f"{base}.%(ext)s")

    def _hook(d: dict) -> None:
        if _job_is_cancelled(job.id):
            raise DownloadCancelled("job cancelled during download")
        _yt_progress_hook(d, job, conn)

    ydl_opts = {
        "outtmpl": temp_template,
        "format": "bestvideo+bestaudio/best",
        "merge_output_format": "mp4",
        "progress_hooks": [_hook],
        **_ytdlp_api_extra_opts(use_private=True),
    }

    GravityRateLimiter.acquire("yt-dlp")
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(job.url, download=True)
            title = info.get("title", job.title)
            job.title = title or job.title
            for f in out_dir.glob(f"{base}.*"):
                if f.suffix.lower() in (".mp4", ".mkv", ".webm"):
                    downloaded = f
                    break
            else:
                downloaded = Path(ydl.prepare_filename(info))
    except DownloadCancelled:
        job.status = "cancelled"
        job.stage = "cancelled"
        job.finished = now_utc_iso()
        save_job(conn, job)
        raise
    except Exception as e:
        err_lines = [str(e)]
        if _output_indicates_403(err_lines):
            GravityRateLimiter.on_403()
        raise

    if _job_is_cancelled(job.id):
        job.status = "cancelled"
        job.stage = "cancelled"
        job.finished = now_utc_iso()
        save_job(conn, job)
        raise DownloadCancelled("job cancelled after download")

    GravityRateLimiter.on_success()
    job.metadata["source"] = {
        "title": job.title,
        "duration": info.get("duration"),
        "uploader": info.get("uploader"),
        "view_count": info.get("view_count"),
    }
    save_job(conn, job)
    return downloaded


def _yt_progress_hook(d: dict, job: Job, conn: sqlite3.Connection):
    if d.get("status") == "downloading":
        pct = d.get("_percent_str", "0%").replace("%", "").strip()
        try:
            job.progress = float(pct) * 0.5  # download is first 50%
        except Exception:
            pass
        job.stage = "download"
        save_job(conn, job)


def generate_thumbnail(video_path: Path, thumb_path: Path, seek_time="00:01:30"):
    """Generate a thumbnail for NLS Visualist preview. Rule #2 no eval."""
    try:
        subprocess.check_call([
            "ffmpeg", "-y", "-ss", seek_time, "-i", str(video_path),
            "-vframes", "1", "-vf", "scale=320:-1", "-q:v", "3",
            str(thumb_path)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False


def prepare_for_noise_gravity(video_path: Path, output_h264: Optional[Path] = None) -> Path:
    """Prepare H.264 video for Noise Protocol transport (gravity mode).
    Analog to SCIS 'prepare-for-noise' for VP56: extract raw elementary stream
    so packets/NALs can be individually protected by Noise CipherState.
    Rule #1 no kill, Rule #2 no eval. Uses ffmpeg demux only.
    """
    if output_h264 is None:
        output_h264 = video_path.with_suffix(".h264")
    cmd = [
        "ffmpeg", "-y", "-i", str(video_path),
        "-c:v", "copy",
        "-f", "h264",
        str(output_h264)
    ]
    subprocess.check_call(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return output_h264


def prepare_interstellar_nonlinear_gravity(video_path: Path) -> Path:
    """Use SCIS noiseprotocol-vcodec + FFMPEG for VP56 'origin form follows function' look
    for interstellar|nonlineari Visualist content (nonlinear time, space, hack reality aesthetics).
    Then prepare raw VP56 packets for Noise Protocol gravity transport (SCIS style).
    Integrates with the monitor pipeline for artistic NLS Visualist data.
    """
    vcodec_bin = "/home/nlsrecords/Downloads/SCIS/dist-newstyle/build/x86_64-linux/ghc-9.6.7/noiseprotocol-0.1.0.0/x/noiseprotocol-vcodec/build/noiseprotocol-vcodec/noiseprotocol-vcodec"
    vp56_out = video_path.with_suffix(".vp6f.interstellar.mov")
    raw_packets = video_path.with_suffix(".vp56-gravity-packets.bin")

    try:
        # Encode/transcode to VP56 origin look (legacy for visualist, nonlinear feel)
        # Using SCIS vcodec for encode-vp56 --variant vp6f (or transcodeOrigin style)
        subprocess.check_call([
            vcodec_bin, "encode-vp56", "--variant", "vp6f",
            str(video_path), str(vp56_out)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        # Prepare for noise gravity transport (extract raw like SCIS)
        subprocess.check_call([
            "ffmpeg", "-y", "-i", str(vp56_out),
            "-c:v", "copy", "-f", "rawvideo", str(raw_packets)
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        return raw_packets
    except Exception as e:
        print(f"Interstellar/nonlineari gravity VP56 prep note: {e} (fallback to H264 gravity)")
        return prepare_for_noise_gravity(video_path)


def get_storage_memory_category(job: Job) -> dict:
    """Storage memory category for NLS Visualist data.
    Includes zone and memory|location|zone|V|Bandwidth.
    Different for interstellar|nonlineari vs default.
    """
    title_lower = (job.title or "").lower()
    is_inter = job.metadata.get("interstellar_nonlinear") or "interstellar" in title_lower or "nonlineari" in title_lower or job.preset == "interstellar-nonlinear"
    if is_inter:
        return {
            "zone": "interstellar-zone-alpha",
            "memory": "16GB",
            "location": "nls-visualist-dc-1",
            "zone": "interstellar-zone-alpha",  # repeated zone as per spec
            "V": "vp56-vol-1999",
            "Bandwidth": "10Gbps"
        }
    else:
        return {
            "zone": "default-zone",
            "memory": "8GB",
            "location": "local-dc",
            "zone": "default-zone",
            "V": "h264-vol",
            "Bandwidth": "1Gbps"
        }


def run_convert(source: Path, job: Job, conn: sqlite3.Connection, cfg: dict, preset: dict):
    """Run ffmpeg conversion with live progress parsing."""
    job.status = "converting"
    job.stage = "convert"
    job.progress = 50.0
    save_job(conn, job)

    root = ensure_visualist_root(cfg)
    safe_title = sanitize_filename(job.title or f"job-{job.id}")
    final_name = f"{safe_title} [{job.id}].mp4"
    final_path = root / final_name
    final_path.parent.mkdir(parents=True, exist_ok=True)

    job.output_path = str(final_path)
    job.log_path = str(LOG_DIR / f"job-{job.id}.log")
    save_job(conn, job)

    # Get duration for % calculation
    duration = None
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(source)],
            text=True
        ).strip()
        duration = float(out)
        job.metadata.setdefault("technical", {})["source_duration"] = duration
    except Exception:
        pass

    cmd = [
        "ffmpeg", "-y", "-i", str(source),
        *preset["ffmpeg_extra"],
    ]
    if preset.get("max_height"):
        cmd += ["-vf", f"scale=-2:{preset['max_height']}"]

    cmd += ["-progress", "pipe:1", "-nostats", str(final_path)]

    log_f = open(job.log_path, "a")
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=log_f, text=True, bufsize=1)
    _register_ffmpeg_proc(job.id, proc)

    start = time.time()
    last_update = 0.0

    while True:
        if _job_is_cancelled(job.id):
            try:
                proc.terminate()
            except Exception:
                pass
            job.status = "cancelled"
            job.stage = "cancelled"
            job.finished = now_utc_iso()
            save_job(conn, job)
            log_f.close()
            _unregister_ffmpeg_proc(job.id)
            return

        line = proc.stdout.readline()
        if not line:
            if proc.poll() is not None:
                break
            continue

        line = line.strip()
        if "=" in line:
            k, v = line.split("=", 1)
            if k == "out_time_ms" and duration:
                try:
                    secs = int(v) / 1_000_000
                    conv_pct = min(100.0, (secs / duration) * 100.0)
                    overall = 50.0 + (conv_pct * 0.5)
                    job.progress = round(overall, 1)
                    job.metadata.setdefault("technical", {})["encode_speed"] = None
                except Exception:
                    pass
            elif k == "speed":
                job.metadata.setdefault("technical", {})["encode_speed"] = v
            elif k == "fps":
                job.metadata.setdefault("technical", {})["encode_fps"] = v

        now = time.time()
        if now - last_update > 1.5:
            save_job(conn, job)
            last_update = now

    proc.wait()
    log_f.close()
    _unregister_ffmpeg_proc(job.id)

    if _job_is_cancelled(job.id):
        job.status = "cancelled"
        job.stage = "cancelled"
        job.finished = now_utc_iso()
        save_job(conn, job)
        return

    if proc.returncode != 0:
        job.status = "failed"
        job.error = f"ffmpeg exited with {proc.returncode}"
        save_job(conn, job)
        return

    # Success
    job.status = "completed"
    job.progress = 100.0
    job.stage = "done"
    job.finished = now_utc_iso()
    job.metadata["technical"]["final_size"] = final_path.stat().st_size
    save_job(conn, job)

    # Generate thumbnail for Visualist interface
    thumb = final_path.with_suffix(".thumb.jpg")
    if generate_thumbnail(final_path, thumb):
        job.metadata["thumbnail"] = str(thumb)
        save_job(conn, job)

    # Gravity / Noise Protocol prep (using SCIS philosophy for secure transport of Visualist data)
    preset_def = DEFAULT_PRESETS.get(job.preset, {})
    do_gravity = job.metadata.get("gravity") or preset_def.get("gravity", False)
    if do_gravity:
        h264 = prepare_for_noise_gravity(final_path)
        job.metadata["gravity_prepared"] = True
        job.metadata["raw_h264_stream"] = str(h264)
        save_job(conn, job)

    # Interstellar|nonlineari support: use SCIS noiseprotocol-vcodec + FFMPEG for VP56 origin form
    # (legacy visualist look for nonlinear/hack reality, space themes like Interstellar)
    # Then gravity prep for Noise transport
    do_vp56_gravity = preset_def.get("vp56", False) or job.metadata.get("gravity") or "interstellar" in (job.title or "").lower() or "nonlineari" in (job.title or "").lower()
    if do_vp56_gravity:
        vp56_gravity = prepare_interstellar_nonlinear_gravity(final_path)
        job.metadata["vp56_gravity_prepared"] = True
        job.metadata["vp56_raw_stream"] = str(vp56_gravity)
        job.metadata["interstellar_nonlinear"] = True
        save_job(conn, job)

    # Storage memory category (must have zone and memory|location|zone|V|Bandwidth)
    job.metadata["storage_memory_category"] = get_storage_memory_category(job)
    save_job(conn, job)

    # NLS Visualist data interface
    write_visualist_sidecar(final_path, job, cfg)

    if cfg.get("notify", True):
        desktop_notify("NLS Video Complete", f"{job.title} ready → {final_path.name}")

    # Optional: remove source download if it was a temp
    # (we keep it for now so user can re-encode with different preset)


def process_one_job(job_id: int):
    conn = get_db()
    job = load_job(conn, job_id)
    if not job or job.status not in ("pending",):
        return

    cfg = load_config()
    preset = DEFAULT_PRESETS.get(job.preset, DEFAULT_PRESETS["balanced-4k"])

    job.started = now_utc_iso()

    if job.source_file and Path(job.source_file).exists():
        downloaded = Path(job.source_file)
        job.progress = 50.0
        job.stage = "convert"
        job.status = "converting"
        save_job(conn, job)
    else:
        job.status = "downloading"
        save_job(conn, job)
        downloaded = run_download(job, conn, cfg)

    try:
        if _job_is_cancelled(job_id):
            return
        run_convert(downloaded, job, conn, cfg, preset)

    except Exception as e:
        from yt_dlp.utils import DownloadCancelled
        if isinstance(e, DownloadCancelled) or _job_is_cancelled(job_id):
            job = load_job(conn, job_id)
            if job and job.status != "cancelled":
                job.status = "cancelled"
                job.stage = "cancelled"
                job.finished = now_utc_iso()
                save_job(conn, job)
            return
        job.status = "failed"
        job.error = str(e)
        job.finished = now_utc_iso()
        save_job(conn, job)
        if cfg.get("notify", True):
            desktop_notify("NLS Video Failed", f"{job.title}: {e}")
    finally:
        _stop_job_processes(job_id)
        conn.close()


# ----------------------------- Worker -----------------------------
def worker():
    """Simple foreground worker. Run in tmux or with & for background."""
    print("NLS Video worker started. Press Ctrl-C to stop.")
    while True:
        conn = get_db()
        pending = conn.execute(
            "SELECT id FROM jobs WHERE status IN ('pending') ORDER BY id LIMIT 1"
        ).fetchall()
        conn.close()

        if pending:
            job_id = pending[0][0]
            print(f"Processing job {job_id}...")
            process_one_job(job_id)
        else:
            time.sleep(3)


# ----------------------------- CLI -----------------------------
def cmd_add(args):
    conn = get_db()
    cfg = load_config()
    preset = args.preset or cfg.get("default_preset", "balanced-4k")
    if preset not in DEFAULT_PRESETS:
        print(f"Unknown preset. Available: {list(DEFAULT_PRESETS.keys())}")
        return

    source_file = getattr(args, 'source_file', None)
    url = args.url or ""

    # Get title early
    title = args.title
    if not title and url:
        try:
            import yt_dlp
            with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
                info = ydl.extract_info(url, download=False)
                title = info.get("title", "Untitled")
        except Exception:
            title = "Untitled"
    elif not title and source_file:
        title = Path(source_file).stem

    now = now_utc_iso()
    metadata = {}
    if getattr(args, 'gravity', False):
        metadata["gravity"] = True
    if getattr(args, 'interstellar_nonlinear', False):
        metadata["interstellar_nonlinear"] = True
        metadata["gravity"] = True  # implies gravity for noise prep

    job = Job(
        id=0,
        url=url,
        title=title,
        preset=preset,
        status="pending",
        progress=0,
        stage="queued",
        output_path=None,
        log_path="",
        metadata=metadata,
        created=now,
        source_file=source_file,
    )
    conn.execute("""
        INSERT INTO jobs (url, title, preset, status, progress, stage, created, metadata, source_file)
        VALUES (?,?,?,?,?,?,?,?,?)
    """, (job.url, job.title, job.preset, job.status, job.progress, job.stage, job.created, json.dumps(job.metadata), job.source_file))
    job.id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()

    print(f"Added job #{job.id}: {job.title} ({preset})")
    if source_file:
        print(f"  (convert-only from {source_file})")
    if metadata.get("gravity"):
        print("  (gravity / Noise Protocol prep enabled - raw stream for secure transport)")
    print("Run `nls-video worker` (or in background) to process.")


def cmd_list(args):
    conn = get_db()
    jobs = list_jobs(conn, args.status)
    conn.close()

    if RICH_AVAILABLE:
        table = Table(title="NLS Video Jobs")
        table.add_column("ID", style="cyan")
        table.add_column("Title")
        table.add_column("Status", style="magenta")
        table.add_column("Progress")
        table.add_column("Preset")
        for j in jobs:
            table.add_row(str(j.id), j.title[:50], j.status, f"{j.progress:.1f}%", j.preset)
        Console().print(table)
    else:
        print(f"{'ID':<5} {'Title':<40} {'Status':<12} {'%':>6} Preset")
        for j in jobs:
            print(f"{j.id:<5} {j.title[:40]:<40} {j.status:<12} {j.progress:>5.1f}% {j.preset}")


def cmd_status(args):
    conn = get_db()
    job = load_job(conn, args.id)
    conn.close()
    if not job:
        print("Job not found")
        return
    print(json.dumps(job.to_dict(), indent=2, default=str))


def cmd_logs(args):
    conn = get_db()
    job = load_job(conn, args.id)
    conn.close()
    if not job or not job.log_path or not Path(job.log_path).exists():
        print("No log for this job (or still downloading)")
        return
    with open(job.log_path) as f:
        for line in f:
            print(line, end="")
            if args.follow:
                # naive follow (better to use tail -f in practice)
                pass


def cmd_cancel(args):
    result = api_cancel_job(args.id)
    if result.get("ok"):
        print(f"Job {args.id} cancelled.")
    else:
        print(result.get("error", "Job not cancelable or not found."))


def cmd_serve(args):
    """Web dashboard / full interface for NLS Visualist data + pipeline.
    Serves videos and thumbnails from the Visualist root under /visualist/
    for in-browser preview and playback (the "interface").
    """
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            cfg = load_config()
            vroot = Path(cfg.get("visualist_root", DEFAULT_VISUALIST_ROOT))

            if self.path == "/" or self.path == "/index.html":
                self.send_response(200)
                self.send_header("Content-Type", "text/html")
                self.end_headers()
                html = self._dashboard_html()
                self.wfile.write(html.encode())
            elif self.path == "/api/jobs":
                self._json_response(self._get_jobs())
            elif self.path == "/api/catalog":
                self._json_response(self._get_catalog())
            elif self.path.startswith("/visualist/"):
                rel = self.path[len("/visualist/"):]
                full = _safe_file_under(vroot, rel)
                if full and _serve_media_file(self, full):
                    return
                self.send_error(404)
            else:
                self.send_error(404)

        def _json_response(self, data):
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(json.dumps(data, default=str).encode())

        def _get_jobs(self):
            conn = get_db()
            jobs = [j.to_dict() for j in list_jobs(conn)]
            conn.close()
            return {"jobs": jobs, "catalog_path": str(CATALOG_PATH)}

        def _get_catalog(self):
            catalog = []
            if CATALOG_PATH.exists():
                try:
                    catalog = json.loads(CATALOG_PATH.read_text())
                except Exception:
                    catalog = []
            return {"catalog": catalog}

        def _dashboard_html(self):
            return """<!DOCTYPE html>
<html>
<head>
  <meta charset="utf-8">
  <title>NLS Visualist • Video Pipeline &amp; Media</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <style>
    body { background: #0a0a0a; color: #ddd; font-family: ui-monospace, monospace, system-ui; }
    .card { background:#111; border: 1px solid #222; }
    .nav-tab { padding: 0.5rem 1rem; cursor: pointer; border-bottom: 2px solid transparent; }
    .nav-tab.active { border-bottom-color: #10b981; color: #10b981; }
    .thumb { width:100%; height:120px; object-fit:cover; background:#222; }
    .asc-thumbnail { filter: contrast(1.15) saturate(0.85) sepia(0.15) hue-rotate(-8deg); /* ASC cinematic film look */ }
    .glitch {
      position: relative;
      display: inline-block;
    }
    .glitch::before, .glitch::after {
      content: attr(data-text);
      position: absolute;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
    }
    .glitch::before {
      left: 2px;
      text-shadow: -2px 0 #ff00ff;
      clip: rect(24px, 9999px, 86px, 0);
      animation: glitch-anim 1.5s infinite linear alternate-reverse;
    }
    .glitch::after {
      left: -2px;
      text-shadow: 2px 0 #00ffff;
      clip: rect(86px, 9999px, 140px, 0);
      animation: glitch-anim2 1.5s infinite linear alternate-reverse;
    }
    @keyframes glitch-anim {
      0% { clip: rect(24px, 9999px, 86px, 0); }
      20% { clip: rect(140px, 9999px, 86px, 0); }
      40% { clip: rect(24px, 9999px, 140px, 0); }
      60% { clip: rect(86px, 9999px, 24px, 0); }
      80% { clip: rect(140px, 9999px, 140px, 0); }
      100% { clip: rect(24px, 9999px, 86px, 0); }
    }
    @keyframes glitch-anim2 {
      0% { clip: rect(86px, 9999px, 140px, 0); }
      20% { clip: rect(24px, 9999px, 24px, 0); }
      40% { clip: rect(140px, 9999px, 86px, 0); }
      60% { clip: rect(86px, 9999px, 140px, 0); }
      80% { clip: rect(24px, 9999px, 24px, 0); }
      100% { clip: rect(86px, 9999px, 140px, 0); }
    }
    .visualist-banner {
      font-size: 0.9rem;
      opacity: 0.7;
      letter-spacing: 2px;
      text-transform: uppercase;
    }
    video { max-width:100%; max-height:320px; }
  </style>
</head>
<body class="p-6 font-sans">
  <div class="max-w-7xl mx-auto">
    <div class="flex items-center justify-between mb-4">
      <div>
        <h1 class="text-3xl font-bold glitch" data-text="NLS Visualist • Video Pipeline &amp; Media">NLS Visualist • Video Pipeline &amp; Media</h1>
        <p class="visualist-banner">1000 years old nonlinear h@k reality</p>
        <p class="text-sm opacity-70">yt-dlp + ffmpeg H.264 • Live jobs + your Visualist catalog • noiseprotocol gravity</p>
      </div>
      <div class="text-xs opacity-60">Rules: #1 no kill • #2 no eval</div>
    </div>

    <div class="flex gap-2 border-b border-neutral-800 mb-4 text-sm">
      <div onclick="showTab('jobs')" id="tab-jobs" class="nav-tab active">Pipeline Jobs</div>
      <div onclick="showTab('visualist')" id="tab-visualist" class="nav-tab">NLS Visualist Data</div>
    </div>

    <div id="tab-jobs-content">
      <div id="stats" class="grid grid-cols-2 md:grid-cols-4 gap-3 mb-4"></div>
      <div class="card rounded-xl p-4">
        <h2 class="font-semibold mb-3">Jobs (auto-refresh every 1.5s)</h2>
        <div id="jobs" class="space-y-3"></div>
      </div>
    </div>

    <div id="tab-visualist-content" class="hidden">
      <div class="card rounded-xl p-4">
        <h2 class="font-semibold mb-3">NLS Visualist Media Catalog</h2>
        <div id="catalog" class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 text-sm"></div>
        <div class="mt-3 text-xs opacity-60">Thumbnails generated automatically. Click Play to stream the H.264 in-browser.</div>
      </div>
    </div>
  </div>

  <script>
    let currentTab = 'jobs';
    function showTab(tab) {
      currentTab = tab;
      document.getElementById('tab-jobs-content').classList.toggle('hidden', tab !== 'jobs');
      document.getElementById('tab-visualist-content').classList.toggle('hidden', tab !== 'visualist');
      document.getElementById('tab-jobs').classList.toggle('active', tab === 'jobs');
      document.getElementById('tab-visualist').classList.toggle('active', tab === 'visualist');
      if (tab === 'visualist') refreshCatalog();
    }

    async function refreshJobs() {
      const res = await fetch('/api/jobs');
      const data = await res.json();
      const jobs = data.jobs || [];
      const active = jobs.filter(j => ['downloading','converting'].includes(j.status)).length;
      const done = jobs.filter(j => j.status === 'completed').length;
      document.getElementById('stats').innerHTML = `
        <div class="card p-3 rounded"><div class="text-xs opacity-60">Active</div><div class="text-2xl font-semibold">${active}</div></div>
        <div class="card p-3 rounded"><div class="text-xs opacity-60">Completed</div><div class="text-2xl font-semibold">${done}</div></div>
        <div class="card p-3 rounded"><div class="text-xs opacity-60">Total</div><div class="text-2xl font-semibold">${jobs.length}</div></div>
        <div class="card p-3 rounded text-xs">Catalog updated on completion</div>
      `;
      const c = document.getElementById('jobs'); c.innerHTML = '';
      jobs.forEach(j => {
        const pct = Math.max(0, Math.min(100, j.progress || 0));
        const d = document.createElement('div');
        d.className = 'card p-3 rounded';
        d.innerHTML = `
          <div class="flex justify-between">
            <div class="font-medium truncate">${j.title || j.url}</div>
            <div class="text-xs opacity-70">${j.preset}</div>
          </div>
          <div class="text-xs opacity-60">${j.status} • ${j.stage || ''}</div>
          <div class="h-2 bg-neutral-800 rounded mt-1 overflow-hidden"><div class="h-2 bg-emerald-500" style="width:${pct}%"></div></div>
          <div class="text-[10px] opacity-60 mt-0.5">${pct.toFixed(1)}% ${j.output_path ? '— ready in Visualist' : ''}</div>
        `;
        c.appendChild(d);
      });
    }

    async function refreshCatalog() {
      const res = await fetch('/api/catalog');
      const data = await res.json();
      const items = (data.catalog || []).slice().reverse();
      const c = document.getElementById('catalog'); c.innerHTML = '';
      if (items.length === 0) {
        c.innerHTML = '<div class="opacity-60">No items yet — completed jobs appear here automatically with thumbnails and metadata.</div>';
        return;
      }
      items.forEach(it => {
        const d = document.createElement('div');
        d.className = 'card rounded-xl overflow-hidden';
        const thumbClass = (it.gravity_prepared || it.raw_h264_stream) ? 'asc-thumbnail' : '';
        const t = it.thumbnail ? `<img src="/visualist/${it.thumbnail.split('/').pop()}" class="thumb ${thumbClass}">` : `<div class="thumb ${thumbClass} flex items-center justify-center text-xs opacity-50">ASC no thumb</div>`;
        const gravityBadge = (it.gravity_prepared || it.raw_h264_stream) ? `<span class="text-[10px] px-1 py-0.5 bg-purple-900 text-purple-300 rounded ml-1">GRAVITY / NOISEPROTOCOL</span>` : '';
        const smc = it.storage_memory_category || {};
        const storageInfo = smc.zone || smc.memory ? `Storage: zone=${smc.zone || ''} mem=${smc.memory || ''} loc=${smc.location || ''} V=${smc.V || ''} BW=${smc.Bandwidth || ''}` : '';
        d.innerHTML = `
          <div>${t}</div>
          <div class="p-3">
            <div class="font-medium truncate">${it.title || 'Untitled'} ${gravityBadge}</div>
            <div class="text-xs opacity-70 mt-1">
              ${it.technical && it.technical.duration ? Math.round(it.technical.duration)+'s' : ''}
              ${it.source_url ? '• ' + it.source_url.split('v=')[1] || '' : ''}
              ${storageInfo ? '<br>' + storageInfo : ''}
            </div>
            <div class="mt-2 flex gap-2 text-xs">
              ${it.output_path ? `<a href="/visualist/${encodeURIComponent(it.output_path.split('/').pop())}" target="_blank" class="px-2 py-px bg-neutral-800 rounded hover:bg-neutral-700">Play</a>` : ''}
              ${it.output_path ? `<a href="/visualist/${encodeURIComponent(it.output_path.split('/').pop().replace(/\\.mp4$/,'.nlsvis.json'))}" target="_blank" class="px-2 py-px bg-neutral-800 rounded hover:bg-neutral-700">JSON</a>` : ''}
              ${it.raw_h264_stream ? `<a href="/visualist/${encodeURIComponent(it.raw_h264_stream.split('/').pop())}" target="_blank" class="px-2 py-px bg-purple-800 rounded hover:bg-purple-700">Gravity Stream</a>` : ''}
            </div>
          </div>
        `;
        c.appendChild(d);
      });
    }

    function start() {
      setInterval(() => {
        if (currentTab === 'jobs') refreshJobs();
        if (currentTab === 'visualist') refreshCatalog();
      }, 1500);
      refreshJobs();
    }
    let currentTab = 'jobs';
    window.showTab = showTab;
    start();
  </script>
</body>
</html>"""

    import mimetypes  # ensure

    port = args.port
    print(f"Starting enhanced NLS Visualist interface on http://localhost:{port} (jobs + media gallery)")
    try:
        subprocess.run(["xdg-open", f"http://localhost:{port}"], check=False)
    except Exception:
        pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    server.serve_forever()


# ----------------------------- Gravity Serve (browser UI) -----------------------------

class RuntimeJsonLogger:
    """Append-only JSONL runtime log for gravity-serve / gravity-desktop parity."""

    def __init__(self, source: str, session_meta: Optional[Dict[str, Any]] = None):
        self.source = source
        self.started = time.time()
        self._lock = threading.Lock()
        RUNTIME_LOG_DIR.mkdir(parents=True, exist_ok=True)
        self.live_path = RUNTIME_LOG_DIR / f"{source}-live.jsonl"
        self.session_path = RUNTIME_LOG_DIR / f"{source}-session.json"
        meta = {
            "source": source,
            "pid": os.getpid(),
            "started_at": now_utc_iso(),
            "live_log": str(self.live_path),
        }
        if session_meta:
            meta.update(session_meta)
        self._write_session(meta)

    @staticmethod
    def enabled() -> bool:
        return os.environ.get("GRAVITY_RUNTIME_LOG", "1").lower() not in ("0", "false", "no", "off")

    def runtime_ms(self) -> int:
        return int((time.time() - self.started) * 1000)

    def _write_session(self, data: Dict[str, Any]) -> None:
        if not self.enabled():
            return
        try:
            self.session_path.write_text(json.dumps(data, indent=2))
        except Exception:
            pass

    def append(self, event: str, payload: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled():
            return
        row = {
            "ts": now_utc_iso(),
            "runtime_ms": self.runtime_ms(),
            "source": self.source,
            "event": event,
        }
        if payload:
            row.update(payload)
        line = json.dumps(row, default=str) + "\n"
        with self._lock:
            try:
                with self.live_path.open("a", encoding="utf-8") as f:
                    f.write(line)
            except Exception:
                pass

    def tail(self, n: int = 20) -> List[Dict[str, Any]]:
        if not self.live_path.is_file():
            return []
        try:
            lines = self.live_path.read_text(encoding="utf-8").splitlines()
            out: List[Dict[str, Any]] = []
            for ln in lines[-n:]:
                try:
                    out.append(json.loads(ln))
                except Exception:
                    pass
            return out
        except Exception:
            return []


class GravityBridge:
    """Background TCP client for gravity-server; caches latest gravity_update for HTTP."""

    def __init__(self, host: str = "127.0.0.1", port: int = 4242, logger: Optional[RuntimeJsonLogger] = None):
        self.host = host
        self.port = port
        self.logger = logger
        self._lock = threading.Lock()
        self._was_connected = False
        self.latest: Dict[str, Any] = {
            "type": "gravity_update",
            "jobs": [],
            "catalog": [],
            "connected": False,
            "timestamp": None,
            "error": None,
        }

    def snapshot(self) -> Dict[str, Any]:
        with self._lock:
            return dict(self.latest)

    def _set(self, **kwargs) -> None:
        with self._lock:
            self.latest.update(kwargs)
        self._maybe_log(kwargs)

    def _maybe_log(self, kwargs: Dict[str, Any]) -> None:
        if not self.logger:
            return
        connected = kwargs.get("connected", self.latest.get("connected"))
        if "connected" in kwargs and connected != self._was_connected:
            self._was_connected = bool(connected)
            self.logger.append(
                "gravity_connected" if connected else "gravity_disconnected",
                {"connected": connected, "error": kwargs.get("error")},
            )
        if kwargs.get("type") == "gravity_update" or "jobs" in kwargs:
            jobs = kwargs.get("jobs", self.latest.get("jobs", []))
            catalog = kwargs.get("catalog", self.latest.get("catalog", []))
            self.logger.append(
                "gravity_update",
                {
                    "connected": bool(connected),
                    "jobs_count": len(jobs) if isinstance(jobs, list) else 0,
                    "catalog_count": len(catalog) if isinstance(catalog, list) else 0,
                    "timestamp": kwargs.get("timestamp"),
                    "update": {
                        "type": "gravity_update",
                        "jobs": jobs,
                        "catalog": catalog,
                        "timestamp": kwargs.get("timestamp"),
                        "connected": bool(connected),
                    },
                },
            )

    def _load_fallback(self) -> None:
        conn = get_db()
        jobs = [j.to_dict() for j in list_jobs(conn)]
        conn.close()
        catalog: List[Dict[str, Any]] = []
        if CATALOG_PATH.exists():
            try:
                catalog = json.loads(CATALOG_PATH.read_text())
            except Exception:
                catalog = []
        self._set(
            type="gravity_update",
            jobs=jobs,
            catalog=catalog,
            timestamp=now_utc_iso(),
        )

    def run_forever(self) -> None:
        while True:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(8.0)
                s.connect((self.host, self.port))
                s.settimeout(None)
                s.recv(10)  # prologue GRAVITY\x00\x01
                s.send(b"\x42" * 32)
                s.recv(32)
                s.send(b"\x43" * 48)
                buf = b""
                self._set(connected=True, error=None)
                while True:
                    chunk = s.recv(4096)
                    if not chunk:
                        break
                    buf += chunk
                    while b"\n" in buf:
                        line, buf = buf.split(b"\n", 1)
                        if not line.strip():
                            continue
                        try:
                            update = json.loads(line.decode("utf-8"))
                            update["connected"] = True
                            update["error"] = None
                            self._set(**update)
                        except Exception:
                            pass
            except Exception as e:
                self._load_fallback()
                self._set(connected=False, error=str(e))
                time.sleep(3.0)


def _media_content_type(path: Path) -> str:
    lower = str(path).lower()
    if lower.endswith(".mp4"):
        return "video/mp4"
    if lower.endswith(".webm"):
        return "video/webm"
    if lower.endswith(".gif"):
        return "image/gif"
    if lower.endswith((".jpg", ".jpeg")):
        return "image/jpeg"
    if lower.endswith(".h264"):
        return "video/mp4"  # elementary stream — not browser-playable; label only
    return mimetypes.guess_type(str(path))[0] or "application/octet-stream"


def _serve_media_file(handler: BaseHTTPRequestHandler, full: Path, head_only: bool = False) -> bool:
    """Serve media with HTTP Range support (required for in-browser MP4 playback)."""
    if not full.is_file():
        return False
    head_only = head_only or getattr(handler, "_head_request", False)
    ctype = _media_content_type(full)
    size = full.stat().st_size
    range_header = handler.headers.get("Range")
    if range_header and not head_only:
        m = re.match(r"bytes=(\d+)-(\d*)", range_header.strip())
        if m:
            start = int(m.group(1))
            end = int(m.group(2)) if m.group(2) else size - 1
            end = min(end, size - 1)
            if start >= size or start > end:
                handler.send_response(416)
                handler.send_header("Content-Range", f"bytes */{size}")
                handler.end_headers()
                return True
            length = end - start + 1
            handler.send_response(206)
            handler.send_header("Content-Type", ctype)
            handler.send_header("Content-Length", str(length))
            handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
            handler.send_header("Accept-Ranges", "bytes")
            handler.end_headers()
            with open(full, "rb") as f:
                f.seek(start)
                handler.wfile.write(f.read(length))
            return True
    handler.send_response(200)
    handler.send_header("Content-Type", ctype)
    handler.send_header("Content-Length", str(size))
    handler.send_header("Accept-Ranges", "bytes")
    handler.end_headers()
    if head_only:
        return True
    with open(full, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            handler.wfile.write(chunk)
    return True


def _safe_file_under(base: Path, name: str) -> Optional[Path]:
    if not name:
        return None
    name = unquote(name.split("?", 1)[0], encoding="utf-8", errors="strict")
    if ".." in name or name.startswith("/"):
        return None
    full = (base / name).resolve()
    try:
        full.relative_to(base.resolve())
    except ValueError:
        return None
    return full if full.is_file() else None


def _enrich_visualist_item(item: Dict[str, Any], vroot: Path) -> Dict[str, Any]:
    """Add browser-friendly play/thumb names for ASC FILMIC / GRAVITY catalog cards."""
    out = dict(item)
    op = item.get("output_path") or ""
    if op:
        p = Path(op)
        out["play_name"] = p.name
        thumb_path = item.get("thumbnail")
        if thumb_path:
            out["thumb_name"] = Path(thumb_path).name
        else:
            for cand in (p.with_suffix(".thumb.jpg"), Path(str(p) + ".thumb.jpg")):
                if cand.is_file():
                    out["thumb_name"] = cand.name
                    break
            else:
                out["thumb_name"] = None
    grav = bool(item.get("gravity_prepared") or item.get("raw_h264_stream"))
    out["asc_mode"] = "GRAVITY" if grav else "FILMIC"
    out["playable"] = bool(op and Path(op).suffix.lower() in (".mp4", ".webm", ".gif"))
    if item.get("raw_h264_stream"):
        out["h264_stream_name"] = Path(item["raw_h264_stream"]).name
    return out


def _enrich_gravity_snapshot(snap: Dict[str, Any]) -> Dict[str, Any]:
    cfg = load_config()
    vroot = Path(cfg.get("visualist_root", DEFAULT_VISUALIST_ROOT))
    out = dict(snap)
    catalog = snap.get("catalog") or []
    if isinstance(catalog, list):
        out["catalog"] = [_enrich_visualist_item(it, vroot) for it in catalog]
    bridge_jobs = snap.get("jobs") or []
    bridge_by_id: Dict[int, Dict[str, Any]] = {}
    if isinstance(bridge_jobs, list):
        for j in bridge_jobs:
            if not isinstance(j, dict):
                continue
            try:
                bridge_by_id[int(j.get("id"))] = j
            except (TypeError, ValueError):
                continue
    conn = get_db()
    fresh = {j.id: j.to_dict() for j in list_jobs(conn)}
    conn.close()
    merged: List[Dict[str, Any]] = []
    for jid in sorted(fresh.keys(), reverse=True):
        db_job = fresh[jid]
        if jid in bridge_by_id:
            merged.append({**bridge_by_id[jid], **db_job})
        else:
            merged.append(db_job)
    out["jobs"] = merged
    return out


def _recent_downloads_list(limit: int = 25) -> List[Dict[str, Any]]:
    patterns = (
        re.compile(r"^direct-h264-.+\.mp4$"),
        re.compile(r"^direct-gif-.+\.gif$"),
        re.compile(r"^direct-h264-rot\d+-.+\.mp4$"),
    )
    items: List[Dict[str, Any]] = []
    if not DOWNLOADS_DIR.is_dir():
        return items
    files = [f for f in DOWNLOADS_DIR.iterdir() if f.is_file() and any(p.match(f.name) for p in patterns)]
    files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    for f in files[:limit]:
        entry: Dict[str, Any] = {
            "name": f.name,
            "path": str(f),
            "modified": datetime.utcfromtimestamp(f.stat().st_mtime).isoformat(),
        }
        sidecar = Path(str(f) + ".interlaterus.json")
        if sidecar.is_file():
            try:
                sc = json.loads(sidecar.read_text())
                entry["pattern_code"] = sc.get("pattern_code")
                entry["vertex"] = sc.get("vertex")
            except Exception:
                pass
        items.append(entry)
    return items


def _interlaterus_catalog() -> List[Dict[str, Any]]:
    if not INTERLATERUS_CATALOG.is_file():
        return []
    try:
        data = json.loads(INTERLATERUS_CATALOG.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _load_visualist_catalog() -> List[Dict[str, Any]]:
    if not CATALOG_PATH.is_file():
        return []
    try:
        data = json.loads(CATALOG_PATH.read_text())
        return data if isinstance(data, list) else []
    except Exception:
        return []


def _vertex_key(vertex: Any) -> str:
    if isinstance(vertex, (list, tuple)) and len(vertex) == 4:
        return ",".join(str(int(v)) for v in vertex)
    return ""


def _blockcode_positions() -> Dict[str, Dict[str, Any]]:
    """Authoritative POS vertex map keyed by sha256."""
    if not BLOCKCODE_DB.is_file():
        return {}
    out: Dict[str, Dict[str, Any]] = {}
    try:
        conn = sqlite3.connect(BLOCKCODE_DB)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT pattern_code, vertex_x, vertex_y, vertex_z, vertex_t, "
            "media_path, source_url, sha256, created_at FROM blockcode_nft_records"
        ).fetchall()
        conn.close()
        for r in rows:
            sha = (r["sha256"] or "").strip()
            if not sha:
                continue
            out[sha] = {
                "pattern_code": r["pattern_code"],
                "vertex": [r["vertex_x"], r["vertex_y"], r["vertex_z"], r["vertex_t"]],
                "media_path": r["media_path"],
                "source_url": r["source_url"],
                "minted_at": r["created_at"],
            }
    except Exception:
        pass
    return out


def _visualist_by_basename() -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for item in _load_visualist_catalog():
        op = item.get("output_path") or ""
        if not op:
            continue
        out[Path(op).name] = item
    return out


def _avd_entries() -> List[Dict[str, Any]]:
    """Analog Video Data (ASC filmic side) from ~/Downloads direct files."""
    entries: List[Dict[str, Any]] = []
    for item in _recent_downloads_list(limit=100):
        path = Path(item.get("path") or "")
        avd: Dict[str, Any] = {
            "path": str(path),
            "name": item.get("name"),
            "asc_mode": "FILMIC",
            "modified": item.get("modified"),
            "pattern_code": item.get("pattern_code"),
            "vertex": item.get("vertex"),
        }
        sidecar = Path(str(path) + ".interlaterus.json")
        if sidecar.is_file():
            try:
                sc = json.loads(sidecar.read_text())
                avd["sha256"] = (sc.get("probe") or {}).get("sha256") or sc.get("sha256")
                avd["pattern_code"] = avd.get("pattern_code") or sc.get("pattern_code")
                avd["vertex"] = avd.get("vertex") or sc.get("vertex")
            except Exception:
                pass
        entries.append(avd)
    return entries


def pos_reconcile(write: bool = True) -> Dict[str, Any]:
    """Merge AVD + POS across blockcode DB, interlaterus, visualist, Downloads."""
    blockcode = _blockcode_positions()
    interlaterus = {((it.get("sha256") or "").strip()): it for it in _interlaterus_catalog() if it.get("sha256")}
    visualist_names = _visualist_by_basename()
    avd_list = _avd_entries()

    by_id: Dict[str, Dict[str, Any]] = {}

    def ensure_entry(eid: str) -> Dict[str, Any]:
        if eid not in by_id:
            by_id[eid] = {"id": eid, "avd": None, "pos": None, "synced_at": now_utc_iso()}
        return by_id[eid]

    for sha, pos in blockcode.items():
        ent = ensure_entry(sha)
        mint = interlaterus.get(sha, {})
        smc = {}
        media_name = Path(pos.get("media_path") or "").name
        vis = visualist_names.get(media_name)
        if vis:
            smc = vis.get("storage_memory_category") or {}
        elif mint:
            title = (mint.get("title") or "").lower()
            is_inter = "interstellar" in title or "nonlineari" in title
            smc = {
                "zone": "interstellar-zone-alpha" if is_inter else "default-zone",
                "memory": "16GB" if is_inter else "8GB",
                "location": "nls-visualist-dc-1" if is_inter else "local-dc",
                "V": "vp56-vol-1999" if is_inter else "h264-vol",
                "Bandwidth": "10Gbps" if is_inter else "1Gbps",
            }
        ent["pos"] = {
            "vertex": pos["vertex"],
            "pattern_code": pos["pattern_code"],
            "storage_memory_category": smc,
            "media_path": pos.get("media_path"),
            "source_url": pos.get("source_url"),
            "minted_at": pos.get("minted_at"),
        }
        if media_name and Path(pos.get("media_path") or "").is_file():
            ent["avd"] = {
                "path": pos["media_path"],
                "name": media_name,
                "asc_mode": "GRAVITY" if vis and (vis.get("gravity_prepared") or vis.get("raw_h264_stream")) else "FILMIC",
                "sha256": sha,
            }

    for avd in avd_list:
        sha = (avd.get("sha256") or "").strip()
        eid = sha or f"avd:{avd.get('name') or 'unknown'}"
        ent = ensure_entry(eid)
        if ent.get("avd") is None:
            ent["avd"] = {k: v for k, v in avd.items() if k != "sha256"}
            if sha:
                ent["avd"]["sha256"] = sha
        if sha and sha in blockcode and ent.get("pos") is None:
            pos = blockcode[sha]
            ent["pos"] = {
                "vertex": pos["vertex"],
                "pattern_code": pos["pattern_code"],
                "storage_memory_category": {},
                "media_path": pos.get("media_path"),
            }

    for name, vis in visualist_names.items():
        eid = f"vis:{name}"
        if any((e.get("avd") or {}).get("name") == name or Path((e.get("pos") or {}).get("media_path") or "").name == name for e in by_id.values()):
            continue
        ent = ensure_entry(eid)
        ent["pos"] = {
            "vertex": None,
            "pattern_code": None,
            "storage_memory_category": vis.get("storage_memory_category") or {},
            "media_path": vis.get("output_path"),
            "visualist_only": True,
        }
        ent["avd"] = {
            "path": vis.get("output_path"),
            "name": name,
            "asc_mode": "GRAVITY" if vis.get("gravity_prepared") or vis.get("raw_h264_stream") else "FILMIC",
            "title": vis.get("title"),
        }

    entries = sorted(by_id.values(), key=lambda e: e.get("id", ""))
    orphans_avd = [e["id"] for e in entries if e.get("avd") and not e.get("pos")]
    orphans_pos = [e["id"] for e in entries if e.get("pos") and not e.get("avd")]
    paired = [e["id"] for e in entries if e.get("avd") and e.get("pos")]

    vertex_hist: Dict[str, int] = {}
    zone_hist: Dict[str, int] = {}
    for e in entries:
        v = e.get("pos") or {}
        vk = _vertex_key(v.get("vertex"))
        if vk:
            vertex_hist[vk] = vertex_hist.get(vk, 0) + 1
        zone = (v.get("storage_memory_category") or {}).get("zone")
        if zone:
            zone_hist[zone] = zone_hist.get(zone, 0) + 1

    payload = {
        "entries": entries,
        "summary": {
            "total": len(entries),
            "paired_avd_pos": len(paired),
            "orphans_avd_only": len(orphans_avd),
            "orphans_pos_only": len(orphans_pos),
            "vertices_occupied": len(vertex_hist),
            "vertex_histogram": vertex_hist,
            "zone_histogram": zone_hist,
        },
        "orphans": {
            "avd_only": orphans_avd[:50],
            "pos_only": orphans_pos[:50],
        },
    }

    if write:
        XDG_DATA.mkdir(parents=True, exist_ok=True)
        POSITION_INDEX_PATH.write_text(json.dumps(payload, indent=2, default=str))
        build_proof_of_spatio(payload)

    return payload


def build_proof_of_spatio(index: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Proof of Spatio (aka POS) — verifiable digest over position index."""
    if index is None:
        if POSITION_INDEX_PATH.is_file():
            try:
                index = json.loads(POSITION_INDEX_PATH.read_text())
            except Exception:
                index = pos_reconcile(write=True)
        else:
            index = pos_reconcile(write=True)

    entries = index.get("entries") or []
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"), default=str)
    digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    proof = {
        "proof_type": "proof_of_spatio",
        "aka": "POS",
        "generated_at": now_utc_iso(),
        "position_index": str(POSITION_INDEX_PATH),
        "summary": index.get("summary") or {},
        "orphans": index.get("orphans") or {},
        "entry_count": len(entries),
        "proof_digest": digest,
        "tesseract_capacity": 16,
    }
    XDG_DATA.mkdir(parents=True, exist_ok=True)
    PROOF_OF_SPATIO_PATH.write_text(json.dumps(proof, indent=2, default=str))
    return proof


def api_positioning(rebuild: bool = False) -> Dict[str, Any]:
    if rebuild or not POSITION_INDEX_PATH.is_file():
        index = pos_reconcile(write=True)
    else:
        try:
            index = json.loads(POSITION_INDEX_PATH.read_text())
        except Exception:
            index = pos_reconcile(write=True)
    proof = build_proof_of_spatio(index)
    return {
        "ok": True,
        "aka": "POS",
        "proof_type": "proof_of_spatio",
        "position_index": str(POSITION_INDEX_PATH),
        "proof_path": str(PROOF_OF_SPATIO_PATH),
        "summary": index.get("summary") or {},
        "orphans": index.get("orphans") or {},
        "entries": index.get("entries") or [],
        "proof_digest": proof.get("proof_digest"),
        "generated_at": proof.get("generated_at"),
    }


def cmd_spatio(args):
    if args.rebuild or not PROOF_OF_SPATIO_PATH.is_file():
        api_positioning(rebuild=True)
    proof = json.loads(PROOF_OF_SPATIO_PATH.read_text())
    if args.json:
        print(json.dumps(proof, indent=2))
        return
    print("Proof of Spatio (aka POS)")
    print(f"  digest: {proof.get('proof_digest')}")
    print(f"  entries: {proof.get('entry_count')}")
    s = proof.get("summary") or {}
    print(f"  paired AVD↔POS: {s.get('paired_avd_pos', 0)}")
    print(f"  orphans AVD-only: {s.get('orphans_avd_only', 0)}")
    print(f"  orphans POS-only: {s.get('orphans_pos_only', 0)}")
    print(f"  vertices occupied: {s.get('vertices_occupied', 0)}/16")
    print(f"  proof file: {PROOF_OF_SPATIO_PATH}")
    print(f"  index file: {POSITION_INDEX_PATH}")


def cmd_running_status(args):
    if args.json:
        print(json.dumps(api_running(), indent=2))
        return
    r = read_gravity_serve_running()
    if not r.get("running"):
        print("No gravity-serve running version on disk.")
        print(f"  mm notify: {MM_NOTIFY_PATH}")
        return
    live = api_running()
    print("gravity-serve running version (for mm)")
    print(f"  {r.get('for_mm')}")
    print(f"  live pid:  {live.get('live_pid')}")
    print(f"  file:      {GRAVITY_SERVE_RUNNING_PATH}")
    print(f"  mm notify: {MM_NOTIFY_PATH}")
    print(f"  poll:      {r.get('api_running')}")


def cmd_gravity_serve_archive(args):
    from archive_gravity_serve import archive_gravity_serve

    dest = Path(args.dest).expanduser() if args.dest else None
    result = archive_gravity_serve(dest, log_tail_lines=args.log_tail)
    running = read_gravity_serve_running()
    if running.get("running") and running.get("pid"):
        write_gravity_serve_running(
            pid=int(running["pid"]),
            http_port=int(running.get("http_port") or 8766),
            gravity_host=(running.get("gravity_bridge") or {}).get("host", "127.0.0.1"),
            gravity_port=int((running.get("gravity_bridge") or {}).get("port") or 4242),
            archive_dir=result.get("archive_dir"),
            event="archived",
        )
    if args.json:
        print(json.dumps(result, indent=2))
        return
    print("gravity-serve archived — live server kept running")
    print(f"  dir:   {result.get('archive_dir')}")
    print(f"  proof: {result.get('proof_digest')}")
    proc = result.get("live_server") or {}
    if proc.get("pid"):
        print(f"  pid:   {proc['pid']} (still running)")


def cmd_aoa_delta(args):
    from aoa_delta_compose import compose_aoa_delta, DEG_PER_SLICE, SLICES_PER_360

    report_dir = Path(args.report_dir).expanduser() if args.report_dir else None
    result = compose_aoa_delta(report_dir, write=not args.no_write)
    if args.json:
        print(json.dumps(result, indent=2))
        return
    if not result.get("ok"):
        print(result.get("error", "AOA delta compose failed"))
        return
    print("AOA | NLS Visualist — LIFO delta program")
    print(f"  {SLICES_PER_360} angular slices × {DEG_PER_SLICE}° = 360° + slice 0 axiom")
    print(f"  LIFO pop: {' → '.join(str(x) for x in result['lifo_pop_order'])}")
    print(f"  composite: {result.get('composite_sha256')}")
    print(f"  proof:     {result.get('proof_digest')}")
    if result.get("written"):
        print(f"  delta:     {result['written']}")


def write_gravity_serve_running(
    *,
    pid: int,
    http_port: int,
    gravity_host: str,
    gravity_port: int,
    archive_dir: Optional[str] = None,
    event: str = "started",
) -> Dict[str, Any]:
    """Persist live running version — mm polls this file or GET /api/running."""
    manifest = load_version_manifest()
    url = f"http://127.0.0.1:{http_port}/"
    archive_latest = str(ARCHIVE_LATEST_LINK.resolve()) if ARCHIVE_LATEST_LINK.is_symlink() else None
    payload: Dict[str, Any] = {
        "ok": True,
        "running": True,
        "event": event,
        "updated_at_utc": now_utc_iso(),
        "time_axiom": TIME_AXIOM,
        "pid": pid,
        "version": manifest.get("version", __version__),
        "tag": manifest.get("tag", f"v{__version__}"),
        "released": manifest.get("released"),
        "url": url,
        "api_running": f"{url}api/running",
        "api_version": f"{url}api/version",
        "app_root": str(_SCRIPT_DIR),
        "http_port": http_port,
        "gravity_bridge": {"host": gravity_host, "port": gravity_port},
        "archive_latest": archive_latest,
        "last_archive_dir": archive_dir,
        "for_mm": (
            f"gravity-serve {manifest.get('tag', 'v' + __version__)} running on :{http_port} "
            f"(pid {pid}) — poll {url}api/running"
        ),
    }
    XDG_DATA.mkdir(parents=True, exist_ok=True)
    GRAVITY_SERVE_RUNNING_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    MM_NOTIFY_PATH.write_text(
        json.dumps(
            {
                "to": "mm",
                "subject": "gravity-serve running",
                "message": payload["for_mm"],
                "at_utc": payload["updated_at_utc"],
                "running_version": payload,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    return payload


def read_gravity_serve_running() -> Dict[str, Any]:
    if GRAVITY_SERVE_RUNNING_PATH.is_file():
        try:
            return json.loads(GRAVITY_SERVE_RUNNING_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"ok": False, "running": False, "error": "No running version file"}


def api_running(bridge_snapshot: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    base = read_gravity_serve_running()
    if not base.get("running"):
        return {**base, "ok": False, "live_pid": None}
    pid = base.get("pid")
    live = False
    if pid:
        try:
            os.kill(int(pid), 0)
            live = True
        except (OSError, ValueError, TypeError):
            live = False
    out = dict(base)
    out["live_pid"] = live
    out["checked_at_utc"] = now_utc_iso()
    if bridge_snapshot is not None:
        out["gravity_connected"] = bool(bridge_snapshot.get("connected"))
        out["jobs_count"] = len(bridge_snapshot.get("jobs") or [])
    return out


def api_version() -> Dict[str, Any]:
    manifest = load_version_manifest()
    running = read_gravity_serve_running()
    return {
        "ok": True,
        "name": manifest.get("name", APP_NAME),
        "version": manifest.get("version", __version__),
        "tag": manifest.get("tag", f"v{__version__}"),
        "released": manifest.get("released"),
        "components": manifest.get("components", {}),
        "running": bool(running.get("running") and running.get("pid")),
        "running_pid": running.get("pid"),
        "running_url": running.get("url"),
    }


def api_cancel_job(job_id: int) -> Dict[str, Any]:
    conn = get_db()
    job = load_job(conn, int(job_id))
    if job and job.status in ("pending", "downloading", "converting"):
        job.status = "cancelled"
        job.stage = "cancelled"
        job.finished = now_utc_iso()
        save_job(conn, job)
        conn.close()
        _stop_job_processes(int(job_id))
        return {"ok": True, "job_id": job_id, "status": "cancelled"}
    conn.close()
    return {"ok": False, "error": "Job not cancelable or not found", "job_id": job_id}


def api_direct_download(url: str, gif: bool = False, mint: bool = True) -> Dict[str, Any]:
    """Mirror GravityDesktop direct yt-dlp → ~/Downloads/direct-h264-*.mp4."""
    if not url or not url.strip():
        return {"ok": False, "error": "URL required"}
    url = url.strip()

    with _direct_dl_lock:
        if _direct_dl_state.get("status") == "downloading":
            return {"ok": False, "error": "Another direct download is already running"}

    _direct_dl_set(
        status="downloading",
        progress=0.0,
        message="Starting yt-dlp direct to ~/Downloads/...",
        error=None,
        url=url,
        path=None,
    )

    def _worker() -> None:
        outtmpl = str(
            DOWNLOADS_DIR / ("direct-gif-%(id)s.gif" if gif else "direct-h264-%(id)s.mp4")
        )
        fmt = YTDLP_GIF_FORMAT if gif else YTDLP_H264_FORMAT
        use_private = os.environ.get("GRAVITY_USE_COOKIES", "1") != "0"

        def on_line(line: str) -> None:
            pct = _parse_ytdlp_progress(line)
            if pct is not None:
                _direct_dl_set(progress=pct, message=f"Downloading… {pct:.0f}%")
            elif line.strip():
                _direct_dl_set(message=line.strip()[:120])

        try:
            ensure_js_runtime(interactive=False)
            _direct_dl_set(message="Checking formats (yt-dlp --list-formats)...")
            list_args = _build_ytdlp_cli_base(url, use_private) + ["--list-formats", url]
            list_result = _run_ytdlp_cli(list_args)
            if list_result["exit_code"] != 0 and _output_indicates_403(list_result["lines"]):
                GravityRateLimiter.on_403()

            _direct_dl_set(message="Downloading…")
            dl_args = _build_ytdlp_cli_base(url, use_private)
            dl_args += ["-f", fmt, "--merge-output-format", "gif" if gif else "mp4", "--newline", "-o", outtmpl, url]

            max_retries = int(os.environ.get("GRAVITY_403_RETRIES", "2"))
            attempt = 0
            dl_result = _run_ytdlp_cli(dl_args, on_line=on_line)
            while (
                dl_result["exit_code"] != 0
                and _output_indicates_403(dl_result["lines"])
                and attempt < max_retries
            ):
                attempt += 1
                GravityRateLimiter.on_403()
                cool = GravityRateLimiter.cooldown_seconds_remaining()
                _direct_dl_set(
                    message=f"403/IP restricted — cooldown {cool}s, retry {attempt}/{max_retries}",
                    progress=0.0,
                )
                dl_result = _run_ytdlp_cli(dl_args, on_line=on_line)

            if dl_result["exit_code"] != 0:
                if _output_indicates_403(dl_result["lines"]):
                    GravityRateLimiter.on_403()
                    err = "HTTP 403 / IP restricted — try cookies (GRAVITY_COOKIES_BROWSER) or GRAVITY_PROXY"
                else:
                    err = dl_result["last_line"] or "yt-dlp failed"
                _direct_dl_set(status="error", error=err, message=err, progress=0.0)
                return

            GravityRateLimiter.on_success()
            import yt_dlp
            with yt_dlp.YoutubeDL({"quiet": True, **_ytdlp_api_extra_opts(use_private)}) as ydl:
                info = ydl.extract_info(url, download=False)
            path = Path(ydl.prepare_filename(info)) if info else None
            if path is None or not path.is_file():
                candidates = sorted(
                    DOWNLOADS_DIR.glob("direct-gif-*" if gif else "direct-h264-*"),
                    key=lambda p: p.stat().st_mtime,
                    reverse=True,
                )
                path = candidates[0] if candidates else None
            if path is None or not path.is_file():
                _direct_dl_set(status="error", error="Download finished but output file not found", progress=0.0)
                return

            title = (info or {}).get("title", path.stem)
            if mint and os.environ.get("INTERLATERUS_SKIP_MINT") != "1":
                script = Path(__file__).resolve().parent / "interlaterus_desktop.py"
                if script.is_file():
                    _direct_dl_set(message="Minting interlaterus blockcode…", progress=100.0)
                    subprocess.run(
                        ["python3", str(script), "mint", "--file", str(path), "--url", url, "--title", title],
                        capture_output=True,
                        text=True,
                    )

            _direct_dl_set(
                status="done",
                progress=100.0,
                message=f"✓ done → {path.name}",
                error=None,
                path=str(path),
            )
        except Exception as e:
            err = str(e)
            if _output_indicates_403([err]):
                err = "HTTP 403 / IP restricted — try cookies or GRAVITY_PROXY"
            _direct_dl_set(status="error", error=err, message=err, progress=0.0)
            print(f"direct download error: {e}", file=sys.stderr)

    threading.Thread(target=_worker, daemon=True).start()
    return {"ok": True, "mode": "direct", "gif": gif, "url": url, "target": str(DOWNLOADS_DIR)}


def api_add_job(url: str, preset: str = "balanced-4k", gravity: bool = False) -> Dict[str, Any]:
    if not url or not url.strip():
        return {"ok": False, "error": "URL required"}
    cfg = load_config()
    if preset not in DEFAULT_PRESETS:
        preset = cfg.get("default_preset", "balanced-4k")
    title = "Untitled"
    try:
        import yt_dlp
        with yt_dlp.YoutubeDL({"quiet": True}) as ydl:
            info = ydl.extract_info(url.strip(), download=False)
            title = info.get("title", "Untitled")
    except Exception:
        pass
    now = now_utc_iso()
    metadata: Dict[str, Any] = {}
    if gravity:
        metadata["gravity"] = True
    conn = get_db()
    conn.execute(
        """INSERT INTO jobs (url, title, preset, status, progress, stage, created, metadata, source_file)
           VALUES (?,?,?,?,?,?,?,?,?)""",
        (url.strip(), title, preset, "pending", 0, "queued", now, json.dumps(metadata), None),
    )
    job_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
    conn.commit()
    conn.close()
    return {"ok": True, "job_id": job_id, "title": title, "preset": preset}


def cmd_gravity_serve(args):
    """Browser Gravity client — HTML dashboard proxying gravity-server live updates.
    Serves jobs, visualist catalog, interlaterus mints, and ~/Downloads direct files.
    """
    runtime_logger = RuntimeJsonLogger(
        "gravity-serve",
        {
            "http_port": args.port,
            "gravity_host": args.gravity_host,
            "gravity_port": args.gravity_port,
        },
    )
    runtime_logger.append("session_start", {"http_port": args.port})
    bridge = GravityBridge(host=args.gravity_host, port=args.gravity_port, logger=runtime_logger)
    threading.Thread(target=bridge.run_forever, daemon=True).start()
    api_log_interval = float(os.environ.get("GRAVITY_API_LOG_INTERVAL_SEC", "60"))
    last_api_log: Dict[str, float] = {"gravity": 0.0, "downloads": 0.0}

    def _maybe_log_api(kind: str, payload: Dict[str, Any]) -> None:
        now = time.time()
        if now - last_api_log.get(kind, 0.0) < api_log_interval:
            return
        last_api_log[kind] = now
        runtime_logger.append(f"api_{kind}", payload)

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt, *log_args):
            return  # quiet

        def _api_path(self) -> str:
            """Normalize path for routing (strip query, trailing slash)."""
            return urlparse(self.path).path.rstrip("/") or "/"

        def _json(self, data: Any, code: int = 200) -> None:
            body = json.dumps(data, default=str).encode()
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _read_json_body(self) -> Dict[str, Any]:
            length = int(self.headers.get("Content-Length", 0))
            if length <= 0:
                return {}
            try:
                return json.loads(self.rfile.read(length).decode("utf-8"))
            except Exception:
                return {}

        def do_HEAD(self):
            self._head_request = True
            try:
                self.do_GET()
            finally:
                self._head_request = False

        def do_GET(self):
            cfg = load_config()
            vroot = Path(cfg.get("visualist_root", DEFAULT_VISUALIST_ROOT))

            path = self._api_path()
            if path in ("/", "/index.html", "/gravity"):
                html_path = GRAVITY_SERVE_HTML
                if not html_path.is_file():
                    self.send_error(404, "gravity_serve.html missing")
                    return
                body = html_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path in ("/plan", "/plan.html"):
                if not PLAN_HTML.is_file():
                    self.send_error(404, "plan.html missing")
                    return
                body = PLAN_HTML.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/plan.md" and PLAN_MD.is_file():
                body = PLAN_MD.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/plan.original.md" and PLAN_ORIGINAL_MD.is_file():
                body = PLAN_ORIGINAL_MD.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/markdown; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
            elif path == "/api/version":
                self._json(api_version())
            elif path == "/api/running":
                self._json(api_running(bridge.snapshot()))
            elif path == "/api/time":
                self._json(api_time())
            elif path == "/api/gravity":
                snap = _enrich_gravity_snapshot(bridge.snapshot())
                _maybe_log_api(
                    "gravity",
                    {
                        "connected": snap.get("connected"),
                        "jobs_count": len(snap.get("jobs") or []),
                        "catalog_count": len(snap.get("catalog") or []),
                    },
                )
                self._json(snap)
            elif path == "/api/interlaterus":
                self._json({"items": _interlaterus_catalog()})
            elif path == "/api/downloads":
                items = _recent_downloads_list()
                _maybe_log_api(
                    "downloads",
                    {
                        "items_count": len(items),
                        "sample": [i.get("name") for i in items[:3]],
                    },
                )
                self._json({"items": items})
            elif self.path == "/api/download/status":
                self._json(direct_download_status())
            elif self._api_path() in ("/api/positioning", "/api/spatio", "/api/spatio/proof"):
                qs = parse_qs(urlparse(self.path).query)
                rebuild = (qs.get("rebuild") or [""])[0].lower() in ("1", "true", "yes")
                self._json(api_positioning(rebuild=rebuild))
            elif self.path == "/api/logs":
                self._json({
                    "session": json.loads(runtime_logger.session_path.read_text())
                    if runtime_logger.session_path.is_file() else {},
                    "runtime_ms": runtime_logger.runtime_ms(),
                    "live_log": str(runtime_logger.live_path),
                    "tail": runtime_logger.tail(30),
                })
            elif self.path.startswith("/downloads/"):
                rel = self.path[len("/downloads/"):]
                full = _safe_file_under(DOWNLOADS_DIR, rel)
                if full and _serve_media_file(self, full):
                    return
                self.send_error(404)
            elif self.path.startswith("/visualist/"):
                rel = self.path[len("/visualist/"):]
                full = _safe_file_under(vroot, rel)
                if full and _serve_media_file(self, full):
                    return
                self.send_error(404)
            else:
                self.send_error(404)

        def do_POST(self):
            path = self._api_path()
            if path == "/api/add":
                data = self._read_json_body()
                result = api_add_job(
                    data.get("url", ""),
                    data.get("preset", "balanced-4k"),
                    bool(data.get("gravity")),
                )
                runtime_logger.append("api_add_job", result)
                self._json(result, 200 if result.get("ok") else 400)
            elif path == "/api/cancel":
                data = self._read_json_body()
                raw_id = data.get("id", data.get("job_id", 0))
                try:
                    job_id = int(raw_id)
                except (TypeError, ValueError):
                    job_id = 0
                result = api_cancel_job(job_id)
                runtime_logger.append("api_cancel_job", result)
                self._json(result, 200 if result.get("ok") else 400)
            elif path == "/api/download":
                data = self._read_json_body()
                result = api_direct_download(
                    data.get("url", ""),
                    bool(data.get("gif")),
                    data.get("mint", True) is not False,
                )
                runtime_logger.append("api_direct_download", result)
                self._json(result, 200 if result.get("ok") else 400)
            elif path == "/api/open-downloads":
                try:
                    dl = str(DOWNLOADS_DIR)
                    if sys.platform == "darwin":
                        subprocess.Popen(["open", dl])
                    else:
                        subprocess.Popen(["xdg-open", dl])
                    self._json({"ok": True})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, 500)
            else:
                self._json({"ok": False, "error": "Not found", "path": path}, 404)

    class ThreadingHTTPServer(socketserver.ThreadingMixIn, HTTPServer):
        daemon_threads = True

    port = args.port
    url = f"http://127.0.0.1:{port}/"
    running = write_gravity_serve_running(
        pid=os.getpid(),
        http_port=port,
        gravity_host=args.gravity_host,
        gravity_port=args.gravity_port,
        event="started",
    )
    print(f"Gravity Serve HTML on {url}")
    print(f"  Version {__version__} ({load_version_manifest().get('tag', 'v' + __version__)})")
    print(f"  Running version → {GRAVITY_SERVE_RUNNING_PATH}")
    print(f"  mm notify       → {MM_NOTIFY_PATH}")
    print(f"  Poll            → {running.get('api_running')}")
    print(f"  Bridge → gravity-server {args.gravity_host}:{args.gravity_port}")
    print("  Tabs: jobs • visualist • interlaterus mint • recent downloads • ASC live")
    print(f"  Runtime log: {runtime_logger.live_path}")
    print(f"  Verify: {Path(__file__).resolve().parent / 'verify-gravity-api.sh'}")
    try:
        subprocess.run(["xdg-open", url], check=False)
    except Exception:
        pass
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    server.serve_forever()


def cmd_catalog(args):
    """Catalog an existing video file into NLS Visualist data.
    Rule #1: no kill. Rule #2: no eval.
    This just registers metadata without touching running processes.
    """
    cfg = load_config()
    video = Path(args.file)
    if not video.exists():
        print("File not found:", video)
        return
    title = args.title or video.stem
    now = now_utc_iso()
    sidecar = video.with_suffix(".nlsvis.json")
    data = {
        "title": title,
        "source_url": args.source_url or "external/manual",
        "preset": "external",
        "output_path": str(video),
        "processed_at": now,
        "tags": ["h264", "external"],
    }
    try:
        out = subprocess.check_output(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration,size,bit_rate",
             "-of", "json", str(video)],
            text=True
        )
        info = json.loads(out)
        data["technical"] = info.get("format", {})
    except Exception:
        pass
    # Generate thumbnail for Visualist interface
    thumb = video.with_suffix(".thumb.jpg")
    if generate_thumbnail(video, thumb):
        data["thumbnail"] = str(thumb)

    if getattr(args, 'gravity', False):
        h264 = prepare_for_noise_gravity(video)
        data["gravity_prepared"] = True
        data["raw_h264_stream"] = str(h264)
        try:
            keygen_bin = "/home/nlsrecords/Downloads/SCIS/dist-newstyle/build/x86_64-linux/ghc-9.6.7/noiseprotocol-0.1.0.0/x/noiseprotocol-keygen/build/noiseprotocol-keygen/noiseprotocol-keygen"
            if os.path.exists(keygen_bin):
                key_out = subprocess.check_output([keygen_bin], text=True)
                data["noise_gravity_keys"] = key_out.strip()
        except Exception:
            pass

    if getattr(args, 'interstellar_nonlinear', False):
        data["interstellar_nonlinear"] = True
        data["vp56_gravity_prepared"] = True
        vp56 = prepare_interstellar_nonlinear_gravity(video)
        data["vp56_raw_stream"] = str(vp56)

    # Always add storage memory category with zone and memory|location|zone|V|Bandwidth
    is_inter = getattr(args, 'interstellar_nonlinear', False) or "interstellar" in (title or "").lower() or "nonlineari" in (title or "").lower()
    data["storage_memory_category"] = {
        "zone": "interstellar-zone-alpha" if is_inter else "default-zone",
        "memory": "16GB" if is_inter else "8GB",
        "location": "nls-visualist-dc-1" if is_inter else "local-dc",
        "zone": "interstellar-zone-alpha" if is_inter else "default-zone",
        "V": "vp56-vol-1999" if is_inter else "h264-vol",
        "Bandwidth": "10Gbps" if is_inter else "1Gbps"
    }

    sidecar.write_text(json.dumps(data, indent=2))

    catalog = []
    if CATALOG_PATH.exists():
        try:
            catalog = json.loads(CATALOG_PATH.read_text())
        except Exception:
            catalog = []
    catalog.append(data)
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2))

    print(f"Cataloged to NLS Visualist data: {sidecar}")
    print(f"Central catalog updated: {CATALOG_PATH}")


def cmd_list_catalog(args):
    """List the NLS Visualist catalog, highlighting gravity/noiseprotocol prepared items."""
    catalog = []
    if CATALOG_PATH.exists():
        try:
            catalog = json.loads(CATALOG_PATH.read_text())
        except Exception:
            catalog = []
    if not catalog:
        print("Catalog empty. Complete some jobs with --gravity or use nls-video catalog on finished files.")
        return
    if RICH_AVAILABLE:
        table = Table(title="NLS Visualist Data Catalog (Gravity/NoiseProtocol + Storage Memory Category)")
        table.add_column("Title")
        table.add_column("Gravity?", style="green")
        table.add_column("Interstellar?", style="cyan")
        table.add_column("Storage Mem (zone|mem|loc|V|BW)")
        table.add_column("Output")
        for item in catalog:
            grav = "YES" if item.get("gravity_prepared") or item.get("raw_h264_stream") else "no"
            inter = "YES" if item.get("interstellar_nonlinear") or "interstellar" in item.get("title","").lower() or "nonlineari" in item.get("title","").lower() else "no"
            smc = item.get("storage_memory_category", {})
            storage = f"{smc.get('zone','?')}|{smc.get('memory','?')}|{smc.get('location','?')}|{smc.get('V','?')}|{smc.get('Bandwidth','?')}"
            dur = item.get("technical", {}).get("duration", "?")
            out = item.get("output_path", "?")
            table.add_row(item.get("title", "?")[:30], grav, inter, storage, out.split("/")[-1][:25])
        Console().print(table)
    else:
        print("NLS Visualist Data Catalog:")
        for item in catalog:
            grav = "GRAVITY" if item.get("gravity_prepared") or item.get("raw_h264_stream") else ""
            inter = "INTER" if item.get("interstellar_nonlinear") or "interstellar" in item.get("title","").lower() or "nonlineari" in item.get("title","").lower() else ""
            smc = item.get("storage_memory_category", {})
            storage = f"zone={smc.get('zone','?')} mem={smc.get('memory','?')} loc={smc.get('location','?')} V={smc.get('V','?')} BW={smc.get('Bandwidth','?')}"
            print(f"  {item.get('title', '?')} {grav} {inter} {storage} -> {item.get('output_path','?')}")


def cmd_monitor(args):
    """Terminal TUI dashboard inside the terminal with the same idea as the web interface.
    Uses your Visualist aesthetics: glitch-style title, '1000 years old nonlinear h@k reality' banner,
    ASC cinematic thumbnails (styled panels with film-like borders and colors), gravity/noiseprotocol highlights.
    Live updating 'window' using rich panels and tables. No kill, no eval.
    Shows Pipeline Jobs (live from DB) and NLS Visualist Data (from catalog + current job integration).
    """
    if not RICH_AVAILABLE:
        print("rich not available, falling back to simple loop. Install rich for full TUI.")
        # simple fallback
        while True:
            os.system('clear' if os.name == 'posix' else 'cls')
            print("NLS Visualist Terminal Monitor (simple mode)")
            print("1000 years old nonlinear h@k reality")
            print("\nJobs:")
            conn = get_db()
            for j in list_jobs(conn):
                print(f"  #{j.id} {j.title[:40]} {j.status} {j.progress:.1f}% {j.preset}")
            conn.close()
            print("\nCatalog (last 5):")
            if CATALOG_PATH.exists():
                try:
                    cat = json.loads(CATALOG_PATH.read_text())[-5:]
                    for it in cat:
                        print(f"  {it.get('title','?')} gravity={bool(it.get('gravity_prepared'))}")
                except:
                    pass
            time.sleep(2)
        return

    console = Console()
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=5),
        Layout(name="body"),
    )
    layout["body"].split_row(
        Layout(name="jobs", ratio=1),
        Layout(name="visualist", ratio=1),
    )

    def make_header():
        title = Text("NLS Visualist • Terminal Monitor", style="bold cyan")
        banner = Text("\n1000 years old nonlinear h@k reality", style="magenta italic")
        glitch_note = Text("\n[glitch aesthetics + ASC thumbnails + noiseprotocol gravity]", style="dim")
        return Panel(title + banner + glitch_note, border_style="green", title="NLS Visualist Data Interface (Terminal)")

    def make_jobs_panel():
        conn = get_db()
        jobs = list_jobs(conn)
        conn.close()
        table = Table(title="Pipeline Jobs (live)", show_header=True, header_style="bold blue")
        table.add_column("ID", style="cyan", width=4)
        table.add_column("Title", style="white")
        table.add_column("Status", style="magenta")
        table.add_column("Progress", style="green")
        table.add_column("Preset")
        for j in jobs:
            prog = f"{j.progress:.1f}%"
            if j.status == "converting":
                prog += " [convert]"
            table.add_row(str(j.id), j.title[:35], j.status, prog, j.preset)
        return Panel(table, border_style="blue", title="Jobs Window")

    def make_visualist_panel():
        catalog = []
        if CATALOG_PATH.exists():
            try:
                catalog = json.loads(CATALOG_PATH.read_text())
            except:
                pass
        # Include current job as "live" item for Visualist integration
        conn = get_db()
        current_jobs = list_jobs(conn, status="converting")
        conn.close()
        items = catalog[-5:]  # last 5
        table = Table(title="NLS Visualist Data (ASC Thumbnails + Gravity)", show_header=True, header_style="bold purple")
        table.add_column("Item", style="white")
        table.add_column("ASC Thumb", style="yellow")
        table.add_column("Gravity?", style="green")
        table.add_column("Info")
        for it in items:
            grav = "YES (noiseprotocol)" if it.get("gravity_prepared") or it.get("raw_h264_stream") else "no"
            thumb = "[ASC filmic]"  # simulated ASC thumbnail
            dur = it.get("technical", {}).get("duration", "?")
            table.add_row(it.get("title", "?")[:25], thumb, grav, f"{dur}s")
        for j in current_jobs:
            table.add_row(f"[LIVE] {j.title[:20]}", "[ASC live]", "in progress", f"{j.progress:.1f}%")
        return Panel(table, border_style="purple", title="Visualist Data Window (from catalog + live jobs)")

    with Live(layout, refresh_per_second=1, screen=True, console=console) as live:
        while True:
            layout["header"].update(make_header())
            layout["jobs"].update(make_jobs_panel())
            layout["visualist"].update(make_visualist_panel())
            time.sleep(1.5)
            # user can Ctrl+C to exit; follows no kill rule (no process termination)


def cmd_gravity_server(args):
    """Start Gravity protocol server (NoiseProtocol structure from SCIS, for 'gravity' secure transport of Visualist data).
    Clients (e.g. Java + Qt desktop app) connect, perform simple handshake (prologue GRAVITY, hello/finish with magic bytes like SCIS 0x42/0x43), then receive JSON updates of jobs + catalog.
    This allows the desktop window to act *as the protocol client* for the NLS Visualist interface.
    Rule #1 no kill, Rule #2 no eval. Pure sockets + JSON.
    """
    host = "127.0.0.1"
    port = args.port
    print(f"Starting NoiseProtocol Gravity server on {host}:{port} (for Java/Qt desktop windows)...")
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((host, port))
    server_sock.listen(5)

    def client_handler(conn, addr):
        try:
            # Handshake inspired by SCIS NoiseProtocol.Handshake (XX, prologue)
            prologue = b"GRAVITY\x00\x01"
            conn.sendall(prologue)
            # Client hello (expect ~32 bytes)
            hello = conn.recv(32)
            # Server hello
            conn.sendall(b"\x00" * 32)
            # Client finish (expect ~48)
            finish = conn.recv(48)
            # Now in "transport" - send periodic updates
            while True:
                conn_db = get_db()
                jobs = [j.to_dict() for j in list_jobs(conn_db)]
                conn_db.close()
                catalog = []
                if CATALOG_PATH.exists():
                    try:
                        catalog = json.loads(CATALOG_PATH.read_text())
                    except Exception:
                        catalog = []
                update = {
                    "type": "gravity_update",
                    "jobs": jobs,
                    "catalog": catalog,
                    "timestamp": now_utc_iso()
                }
                try:
                    conn.sendall((json.dumps(update) + "\n").encode("utf-8"))
                except (BrokenPipeError, ConnectionResetError):
                    break
                time.sleep(2.0)
        except Exception as e:
            print(f"Gravity client {addr} error: {e}")
        finally:
            conn.close()

    while True:
        conn, addr = server_sock.accept()
        print(f"Gravity client connected from {addr}")
        t = threading.Thread(target=client_handler, args=(conn, addr), daemon=True)
        t.start()


def cmd_gravity_client(args):
    """Terminal client for the Gravity protocol - the 'same' as the Java/Qt desktop window, but inside the terminal.
    Connects to gravity-server, handshake (SCIS-inspired), receives live JSON updates, renders a rich TUI 'window' with panels for:
    - Header with glitch aesthetics + "1000 years old nonlinear h@k reality" banner
    - Jobs table (live from protocol)
    - Visualist Data gallery (ASC thumbnails as styled panels, gravity highlights, links to streams)
    - NEW: URL drag & drop / copy & paste INPUT BAR (size 3) directly above the status bar for data downloading to ~/Downloads/
    Uses rich for 'built-in window' feel (panels as windows). Live updating. Follows no kill, no eval.
    Run this in a terminal to 'open the window' with the same idea as the Java desktop one.
    """
    if not RICH_AVAILABLE:
        print("rich required for TUI. pip install rich")
        return
    console = Console()
    host = "127.0.0.1"
    port = args.port
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.connect((host, port))
        # Handshake (client side, matching server and SCIS structure)
        prologue = s.recv(10)
        s.send(b'\x42' * 32)  # client hello
        s.recv(32)  # server hello
        s.send(b'\x43' * 48)  # finish
        console.print("[green]Gravity handshake complete. Receiving protocol updates...[/green]")

        layout = Layout()
        layout.split_column(
            Layout(name="header", size=5),
            Layout(name="body"),
            Layout(name="input", size=3),
            Layout(name="status", size=3),
        )
        layout["body"].split_row(
            Layout(name="jobs", ratio=1),
            Layout(name="visualist", ratio=1),
        )

        def make_header():
            # KISS + visual_language_animation.svg (monospace, cyan, colored nodes for H.264 stages)
            title = Text("NLS Visualist • H.264", style="bold cyan")
            flow = Text(" ◐URL  ▦DL  ⌬H264  ▣GRAV  ◈CAT ", style="cyan")
            sub = Text("URL → yt-dlp → ffmpeg H.264 → (gravity) → catalog", style="dim")
            return Panel(title + "\n" + flow + "\n" + sub, border_style="cyan", title="KISS")

        def make_progress_bar(percent: float, width: int = 20, status: str = "converting") -> Text:
            """KISS progress. Block bar colored by H.264 pipeline stage."""
            pct = max(0.0, min(100.0, percent))
            filled = int(width * (pct / 100))
            bar = "█" * filled + "░" * (width - filled)
            color = "cyan" if status in ("downloading", "converting") else "green"
            if status == "failed":
                color = "red"
            text = Text()
            text.append(f"[{bar}] ", style=color)
            text.append(f"{pct:.1f}%", style="white")
            return text

        def make_status_bar(jobs_data, catalog_data):
            """KISS bottom bar."""
            active = sum(1 for j in jobs_data if j.get('status') in ['downloading', 'converting'])
            completed = sum(1 for j in jobs_data if j.get('status') == 'completed')
            status_text = Text()
            status_text.append("H.264 • ", style="bold cyan")
            status_text.append(f"{active} active / {completed} done  |  no kill • no eval", style="dim")
            return Panel(status_text, border_style="cyan", title="status")

        def make_jobs_panel(jobs_data):
            table = Table(title="H.264 Jobs (live)", show_header=True, header_style="bold cyan")
            table.add_column("#", style="cyan", width=3)
            table.add_column("Title", style="white")
            table.add_column("Stage", style="magenta")
            table.add_column("Progress", style="cyan")
            for j in jobs_data:
                prog_bar = make_progress_bar(j.get('progress', 0), width=16, status=j.get('status', ''))
                table.add_row(
                    str(j.get('id')),
                    j.get('title', '?')[:32],
                    j.get('status', '?'),
                    prog_bar
                )
            return Panel(table, border_style="cyan", title="jobs")

        def make_visualist_panel(catalog_data):
            text = Text("Visualist (H.264 + Gravity)\n", style="bold cyan")
            text.append("monospace • dark • simple\n", style="dim")
            for it in catalog_data[-4:]:
                grav = " g" if it.get("gravity_prepared") or it.get("raw_h264_stream") else ""
                text.append(f"• {it.get('title','?')[:28]}{grav}\n", style="white")
            return Panel(text, border_style="cyan", title="visualist")

        # Simple stage indicators row (KISS nodes from the SVG visual language)
        def make_stages_panel():
            txt = Text()
            stages = [
                ("◐", "cyan", "URL"),
                ("▦", "yellow", "DL"),
                ("⌬", "red", "H264"),
                ("▣", "green", "GRAV"),
                ("◈", "magenta", "CAT"),
            ]
            for sym, col, name in stages:
                txt.append(f" {sym} {name} ", style=f"bold {col}")
            return Panel(txt, border_style="cyan", title="H.264 flow (KISS)")

        # === URL drag & drop / copy & paste INPUT above status bar for direct download to ~/Downloads/ ===
        input_state = {
            "last_pasted": "",
            "direct_status": "Ready — drag URL or copy-paste + Enter (downloads direct to ~/Downloads/)",
            "direct_progress": 0.0,
            "direct_output": "",
        }

        def make_input_panel(st):
            """The drag & drop + copy-paste bar placed above the status bar.
            Captures pasted/dragged URLs via stdin thread and runs yt-dlp directly to ~/Downloads/.
            Shows live progress bar using the shared make_progress_bar. No feedback loops.
            """
            txt = Text()
            txt.append("▶ URL (H.264) → ~/Downloads/\n", style="bold cyan")
            txt.append("Type/paste + Enter (arrows, backspace via readline; mouse select + terminal copy/paste works before Enter). For full cursor/selection/Ctrl+V in a real input bar use the Java desktop app.\n", style="dim")
            if st.get("last_pasted"):
                txt.append(f"Last: {st['last_pasted'][:62]}\n", style="cyan")
            status_style = "green"
            ds = st.get("direct_status", "")
            if "err" in ds.lower() or "fail" in ds.lower():
                status_style = "red"
            elif "download" in ds.lower() or "start" in ds.lower():
                status_style = "cyan"
            txt.append("Status: ", style="bold")
            txt.append(ds, style=status_style)
            txt.append("\n")
            prog = st.get("direct_progress", 0.0)
            if prog > 0.5:
                bar = make_progress_bar(prog, width=42, status="downloading")
                txt.append(bar)
                txt.append("  direct\n")
            else:
                txt.append("[waiting for URL paste/drag...]\n", style="dim")
            return Panel(txt, border_style="yellow", title="Input Bar (URL to ~/Downloads/)")

        def run_direct_download(url, st):
            """Fire-and-manage direct yt-dlp (no shell, no eval) straight to ~/Downloads/.
            Updates input_state for live progress in the input panel. Independent of job queue.
            Ensures JS runtime (deno etc.) to avoid the "No supported JavaScript runtime" warning.
            """
            ensure_js_runtime(interactive=False)  # non-blocking check + optional auto in future
            downloads = Path.home() / "Downloads"
            downloads.mkdir(parents=True, exist_ok=True)
            outtmpl = str(downloads / "%(title)s [%(id)s].%(ext)s")
            rt = check_js_runtime()
            try:
                import yt_dlp
                def hook(d):
                    if d.get('status') == 'downloading':
                        total = d.get('total_bytes') or d.get('total_bytes_estimate') or 0
                        dl = d.get('downloaded_bytes', 0)
                        p = (dl / total * 100.0) if total > 0 else 0.0
                        st["direct_progress"] = max(0.0, min(100.0, p))
                        fn = d.get('filename') or d.get('_filename') or ''
                        st["direct_status"] = f"downloading: {os.path.basename(str(fn))[:38]}"
                    elif d.get('status') == 'finished':
                        st["direct_progress"] = 100.0
                        fn = d.get('filename') or d.get('_filename') or 'file'
                        base = os.path.basename(str(fn))
                        st["direct_status"] = f"✓ done → ~/Downloads/{base}"
                        st["direct_output"] = str(fn)
                opts = {
                    "outtmpl": outtmpl,
                    "progress_hooks": [hook],
                    "quiet": True,
                    "no_warnings": True,
                    "merge_output_format": "mp4",
                }
                with yt_dlp.YoutubeDL(opts) as ydl:
                    ydl.download([url])
            except ImportError:
                # Fallback: yt-dlp CLI (subprocess list, safe, no shell)
                st["direct_status"] = "yt-dlp py not found, using CLI..."
                try:
                    cli_args = ["yt-dlp", "--newline", "-o", outtmpl, url]
                    if rt:
                        cli_args = ["yt-dlp", "--js-runtimes", rt, "--newline", "-o", outtmpl, url]
                    proc = subprocess.Popen(
                        cli_args,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1
                    )
                    for line in iter(proc.stdout.readline, ""):
                        if not line:
                            break
                        line = line.strip()
                        if "[download]" in line and "%" in line:
                            m = re.search(r"(\d+\.?\d*)%", line)
                            if m:
                                st["direct_progress"] = float(m.group(1))
                            st["direct_status"] = line[:72]
                        elif line and ("Merging" in line or "Destination" in line or "has already" in line):
                            st["direct_status"] = line[:72]
                    proc.wait()
                    if proc.returncode == 0:
                        st["direct_progress"] = 100.0
                        st["direct_status"] = "✓ done (yt-dlp CLI) → ~/Downloads/"
                    else:
                        st["direct_status"] = f"CLI rc={proc.returncode}"
                        st["direct_progress"] = 0.0
                except Exception as e2:
                    st["direct_status"] = f"CLI error: {str(e2)[:60]}"
                    st["direct_progress"] = 0.0
            except Exception as e:
                st["direct_status"] = f"error: {str(e)[:68]}"
                st["direct_progress"] = 0.0

        # Start the paste/drag watcher thread (daemon, captures stdin lines for URLs)
        # This enables "drag and drop && copy & paste" into the gravity-client TUI window.
        def paste_watcher():
            while True:
                try:
                    line = sys.stdin.readline()
                    if not line:
                        time.sleep(0.15)
                        continue
                    url = line.strip()
                    if not url:
                        continue
                    if not (url.startswith("http://") or url.startswith("https://") or "youtu" in url.lower()):
                        input_state["direct_status"] = f"ignored (not http URL): {url[:45]}"
                        input_state["direct_progress"] = 0.0
                        continue
                    input_state["last_pasted"] = url
                    input_state["direct_progress"] = 0.0
                    input_state["direct_status"] = "starting direct yt-dlp to ~/Downloads/..."
                    threading.Thread(target=run_direct_download, args=(url, input_state), daemon=True).start()
                except Exception as ex:
                    input_state["direct_status"] = f"input err: {str(ex)[:55]}"
                    time.sleep(0.2)

        paste_thread = threading.Thread(target=paste_watcher, daemon=True)
        paste_thread.start()

        jobs_data = []
        catalog_data = []

        # KISS initial (SVG style + H.264 stages in header for simplicity)
        layout["header"].update(make_header())
        layout["jobs"].update(make_jobs_panel(jobs_data))
        layout["visualist"].update(make_visualist_panel(catalog_data))
        layout["status"].update(make_status_bar(jobs_data, catalog_data))
        layout["input"].update(make_input_panel(input_state))

        with Live(layout, refresh_per_second=4, screen=True, console=console) as live:
            buffer = b""
            while True:
                readable, _, _ = select.select([s], [], [], 0.25)
                if readable:
                    data = s.recv(4096)
                    if not data:
                        break
                    buffer += data
                    while b'\n' in buffer:
                        line, buffer = buffer.split(b'\n', 1)
                        try:
                            update = json.loads(line.decode('utf-8', errors='ignore'))
                            if update.get("type") == "gravity_update":
                                jobs_data = update.get("jobs", [])
                                catalog_data = update.get("catalog", [])
                                layout["header"].update(make_header())
                                layout["jobs"].update(make_jobs_panel(jobs_data))
                                layout["visualist"].update(make_visualist_panel(catalog_data))
                                layout["status"].update(make_status_bar(jobs_data, catalog_data))
                        except Exception:
                            pass
                layout["input"].update(make_input_panel(input_state))
                time.sleep(0.03)
    except Exception as e:
        console.print(f"[red]Gravity client error: {e}[/red]")
        console.print("Make sure gravity-server is running: nls-video gravity-server --port 4242")


def cmd_hierarchy(args):
    """Launch the Enhanced Interactive 11-Dimensional Hierarchy Explorer.
    Fully integrated with NLS Visualist themes: gravity, H.264 pipeline stages,
    ASC filmic aesthetics, interstellar|nonlineari, noiseprotocol.
    Uses the provided multimedia (ANSI + ASCII) + rich if available.
    KISS interactive journey.
    """
    if HIERARCHY_AVAILABLE:
        try:
            hierarchy_interpreter.main()
        except Exception as e:
            print(f"Hierarchy explorer error: {e}")
            print("Falling back to basic mode...")
            # Fallback simple version if the module has issues
            print("11D Hierarchy (basic): 11 Pure Form → 1 The Way")
            for lvl in range(11, 0, -1):
                print(f"  Level {lvl}: {hierarchy_interpreter.describe_level(lvl)[:70]}...")
                time.sleep(0.3)
    else:
        print("hierarchy_interpreter.py not found or import failed.")
        print("Make sure the file exists in the same directory as nls_video_pipe.py")
        print("Basic hierarchy (manifestation path):")
        for lvl in range(11, 0, -1):
            print(f"  {lvl}: Pure Form ... DNA ... Waves ... Elements ... Human ... The Way")


def cmd_worker(args):
    worker()


def main():
    parser = argparse.ArgumentParser(description="NLS Video download + H.264 convert monitor")
    parser.add_argument("--version", action="version", version=f"{APP_NAME} {__version__}")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("add", help="Queue a YouTube (or direct) video for download + convert. Use --source-file for convert-only on an existing downloaded file (e.g. the current AV1 source).")
    p.add_argument("url", nargs="?", help="YouTube URL (ignored if --source-file is used)")
    p.add_argument("--preset", choices=list(DEFAULT_PRESETS.keys()), default=None)
    p.add_argument("--title", default=None)
    p.add_argument("--source-file", help="Existing local file to convert (skips download step). Useful to adopt the current running encode or re-encode with different preset.")
    p.add_argument("--gravity", action="store_true", help="After successful convert, prepare raw H.264 elementary stream for Noise Protocol transport (gravity mode, using SCIS philosophy for secure Visualist channels). Rule #1 no kill, Rule #2 no eval.")
    p.add_argument("--interstellar-nonlinear", action="store_true", help="Enable interstellar|nonlineari mode: use SCIS noiseprotocol-vcodec + FFMPEG for VP56 origin form (legacy visualist look) + gravity prep. For content with 1000 years old nonlinear h@k reality aesthetics, ASC cinematic thumbnails.")
    p.set_defaults(func=cmd_add)

    p = sub.add_parser("list", help="List jobs")
    p.add_argument("--status", default=None)
    p.set_defaults(func=cmd_list)

    p = sub.add_parser("status", help="Show detailed job info")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_status)

    p = sub.add_parser("logs", help="Show log for a job")
    p.add_argument("id", type=int)
    p.add_argument("--follow", action="store_true")
    p.set_defaults(func=cmd_logs)

    p = sub.add_parser("cancel", help="Cancel a pending/running job")
    p.add_argument("id", type=int)
    p.set_defaults(func=cmd_cancel)

    p = sub.add_parser("worker", help="Run the background processor (recommended in tmux)")
    p.set_defaults(func=cmd_worker)

    p = sub.add_parser("serve", help="Start the web dashboard (NLS Visualist interface)")
    p.add_argument("--port", type=int, default=8765)
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("gravity-serve", help="Browser Gravity client — full HTML dashboard (jobs, catalog, interlaterus mint, ~/Downloads). Proxies gravity-server live updates.")
    p.add_argument("--port", type=int, default=8766, help="HTTP port (default 8766)")
    p.add_argument("--gravity-host", default="127.0.0.1", help="gravity-server host")
    p.add_argument("--gravity-port", type=int, default=4242, help="gravity-server port")
    p.set_defaults(func=cmd_gravity_serve)

    p = sub.add_parser("gravity-serve-archive", help="Archive gravity-serve assets + session + log tail (keeps live server running)")
    p.add_argument("--dest", default=None, help="Optional archive directory")
    p.add_argument("--log-tail", type=int, default=500, help="Lines of live JSONL to include")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_gravity_serve_archive)

    p = sub.add_parser("running-status", help="Show gravity-serve running version (for mm / monitors)")
    p.add_argument("--json", action="store_true")
    p.set_defaults(func=cmd_running_status)

    p = sub.add_parser("catalog", help="Catalog an existing finished video into NLS Visualist data (no download/convert run, follows no-kill no-eval rules). Use --gravity to also prepare raw stream for Noise Protocol.")
    p.add_argument("file")
    p.add_argument("--title", default=None)
    p.add_argument("--source-url", default=None)
    p.add_argument("--gravity", action="store_true", help="Prepare raw H.264 for noiseprotocol gravity / secure transport (SCIS style).")
    p.add_argument("--interstellar-nonlinear", action="store_true", help="Tag as interstellar|nonlineari and prepare VP56 gravity via SCIS noiseprotocol-vcodec + FFMPEG.")
    p.set_defaults(func=cmd_catalog)

    p = sub.add_parser("list-catalog", help="List the NLS Visualist data catalog (gravity / noiseprotocol prepared items)")
    p.set_defaults(func=cmd_list_catalog)

    p = sub.add_parser("spatio", help="Proof of Spatio (aka POS) — reconcile AVD↔POS catalog positioning")
    p.add_argument("--rebuild", action="store_true", help="Force rebuild position_index.json")
    p.add_argument("--json", action="store_true", help="Print proof JSON")
    p.set_defaults(func=cmd_spatio)

    p = sub.add_parser("aoa-delta", help="AOA | NLS Visualist — LIFO 16→0 grok_report PDF delta compose (360°/16 slices)")
    p.add_argument("--report-dir", default=None, help="Directory with grok_report*.pdf (default ~/Downloads)")
    p.add_argument("--no-write", action="store_true", help="Dry run — do not write aoa-delta.json")
    p.add_argument("--json", action="store_true", help="Print full compose JSON")
    p.set_defaults(func=cmd_aoa_delta)

    p = sub.add_parser("monitor", help="Terminal TUI dashboard inside the terminal (same idea as web serve: jobs + NLS Visualist Data gallery with your aesthetics, ASC thumbnails, glitch, gravity. Live updating 'window' in terminal.)")
    p.set_defaults(func=cmd_monitor)

    p = sub.add_parser("gravity-server", help="Start the NoiseProtocol Gravity server (inspired by SCIS) as the protocol backend. Java + Qt (or Swing) desktop clients connect to open a window on the desktop as the NLS Visualist interface/protocol client. No kill, no eval.")
    p.add_argument("--port", type=int, default=4242)
    p.set_defaults(func=cmd_gravity_server)

    p = sub.add_parser("gravity-client", help="Terminal client for the Gravity protocol (same as Java desktop window, but inside terminal). Connects to gravity-server, does handshake, receives live updates, renders TUI with Visualist aesthetics, ASC thumbnails, glitch, gravity elements. The terminal acts as the 'window' for the NLS Visualist data interface/protocol.")
    p.add_argument("--port", type=int, default=4242)
    p.set_defaults(func=cmd_gravity_client)

    p = sub.add_parser("hierarchy", help="Interactive 11-Dimensional Hierarchy Explorer (NLS Visualist edition). Journey through levels 11 (Pure Form / Source) → 1 (The Way / Final Catalog). Ties gravity, H.264, ASC filmic, interstellar|nonlineari, noiseprotocol into an esoteric manifestation map. KISS interactive with ASCII, colors, explanations. Run standalone: python3 hierarchy_interpreter.py")
    p.set_defaults(func=cmd_hierarchy)

    p = sub.add_parser("check-js", help="Check for JS runtime (deno/node/etc.) needed by yt-dlp for YouTube. Deno and Node.js are similarly supported. Offers install (Deno recommended). pythonJava friendly (call from Java app too).")
    p.set_defaults(func=lambda args: print("JS runtime:", ensure_js_runtime(interactive=True) or "none found"))

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
