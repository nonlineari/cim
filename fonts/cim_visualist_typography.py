"""
CIM / NLS Visualist typography — Helvetica canon (A. Visualist).

Preserves Standard 14 Helvetica names for ReportLab PDF output and paths
to archived URW NimbusSans substitutes under fonts/CIM-Visualist/Helvetica/.
"""
from pathlib import Path

CIM_ROOT = Path(__file__).resolve().parent.parent
FONT_ARCHIVE = CIM_ROOT / "fonts" / "CIM-Visualist" / "Helvetica" / "NimbusSans"
VISUALIST_DOC = CIM_ROOT / "fonts" / "CIM-Visualist" / "A-VISUALIST.md"

# Standard 14 — ReportLab built-in Helvetica (PDF-safe, offline)
HELVETICA = {
    "regular": "Helvetica",
    "bold": "Helvetica-Bold",
    "italic": "Helvetica-Oblique",
    "bold_italic": "Helvetica-BoldOblique",
    "mono": "Courier",
    "mono_bold": "Courier-Bold",
}

VISUALIST_CREDIT = "NLS Visualist · A. Visualist · Helvetica — CIM / NLS Records"
VISUALIST_HEADER = "NLS Visualist · A. Visualist"
FONT_FAMILY_NAME = "Helvetica"


def archived_nimbus_files():
    """Return list of preserved .afm/.t1 files (Helvetica substitute)."""
    if not FONT_ARCHIVE.is_dir():
        return []
    return sorted(FONT_ARCHIVE.glob("NimbusSans-*"))


def verify_archive():
    required = [
        "NimbusSans-Regular.afm",
        "NimbusSans-Regular.t1",
        "NimbusSans-Bold.afm",
        "NimbusSans-Bold.t1",
    ]
    missing = [n for n in required if not (FONT_ARCHIVE / n).is_file()]
    return len(missing) == 0, missing


if __name__ == "__main__":
    ok, missing = verify_archive()
    print(f"Helvetica archive: {'OK' if ok else 'MISSING ' + str(missing)}")
    print(f"Faces: {HELVETICA}")
    print(f"Credit: {VISUALIST_CREDIT}")
    print(f"Archived files: {len(archived_nimbus_files())}")