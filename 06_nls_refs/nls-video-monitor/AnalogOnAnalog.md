# Analog on Analog (AoA)

Conceptual framework tying the NLS Video Monitor stack to **nonlineari** portfolio themes: layered signal processing where each stage operates on the output of the previous **analog** (continuous/media) domain without collapsing provenance.

## Definition

**Analog on Analog** means:

1. **Source analog** — raw URL / remote PHP stream / IPFS gateway (continuous media intent)
2. **Capture analog** — yt-dlp preserves best-effort H.264 elementary flow into MP4 container
3. **Analysis analog** — ffprobe reads continuous timing (duration, bitrate) without re-encoding
4. **Address analog** — blockcode maps probe floats → `audio_vector` on tesseract vertices
5. **Catalog analog** — JSON/SQLite layers accumulate without destroying prior representations

Each layer **reads** the previous layer's analog properties; only optional branches (ffmpeg CRF encode, VP56 transcode) introduce lossy re-quantization.

## AoA in this codebase

```
URL (intent)
  └─► yt-dlp → MP4 bitstream     [capture analog]
        └─► ffprobe → durations   [measurement analog]
              └─► SHA256 → pattern [discrete address on continuous hash]
                    └─► audio_vector [4D embedding of probe floats]
                          └─► catalog JSON [semantic analog]
```

### Parallel AoA path (nls-video worker)

```
URL → yt-dlp source → ffmpeg libx264 → .nlsvis.json → visualist_catalog.json
                              └─► optional .h264 gravity stream (noise-packet analog)
```

## Audio-on-audio (NLS Records lineage)

In [Blockcode_NLS_Records](https://github.com/nonlineari/Blockcode_NLS_Records), blockcode patterns historically addressed **audio** releases. InterlaterusDesktop extends the same geometry to **video**:

| NLS audio tradition | Video extension (this repo) |
|---------------------|----------------------------|
| Track duration | `duration_sec` |
| Sample rate / bit depth | `bitrate`, `acodec` |
| Waveform features | `audio_vector` (probe-derived) |
| Album pattern code | `pattern_from_digest(sha256)` |

The name `audio_vector` is retained intentionally — video mints are **media-agnostic** blockcode records.

## Floating-point usage

Floating point appears only in **measurement and embedding** layers, not as a dedicated CS/game stack:

| Location | FP role |
|----------|---------|
| `audio_vector_from_probe()` | Normalized duration, size, bitrate, aspect |
| `nls_video_pipe.py` convert progress | `duration` from ffprobe for % calc |
| nonlineari `EXPONENTIAL_UNCERTAINTY_THEORY.md` | Theoretical uncertainty (external) |
| nonlineari `NCOMM/m2l_protocol.py` | `np.clip` on Hénon map (external) |

No Counter-Strike or FP-specific game architecture was found in audited nonlineari repos.

## Hierarchy mapping (11D)

`hierarchy_interpreter.py` maps AoA stages to levels 11→1:

| Level | AoA stage |
|-------|-----------|
| 11 Pure Form | Original URL / creative intent |
| 10 Geometry | Aspect ratio, ASC thumbnails |
| 9 Numeric | Bitrate, duration floats |
| 8 Encoding/DNA | H.264 NAL / SHA256 digest |
| 6 Waves | audio_vector oscillation |
| 1 The Way | Final catalog entry |

Run: `nls-video hierarchy` or `python3 hierarchy_interpreter.py`

## Interstellar | nonlineari branch

When `interstellar_nonlinear` metadata is set, storage memory category shifts to `interstellar-zone-alpha` and optional VP56 gravity prep applies — an **alternate analog** (legacy codec aesthetic) stacked on the H.264 base:

```
H.264 MP4  ──►  libvpx VP56 .vp56.webm  ──►  raw packet bin (gravity)
```

GravityDesktop exposes VP56 via ffmpeg `libvpx` when dual-video checkbox is enabled.

## Design principles

1. **Provenance chain** — Every catalog entry links `source_url` → `sha256` → `pattern_code`
2. **Non-destructive probe** — ffprobe before any optional re-encode
3. **Deterministic address** — Same bytes → same pattern (modulo vertex occupancy)
4. **Layer independence** — Interlaterus catalog ≠ visualist catalog; both valid AoA stacks

## Summary

Analog on Analog describes how NLS Video Monitor stacks **continuous media operations** (download, probe, optional transcode) with **discrete blockcode addressing** without forcing a single canonical representation. GravityDesktop handles human-facing acquisition; InterlaterusDesktop crystallizes probe data into tesseract NFTs; nls-video worker adds broadcast-grade H.264 conversion for the Visualist archive.

See [ARCHITECTURE.md](ARCHITECTURE.md) for system diagrams and [INTERLATERUS.md](INTERLATERUS.md) for mint data analysis.