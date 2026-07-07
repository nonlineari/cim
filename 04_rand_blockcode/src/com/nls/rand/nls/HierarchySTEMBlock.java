package com.nls.rand.nls;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;
import com.nls.rand.blockcode.STEMModule;

import java.util.Map;

/**
 * NLS — STEM hierarchy tagging for blockcode mint / catalog.
 */
public final class HierarchySTEMBlock implements Block {
    @Override
    public String id() {
        return "hierarchy_stem";
    }

    @Override
    public String system() {
        return "nls";
    }

    @Override
    public BlockResult execute(BlockContext ctx) {
        String stemLabel = ctx.config().get("stem", "engineering");
        STEMModule module = STEMModule.fromLabel(stemLabel);

        String duplexId = ctx.has("duplex_id") ? ctx.get("duplex_id") : "7-4a.1-2b.0";
        String stemPath = module.code() + "/" + duplexId;

        ctx.put("stem_module", module);
        ctx.put("stem_path", stemPath);

        return BlockResult.ok(
                "HierarchySTEMBlock tagged " + module.label() + " → " + stemPath,
                Map.of("stem", module.label(), "code", module.code(), "stem_path", stemPath)
        );
    }
}