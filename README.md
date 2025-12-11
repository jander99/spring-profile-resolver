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
- **Property placeholders**: Expands `${property.name}` and `${property:default}` references
- **Multi-document YAML**: Handles `---` separated documents within files
- **Source tracking**: Comments show which file provided each configuration value
- **Test resource support**: Properly handles test resource overrides

## Installation

```bash
# Using uvx (recommended for one-off usage)
uvx spring-profile-resolver --profiles prod,aws /path/to/project

# Or install globally
uv tool install spring-profile-resolver

# Or install in a project
uv add spring-profile-resolver
```

## Usage

```bash
# Basic usage - compute config for 'prod' profile
spring-profile-resolver --profiles prod /path/to/spring-project

# Multiple profiles (applied in order, later wins)
spring-profile-resolver --profiles prod,aws,postgres /path/to/spring-project

# Custom resource directories
spring-profile-resolver --profiles dev --resources src/main/resources,config/ .

# Output to stdout instead of file
spring-profile-resolver --profiles prod --stdout /path/to/project

# Specify output directory
spring-profile-resolver --profiles prod --output ./my-output /path/to/project
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

## Configuration Resolution Order

Following Spring Boot's precedence rules:

1. `application.yml` (base configuration)
2. `application-{profile}.yml` for each profile in specified order
3. Multi-document sections matching active profiles
4. Test resources (when applicable, applied last)

Later sources override earlier ones for the same keys.

## Requirements

- Python 3.11+
- Spring Boot 2.4+ style configuration files

## Development

```bash
# Clone the repository
git clone https://github.com/your-org/spring-profile-resolver.git
cd spring-profile-resolver

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run the tool locally
uv run spring-profile-resolver --profiles dev ./test-fixtures
```

## License

MIT
