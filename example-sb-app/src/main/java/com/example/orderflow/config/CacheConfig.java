package com.example.orderflow.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.cache.CacheManager;
import org.springframework.cache.concurrent.ConcurrentMapCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import jakarta.annotation.PostConstruct;

@Configuration
public class CacheConfig {

    private static final Logger log = LoggerFactory.getLogger(CacheConfig.class);

    @Value("${orderflow.cache.type:simple}")
    private String cacheType;

    @Value("${orderflow.cache.ttl-seconds:300}")
    private int ttlSeconds;

    @PostConstruct
    public void logCacheConfig() {
        log.info("Cache configuration: type={}, ttl={}s", cacheType, ttlSeconds);
    }

    @Bean
    public CacheManager cacheManager() {
        // In a real app, this would switch between different cache implementations
        // based on the cache type (simple, redis, etc.)
        log.info("Initializing {} cache manager", cacheType);
        return new ConcurrentMapCacheManager("orders", "customers", "products");
    }
}
