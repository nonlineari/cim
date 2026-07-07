#!/usr/bin/env python3
"""Inject git metadata into index.htm Serve Hub (between GIT_META markers)."""
import re
import subprocess
from pathlib import Path

DIR = Path(__file__).resolve().parent
CIM_ROOT = DIR.parent.parent  # …/CIM/06_nls_refs/nls-video-monitor → CIM
INDEX = DIR / "index.htm"
VERSION_FILE = CIM_ROOT / "VERSION"


def git(*args: str) -> str:
    try:
        return subprocess.check_output(["git", *args], cwd=CIM_ROOT, text=True).strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return ""


def main() -> None:
    version = VERSION_FILE.read_text().strip() if VERSION_FILE.is_file() else "?"
    commit = git("log", "-1", "--format=%h %s")
    branch = git("branch", "--show-current") or "main"
    tags = git("tag", "-l") or "(none)"
    dirty = "dirty" if git("status", "--porcelain") else "clean"

    block = f"""    <div class="panel git-meta" id="git-meta">
      <strong>Git review</strong> · branch <code>{branch}</code> · tree <code>{dirty}</code><br>
      <strong>Version</strong> <code>{version}</code><br>
      <strong>Latest</strong> <code>{commit or "n/a"}</code><br>
      <strong>Tags</strong> <code>{tags.replace(chr(10), ", ")}</code>
    </div>"""

    html = INDEX.read_text(encoding="utf-8")
    pattern = r"<!-- GIT_META_START -->.*?<!-- GIT_META_END -->"
    replacement = f"<!-- GIT_META_START -->\n{block}\n    <!-- GIT_META_END -->"
    if not re.search(pattern, html, re.DOTALL):
        raise SystemExit("index.htm missing GIT_META markers")
    INDEX.write_text(re.sub(pattern, replacement, html, count=1, flags=re.DOTALL), encoding="utf-8")
    print(f"Updated {INDEX} — v{version} {commit}")


if __name__ == "__main__":
    main()