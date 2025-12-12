# OrderFlow - Example Spring Boot Application

This is a sample order management microservice demonstrating realistic Spring Boot profile configurations for different environments and platforms.

## Purpose

This example application showcases:

- **Multi-environment configuration** (dev, staging, prod)
- **Multi-platform support** (local, AWS, GCP)
- **Profile groups** for common profile combinations
- **Multi-document YAML** with `spring.config.activate.on-profile`
- **Property placeholders** with defaults and environment variable support
- **Test resource overrides** for isolated testing
- **Feature flags** controlled by profiles

Use this app to test the `spring-profile-resolver` tool and see how it computes the final configuration.

## Project Structure

```
example-sb-app/
├── build.gradle                          # Gradle build configuration
├── settings.gradle
├── src/main/
│   ├── java/com/example/orderflow/
│   │   ├── OrderFlowApplication.java     # Main application class
│   │   ├── config/                       # Configuration classes
│   │   │   ├── CacheConfig.java
│   │   │   ├── OrderFlowProperties.java  # @ConfigurationProperties
│   │   │   └── StartupConfig.java        # Startup logging
│   │   ├── controller/
│   │   │   ├── OrderController.java      # REST API endpoints
│   │   │   └── InfoController.java       # Environment info endpoint
│   │   ├── model/
│   │   │   ├── Order.java
│   │   │   ├── OrderItem.java
│   │   │   └── OrderStatus.java
│   │   ├── repository/
│   │   │   └── OrderRepository.java
│   │   └── service/
│   │       ├── OrderService.java
│   │       └── NotificationService.java
│   └── resources/
│       ├── application.yml               # Base config + multi-document profiles
│       ├── application-dev.yml           # Development environment
│       ├── application-staging.yml       # Staging environment
│       ├── application-prod.yml          # Production environment
│       ├── application-local.yml         # Local platform
│       ├── application-aws.yml           # AWS platform
│       └── application-gcp.yml           # GCP platform
└── src/test/
    ├── java/                             # Test classes
    └── resources/
        └── application.yml               # Test configuration overrides
```

## Available Profiles

### Environment Profiles

| Profile   | Description | Activated Groups |
|-----------|-------------|------------------|
| `dev`     | Development with H2 database, verbose logging | h2, local |
| `staging` | Staging with PostgreSQL, AWS services | postgres, aws |
| `prod`    | Production with full feature set | postgres, aws, metrics, notifications |
| `dev-full`| Development with all features | h2, local, metrics, notifications |

### Platform Profiles

| Profile | Description |
|---------|-------------|
| `local` | Local filesystem storage, console notifications |
| `aws`   | S3 storage, SES email, ElastiCache |
| `gcp`   | Cloud Storage, Pub/Sub, Memorystore |

### Database Profiles

| Profile    | Description |
|------------|-------------|
| `h2`       | H2 in-memory database (dev) |
| `postgres` | PostgreSQL database (staging/prod) |

### Feature Profiles

| Profile         | Description |
|-----------------|-------------|
| `metrics`       | Enable Prometheus metrics endpoint |
| `notifications` | Enable notification system |

## Running the Application

### Prerequisites

- Java 17+
- Gradle 8+ (or use the wrapper)

### Using Profile Groups

```bash
# Development environment (includes h2, local)
SPRING_PROFILES_ACTIVE=dev ./gradlew bootRun

# Staging environment (includes postgres, aws)
SPRING_PROFILES_ACTIVE=staging ./gradlew bootRun

# Production environment (includes postgres, aws, metrics, notifications)
SPRING_PROFILES_ACTIVE=prod ./gradlew bootRun
```

### Combining Individual Profiles

```bash
# Development with metrics
SPRING_PROFILES_ACTIVE=dev,metrics ./gradlew bootRun

# Production on GCP
SPRING_PROFILES_ACTIVE=prod,gcp ./gradlew bootRun

# H2 database with notifications enabled
SPRING_PROFILES_ACTIVE=h2,local,notifications ./gradlew bootRun
```

### Environment Variables

Many properties support environment variable overrides:

```bash
# Database configuration
export DATABASE_URL=jdbc:postgresql://mydb.example.com:5432/orderflow
export DATABASE_USER=admin
export DATABASE_PASSWORD=secret

# AWS configuration
export AWS_S3_BUCKET=my-orderflow-bucket
export AWS_REGION=us-west-2

# Run with prod profile
SPRING_PROFILES_ACTIVE=prod ./gradlew bootRun
```

## Testing

```bash
# Run all tests
./gradlew test

# Run with verbose output
./gradlew test --info
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET    | `/api/info` | Get application info and active profiles |
| GET    | `/api/info/profiles` | Get active and default profiles |
| POST   | `/api/orders` | Create a new order |
| GET    | `/api/orders` | List all orders (supports filtering) |
| GET    | `/api/orders/{id}` | Get order by ID |
| GET    | `/api/orders/{id}/details` | Get order with items |
| PATCH  | `/api/orders/{id}/status` | Update order status |
| POST   | `/api/orders/{id}/items` | Add item to order |
| DELETE | `/api/orders/{id}` | Cancel an order |
| GET    | `/api/orders/stats` | Get order statistics |

## Using with spring-profile-resolver

This example app is designed to work with the `spring-profile-resolver` CLI tool:

```bash
# From the spring-profile-resolver project root

# See computed config for dev profile
spring-profile-resolver --profiles dev example-sb-app

# See computed config for production
spring-profile-resolver --profiles prod example-sb-app

# See computed config for staging on GCP
spring-profile-resolver --profiles staging,gcp example-sb-app

# Include test resources
spring-profile-resolver --profiles dev --include-test example-sb-app

# Output to file
spring-profile-resolver --profiles prod --output ./computed-config example-sb-app
```

## Configuration Highlights

### Profile Groups (application.yml)

```yaml
spring:
  profiles:
    group:
      dev: "h2,local"
      staging: "postgres,aws"
      prod: "postgres,aws,metrics,notifications"
```

### Multi-document YAML with Conditions

```yaml
---
spring:
  config:
    activate:
      on-profile: prod & aws

orderflow:
  features:
    audit-logging: true
    rate-limiting: true
```

### Property Placeholders with Defaults

```yaml
orderflow:
  orders:
    default-region: ${ORDERFLOW_DEFAULT_REGION:US}

spring:
  datasource:
    url: ${DATABASE_URL:jdbc:postgresql://localhost:5432/orderflow}
```

## Feature Flags by Environment

| Feature | dev | staging | prod |
|---------|-----|---------|------|
| Auto-confirm orders | ✅ | ❌ | ❌ |
| Metrics | ❌ | ❌ | ✅ |
| Notifications | ❌ | ❌ | ✅ |
| Audit logging | ❌ | ✅ | ✅ |
| Rate limiting | ❌ | ❌ | ✅ |
