package com.nls.rand.blockcode;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

/**
 * Lightweight key-value configuration (parsed from pipeline JSON fragments).
 */
public final class SimpleConfig {
    private final Map<String, String> values;

    public SimpleConfig() {
        this.values = new HashMap<>();
    }

    public SimpleConfig(Map<String, String> values) {
        this.values = new HashMap<>(values);
    }

    public void put(String key, String value) {
        values.put(key, value);
    }

    public String get(String key, String defaultValue) {
        return values.getOrDefault(key, defaultValue);
    }

    public int getInt(String key, int defaultValue) {
        String raw = values.get(key);
        if (raw == null || raw.isBlank()) {
            return defaultValue;
        }
        try {
            return Integer.parseInt(raw.trim());
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    public double getDouble(String key, double defaultValue) {
        String raw = values.get(key);
        if (raw == null || raw.isBlank()) {
            return defaultValue;
        }
        try {
            return Double.parseDouble(raw.trim());
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }

    public boolean getBoolean(String key, boolean defaultValue) {
        String raw = values.get(key);
        if (raw == null || raw.isBlank()) {
            return defaultValue;
        }
        return Boolean.parseBoolean(raw.trim());
    }

    public Map<String, String> asMap() {
        return Collections.unmodifiableMap(values);
    }
}