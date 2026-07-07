package com.nls.rand.nls;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;

import java.util.Map;

/**
 * NLS — bridge pipeline output to Visualist catalog JSON fragment.
 */
public final class NLSVisualistBridge implements Block {
    @Override
    public String id() {
        return "nls_visualist_bridge";
    }

    @Override
    public String system() {
        return "nls";
    }

    @Override
    public BlockResult execute(BlockContext ctx) {
        String catalog = ctx.config().get("catalog", "nls_media_catalog.json");
        String stemPath = ctx.has("stem_path") ? ctx.get("stem_path") : "E/7-4a.1-2b.0";
        String spoutFrame = ctx.has("spout_frame") ? ctx.get("spout_frame") : "spout://unset";
        String pipelineName = ctx.has("pipeline_name") ? ctx.get("pipeline_name") : "rand_blockcode";

        String entry = String.format(
                "{\"pipeline\":\"%s\",\"stem_path\":\"%s\",\"frame\":\"%s\",\"catalog\":\"%s\"}",
                pipelineName, stemPath, spoutFrame, catalog
        );

        ctx.put("visualist_entry", entry);
        ctx.put("visualist_catalog", catalog);

        return BlockResult.ok(
                "NLSVisualistBridge wrote catalog entry → " + catalog,
                Map.of("catalog", catalog, "stem_path", stemPath)
        );
    }
}