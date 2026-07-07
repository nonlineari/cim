package com.nls.rand.blockcode;

import java.util.Collections;
import java.util.HashMap;
import java.util.Map;

/**
 * Shared mutable state passed between blocks in a pipeline run.
 */
public final class BlockContext {
    private final SimpleConfig config;
    private final Map<String, Object> store = new HashMap<>();

    public BlockContext(SimpleConfig config) {
        this.config = config;
    }

    public SimpleConfig config() {
        return config;
    }

    public void put(String key, Object value) {
        store.put(key, value);
    }

    @SuppressWarnings("unchecked")
    public <T> T get(String key) {
        return (T) store.get(key);
    }

    public boolean has(String key) {
        return store.containsKey(key);
    }

    public Map<String, Object> snapshot() {
        return Collections.unmodifiableMap(new HashMap<>(store));
    }
}