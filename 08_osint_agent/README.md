# 08_osint_agent — NLS OSINT Agent STEM inside CIM

**Version 1.0.0** · 2026-07-22 · NLS Records / @nlsrecords

Integrates the **Best OSINT resources** modular knowledge base (YouTube · Newsletters · Blogs · Podcasts · CTFs) as a first-class **STEM layer** in the Common Information Model.

## Pipeline notation (extended)

```
RAND System B \ RAND System A | NLS YOLODarket STEM | NLS OSINT Agent STEM
```

1. RAND System A — stacking foundation  
2. RAND System B — collision overlay  
3. NLS YOLODarket STEM — vision + hierarchy  
4. **NLS OSINT Agent STEM** — intelligence knowledge + Grok persona (EN/FR)

## Structure

```
08_osint_agent/
├── README.md                 # this file
├── agent/
│   ├── SYSTEM_PROMPT_EN.md   # Grok system prompt (English)
│   └── SYSTEM_PROMPT_FR.md   # Prompt système francisé
├── modules/
│   ├── index.json            # machine-readable module catalog
│   ├── youtube.md
│   ├── newsletters.md
│   ├── blogs.md
│   ├── podcasts.md
│   └── ctfs.md
└── docs/
    └── cim-integration.md
```

## Java Block

- **Class:** `com.nls.rand.osint.OSINTAgentBlock`
- **id:** `osint_agent`
- **system:** `nls`
- Registered in `BlockRegistry`
- Optional pipeline step (see `04_rand_blockcode/blocks/pipeline-osint.json`)

### Params

| Param    | Default      | Description                          |
|----------|--------------|--------------------------------------|
| stem     | technology   | STEMModule label (T recommended)     |
| query    | osint        | Free-text investigation focus        |
| lang     | en           | en \| fr                             |
| module   | all          | youtube / newsletters / blogs / podcasts / ctfs / all |

## Quick load (Grok / host)

```bash
# From CIM root
cat 08_osint_agent/agent/SYSTEM_PROMPT_FR.md   # or EN
# paste into Grok custom instructions
```

Or via hierarchy interpreter / Python host:

```python
import json
with open("08_osint_agent/modules/index.json") as f:
    osint = json.load(f)
print(osint["modules"])
```

## Source

- Upstream: https://github.com/nonlineari/nls-osint-agent
- Original curation: OSINTTEAM Best OSINT resources
- CIM packaging: NLS / Grok constructor

## License

Curated public resources + modular packaging under CIM / MIT / CC-BY-NC (NLS). See root LICENSE files.
