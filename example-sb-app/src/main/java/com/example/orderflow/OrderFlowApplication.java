package com.example.orderflow;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.cache.annotation.EnableCaching;

/**
 * OrderFlow - A sample order management microservice demonstrating
 * Spring Boot profile configurations for different environments and platforms.
 *
 * Supports the following profile combinations:
 * - Environments: dev, staging, prod
 * - Platforms: local, aws, gcp
 * - Databases: h2, postgres
 * - Features: metrics, notifications
 *
 * Example usage:
 *   SPRING_PROFILES_ACTIVE=dev,local ./gradlew bootRun
 *   SPRING_PROFILES_ACTIVE=prod,aws ./gradlew bootRun
 */
@SpringBootApplication
@EnableCaching
public class OrderFlowApplication {

    public static void main(String[] args) {
        SpringApplication.run(OrderFlowApplication.class, args);
    }
}
