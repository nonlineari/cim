#!/usr/bin/env python3
"""
Concise Interactive 11D Hierarchy: Streamlined Prompts & Flow (Levels 11→1)
Integrated into NLS Video / Visualist system.

Concise version with abbreviated commands (n/e/a/s/q).
Ties into NLS Visualist aesthetics: ASC/FILMIC, gravity, interstellar|nonlineari, H.264 pipeline stages.
Levels map to creative/manifestation process (source → geometry → numeric → encoding/DNA → waves → elements → final form).

Multimedia: ANSI colors, ASCII art, "animation".
KISS: Simple, no external deps. Uses rich if available.

Run standalone:
  python3 hierarchy_interpreter.py

Or via nls-video:
  nls-video hierarchy
"""

import time
import sys
from typing import Optional

# Try rich for better output (consistent with nls_video_pipe.py)
try:
    from rich.console import Console
    from rich.text import Text
    RICH_AVAILABLE = True
    console = Console()
except ImportError:
    RICH_AVAILABLE = False
    console = None

# ANSI colors for fallback multimedia terminal "visualization"
class C:
    P = '\033[95m'  # Purple
    C = '\033[96m'  # Cyan
    B = '\033[94m'  # Blue
    G = '\033[92m'  # Green
    Y = '\033[93m'  # Yellow
    R = '\033[91m'  # Red
    BD = '\033[1m'  # Bold
    UL = '\033[4m'  # Underline
    E = '\033[0m'   # End

# Compact ASCII representations for key levels (enhanced with Visualist flavor)
ART = {
    11: "∞ FORM ∞\n• • •",
    10: "⊙ GEOM ⊙\n● ● ●",
    9: "₉₃₆\n₈₁₄\n₇₅₂",
    8: "╱╲\n╱ ╲\n╱  ╲",
    6: "~~~~~\n∼∼∼∼∼",
    1: "☯ WAY ☯",
}

def desc(l: int) -> str:
    """Core Level Descriptions, mapped to NLS Visualist / H.264 / Gravity themes (concise)."""
    d = {
        11: "Pure Form: Source blueprint (original video / intent).",
        10: "Geometric: Patterns, ratios (ASC cinematic thumbnails, film grain).",
        9: "Numeric: Vib keys, harmonics (gematria, gravity keys, noiseprotocol).",
        8: "DNA: Genetic helix code (H.264 elementary + VP56 gravity prep).",
        7: "Network: Interconnects all (interstellar|nonlineari, SCIS gravity).",
        6: "Waves: Vib propagation (audio/video waves in yt-dlp + ffmpeg).",
        5: "Elements: Matter blocks (raw H.264 pixels, physical output).",
        4: "Time: Sequence & cycles (ffmpeg duration, processing time).",
        3: "Human: Conscious bridge (NLS Visualist creator / observer).",
        2: "Journey: Soul evolution (download→convert→catalog path).",
        1: "Way: Unified harmony (final cataloged piece in NLS-Visualist).",
    }
    return d.get(l, "???")

def print_rich(text: str, style: str = ""):
    """Helper for rich or fallback printing."""
    if RICH_AVAILABLE and console:
        console.print(text, style=style)
    else:
        print(text)

# Animation (Timed Descent)
def anim(s: int, t: int):
    print(f"{C.C}Desc: [{11-s+1}→{11-s}]{C.E}")
    for _ in range(3):
        sys.stdout.write(f"{C.B}.{C.E}")
        sys.stdout.flush()
        time.sleep(0.3)
    print()

# Traversal Engine (Concise Prompts: n/e/a/s/q)
def trav(dir: str = "d"):
    print(f"{C.BD}{C.UL}11D Explorer (NLS Visualist Edition){C.E}")
    print("Manifestation path: 11 (Pure Form / Source) → 1 (The Way / Final Cataloged Piece)")
    print("Cmds: n (next), e (explain), a (art), s (skip), q (quit)\n")
    
    time.sleep(0.5)
    
    cur = 11 if dir == "d" else 1
    stp = -1 if dir == "d" else 1
    end = 0 if dir == "d" else 12
    
    while cur != end:
        if dir == "d":
            anim(11 - cur, 11)
        
        print(f"{C.P}Lvl {cur}: {desc(cur).split(':')[0]}{C.E}")
        print(f"{C.Y}{desc(cur)}{C.E}\n")
        
        if cur in ART:
            print(f"{C.G}{ART[cur]}{C.E}")
        
        while True:
            try:
                ui = input(f"{C.C}→ [n/e/a/s/q]: {C.E}").strip().lower()
            except (EOFError, KeyboardInterrupt):
                print_rich("\nJourney interrupted. Return when ready.", "red")
                return
            
            if ui in ["n", ""]:
                break
            elif ui == "e":
                print(f"{C.BD}Deeper Explanation:{C.E}")
                print(f"   • Builds {'from' if dir == 'd' else 'toward'} Level {cur + stp}")
                print(f"   • Interpreter layer for {'lower physical' if dir == 'd' else 'higher spiritual'} manifestations.")
                print(f"   • In NLS Visualist terms: maps to {'source geometry / encoding' if cur > 6 else 'human experience / final integration'}.\n")
            elif ui == "a" and cur in ART:
                print(f"{C.G}{ART[cur]}{C.E}")
            elif ui == "s":
                print(f"{C.Y}Skipping detailed view...{C.E}")
                break
            elif ui == "q":
                print(f"{C.R}Journey ended early. The Way remains.{C.E}")
                return
            else:
                print(f"{C.R}Unknown. Use: n/e/a/s/q{C.E}")
        
        cur += stp
    
    print(f"\n{C.BD}{C.P}══════════════════════════════════{C.E}")
    if dir == "d":
        print(f"{C.BD}{C.Y}You have reached Level 1: The Way{C.E}")
        print(f"{C.BD}{C.G}Full manifestation achieved. Your video is now cataloged Visualist data.{C.E}")
    else:
        print(f"{C.BD}{C.Y}You have reached Level 11: Pure Form{C.E}")
        print(f"{C.BD}{C.G}Return to Source complete. The blueprint is clear.{C.E}")
    print(f"{C.BD}{C.P}══════════════════════════════════{C.E}\n")

# Ascension Mode (reverse journey)
def asc():
    print(f"{C.BD}Now initiating ASCENSION mode: 1 → 11 (Return to Pure Form / Source){C.E}")
    trav("a")

# Main Interactive Launcher (Concise Menu)
def main():
    print(f"{C.BD}11-Dimensional Hierarchy Interactive System{C.E}")
    print("NLS Visualist / Gravity / H.264 Edition\n")
    print("1. Descend  (11 → 1) – Manifestation from Source to Physical / Catalog")
    print("2. Ascend   (1 → 11) – Return to Pure Form / Source")
    print("3. Auto-run (fast non-interactive descent)")
    print("4. Quit")
    
    try:
        ch = input(f"{C.C}Enter choice (1/2/3/4): {C.E}").strip()
    except (EOFError, KeyboardInterrupt):
        print_rich("\nExiting.", "red")
        return
    
    if ch == "1":
        trav("d")
    elif ch == "2":
        asc()
    elif ch == "3":
        print(f"{C.Y}Auto-running full descent (non-interactive)...{C.E}")
        for lvl in range(11, 0, -1):
            print(f"Level {lvl}: {desc(lvl)}")
            if lvl in ART:
                print(ART[lvl])
            time.sleep(0.5)
        print(f"\n{C.G}Journey complete.{C.E}")
    elif ch == "4":
        print_rich("The hierarchy awaits your return.", "dim")
    else:
        print(f"{C.R}Invalid choice. Restarting...{C.E}")
        main()

if __name__ == "__main__":
    main()
