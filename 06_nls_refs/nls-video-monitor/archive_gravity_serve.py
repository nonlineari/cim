#!/usr/bin/env python3
"""
Archive gravity-serve — keep live server running; snapshot assets + session + log tail.

Writes: ~/.local/share/nls-video/archives/gravity-serve-<UTC-stamp>/
        manifest.json + proof digest (sha256 of file hashes)
"""
from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ARCHIVE_ROOT = Path.home() / ".local" / "share" / "nls-video" / "archives"
RUNTIME_LOG_DIR = Path.home() / ".local" / "share" / "gravity-desktop" / "runtime-logs"
LATEST_LINK = ARCHIVE_ROOT / "gravity-serve-latest"

# Resolve project root (same as nls_video_pipe)
def _app_root() -> Path:
    env = __import__("os").environ.get("NLS_VIDEO_HOME", "").strip()
    if env:
        p = Path(env).expanduser().resolve()
        if (p / "nls_video_pipe.py").is_file():
            return p
    here = Path(__file__).resolve().parent
    if (here / "nls_video_pipe.py").is_file():
        return here
    return here


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tail_lines(path: Path, n: int = 500) -> List[str]:
    if not path.is_file():
        return []
    try:
        out = subprocess.run(
            ["tail", "-n", str(n), str(path)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return [ln for ln in out.stdout.splitlines() if ln.strip()]
    except Exception:
        return []


def _running_gravity_serve() -> Optional[Dict[str, Any]]:
    try:
        out = subprocess.run(
            ["pgrep", "-af", "[n]ls_video_pipe.py gravity-serve"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        line = out.stdout.strip().splitlines()
        if not line:
            return None
        parts = line[0].split(None, 1)
        return {"pid": int(parts[0]), "cmd": parts[1] if len(parts) > 1 else ""}
    except Exception:
        return None


def archive_gravity_serve(
    dest: Optional[Path] = None,
    log_tail_lines: int = 500,
    update_latest_link: bool = True,
) -> Dict[str, Any]:
    app = _app_root()
    stamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H%M%SZ")
    archive_dir = dest or (ARCHIVE_ROOT / f"gravity-serve-{stamp}")
    archive_dir.mkdir(parents=True, exist_ok=True)

    source_files = [
        app / "gravity_serve.html",
        app / "run-gravity-serve.sh",
        app / "restart-gravity-serve.sh",
        app / "verify-gravity-api.sh",
        app / "version.json",
        app / "test_timezone_axiom.py",
        app / "aoa_delta_compose.py",
    ]
    copied: List[Dict[str, Any]] = []
    for src in source_files:
        if not src.is_file():
            continue
        dst = archive_dir / "sources" / src.name
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
        copied.append({"name": src.name, "sha256": _sha256_file(dst), "bytes": dst.stat().st_size})

    runtime_dir = archive_dir / "runtime"
    runtime_dir.mkdir(exist_ok=True)
    for name in ("gravity-serve-session.json", "gravity-desktop-session.json"):
        src = RUNTIME_LOG_DIR / name
        if src.is_file():
            shutil.copy2(src, runtime_dir / name)

    live_log = RUNTIME_LOG_DIR / "gravity-serve-live.jsonl"
    tail = _tail_lines(live_log, log_tail_lines)
    tail_path = runtime_dir / "gravity-serve-live.tail.jsonl"
    tail_path.write_text("\n".join(tail) + ("\n" if tail else ""), encoding="utf-8")

    if live_log.is_file():
        (runtime_dir / "gravity-serve-live.meta.json").write_text(
            json.dumps({"path": str(live_log), "bytes": live_log.stat().st_size, "tail_lines": len(tail)}, indent=2),
            encoding="utf-8",
        )

    proc = _running_gravity_serve()
    manifest: Dict[str, Any] = {
        "ok": True,
        "archive_type": "gravity-serve",
        "archived_at_utc": datetime.now(timezone.utc).isoformat(),
        "time_axiom": "utc",
        "version": json.loads((app / "version.json").read_text()) if (app / "version.json").is_file() else {},
        "app_root": str(app),
        "archive_dir": str(archive_dir),
        "live_server": proc,
        "keep_running": True,
        "sources": copied,
        "runtime": {
            "session": str(runtime_dir / "gravity-serve-session.json"),
            "log_tail": str(tail_path),
            "log_tail_lines": len(tail),
            "full_log_bytes": live_log.stat().st_size if live_log.is_file() else 0,
        },
        "ports": {"gravity_serve": 8766, "gravity_server": 4242},
    }

    proof_src = json.dumps({c["name"]: c["sha256"] for c in copied}, sort_keys=True)
    manifest["proof_digest"] = hashlib.sha256(proof_src.encode()).hexdigest()
    manifest_path = archive_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if update_latest_link:
        if LATEST_LINK.is_symlink() or LATEST_LINK.exists():
            LATEST_LINK.unlink()
        LATEST_LINK.symlink_to(archive_dir.name)

    manifest["latest_link"] = str(LATEST_LINK)
    return manifest


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="Archive gravity-serve (live server keeps running)")
    p.add_argument("--dest", type=Path, default=None)
    p.add_argument("--log-tail", type=int, default=500)
    p.add_argument("--json", action="store_true")
    args = p.parse_args()
    result = archive_gravity_serve(args.dest, log_tail_lines=args.log_tail)
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        print("gravity-serve archived (live server kept running)")
        print(f"  dir:   {result['archive_dir']}")
        print(f"  proof: {result['proof_digest'][:32]}…")
        print(f"  pid:   {(result.get('live_server') or {}).get('pid', '—')}")
        print(f"  files: {len(result.get('sources', []))}")


if __name__ == "__main__":
    main()