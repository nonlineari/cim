package com.nls.rand.systema;

import com.nls.rand.blockcode.Block;
import com.nls.rand.blockcode.BlockContext;
import com.nls.rand.blockcode.BlockResult;

import javax.imageio.ImageIO;
import java.awt.image.BufferedImage;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.Map;

/**
 * RAND System A — neat pixel stacking from extrusion sketch source image.
 * Uses int[height][width] layout (row-major by scanline).
 */
public final class PixelStackBlock implements Block {
    public static final String DEFAULT_IMAGE =
            "/home/s9/Downloads/CIM/05_extrusion_sketches/Extrusion3_2_2_1_MONO_XXI_PS_INT_dual/data/mwo_001.jpg";

    @Override
    public String id() {
        return "pixel_stack";
    }

    @Override
    public String system() {
        return "systema";
    }

    @Override
    public BlockResult execute(BlockContext ctx) {
        String imagePath = ctx.config().get("image", DEFAULT_IMAGE);
        int width = ctx.config().getInt("width", 1080);
        int height = ctx.config().getInt("height", 790);

        int[][] pixels = new int[height][width];
        int[][] values = new int[height][width];

        Path path = Path.of(imagePath);
        if (Files.exists(path)) {
            try {
                BufferedImage img = ImageIO.read(path.toFile());
                int imgW = img.getWidth();
                int imgH = img.getHeight();
                for (int y = 1; y < height && y < imgH; y++) {
                    for (int x = 1; x < width && x < imgW; x++) {
                        int rgb = img.getRGB(x, y);
                        pixels[y][x] = rgb;
                        values[y][x] = rgb & 0xFFFFFF;
                    }
                }
            } catch (IOException e) {
                return BlockResult.fail("PixelStackBlock: failed to read image " + imagePath + " — " + e.getMessage());
            }
        } else {
            synthesizeGradient(pixels, values, width, height);
        }

        ctx.put("pixels", pixels);
        ctx.put("values", values);
        ctx.put("width", width);
        ctx.put("height", height);
        ctx.put("image_path", imagePath);

        int sample = values[Math.min(height - 1, 64)][Math.min(width - 1, 64)];
        return BlockResult.ok(
                "PixelStackBlock loaded " + width + "x" + height + " int[height][width] from " + path.getFileName(),
                Map.of("sample_value", sample, "layout", "int[height][width]")
        );
    }

    private static void synthesizeGradient(int[][] pixels, int[][] values, int width, int height) {
        for (int y = 0; y < height; y++) {
            for (int x = 0; x < width; x++) {
                int v = ((x * 255) / Math.max(1, width - 1) + (y * 255) / Math.max(1, height - 1)) / 2;
                int rgb = (v << 16) | (v << 8) | v;
                pixels[y][x] = rgb;
                values[y][x] = rgb;
            }
        }
    }
}