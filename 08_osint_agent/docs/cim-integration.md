# CIM Integration — NLS OSINT Agent STEM

## How it sits in the architecture

```
Conversation Entity Archive (CIM)
├── 04_rand_blockcode/          ← Java BlockCode engine
│   └── src/com/nls/rand/osint/OSINTAgentBlock.java
├── 07_conversation_entity/     ← manifests / generation
└── 08_osint_agent/             ← THIS STEM (knowledge + persona)
    ├── agent/                  ← Grok system prompts EN/FR
    └── modules/                ← Best OSINT resources nodules
```

## Registration

`BlockRegistry` now includes:

```java
register(new OSINTAgentBlock());
```

## Example pipeline step

```json
{
  "block": "osint_agent",
  "params": {
    "stem": "technology",
    "query": "hk music label competitor monitoring",
    "lang": "fr",
    "module": "blogs"
  }
}
```

## Downstream effects

- Sets `osint_agent_loaded = true` in BlockContext
- Writes `stem_path` of form `T/osint/<duplex>`
- Exposes prompt path + index.json for Visualist / hierarchy_interpreter / Grok hosts
- Compatible with NLS Visualist bridge and conversation entity minting

## Activation patterns

1. **Grok persona** — paste `SYSTEM_PROMPT_FR.md` (or EN)
2. **Java pipeline** — add `osint_agent` step or use `pipeline-osint.json`
3. **Python / hierarchy** — load `modules/index.json`
4. **Studio** — drop folder into Xserve/Mac Mini knowledge base

## Version

1.0.0 — initial CIM STEM integration · 2026-07-22
