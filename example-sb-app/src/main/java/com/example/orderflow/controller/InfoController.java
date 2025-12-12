package com.example.orderflow.controller;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.env.Environment;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Arrays;
import java.util.HashMap;
import java.util.Map;

@RestController
@RequestMapping("/api/info")
public class InfoController {

    private final Environment environment;

    @Value("${spring.application.name:orderflow}")
    private String applicationName;

    @Value("${orderflow.environment:unknown}")
    private String environmentName;

    @Value("${orderflow.platform:unknown}")
    private String platform;

    @Value("${orderflow.features.auto-confirm:false}")
    private boolean autoConfirm;

    @Value("${orderflow.features.metrics-enabled:false}")
    private boolean metricsEnabled;

    @Value("${orderflow.notifications.enabled:false}")
    private boolean notificationsEnabled;

    public InfoController(Environment environment) {
        this.environment = environment;
    }

    @GetMapping
    public ResponseEntity<Map<String, Object>> getInfo() {
        Map<String, Object> info = new HashMap<>();

        info.put("application", applicationName);
        info.put("environment", environmentName);
        info.put("platform", platform);
        info.put("activeProfiles", Arrays.asList(environment.getActiveProfiles()));

        Map<String, Boolean> features = new HashMap<>();
        features.put("autoConfirm", autoConfirm);
        features.put("metricsEnabled", metricsEnabled);
        features.put("notificationsEnabled", notificationsEnabled);
        info.put("features", features);

        return ResponseEntity.ok(info);
    }

    @GetMapping("/profiles")
    public ResponseEntity<Map<String, Object>> getProfiles() {
        Map<String, Object> profiles = new HashMap<>();
        profiles.put("active", Arrays.asList(environment.getActiveProfiles()));
        profiles.put("default", Arrays.asList(environment.getDefaultProfiles()));
        return ResponseEntity.ok(profiles);
    }
}
