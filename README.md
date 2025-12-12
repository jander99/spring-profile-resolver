# Spring Profile Resolver

A CLI tool that computes the effective configuration for Spring Boot applications by merging multiple `application.yml` files based on active profiles.

## Problem

Spring Boot applications often have numerous configuration files across different profiles (dev, prod, aws, postgres, etc.). Understanding the final "computed" configuration for a specific combination of profiles can be challenging and error-prone.

## Solution

This tool parses all relevant `application*.yml` files and produces a single computed output file showing:
- The final merged configuration values
- Comments indicating which source file provided each value
- Warnings for missing profile files

## Features

- **Multi-profile support**: Accepts comma-separated list of profiles (e.g., `prod,aws,postgres`)
- **Spring Boot 2.4+ compatible**: Supports `spring.config.activate.on-profile` syntax
- **Profile groups**: Resolves `spring.profiles.group.*` definitions
- **Profile expressions**: Supports `!`, `&`, `|` operators (e.g., `prod & cloud`, `!staging`)
- **Property placeholders**: Expands `${property.name}` and `${property:default}` references
- **Multi-document YAML**: Handles `---` separated documents within files
- **Properties file support**: Handles `.properties` files in addition to YAML
- **Config imports**: Supports `spring.config.import` directive
- **Environment variables**: Env vars can override placeholders via `--env-file` or `--env`
- **Source tracking**: Comments show which file provided each configuration value
- **Test resource support**: Properly handles test resource overrides

## Installation

```bash
# Clone the repository
git clone https://github.com/jander99/spring-profile-resolver.git
cd spring-profile-resolver

# Install the tool globally
uv tool install .

# Or install in editable mode for development
uv pip install -e .
```

## Usage

```bash
# Basic usage - compute config for 'prod' profile
spring-profile-resolver --profiles prod /path/to/spring-project

# Multiple profiles (applied in order, later wins)
spring-profile-resolver --profiles prod,aws,postgres /path/to/spring-project

# Include test resource overrides (for debugging test behavior)
spring-profile-resolver --profiles dev --include-test /path/to/spring-project

# Custom resource directories
spring-profile-resolver --profiles dev --resources src/main/resources,config/ .

# Output to stdout instead of file
spring-profile-resolver --profiles prod --stdout /path/to/project

# Specify output directory
spring-profile-resolver --profiles prod --output ./my-output /path/to/project

# Use environment variables for placeholder resolution
spring-profile-resolver --profiles prod --env-file .env.prod /path/to/project

# Override specific environment variables
spring-profile-resolver --profiles prod --env DATABASE_HOST=prod-db --env DATABASE_PORT=5432 /path/to/project

# Disable system environment variable lookup
spring-profile-resolver --profiles prod --no-system-env /path/to/project
```

## Output

By default, outputs to `.computed/application-{profiles}-computed.yml` in the current working directory.

Example output:
```yaml
# From: application.yml
server:
  port: 8080  # application-prod.yml

# From: application-prod.yml
database:
  host: prod-db.example.com
  port: 5432
  # From: application-aws.yml
  connection-pool:
    max-size: 50
```

## How Spring Boot Compiles application.yml into Profiles

Spring Boot 2.4+ uses a sophisticated system for loading and merging configuration files. Here's how it works:

### Spring Boot's Config Data Loading Order

When Spring Boot starts, it loads config data files in this order (later sources override earlier ones):

1. **Application properties inside the jar** - `application.yml` or `application.properties` packaged in your jar
2. **Profile-specific properties inside the jar** - `application-{profile}.yml` for each active profile
3. **Application properties outside the jar** - External `application.yml` in the working directory or config locations
4. **Profile-specific properties outside the jar** - External `application-{profile}.yml` files

### Multi-Document YAML Files

Spring Boot supports multiple YAML documents in a single file, separated by `---`:

```yaml
# Base configuration (always loaded)
server:
  port: 8080
app:
  name: MyApp
---
# Loaded only when 'dev' profile is active
spring:
  config:
    activate:
      on-profile: dev
server:
  port: 9000
logging:
  level:
    root: DEBUG
---
# Loaded only when 'prod' profile is active
spring:
  config:
    activate:
      on-profile: prod
server:
  port: 80
logging:
  level:
    root: WARN
```

**Key rules for multi-document YAML:**
- Documents are loaded in declaration order (top to bottom)
- Documents without `spring.config.activate.on-profile` apply to all profiles
- Documents with `on-profile` only apply when that profile is active
- Later documents override earlier ones ("last wins")

### Profile Groups

Profile groups let you activate multiple profiles with a single name:

```yaml
spring:
  profiles:
    group:
      production: proddb,prodmq,monitoring
      proddb: postgres,hikari
```

When you activate `production`, Spring Boot expands it to: `production`, `proddb`, `postgres`, `hikari`, `prodmq`, `monitoring`.

### Property Placeholders

Spring Boot resolves `${...}` placeholders after all files are merged:

```yaml
database:
  host: localhost
  port: 5432
  url: jdbc:postgresql://${database.host}:${database.port}/${database.name}

cache:
  host: ${CACHE_HOST:redis.local}  # Uses default if CACHE_HOST not defined
```

### Spring Boot's Full PropertySource Hierarchy

For context, here's the complete precedence order (highest priority first):

1. Command-line arguments (`--server.port=9000`)
2. `SPRING_APPLICATION_JSON` properties
3. ServletConfig/ServletContext init parameters
4. JNDI attributes
5. Java System properties
6. OS environment variables
7. RandomValuePropertySource (`random.*`)
8. **Config data files** (see loading order above)
9. `@PropertySource` annotations
10. Default properties via `SpringApplication.setDefaultProperties()`

### Restrictions in Spring Boot 2.4+

The following combinations are **not allowed**:
- `spring.config.activate.on-profile` + `spring.profiles.active` in the same document
- `spring.config.activate.on-profile` + `spring.profiles.include` in the same document
- `spring.profiles.group.*` in profile-specific documents (must be in base config)

---

## What This Tool Implements

This tool implements the **config data file** portion of Spring Boot's configuration resolution:

| Feature | Supported | Notes |
|---------|-----------|-------|
| Base `application.yml` | ✅ | |
| Base `application.properties` | ✅ | Full .properties format support |
| Profile-specific files | ✅ | Both `.yml` and `.properties` |
| Multi-document YAML (`---` separator) | ✅ | |
| Multi-document properties (`#---`) | ✅ | |
| `spring.config.activate.on-profile` | ✅ | Full expression support |
| Profile expressions (`prod & cloud`) | ✅ | `!`, `&`, `\|`, parentheses |
| Profile groups | ✅ | With circular reference detection |
| Property placeholders (`${name}`) | ✅ | |
| Default values (`${name:default}`) | ✅ | |
| Environment variables | ✅ | Via `--env-file` and `--env` |
| `spring.config.import` | ✅ | `file:`, `classpath:`, `optional:` |
| Test resources override | ✅ | With `--include-test` flag |
| Last-wins merge strategy | ✅ | |
| External config files | ❌ | Focuses on source files only |

### Resolution Order in This Tool

Following Spring Boot's precedence rules for packaged config files:

1. `application.yml` (base YAML configuration)
2. `application.properties` (base properties, overrides YAML)
3. Imported files via `spring.config.import`
4. Multi-document sections matching active profiles
5. `application-{profile}.yml` for each profile in specified order
6. `application-{profile}.properties` for each profile (overrides YAML)
7. Test resources (only with `--include-test`, applied last as overrides)
8. Environment variables (highest precedence for placeholders)

Later sources override earlier ones for the same keys.

## Requirements

- Python 3.11+
- Spring Boot 2.4+ style configuration files

## Development

```bash
# Clone the repository
git clone https://github.com/jander99/spring-profile-resolver.git
cd spring-profile-resolver

# Install dependencies (including dev tools)
uv sync --extra dev

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=spring_profile_resolver

# Run linter
uv run ruff check src tests

# Run formatter check
uv run ruff format --check src tests

# Run type checker
uv run mypy src

# Run the tool locally
uv run spring-profile-resolver --profiles dev --resources . ./test-fixtures/simple
```

## License

MIT
