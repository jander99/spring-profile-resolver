# Implementation Plan

## Overview

Build a Python CLI tool that computes the effective Spring Boot configuration by merging `application*.yml` files based on specified profiles, outputting a single computed YAML file with source attribution comments.

---

## Architecture

```
src/spring_profile_resolver/
├── __init__.py
├── cli.py              # Typer CLI entry point
├── resolver.py         # Main orchestration logic
├── parser.py           # YAML parsing (multi-doc, activation conditions)
├── merger.py           # Deep merge with source tracking
├── placeholders.py     # ${property} resolution
├── profiles.py         # Profile group expansion, ordering
├── output.py           # Computed YAML generation with comments
└── models.py           # Data classes for typed config handling

tests/
├── conftest.py
├── test_parser.py
├── test_merger.py
├── test_placeholders.py
├── test_profiles.py
├── test_output.py
└── test_integration.py

test-fixtures/           # Sample Spring Boot configs for testing
├── simple/
├── multi-document/
├── with-groups/
└── with-placeholders/
```

---

## Module Specifications

### 1. `models.py` - Data Structures

Define typed data classes for configuration handling:

```python
@dataclass
class ConfigSource:
    """Tracks where a configuration value originated."""
    file_path: Path
    line_number: int | None = None

@dataclass
class TrackedValue:
    """A configuration value with its source information."""
    value: Any
    source: ConfigSource

@dataclass
class ConfigDocument:
    """A single YAML document with optional activation profile."""
    content: dict[str, Any]
    activation_profile: str | None  # from spring.config.activate.on-profile
    source_file: Path
```

### 2. `parser.py` - YAML Parsing

**Responsibilities:**
- Load YAML files using `ruamel.yaml` for comment preservation
- Handle multi-document YAML (split on `---`)
- Extract `spring.config.activate.on-profile` conditions
- Return list of `ConfigDocument` objects

**Key Functions:**
```python
def parse_yaml_file(path: Path) -> list[ConfigDocument]:
    """Parse a YAML file, handling multi-document format."""

def extract_activation_profile(doc: dict) -> str | None:
    """Extract spring.config.activate.on-profile value if present."""

def discover_config_files(base_dirs: list[Path]) -> list[Path]:
    """Find all application*.yml files in given directories."""
```

**Multi-document handling:**
```yaml
# application.yml with embedded profile configs
server:
  port: 8080
---
spring:
  config:
    activate:
      on-profile: dev
server:
  port: 8081
---
spring:
  config:
    activate:
      on-profile: prod
server:
  port: 80
```

### 3. `profiles.py` - Profile Resolution

**Responsibilities:**
- Parse profile group definitions (`spring.profiles.group.*`)
- Expand profile list based on groups
- Determine final profile application order

**Key Functions:**
```python
def parse_profile_groups(config: dict) -> dict[str, list[str]]:
    """Extract profile group definitions from config."""

def expand_profiles(
    requested: list[str],
    groups: dict[str, list[str]]
) -> list[str]:
    """Expand profile list, resolving groups recursively."""

def get_applicable_documents(
    documents: list[ConfigDocument],
    active_profiles: list[str]
) -> list[ConfigDocument]:
    """Filter and order documents applicable to active profiles."""
```

**Profile group example:**
```yaml
spring:
  profiles:
    group:
      prod: proddb, prodmq
      proddb: postgres, hikari
```

With `--profiles prod`, expands to: `[prod, proddb, prodmq, postgres, hikari]`

### 4. `merger.py` - Configuration Merging

**Responsibilities:**
- Deep merge dictionaries with later values winning
- Track source file for each leaf value
- Handle list replacement (not merging, per Spring behavior)
- Build a parallel structure tracking sources

**Key Functions:**
```python
def deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
    base_sources: dict[str, ConfigSource],
    override_source: ConfigSource
) -> tuple[dict[str, Any], dict[str, ConfigSource]]:
    """
    Deep merge override into base, tracking sources.
    Returns (merged_config, sources_map).
    """

def merge_configs(
    documents: list[ConfigDocument]
) -> tuple[dict[str, Any], dict[str, ConfigSource]]:
    """Merge multiple config documents in order."""
```

**Source tracking structure:**
For a config like:
```yaml
server:
  port: 8080
  ssl:
    enabled: true
```

The sources map would be:
```python
{
    "server.port": ConfigSource("application-prod.yml", line=3),
    "server.ssl.enabled": ConfigSource("application.yml", line=7),
}
```

### 5. `placeholders.py` - Property Placeholder Resolution

**Responsibilities:**
- Find `${property.name}` patterns in string values
- Support default values: `${property:default}`
- Resolve references from the merged config
- Handle nested placeholders
- Leave unresolvable placeholders with a warning

**Key Functions:**
```python
def resolve_placeholders(
    config: dict[str, Any],
    max_iterations: int = 10
) -> dict[str, Any]:
    """
    Resolve all ${...} placeholders in config values.
    Iterates to handle chained references.
    """

def resolve_single_value(
    value: str,
    config: dict[str, Any]
) -> str:
    """Resolve placeholders in a single string value."""

def get_nested_value(config: dict, key_path: str) -> Any | None:
    """Get value by dot-notation path (e.g., 'server.port')."""
```

**Placeholder examples:**
```yaml
database:
  host: ${DB_HOST:localhost}
  port: ${DB_PORT:5432}
  url: jdbc:postgresql://${database.host}:${database.port}/mydb
```

### 6. `output.py` - Computed YAML Generation

**Responsibilities:**
- Generate YAML output with source attribution comments
- Use block comments for stanzas from single source
- Use inline comments when individual keys differ
- Format output cleanly with `ruamel.yaml`

**Key Functions:**
```python
def generate_computed_yaml(
    config: dict[str, Any],
    sources: dict[str, ConfigSource],
    output_path: Path | None = None,
    to_stdout: bool = False
) -> str:
    """Generate the computed YAML with source comments."""

def determine_comment_style(
    key_path: str,
    sources: dict[str, ConfigSource]
) -> CommentStyle:
    """Decide if a section needs block or inline comments."""

def add_source_comments(
    yaml_node: Any,
    key_path: str,
    sources: dict[str, ConfigSource]
) -> None:
    """Attach appropriate comments to YAML nodes."""
```

**Output format example:**
```yaml
# From: application.yml
server:
  port: 8080  # application-prod.yml (overridden)
  servlet:
    context-path: /api

# From: application-prod.yml
database:
  host: prod-db.example.com
  port: 5432
  pool:
    max-size: 50  # application-aws.yml
    min-idle: 10
```

### 7. `resolver.py` - Main Orchestration

**Responsibilities:**
- Coordinate the full resolution pipeline
- Handle warnings (missing files, unresolved placeholders)
- Manage the resolution order

**Key Functions:**
```python
def resolve_profiles(
    project_path: Path,
    profiles: list[str],
    resource_dirs: list[str] | None = None,
    include_test: bool = True
) -> ResolverResult:
    """
    Main entry point for profile resolution.

    Steps:
    1. Discover config files
    2. Parse all YAML documents
    3. Extract and expand profile groups
    4. Filter applicable documents
    5. Merge in order
    6. Resolve placeholders
    7. Return result with warnings
    """

@dataclass
class ResolverResult:
    config: dict[str, Any]
    sources: dict[str, ConfigSource]
    warnings: list[str]
```

### 8. `cli.py` - Command Line Interface

**Responsibilities:**
- Parse command line arguments via Typer
- Invoke resolver
- Handle output (file vs stdout)
- Display warnings with Rich

**CLI Interface:**
```python
@app.command()
def main(
    project_path: Path = typer.Argument(..., help="Path to Spring Boot project"),
    profiles: str = typer.Option(..., "--profiles", "-p", help="Comma-separated profiles"),
    resources: str | None = typer.Option(None, "--resources", "-r", help="Custom resource dirs"),
    output: Path | None = typer.Option(None, "--output", "-o", help="Output directory"),
    stdout: bool = typer.Option(False, "--stdout", help="Output to stdout"),
    no_test: bool = typer.Option(False, "--no-test", help="Exclude test resources"),
):
    """Compute effective Spring Boot configuration for given profiles."""
```

---

## Resolution Order (Critical)

The order of config application follows Spring Boot's rules:

1. **Base config**: `application.yml` (all documents without activation condition)
2. **Profile-specific files**: For each profile in order:
   - `application-{profile}.yml`
   - Documents from `application.yml` with matching `on-profile`
3. **Test resources**: Same pattern, applied last (overrides main)

**Example with `--profiles prod,aws`:**
```
1. src/main/resources/application.yml (base documents)
2. src/main/resources/application-prod.yml
3. src/main/resources/application.yml (on-profile: prod documents)
4. src/main/resources/application-aws.yml
5. src/main/resources/application.yml (on-profile: aws documents)
6. src/test/resources/application.yml (base documents)
7. src/test/resources/application-prod.yml
8. src/test/resources/application.yml (on-profile: prod documents)
9. src/test/resources/application-aws.yml
10. src/test/resources/application.yml (on-profile: aws documents)
```

---

## Implementation Phases

### Phase 1: Core Infrastructure
- [ ] Set up project structure with `uv`
- [ ] Implement `models.py` data classes
- [ ] Implement `parser.py` with multi-document support
- [ ] Add basic tests with fixtures

### Phase 2: Profile Handling
- [ ] Implement `profiles.py` with group expansion
- [ ] Implement `merger.py` with source tracking
- [ ] Add tests for merge behavior

### Phase 3: Placeholder Resolution
- [ ] Implement `placeholders.py`
- [ ] Handle nested and default placeholders
- [ ] Add tests for placeholder edge cases

### Phase 4: Output Generation
- [ ] Implement `output.py` with comment styles
- [ ] Implement block vs inline comment logic
- [ ] Add output formatting tests

### Phase 5: CLI & Integration
- [ ] Implement `cli.py` with Typer
- [ ] Implement `resolver.py` orchestration
- [ ] Add integration tests
- [ ] Create comprehensive test fixtures

### Phase 6: Polish
- [ ] Add detailed error messages
- [ ] Improve warning output with Rich
- [ ] Documentation and examples
- [ ] CI/CD setup

---

## Test Fixtures Needed

### `test-fixtures/simple/`
Basic separate file structure:
- `application.yml`
- `application-dev.yml`
- `application-prod.yml`

### `test-fixtures/multi-document/`
Multi-document YAML:
- `application.yml` with `---` separators and `on-profile` conditions

### `test-fixtures/with-groups/`
Profile groups:
- `application.yml` with `spring.profiles.group.*`
- Related profile files

### `test-fixtures/with-placeholders/`
Placeholder resolution:
- Configs with `${...}` patterns
- Nested references
- Default values

### `test-fixtures/with-test-resources/`
Test override scenario:
- `src/main/resources/application*.yml`
- `src/test/resources/application*.yml`

---

## Edge Cases to Handle

1. **Circular profile groups**: Detect and error
2. **Missing profile files**: Warn, continue
3. **Unresolvable placeholders**: Warn, leave as-is
4. **Invalid YAML**: Error with file/line info
5. **Empty documents**: Skip gracefully
6. **Conflicting activation conditions**: Follow Spring's behavior
7. **Very deep nesting**: Handle without stack overflow
8. **Unicode in configs**: Preserve correctly
9. **Special YAML types**: Anchors, aliases, tags

---

## Success Criteria

1. **Correctness**: Output matches what Spring Boot would actually use
2. **Traceability**: Every value clearly attributed to source file
3. **Usability**: Clear warnings, helpful error messages
4. **Performance**: Handle large configs quickly
5. **Reliability**: Comprehensive test coverage

---

## Open Questions (For Future Consideration)

1. Should we support `spring.config.import` for external files?
2. Should we support environment variable injection?
3. Should we offer a "diff" mode comparing two profile combinations?
4. Should we validate against a schema?
