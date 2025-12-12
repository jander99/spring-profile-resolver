package com.example.orderflow.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.stereotype.Component;

@Component
@ConfigurationProperties(prefix = "orderflow")
public class OrderFlowProperties {

    private String environment = "local";
    private String platform = "local";

    private Orders orders = new Orders();
    private Features features = new Features();
    private Notifications notifications = new Notifications();
    private Storage storage = new Storage();
    private Cache cache = new Cache();

    // Nested classes for structured configuration

    public static class Orders {
        private String defaultRegion = "US";
        private int maxItemsPerOrder = 100;
        private String defaultCurrency = "USD";

        public String getDefaultRegion() {
            return defaultRegion;
        }

        public void setDefaultRegion(String defaultRegion) {
            this.defaultRegion = defaultRegion;
        }

        public int getMaxItemsPerOrder() {
            return maxItemsPerOrder;
        }

        public void setMaxItemsPerOrder(int maxItemsPerOrder) {
            this.maxItemsPerOrder = maxItemsPerOrder;
        }

        public String getDefaultCurrency() {
            return defaultCurrency;
        }

        public void setDefaultCurrency(String defaultCurrency) {
            this.defaultCurrency = defaultCurrency;
        }
    }

    public static class Features {
        private boolean autoConfirm = false;
        private boolean metricsEnabled = false;
        private boolean auditLogging = false;
        private boolean rateLimiting = false;

        public boolean isAutoConfirm() {
            return autoConfirm;
        }

        public void setAutoConfirm(boolean autoConfirm) {
            this.autoConfirm = autoConfirm;
        }

        public boolean isMetricsEnabled() {
            return metricsEnabled;
        }

        public void setMetricsEnabled(boolean metricsEnabled) {
            this.metricsEnabled = metricsEnabled;
        }

        public boolean isAuditLogging() {
            return auditLogging;
        }

        public void setAuditLogging(boolean auditLogging) {
            this.auditLogging = auditLogging;
        }

        public boolean isRateLimiting() {
            return rateLimiting;
        }

        public void setRateLimiting(boolean rateLimiting) {
            this.rateLimiting = rateLimiting;
        }
    }

    public static class Notifications {
        private boolean enabled = false;
        private String provider = "log";
        private Email email = new Email();

        public static class Email {
            private String from = "noreply@orderflow.example";
            private String replyTo = "support@orderflow.example";

            public String getFrom() {
                return from;
            }

            public void setFrom(String from) {
                this.from = from;
            }

            public String getReplyTo() {
                return replyTo;
            }

            public void setReplyTo(String replyTo) {
                this.replyTo = replyTo;
            }
        }

        public boolean isEnabled() {
            return enabled;
        }

        public void setEnabled(boolean enabled) {
            this.enabled = enabled;
        }

        public String getProvider() {
            return provider;
        }

        public void setProvider(String provider) {
            this.provider = provider;
        }

        public Email getEmail() {
            return email;
        }

        public void setEmail(Email email) {
            this.email = email;
        }
    }

    public static class Storage {
        private String type = "local";
        private String basePath = "/tmp/orderflow";
        private Aws aws = new Aws();
        private Gcp gcp = new Gcp();

        public static class Aws {
            private String bucket = "";
            private String region = "us-east-1";
            private String accessKey = "";
            private String secretKey = "";

            public String getBucket() {
                return bucket;
            }

            public void setBucket(String bucket) {
                this.bucket = bucket;
            }

            public String getRegion() {
                return region;
            }

            public void setRegion(String region) {
                this.region = region;
            }

            public String getAccessKey() {
                return accessKey;
            }

            public void setAccessKey(String accessKey) {
                this.accessKey = accessKey;
            }

            public String getSecretKey() {
                return secretKey;
            }

            public void setSecretKey(String secretKey) {
                this.secretKey = secretKey;
            }
        }

        public static class Gcp {
            private String bucket = "";
            private String projectId = "";
            private String credentialsPath = "";

            public String getBucket() {
                return bucket;
            }

            public void setBucket(String bucket) {
                this.bucket = bucket;
            }

            public String getProjectId() {
                return projectId;
            }

            public void setProjectId(String projectId) {
                this.projectId = projectId;
            }

            public String getCredentialsPath() {
                return credentialsPath;
            }

            public void setCredentialsPath(String credentialsPath) {
                this.credentialsPath = credentialsPath;
            }
        }

        public String getType() {
            return type;
        }

        public void setType(String type) {
            this.type = type;
        }

        public String getBasePath() {
            return basePath;
        }

        public void setBasePath(String basePath) {
            this.basePath = basePath;
        }

        public Aws getAws() {
            return aws;
        }

        public void setAws(Aws aws) {
            this.aws = aws;
        }

        public Gcp getGcp() {
            return gcp;
        }

        public void setGcp(Gcp gcp) {
            this.gcp = gcp;
        }
    }

    public static class Cache {
        private String type = "simple";
        private int ttlSeconds = 300;
        private int maxSize = 1000;
        private Redis redis = new Redis();

        public static class Redis {
            private String host = "localhost";
            private int port = 6379;
            private String password = "";

            public String getHost() {
                return host;
            }

            public void setHost(String host) {
                this.host = host;
            }

            public int getPort() {
                return port;
            }

            public void setPort(int port) {
                this.port = port;
            }

            public String getPassword() {
                return password;
            }

            public void setPassword(String password) {
                this.password = password;
            }
        }

        public String getType() {
            return type;
        }

        public void setType(String type) {
            this.type = type;
        }

        public int getTtlSeconds() {
            return ttlSeconds;
        }

        public void setTtlSeconds(int ttlSeconds) {
            this.ttlSeconds = ttlSeconds;
        }

        public int getMaxSize() {
            return maxSize;
        }

        public void setMaxSize(int maxSize) {
            this.maxSize = maxSize;
        }

        public Redis getRedis() {
            return redis;
        }

        public void setRedis(Redis redis) {
            this.redis = redis;
        }
    }

    // Getters and setters for top-level properties

    public String getEnvironment() {
        return environment;
    }

    public void setEnvironment(String environment) {
        this.environment = environment;
    }

    public String getPlatform() {
        return platform;
    }

    public void setPlatform(String platform) {
        this.platform = platform;
    }

    public Orders getOrders() {
        return orders;
    }

    public void setOrders(Orders orders) {
        this.orders = orders;
    }

    public Features getFeatures() {
        return features;
    }

    public void setFeatures(Features features) {
        this.features = features;
    }

    public Notifications getNotifications() {
        return notifications;
    }

    public void setNotifications(Notifications notifications) {
        this.notifications = notifications;
    }

    public Storage getStorage() {
        return storage;
    }

    public void setStorage(Storage storage) {
        this.storage = storage;
    }

    public Cache getCache() {
        return cache;
    }

    public void setCache(Cache cache) {
        this.cache = cache;
    }
}
