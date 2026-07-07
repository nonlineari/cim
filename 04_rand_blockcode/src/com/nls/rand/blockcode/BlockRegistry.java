package com.nls.rand.blockcode;

import com.nls.rand.extrusion.ExtrusionDualAdapter;
import com.nls.rand.extrusion.ExtrusionDUPAdapter;
import com.nls.rand.nls.HierarchySTEMBlock;
import com.nls.rand.nls.NLSVisualistBridge;
import com.nls.rand.nls.YOLODarketBlock;
import com.nls.rand.systema.LSystemStackBlock;
import com.nls.rand.systema.PixelStackBlock;
import com.nls.rand.systema.RecursiveSphereBlock;
import com.nls.rand.systema.SpoutOutputBlock;
import com.nls.rand.systemb.AudioInBlock;
import com.nls.rand.systemb.DuplexBranchBlock;
import com.nls.rand.systemb.FFTCollisionBlock;
import com.nls.rand.systemb.SpectrumRenderBlock;

import java.util.LinkedHashMap;
import java.util.Map;

public final class BlockRegistry {
    private final Map<String, Block> blocks = new LinkedHashMap<>();

    public BlockRegistry() {
        registerDefaults();
    }

    private void registerDefaults() {
        register(new PixelStackBlock());
        register(new LSystemStackBlock());
        register(new RecursiveSphereBlock());
        register(new SpoutOutputBlock());
        register(new FFTCollisionBlock());
        register(new AudioInBlock());
        register(new DuplexBranchBlock());
        register(new SpectrumRenderBlock());
        register(new YOLODarketBlock());
        register(new HierarchySTEMBlock());
        register(new NLSVisualistBridge());
        register(new ExtrusionDualAdapter());
        register(new ExtrusionDUPAdapter());
    }

    public void register(Block block) {
        blocks.put(block.id(), block);
    }

    public Block get(String id) {
        Block block = blocks.get(id);
        if (block == null) {
            throw new IllegalArgumentException("Unknown block id: " + id);
        }
        return block;
    }

    public Map<String, Block> all() {
        return Map.copyOf(blocks);
    }
}