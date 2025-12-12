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
7. Return `ResolverResult` with merged config and source tracking

### Key Modules

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
    YAML output       (output.py)
```

### Test Fixtures

Test fixtures are in `test-fixtures/` with scenarios for:
- `simple/`: Basic profile files
- `multi-document/`: `---` separated YAML documents
- `with-groups/`: Profile group expansion
- `with-placeholders/`: Property placeholder resolution
- `with-properties/`: `.properties` file format
- `with-test-resources/`: Test resource override behavior
- `edge-cases/`: Unicode, deep nesting, circular groups, invalid YAML
