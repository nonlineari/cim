package com.nls.rand.systemb;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;

import java.util.Map;

/**
 * RAND System B — FFT spectrum collision (cloud collision / dUP sketch).
 */
public final class FFTCollisionBlock implements Block {
    @Override
    public String id() {
        return "fft_collision";
    }

    @Override
    public String system() {
        return "systemb";
    }

    @Override
    public BlockResult execute(BlockContext ctx) {
        int bands = ctx.config().getInt("bands", 512);
        float[] audio = ctx.get("audio_buffer");
        float[] spectrum = new float[bands];

        if (audio != null) {
            for (int b = 0; b < bands; b++) {
                float acc = 0f;
                for (int i = 0; i < audio.length; i++) {
                    acc += audio[i] * (float) Math.sin((b + 1) * i * 0.01);
                }
                spectrum[b] = Math.abs(acc) / audio.length;
            }
        } else {
            for (int b = 0; b < bands; b++) {
                spectrum[b] = (float) Math.random() * 0.1f;
            }
        }

        float peak = 0f;
        int peakBand = 0;
        for (int b = 0; b < bands; b++) {
            if (spectrum[b] > peak) {
                peak = spectrum[b];
                peakBand = b;
            }
        }

        ctx.put("spectrum", spectrum);
        ctx.put("fft_bands", bands);
        ctx.put("fft_peak_band", peakBand);

        return BlockResult.ok(
                "FFTCollisionBlock computed " + bands + " bands (peak@" + peakBand + "=" + String.format("%.4f", peak) + ")",
                Map.of("bands", bands, "peak_band", peakBand, "peak", peak)
        );
    }
}