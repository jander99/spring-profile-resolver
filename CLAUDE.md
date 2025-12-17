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

## Updating Spring Boot Rules

The validation, security, and linting modules contain rules specific to Spring Boot versions. When Spring Boot releases a new major or minor version, these rules may need updates.

### Rule Version Tracking

Each rule module has version constants at the top:
- `SPRING_BOOT_VERSION`: The Spring Boot version these rules were tested against
- `LAST_UPDATED`: When the rules were last reviewed

**Current versions:**
- `validation.py`: Spring Boot 3.2 (updated 2024-12)
- `security.py`: Spring Boot 3.2 (updated 2024-12)
- `linting.py`: Spring Boot 3.2 (updated 2024-12)

### When to Update Rules

Update rules when:
1. **Major Spring Boot version** (e.g., 3.x → 4.x)
2. **Minor version with deprecations** (check release notes)
3. **New security defaults** or best practices change
4. **Users report false positives** for newer Spring Boot versions

### Update Process

#### 1. Review Spring Boot Release Notes

Check the official Spring Boot migration guide and configuration changelog:
- **Deprecated properties**: Add to `COMMON_TYPOS` in `validation.py`
- **Renamed properties**: Update typo mappings
- **New security defaults**: Update `INSECURE_CONFIGURATIONS` in `security.py`
- **New mutually exclusive options**: Add to `MUTUALLY_EXCLUSIVE_PROPERTIES`

Resources:
- Spring Boot Release Notes: https://github.com/spring-projects/spring-boot/wiki
- Configuration Properties Reference: https://docs.spring.io/spring-boot/appendix/application-properties/
- Migration Guides: https://github.com/spring-projects/spring-boot/wiki/Spring-Boot-3.0-Migration-Guide

#### 2. Update Rule Files

**validation.py:**
```python
# Update version constants
SPRING_BOOT_VERSION = "3.3"  # New version
LAST_UPDATED = "2025-01"

# Add deprecated properties to COMMON_TYPOS
COMMON_TYPOS = {
    "old.property.name": "new.property.name",  # Deprecated in Spring Boot 3.3
}

# Add new dangerous combinations if needed
DANGEROUS_COMBINATIONS = [
    {
        # Spring Boot 3.3+ - New security concern
        "condition": lambda config: ...,
        "message": "...",
    }
]
```

**security.py:**
```python
# Update version constants
SPRING_BOOT_VERSION = "3.3"
LAST_UPDATED = "2025-01"

# Add new insecure patterns or update existing
INSECURE_CONFIGURATIONS = [
    {
        # Spring Boot 3.3+ - New security property
        "property": "spring.new.security.property",
        ...
    }
]
```

**linting.py:**
```python
# Update version constants (linting is mostly version-agnostic)
SPRING_BOOT_VERSION = "3.3"
LAST_UPDATED = "2025-01"
```

#### 3. Add Tests for New Rules

Create tests in the appropriate test file:
```python
# tests/test_validation.py
def test_new_spring_boot_33_deprecation():
    """Test detection of property deprecated in Spring Boot 3.3."""
    config = {"old.property": "value"}
    issues = validate_configuration(config)
    assert any("old.property" in i.property_path for i in issues)
```

#### 4. Run Full Test Suite

```bash
uv run pytest
uv run ruff check src tests
uv run mypy src
```

#### 5. Update This Documentation

Update the "Current versions" section above with new version numbers and dates.

### Rule Organization

Rules are stored as Python constants at the top of each module:

**validation.py:**
- `MUTUALLY_EXCLUSIVE_PROPERTIES`: Properties that can't be used together
- `DANGEROUS_COMBINATIONS`: Property combinations that are risky
- `REQUIRED_DEPENDENCIES`: Properties that require other properties
- `COMMON_TYPOS`: Typo corrections and deprecated property mappings

**security.py:**
- `SECRET_PATTERNS`: Regex patterns for detecting secrets
- `SUSPICIOUS_PROPERTY_KEYWORDS`: Property names that often contain secrets
- `INSECURE_CONFIGURATIONS`: Insecure Spring Boot settings
- `SHOULD_USE_ENV_VARS`: Properties that should use environment variables

**linting.py:**
- Programmatic checks (functions, not data)
- Generally version-agnostic

### Quick Reference: Common Updates

| Spring Boot Change | Update Location | Example |
|-------------------|----------------|---------|
| Property deprecated | `validation.py` → `COMMON_TYPOS` | `"old.name": "new.name"` |
| New security default | `security.py` → `INSECURE_CONFIGURATIONS` | Add new rule |
| Properties conflict | `validation.py` → `MUTUALLY_EXCLUSIVE_PROPERTIES` | Add property pair |
| New security risk | `validation.py` → `DANGEROUS_COMBINATIONS` | Add lambda condition |

### Tracking Changes

Consider creating a `RULES_CHANGELOG.md` to track updates:
```markdown
# Rule Updates Changelog

## 2025-01 - Spring Boot 3.3 Support
- Added: `spring.old.property` → `spring.new.property` deprecation mapping
- Updated: SSL configuration security check for new defaults
- Removed: Obsolete `management.security.enabled` check (removed in 2.x)
```
