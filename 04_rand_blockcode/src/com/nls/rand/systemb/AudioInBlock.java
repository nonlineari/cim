package com.nls.rand.systemb;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;

import java.util.Map;

/**
 * RAND System B — audio input stub (processing.sound.AudioIn analogue).
 */
public final class AudioInBlock implements Block {
    @Override
    public String id() {
        return "audio_in";
    }

    @Override
    public String system() {
        return "systemb";
    }

    @Override
    public BlockResult execute(BlockContext ctx) {
        int channel = ctx.config().getInt("channel", 0);
        float[] buffer = new float[1024];
        for (int i = 0; i < buffer.length; i++) {
            buffer[i] = (float) (Math.sin(i * 0.05) * 0.25);
        }
        ctx.put("audio_buffer", buffer);
        ctx.put("audio_channel", channel);
        return BlockResult.ok(
                "AudioInBlock started channel " + channel + " (simulated sine buffer)",
                Map.of("samples", buffer.length, "channel", channel)
        );
    }
}