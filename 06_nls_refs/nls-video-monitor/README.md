# NLS Video Monitor — InterlaterusDesktop Vertical Stack

Desktop-grade media pipeline for **NLS Visualist** workflows: download H.264, probe with **ffprobe**, mint **Blockcode NFT** records, catalog media, and optionally stream live job state over the **Gravity** protocol.

## What this is

Three layers work together:

| Layer | Component | Role |
|-------|-----------|------|
| **Desktop client** | `GravityDesktop.java` | Swing UI, direct yt-dlp downloads, remote PHP viewers, auto-mint hook |
| **Vertical orchestrator** | `interlaterus_desktop.py` | ffprobe → blockcode mint → `nls_media_catalog.json` → NCOMM export |
| **Pipeline backend** | `nls_video_pipe.py` | Job queue, ffmpeg convert, web/TUI monitor, `gravity-server` / `gravity-client` |

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        InterlaterusDesktop (vertical)                    │
├─────────────────────────────────────────────────────────────────────────┤
│  GravityDesktop  →  yt-dlp  →  ~/Downloads/direct-h264-*.mp4          │
│        │                    ffprobe (probe)                              │
│        └──────────►  blockcode_nft_client.mint_nft()                    │
│                              │                                           │
│                              ▼                                           │
│                    nls_media_catalog.json + SQLite registry              │
│                              │                                           │
│                              ▼                                           │
│                    ncomm_export_manifest.json (optional sync)            │
└─────────────────────────────────────────────────────────────────────────┘
         ▲                                    ▲
         │ JSON gravity_update (port 4242)    │ worker / serve (8765)
         │                                    │
    gravity-server                      nls-video worker
```

## Quick start

### GravityDesktop (primary UI)

```bash
# Run directory (bundled yt-dlp + launch scripts)
~/Downloads/GravityDesktop/run.sh

# Dependency check
~/Downloads/GravityDesktop/check-paths.sh
```

Paste or drag a URL into the input bar → H.264 MP4 lands in `~/Downloads/direct-h264-<id>.mp4` → Interlaterus auto-mints (unless `INTERLATERUS_SKIP_MINT=1`).

### InterlaterusDesktop (mint / watch / export)

```bash
~/Downloads/GravityDesktop/run-interlaterus.sh watch   # auto-mint new downloads
~/Downloads/GravityDesktop/run-interlaterus.sh list    # SQLite registry
~/Downloads/GravityDesktop/run-interlaterus.sh export    # NCOMM manifest
```

### NLS Video Pipeline (full convert + monitor)

```bash
cd ~/Downloads/nls-video-monitor
./install.sh

nls-video add "https://www.youtube.com/watch?v=VIDEO_ID" --preset balanced-4k
nls-video worker                    # download + ffmpeg in background
nls-video serve                     # web dashboard :8765
nls-video gravity-server --port 4242   # live feed for GravityDesktop
nls-video gravity-client            # terminal equivalent of GravityDesktop
```

## Data outputs

| Artifact | Path | Purpose |
|----------|------|---------|
| Direct downloads | `~/Downloads/direct-h264-*.mp4`, `direct-gif-*.gif` | Raw yt-dlp output |
| Blockcode registry | `~/.local/share/interlaterus-desktop/blockcode_registry.db` | SQLite NFT records |
| NLS media catalog | `~/.local/share/interlaterus-desktop/nls_media_catalog.json` | JSON catalog for Visualist tools |
| NCOMM manifest | `~/.local/share/interlaterus-desktop/ncomm_export_manifest.json` | Portable sync manifest |
| Per-file sidecar | `<file>.mp4.interlaterus.json` | Mint record next to media |
| Visualist catalog | `~/.local/share/nls-video/visualist_catalog.json` | Full pipeline completions |
| Per-job sidecar | `<Title> [ID].nlsvis.json` | Worker metadata |

## Tool chain

| Tool | Used by | Function |
|------|---------|----------|
| **yt-dlp** | GravityDesktop, nls-video worker | Download; `--list-formats` pre-check |
| **ffmpeg** | GravityDesktop (VP56 rotate), nls-video worker | H.264 encode, GIF, libvpx VP56 |
| **ffprobe** | interlaterus_desktop, nls-video worker | Duration, codecs, bitrate, SHA256 input |
| **ffplay** | Manual / optional | Preview finished media (`ffplay ~/Downloads/direct-h264-*.mp4`) |
| **gravity-server** | nls_video_pipe | NoiseProtocol handshake + JSON job/catalog stream |
| **gravity-client** | nls_video_pipe | Rich TUI mirror of GravityDesktop panels |

## Documentation map

| Doc | Contents |
|-----|----------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System + vertical architecture, gravity protocol, diagrams |
| [INTERLATERUS.md](INTERLATERUS.md) | Mint flow, watch mode, catalog schema, data analysis |
| [BLOCKCODE_NFT_CLIENT.md](BLOCKCODE_NFT_CLIENT.md) | Tesseract geometry, pattern codes, mint API |
| [GRAVITYDESKTOP_JAVA.md](GRAVITYDESKTOP_JAVA.md) | Swing UI, yt-dlp, cookies, remote nav, rate limits |
| [AnalogOnAnalog.md](AnalogOnAnalog.md) | Analog-on-analog theory tie-in (audio/media layering) |
| [Installation.md](Installation.md) | Dependencies, paths, Deno, cookies, troubleshooting |

## Example mint (verified)

File: `direct-h264-04gz1ZId5VI.mp4`

| Field | Value |
|-------|-------|
| Pattern | `ABAB.2:4.P←B.F3` |
| Vertex | `[0, 0, 0, 0]` |
| audio_vector | `[duration_norm, size_norm, bitrate_norm, aspect]` from ffprobe |
| Status | `minted` → sidecar + catalog + SQLite |

## Repository layout

```
nls-video-monitor/
├── GravityDesktop.java          # Swing gravity client + yt-dlp
├── interlaterus_desktop.py      # Vertical orchestrator
├── blockcode_nft_client.py      # Tesseract NFT client
├── nls_video_pipe.py            # Pipeline, gravity-server/client
├── hierarchy_interpreter.py     # 11D hierarchy explorer
├── install.sh                   # Link nls-video to ~/.local/bin
├── visual_language_animation.svg
└── docs: ARCHITECTURE.md, INTERLATERUS.md, …

~/Downloads/GravityDesktop/      # Runtime (bundled yt-dlp, run.sh)
```

## Environment variables (summary)

| Variable | Default | Effect |
|----------|---------|--------|
| `YTDLP_PATH` | bundled `~/Downloads/GravityDesktop/yt-dlp` | yt-dlp binary |
| `FFMPEG_PATH` / `FFPROBE_PATH` | `/usr/bin/…` | Media tools |
| `GRAVITY_COOKIES_BROWSER` | auto-detect brave/chromium/chrome/firefox | Age-restricted content |
| `GRAVITY_PROXY` / `GRAVITY_GEO_PROXY` | unset | VPN/proxy bypass |
| `GRAVITY_MIN_SLEEP_INTERVAL` | 3 | Human-like yt-dlp pacing |
| `INTERLATERUS_SKIP_MINT` | unset | Skip post-download mint |
| `GRAVITY_REMOTE_BASE` | unset | PHP remote viewer base URL |

## Principles

- **no kill, no eval** — ProcessBuilder with fixed argv; no shell injection
- **H.264 first** — MP4 with `avc`/`avc1`; avoids AV1 WebM VLC issues
- **Deterministic blockcode** — Pattern from SHA256; vertex from tesseract occupancy
- **Dual catalogs** — Interlaterus (`nls_media_catalog.json`) + nls-video (`visualist_catalog.json`)

## Related nonlineari repos

Blockcode geometry derives from [nonlineari/Blockcode_NLS_Records](https://github.com/nonlineari/Blockcode_NLS_Records). NCOMM transport is optional export; no Counter-Strike or dedicated floating-point stack was found in the audited nonlineari portfolio (FP appears in audio/ML contexts only).

---

Source repo: `~/Downloads/nls-video-monitor` · Run dir: `~/Downloads/GravityDesktop`