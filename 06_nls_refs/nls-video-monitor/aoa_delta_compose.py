#!/usr/bin/env python3
"""
AOA | NLS Visualist — LIFO 16→0 delta program mechanism.

17 grok_report PDFs:
  slice 0  → grok_report.pdf      (axiom / program origin)
  slice 1…16 → grok_report-N.pdf (16 wedges × 22.5° = 360°)

LIFO pop order: 16, 15, …, 1, 0 (top of stack first).

Each pop computes a delta against the previous composite (Analog on Analog).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

SLICES_PER_360 = 16
DEG_PER_SLICE = 360.0 / SLICES_PER_360
DEFAULT_REPORT_DIR = Path.home() / "Downloads"
XDG_AOA = Path.home() / ".local" / "share" / "nls-video"
AOA_DELTA_PATH = XDG_AOA / "aoa-delta.json"
AOA_DELTA_PROOF_PATH = XDG_AOA / "aoa-delta-proof.json"


def _vertex_from_index(n: int) -> List[int]:
    """Map slice 1..16 → tesseract vertex (4-bit, 16 vertices)."""
    if n < 1 or n > 16:
        return [0, 0, 0, 0]
    v = n - 1
    return [(v >> b) & 1 for b in (3, 2, 1, 0)]


def _angle_wedge(slice_index: int) -> Dict[str, float]:
    """Angular wedge for slice 1..16; slice 0 is axiom at 0°."""
    if slice_index == 0:
        return {"start": 0.0, "end": DEG_PER_SLICE, "center": DEG_PER_SLICE / 2, "role": "axiom"}
    start = (slice_index - 1) * DEG_PER_SLICE
    end = slice_index * DEG_PER_SLICE
    center = start + DEG_PER_SLICE / 2
    return {"start": start, "end": end % 360, "center": center % 360, "role": "wedge"}


def _pdf_pages(path: Path) -> int:
    try:
        out = subprocess.run(["pdfinfo", str(path)], capture_output=True, text=True, timeout=10)
        for line in out.stdout.splitlines():
            if line.startswith("Pages:"):
                return int(line.split(":", 1)[1].strip())
    except Exception:
        pass
    return 0


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _delta_layer(prev_sha: str, curr_sha: str, meta: Dict[str, Any]) -> Dict[str, Any]:
    """AOA delta: discrete digest delta between analog layers."""
    combined = f"{prev_sha}:{curr_sha}".encode()
    delta_digest = hashlib.sha256(combined).hexdigest()
    xor_prefix = "".join(f"{int(a, 16) ^ int(b, 16):x}" for a, b in zip(prev_sha[:16], curr_sha[:16]))
    return {
        "delta_digest": delta_digest,
        "delta_xor_prefix": xor_prefix,
        "from_sha256": prev_sha,
        "to_sha256": curr_sha,
        "slice": meta,
    }


def resolve_report_paths(report_dir: Optional[Path] = None) -> Dict[int, Path]:
    root = report_dir or DEFAULT_REPORT_DIR
    paths: Dict[int, Path] = {0: root / "grok_report.pdf"}
    for i in range(1, 17):
        paths[i] = root / f"grok_report-{i}.pdf"
    return paths


def compose_aoa_delta(report_dir: Optional[Path] = None, write: bool = True) -> Dict[str, Any]:
    paths = resolve_report_paths(report_dir)
    missing = [i for i, p in paths.items() if not p.is_file()]
    if missing:
        return {"ok": False, "error": f"Missing slices: {missing}", "report_dir": str(report_dir or DEFAULT_REPORT_DIR)}

    # Build slice records indexed 0..16
    slices: Dict[int, Dict[str, Any]] = {}
    for idx, path in paths.items():
        sha = _file_sha256(path)
        slices[idx] = {
            "slice_index": idx,
            "file": path.name,
            "path": str(path),
            "pages": _pdf_pages(path),
            "sha256": sha,
            "size_bytes": path.stat().st_size,
            "angle_deg": _angle_wedge(idx),
            "vertex_4d": _vertex_from_index(idx) if idx else None,
            "aoa_role": "axiom" if idx == 0 else "analog_layer",
        }

    # LIFO 16 → 0
    lifo_order = list(range(16, -1, -1))
    stack: List[Dict[str, Any]] = []
    deltas: List[Dict[str, Any]] = []
    composite_sha = hashlib.sha256(b"AOA|NLS-Visualist|axiom:utc").hexdigest()

    for pop_i, slice_idx in enumerate(lifo_order):
        layer = dict(slices[slice_idx])
        layer["lifo_pop_order"] = pop_i
        prev_composite = composite_sha
        layer_sha = layer["sha256"]
        delta = _delta_layer(prev_composite, layer_sha, {
            "slice_index": slice_idx,
            "lifo_pop_order": pop_i,
            "angle_center": layer["angle_deg"]["center"],
        })
        deltas.append(delta)
        composite_sha = hashlib.sha256(f"{composite_sha}:{layer_sha}".encode()).hexdigest()
        layer["composite_sha256_after"] = composite_sha
        stack.append(layer)

    proof_body = json.dumps(
        {"lifo": lifo_order, "deltas": [d["delta_digest"] for d in deltas], "composite": composite_sha},
        sort_keys=True,
    )
    proof_digest = hashlib.sha256(proof_body.encode()).hexdigest()

    payload: Dict[str, Any] = {
        "ok": True,
        "program": "AOA | NLS Visualist",
        "mechanism": "LIFO_delta_compose",
        "axiom": {
            "time": "utc",
            "slice_0": "grok_report.pdf",
            "slices_per_360": SLICES_PER_360,
            "deg_per_slice": DEG_PER_SLICE,
        },
        "lifo_pop_order": lifo_order,
        "stack": stack,
        "deltas": deltas,
        "composite_sha256": composite_sha,
        "proof_digest": proof_digest,
        "summary": {
            "total_slices": 17,
            "angular_slices": 16,
            "total_pages": sum(s["pages"] for s in slices.values()),
            "total_bytes": sum(s["size_bytes"] for s in slices.values()),
        },
    }

    if write:
        XDG_AOA.mkdir(parents=True, exist_ok=True)
        AOA_DELTA_PATH.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        AOA_DELTA_PROOF_PATH.write_text(
            json.dumps({"proof_digest": proof_digest, "composite_sha256": composite_sha, "path": str(AOA_DELTA_PATH)}, indent=2),
            encoding="utf-8",
        )
        payload["written"] = str(AOA_DELTA_PATH)
        payload["proof_path"] = str(AOA_DELTA_PROOF_PATH)

    return payload


def main() -> None:
    import argparse

    p = argparse.ArgumentParser(description="AOA LIFO 16→0 delta compose — grok_report PDF stack")
    p.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    p.add_argument("--json", action="store_true")
    p.add_argument("--no-write", action="store_true")
    args = p.parse_args()
    result = compose_aoa_delta(args.report_dir, write=not args.no_write)
    if args.json:
        print(json.dumps(result, indent=2))
    elif result.get("ok"):
        s = result["summary"]
        print("AOA | NLS Visualist — LIFO delta compose OK")
        print(f"  16 slices × {DEG_PER_SLICE}° = 360°  +  slice 0 axiom")
        print(f"  LIFO pop: 16 → 0  ({len(result['lifo_pop_order'])} layers)")
        print(f"  Pages: {s['total_pages']}  Bytes: {s['total_bytes']}")
        print(f"  Composite: {result['composite_sha256'][:32]}…")
        print(f"  Proof:     {result['proof_digest'][:32]}…")
        if result.get("written"):
            print(f"  Delta:     {result['written']}")
    else:
        print(result.get("error", "compose failed"))
        raise SystemExit(1)


if __name__ == "__main__":
    main()