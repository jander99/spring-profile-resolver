# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Development Commands

```bash
# Install dependencies (including dev tools)
uv sync --extra dev

# Run tests
uv run pytest

# Run single test file
uv run pytest tests/test_parser.py

# Run single test
uv run pytest tests/test_parser.py::test_function_name -v

# Run tests with coverage
uv run pytest --cov=spring_profile_resolver

# Linting
uv run ruff check src tests

# Formatting check
uv run ruff format --check src tests

# Type checking
uv run mypy src

# Run the CLI locally
uv run spring-profile-resolver --profiles dev --resources . ./test-fixtures/simple

# Run with validation, security scanning, and linting
uv run spring-profile-resolver --profiles prod --validate --security-scan --lint ./test-fixtures/simple
```

## Architecture Overview

This is a CLI tool that computes effective Spring Boot configuration by merging profile-specific YAML/Properties files.

### Core Pipeline (resolver.py)

The main flow in `resolve_profiles()`:
1. Discover config files in resource directories
2. Parse YAML/Properties into `ConfigDocument` objects
3. Extract and expand profile groups (handles `spring.profiles.group.*`)
4. Filter documents based on active profiles using profile expressions
5. Sort and merge documents (last-wins semantics)
6. Resolve `${placeholder}` references (supports env vars, defaults, VCAP)
7. Run optional validation, security scanning, and linting (if enabled)
8. Return `ResolverResult` with merged config, source tracking, and analysis results

### Key Modules

#### Core Pipeline
- **cli.py**: Typer-based CLI, handles arg parsing and output formatting
- **resolver.py**: Orchestrates the full resolution pipeline
- **parser.py**: Parses YAML/Properties files into `ConfigDocument` objects
- **profiles.py**: Profile group expansion and document filtering
- **expressions.py**: Evaluates profile expressions (`!`, `&`, `|`, parentheses)
- **merger.py**: Deep merges configs with source tracking
- **placeholders.py**: Resolves `${property}` and `${property:default}` syntax
- **vcap_services.py**: Cloud Foundry VCAP_SERVICES/VCAP_APPLICATION support
- **imports.py**: Handles `spring.config.import` directives
- **output.py**: Generates final YAML with source comments
- **models.py**: Core data structures (`ConfigDocument`, `ConfigSource`, `ResolverResult`)

#### Configuration Analysis (Optional Features)
- **validation.py**: Validates configuration for property conflicts and dangerous patterns
- **security.py**: Scans for hardcoded secrets and insecure configurations
- **linting.py**: Checks naming conventions and configuration best practices

### Data Flow

```
application*.yml/properties files
        ↓
    ConfigDocument[]  (parser.py)
        ↓
    expand profiles   (profiles.py)
        ↓
    filter applicable (profiles.py + expressions.py)
        ↓
    merge configs     (merger.py)
        ↓
    resolve ${...}    (placeholders.py)
        ↓
    analyze (optional) (validation.py, security.py, linting.py)
        ↓
    YAML output       (output.py)
```

### Configuration Analysis Features

The tool provides optional analysis features to help identify issues in Spring Boot configurations:

#### Validation (`--validate`)
Checks for:
- Mutually exclusive properties (e.g., `datasource.url` and `datasource.jndi-name`)
- Missing required dependencies (e.g., SSL enabled without keystore)
- Dangerous combinations (e.g., `ddl-auto: create-drop` with production profiles)
- Common property typos (e.g., `server.prot` → suggests `server.port`)

#### Security Scanning (`--security-scan`)
Detects:
- Hardcoded secrets (passwords, API keys, AWS credentials, JWT tokens)
- Weak/default passwords
- Insecure configurations (H2 console enabled, debug logging, SSL disabled)
- Database credentials in connection strings
- Values that should use environment variables

#### Linting (`--lint`)
Enforces:
- Naming conventions (kebab-case recommended for Spring Boot)
- Empty or null values
- Excessive nesting depth
- Case-insensitive duplicate properties
- Redundant enabled/disabled flags

Use `--strict-lint` to upgrade linting warnings to errors.

### Test Fixtures

Test fixtures are in `test-fixtures/` with scenarios for:
- `simple/`: Basic profile files
- `multi-document/`: `---` separated YAML documents
- `with-groups/`: Profile group expansion
- `with-placeholders/`: Property placeholder resolution
- `with-properties/`: `.properties` file format
- `with-test-resources/`: Test resource override behavior
- `edge-cases/`: Unicode, deep nesting, circular groups, invalid YAML
