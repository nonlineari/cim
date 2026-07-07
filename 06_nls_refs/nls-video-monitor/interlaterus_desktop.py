#!/usr/bin/env python3
"""
InterlaterusDesktop — vertical integration orchestrator.

Stack (Image #1 / nonlineari arch):
  GravityDesktop (download) → ffmpeg/ffprobe (media data)
  → Blockcode_NLS_Records (tesseract mint) → NLS-Record catalog
  → optional NCOMM export manifest

Usage:
  python3 interlaterus_desktop.py mint --file ~/Downloads/direct-h264-xxx.mp4 --url URL --title TITLE
  python3 interlaterus_desktop.py watch
  python3 interlaterus_desktop.py list
  python3 interlaterus_desktop.py export
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from blockcode_nft_client import get_blockcode_nft_client

XDG_CONFIG = Path.home() / ".config" / "interlaterus-desktop"
XDG_DATA = Path.home() / ".local" / "share" / "interlaterus-desktop"
DB_PATH = XDG_DATA / "blockcode_registry.db"
CATALOG_PATH = XDG_DATA / "nls_media_catalog.json"
MANIFEST_PATH = XDG_DATA / "ncomm_export_manifest.json"
DOWNLOADS = Path.home() / "Downloads"
WATCH_PATTERNS = (
    re.compile(r"^direct-h264-.+\.mp4$"),
    re.compile(r"^direct-gif-.+\.gif$"),
    re.compile(r"^direct-h264-rot\d+-.+\.mp4$"),
)

SPATIAL = ["AB", "AABB", "ABAB", "ABBA"]
RHYTHM = ["2:4", "3:3", "4:4", "5:3"]
STRUCTURE = ["P&B", "P|B", "P→B", "P←B"]
TRANSFORM = ["F1", "F2", "F3", "F4"]
OWNER_DEFAULT = "AABB.3:3.P|B.F2"
TESSERACT_VERTICES = [
    [x, y, z, t]
    for x in (0, 1)
    for y in (0, 1)
    for z in (0, 1)
    for t in (0, 1)
]


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def ensure_dirs() -> None:
    XDG_CONFIG.mkdir(parents=True, exist_ok=True)
    XDG_DATA.mkdir(parents=True, exist_ok=True)


def ffmpeg_path() -> str:
    return os.environ.get("FFMPEG_PATH", shutil.which("ffmpeg") or "/usr/bin/ffmpeg")


def ffprobe_path() -> str:
    return os.environ.get("FFPROBE_PATH", shutil.which("ffprobe") or "/usr/bin/ffprobe")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def run_json(cmd: List[str]) -> Dict[str, Any]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, text=True)
        return json.loads(out)
    except Exception:
        return {}


def probe_media(path: Path) -> Dict[str, Any]:
    data = run_json(
        [
            ffprobe_path(),
            "-v",
            "quiet",
            "-print_format",
            "json",
            "-show_format",
            "-show_streams",
            str(path),
        ]
    )
    fmt = data.get("format") or {}
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), {})
    audio = next((s for s in streams if s.get("codec_type") == "audio"), {})
    duration = float(fmt.get("duration") or video.get("duration") or 0)
    size = int(fmt.get("size") or path.stat().st_size)
    bitrate = int(fmt.get("bit_rate") or 0)
    width = int(video.get("width") or 0)
    height = int(video.get("height") or 0)
    return {
        "path": str(path),
        "filename": path.name,
        "duration_sec": duration,
        "size_bytes": size,
        "bitrate": bitrate,
        "width": width,
        "height": height,
        "vcodec": video.get("codec_name", ""),
        "acodec": audio.get("codec_name", ""),
        "format": fmt.get("format_name", path.suffix.lstrip(".")),
        "sha256": sha256_file(path),
    }


def audio_vector_from_probe(probe: Dict[str, Any]) -> List[float]:
    """4D metadata vector for blockcode (duration, size norm, bitrate norm, aspect)."""
    dur = max(probe.get("duration_sec") or 0, 0.001)
    size_mb = (probe.get("size_bytes") or 0) / (1024 * 1024)
    br_mbps = (probe.get("bitrate") or 0) / 1_000_000
    w, h = probe.get("width") or 1, probe.get("height") or 1
    aspect = w / max(h, 1)
    return [
        round(min(dur / 600.0, 2.0), 4),
        round(min(size_mb / 500.0, 2.0), 4),
        round(min(br_mbps / 10.0, 2.0), 4),
        round(min(aspect, 2.0), 4),
    ]


def pattern_from_digest(digest: str) -> str:
    """Deterministic blockcode pattern from sha256 hex."""
    i = int(digest[:8], 16)
    return ".".join(
        [
            SPATIAL[i % len(SPATIAL)],
            RHYTHM[(i >> 4) % len(RHYTHM)],
            STRUCTURE[(i >> 8) % len(STRUCTURE)],
            TRANSFORM[(i >> 12) % len(TRANSFORM)],
        ]
    )


def get_db() -> sqlite3.Connection:
    ensure_dirs()
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS blockcode_nft_records (
            pattern_code TEXT PRIMARY KEY,
            vertex_x INTEGER, vertex_y INTEGER, vertex_z INTEGER, vertex_t INTEGER,
            owner_pattern TEXT,
            metadata_json TEXT,
            media_path TEXT,
            source_url TEXT,
            sha256 TEXT UNIQUE,
            created_at TEXT
        )
        """
    )
    conn.commit()
    return conn


def load_client_from_db(conn: sqlite3.Connection):
    client = get_blockcode_nft_client("interlaterus-main", [0, 0, 0, 0])
    rows = conn.execute("SELECT * FROM blockcode_nft_records").fetchall()
    for r in rows:
        meta = json.loads(r["metadata_json"] or "{}")
        pattern = r["pattern_code"]
        vertex = [r["vertex_x"], r["vertex_y"], r["vertex_z"], r["vertex_t"]]
        if pattern not in client.nft_registry:
            client.nft_registry[pattern] = {
                "pattern_code": pattern,
                "vertex": vertex,
                "owner_pattern": r["owner_pattern"],
                "metadata": meta,
                "metadata_vector": meta.get("audio_vector", [0, 0, 0, 0]),
                "created_at": r["created_at"],
                "transfer_history": [],
            }
    return client


def occupied_vertices(conn: sqlite3.Connection) -> set:
    occ = set()
    for r in conn.execute(
        "SELECT vertex_x, vertex_y, vertex_z, vertex_t FROM blockcode_nft_records"
    ):
        occ.add((r[0], r[1], r[2], r[3]))
    return occ


def pick_vertex(conn: sqlite3.Connection) -> List[int]:
    occ = occupied_vertices(conn)
    for v in TESSERACT_VERTICES:
        t = tuple(v)
        if t not in occ:
            return v
    return TESSERACT_VERTICES[len(occ) % 16]


def append_catalog(entry: Dict[str, Any]) -> None:
    catalog: List[Dict[str, Any]] = []
    if CATALOG_PATH.exists():
        try:
            catalog = json.loads(CATALOG_PATH.read_text())
        except Exception:
            catalog = []
    catalog.append(entry)
    CATALOG_PATH.write_text(json.dumps(catalog, indent=2))


def write_sidecar(media: Path, record: Dict[str, Any]) -> Path:
    sidecar = media.with_suffix(media.suffix + ".interlaterus.json")
    sidecar.write_text(json.dumps(record, indent=2))
    return sidecar


def mint_media_file(
    path: Path,
    source_url: str = "",
    title: str = "",
    owner_pattern: str = OWNER_DEFAULT,
) -> Dict[str, Any]:
    path = path.expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)

    probe = probe_media(path)
    conn = get_db()
    existing = conn.execute(
        "SELECT pattern_code FROM blockcode_nft_records WHERE sha256 = ?",
        (probe["sha256"],),
    ).fetchone()
    if existing:
        conn.close()
        return {
            "status": "already_minted",
            "pattern_code": existing["pattern_code"],
            "sha256": probe["sha256"],
        }

    pattern = pattern_from_digest(probe["sha256"])
    vertex = pick_vertex(conn)
    audio_vector = audio_vector_from_probe(probe)
    display_title = title or path.stem.replace("direct-h264-", "").replace("direct-gif-", "")

    metadata = {
        "title": display_title,
        "artist": "NLS / InterlaterusDesktop",
        "source_url": source_url,
        "media_path": str(path),
        "sha256": probe["sha256"],
        "technical": probe,
        "audio_vector": audio_vector,
        "interstellar_nonlinear": True,
        "gravity_prepared": True,
        "minted_by": "InterlaterusDesktop",
        "stack": [
            "nlsrecords-executive-portfolio/ffmpeg",
            "Blockcode_NLS_Records/tesseract",
            "NLS-Record/catalog",
        ],
    }

    client = load_client_from_db(conn)
    if client.get_nft_by_pattern(pattern):
        suffix = probe["sha256"][:6]
        pattern = f"{pattern}.{suffix}"

    nft = client.mint_nft(
        pattern_code=pattern,
        vertex=vertex,
        owner_pattern=owner_pattern,
        metadata=metadata,
    )

    created = utc_now()
    conn.execute(
        """
        INSERT INTO blockcode_nft_records
        (pattern_code, vertex_x, vertex_y, vertex_z, vertex_t, owner_pattern,
         metadata_json, media_path, source_url, sha256, created_at)
        VALUES (?,?,?,?,?,?,?,?,?,?,?)
        """,
        (
            pattern,
            vertex[0],
            vertex[1],
            vertex[2],
            vertex[3],
            owner_pattern,
            json.dumps(metadata),
            str(path),
            source_url,
            probe["sha256"],
            created,
        ),
    )
    conn.commit()
    conn.close()

    record = {
        "pattern_code": pattern,
        "vertex": vertex,
        "owner_pattern": owner_pattern,
        "nft": nft,
        "probe": probe,
        "minted_at": created,
    }
    write_sidecar(path, record)
    append_catalog(
        {
            "pattern_code": pattern,
            "vertex": vertex,
            "title": display_title,
            "source_url": source_url,
            "media_path": str(path),
            "sha256": probe["sha256"],
            "audio_vector": audio_vector,
            "minted_at": created,
        }
    )
    return {"status": "minted", **record}


def export_ncomm_manifest() -> Path:
    ensure_dirs()
    conn = get_db()
    rows = conn.execute(
        "SELECT pattern_code, vertex_x, vertex_y, vertex_z, vertex_t, "
        "media_path, source_url, sha256, created_at FROM blockcode_nft_records"
    ).fetchall()
    conn.close()
    manifest = {
        "exported_at": utc_now(),
        "origin": "InterlaterusDesktop",
        "transport": "NCOMM/SSH/USB-C (optional)",
        "records": [
            {
                "pattern_code": r["pattern_code"],
                "vertex": [r["vertex_x"], r["vertex_y"], r["vertex_z"], r["vertex_t"]],
                "media_path": r["media_path"],
                "source_url": r["source_url"],
                "sha256": r["sha256"],
                "created_at": r["created_at"],
            }
            for r in rows
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2))
    return MANIFEST_PATH


def list_mints() -> None:
    conn = get_db()
    rows = conn.execute(
        "SELECT pattern_code, vertex_x, vertex_y, vertex_z, vertex_t, "
        "media_path, sha256, created_at FROM blockcode_nft_records ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    if not rows:
        print("No blockcode mints yet.")
        return
    for r in rows:
        v = f"[{r['vertex_x']},{r['vertex_y']},{r['vertex_z']},{r['vertex_t']}]"
        print(f"{r['pattern_code']:28} {v}  {Path(r['media_path']).name}  {r['created_at']}")


def pending_meta_path(media: Path) -> Path:
    return media.with_suffix(media.suffix + ".pending-mint.json")


def read_pending(media: Path) -> Dict[str, Any]:
    p = pending_meta_path(media)
    if p.is_file():
        try:
            return json.loads(p.read_text())
        except Exception:
            pass
    return {}


def watch_downloads(interval: float = 2.0) -> None:
    seen: set[str] = set()
    print(f"InterlaterusDesktop watch: {DOWNLOADS} (patterns: direct-h264/gif)")
    while True:
        for f in sorted(DOWNLOADS.iterdir()):
            if not f.is_file():
                continue
            if not any(p.match(f.name) for p in WATCH_PATTERNS):
                continue
            key = f"{f.name}:{f.stat().st_size}"
            if key in seen:
                continue
            if f.stat().st_size < 1024:
                continue
            pending = read_pending(f)
            try:
                result = mint_media_file(
                    f,
                    source_url=pending.get("source_url", ""),
                    title=pending.get("title", ""),
                )
                seen.add(key)
                print(f"✓ {result['status']}: {result.get('pattern_code', '?')} ← {f.name}")
            except Exception as e:
                print(f"✗ mint failed {f.name}: {e}", file=sys.stderr)
        time.sleep(interval)


def cmd_mint(args: argparse.Namespace) -> int:
    path = Path(args.file)
    result = mint_media_file(path, source_url=args.url or "", title=args.title or "")
    print(json.dumps(result, indent=2))
    return 0 if result.get("status") in ("minted", "already_minted") else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="InterlaterusDesktop vertical NFT/media orchestrator")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_mint = sub.add_parser("mint", help="Probe media + mint blockcode NFT + catalog")
    p_mint.add_argument("--file", required=True, help="Downloaded media file path")
    p_mint.add_argument("--url", default="", help="Source URL")
    p_mint.add_argument("--title", default="", help="Display title")
    p_mint.set_defaults(func=cmd_mint)

    sub.add_parser("list", help="List minted blockcode records").set_defaults(
        func=lambda _: list_mints() or 0
    )
    sub.add_parser("watch", help="Watch ~/Downloads and auto-mint").set_defaults(
        func=lambda _: watch_downloads() or 0
    )
    sub.add_parser("export", help="Export NCOMM sync manifest").set_defaults(
        func=lambda _: print(export_ncomm_manifest()) or 0
    )

    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())