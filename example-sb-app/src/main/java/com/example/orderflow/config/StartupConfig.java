package com.example.orderflow.config;

import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.CommandLineRunner;
import org.springframework.core.env.Environment;
import org.springframework.stereotype.Component;

import java.util.Arrays;

@Component
public class StartupConfig implements CommandLineRunner {

    private static final Logger log = LoggerFactory.getLogger(StartupConfig.class);

    private final Environment environment;
    private final OrderFlowProperties properties;

    public StartupConfig(Environment environment, OrderFlowProperties properties) {
        this.environment = environment;
        this.properties = properties;
    }

    @Override
    public void run(String... args) {
        log.info("========================================");
        log.info("OrderFlow Application Started");
        log.info("========================================");
        log.info("Active Profiles: {}", Arrays.toString(environment.getActiveProfiles()));
        log.info("Environment: {}", properties.getEnvironment());
        log.info("Platform: {}", properties.getPlatform());
        log.info("----------------------------------------");
        log.info("Feature Flags:");
        log.info("  - Auto Confirm: {}", properties.getFeatures().isAutoConfirm());
        log.info("  - Metrics Enabled: {}", properties.getFeatures().isMetricsEnabled());
        log.info("  - Audit Logging: {}", properties.getFeatures().isAuditLogging());
        log.info("  - Rate Limiting: {}", properties.getFeatures().isRateLimiting());
        log.info("----------------------------------------");
        log.info("Orders Config:");
        log.info("  - Default Region: {}", properties.getOrders().getDefaultRegion());
        log.info("  - Max Items per Order: {}", properties.getOrders().getMaxItemsPerOrder());
        log.info("  - Default Currency: {}", properties.getOrders().getDefaultCurrency());
        log.info("----------------------------------------");
        log.info("Notifications:");
        log.info("  - Enabled: {}", properties.getNotifications().isEnabled());
        log.info("  - Provider: {}", properties.getNotifications().getProvider());
        log.info("----------------------------------------");
        log.info("Storage:");
        log.info("  - Type: {}", properties.getStorage().getType());
        log.info("----------------------------------------");
        log.info("Cache:");
        log.info("  - Type: {}", properties.getCache().getType());
        log.info("  - TTL: {}s", properties.getCache().getTtlSeconds());
        log.info("========================================");
    }
}
