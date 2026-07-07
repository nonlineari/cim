package com.nls.rand.blockcode;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

public final class BlockResult {
    private final boolean success;
    private final String message;
    private final Map<String, Object> data;

    private BlockResult(boolean success, String message, Map<String, Object> data) {
        this.success = success;
        this.message = message;
        this.data = data == null ? Map.of() : Collections.unmodifiableMap(new HashMap<>(data));
    }

    public static BlockResult ok(String message) {
        return new BlockResult(true, message, null);
    }

    public static BlockResult ok(String message, Map<String, Object> data) {
        return new BlockResult(true, message, data);
    }

    public static BlockResult fail(String message) {
        return new BlockResult(false, message, null);
    }

    public boolean success() {
        return success;
    }

    public String message() {
        return message;
    }

    public Map<String, Object> data() {
        return data;
    }

    @Override
    public String toString() {
        return (success ? "OK" : "FAIL") + ": " + message + (data.isEmpty() ? "" : " " + data);
    }
}