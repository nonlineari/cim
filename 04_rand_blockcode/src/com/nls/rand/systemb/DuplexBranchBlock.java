package com.nls.rand.systemb;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;

import java.util.Map;

/**
 * RAND System B — duplex-numeric branch (grok_report neat stacking ID).
 */
public final class DuplexBranchBlock implements Block {
    @Override
    public String id() {
        return "duplex_branch";
    }

    @Override
    public String system() {
        return "systemb";
    }

    @Override
    public BlockResult execute(BlockContext ctx) {
        String branch = ctx.config().get("branch", "7-4a.1-2b");
        int peakBand = ctx.has("fft_peak_band") ? ctx.get("fft_peak_band") : 0;
        String duplexId = branch + "." + peakBand;

        ctx.put("duplex_id", duplexId);
        ctx.put("branch_base", branch);

        return BlockResult.ok(
                "DuplexBranchBlock assigned duplex ID " + duplexId,
                Map.of("duplex_id", duplexId, "peak_band", peakBand)
        );
    }
}