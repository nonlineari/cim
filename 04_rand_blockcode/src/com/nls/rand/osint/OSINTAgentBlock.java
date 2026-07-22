package com.nls.rand.osint;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;
import com.nls.rand.blockcode.STEMModule;

import java.util.Map;

/**
 * NLS OSINT Agent STEM — loads modular Best OSINT resources knowledge base
 * and tags the pipeline with OSINT / GEOINT / SOCMINT / CTI hierarchy.
 *
 * Integrates the nls-osint-agent (YouTube, Newsletters, Blogs, Podcasts, CTFs)
 * as a Conversation Entity layer inside CIM.
 *
 * Pipeline notation extension:
 *   RAND System B \ RAND System A | NLS YOLODarket STEM | NLS OSINT Agent STEM
 */
public final class OSINTAgentBlock implements Block {

    @Override
    public String id() {
        return "osint_agent";
    }

    @Override
    public String system() {
        return "nls";
    }

    @Override
    public BlockResult execute(BlockContext ctx) {
        // Default to TECHNOLOGY (T) for OSINT / intelligence ops; allow override
        String stemLabel = ctx.config().get("stem", "technology");
        STEMModule module = STEMModule.fromLabel(stemLabel);

        String query = ctx.config().get("query", "osint");
        String lang = ctx.config().get("lang", "en");          // en | fr
        String moduleId = ctx.config().get("module", "all");   // youtube|newsletters|blogs|podcasts|ctfs|all

        String duplexId = ctx.has("duplex_id") ? ctx.get("duplex_id") : "osint-7.4a.1";
        String stemPath = module.code() + "/osint/" + duplexId;

        // Context enrichment for downstream Visualist / hierarchy interpreter
        ctx.put("stem_module", module);
        ctx.put("stem_path", stemPath);
        ctx.put("osint_query", query);
        ctx.put("osint_lang", lang);
        ctx.put("osint_module", moduleId);
        ctx.put("osint_agent_loaded", true);
        ctx.put("osint_index", "08_osint_agent/modules/index.json");
        ctx.put("osint_prompt", "en".equalsIgnoreCase(lang)
                ? "08_osint_agent/agent/SYSTEM_PROMPT_EN.md"
                : "08_osint_agent/agent/SYSTEM_PROMPT_FR.md");

        String cap = "OSINTAgentBlock [" + lang.toUpperCase() + "] loaded module=" + moduleId
                + " query=\"" + query + "\" → " + stemPath;

        return BlockResult.ok(
                cap,
                Map.of(
                        "stem", module.label(),
                        "code", module.code(),
                        "stem_path", stemPath,
                        "osint_query", query,
                        "osint_lang", lang,
                        "osint_module", moduleId,
                        "agent", "NLS OSINT Agent"
                )
        );
    }
}
