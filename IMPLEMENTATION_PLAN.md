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
    line_number: int | None = None  # Note: Requires ruamel.yaml node inspection

@dataclass
class ConfigDocument:
    """A single YAML document with optional activation profile."""
    content: dict[str, Any]
    activation_profile: str | None  # from spring.config.activate.on-profile
    source_file: Path
```

**Note on line numbers**: Capturing exact line numbers requires deep integration with ruamel.yaml's node API. This should be implemented in Phase 6 (Polish) after verifying feasibility. Initial implementation can use `line_number: None`.

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

**Supported activation conditions:**
- `spring.config.activate.on-profile: <profile-name>` - Standard profile activation

**Limitations (initial release):**
- `spring.config.activate.on-cloud-platform` - NOT supported (document as future enhancement)
- Environment variable substitution at parse time - NOT supported (only property placeholders)
- External config locations (`spring.config.location`, `spring.config.import`) - NOT supported

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
    """
    Expand profile list, resolving groups recursively.

    Algorithm (matches Spring Boot 2.4+):
    1. Process profiles in the order specified
    2. For each profile, if it's a group, expand it depth-first
    3. Maintain insertion order, avoiding duplicates
    4. Detect circular references and raise error

    Returns expanded list maintaining proper precedence order.
    """

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
      prod: proddb,prodmq
      proddb: postgres,hikari
```

With `--profiles prod`, the expansion works as follows:
1. Start with `[prod]`
2. `prod` is a group → expand to `[proddb, prodmq]`
3. `proddb` is also a group → expand to `[postgres, hikari]`
4. Final result: `[prod, proddb, postgres, hikari, prodmq]`

**Important**: Spring Boot processes groups depth-first. The profile itself is included first, followed by its group members. Members are processed in declaration order.

**Circular reference handling**: If `prod → proddb → prod` is detected, raise an error immediately. Track the expansion path to detect cycles.

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

**Array/List Handling:**
Per Spring Boot behavior, lists are **replaced entirely**, not merged. Source tracking for lists works as follows:

- The entire list is attributed to a single source (the file that last set it)
- Individual list items are NOT tracked separately
- The source key uses the parent path (e.g., `"server.endpoints"` for a list)

Example:
```yaml
# application.yml
server:
  endpoints:
    - /health
    - /info

# application-prod.yml
server:
  endpoints:
    - /health
    - /metrics
    - /prometheus
```

Result with `--profiles prod`:
```python
config = {"server": {"endpoints": ["/health", "/metrics", "/prometheus"]}}
sources = {"server.endpoints": ConfigSource("application-prod.yml")}
```

The entire list from `application-prod.yml` replaces the one from `application.yml`.

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
    include_test: bool = False
) -> ResolverResult:
    """
    Main entry point for profile resolution.

    Steps:
    1. Discover config files in main resources
    2. If include_test=True, also discover test resources
    3. Parse all YAML documents
    4. Extract and expand profile groups from base config
    5. Filter applicable documents based on active profiles
    6. Merge in order (main first, then test overrides if enabled)
    7. Resolve placeholders
    8. Return result with warnings
    """

@dataclass
class ResolverResult:
    config: dict[str, Any]
    sources: dict[str, ConfigSource]
    warnings: list[str]
```

**Test Resource Handling:**

Test resources (`src/test/resources/application*.yml`) are handled based on the `include_test` parameter:

- **`include_test=False` (default)**: Only main resources are processed. This represents the production configuration without test overrides. This is the most common use case.

- **`include_test=True` (via `--include-test` or `-t` flag)**: Test resources are processed AFTER main resources, allowing test configurations to override production settings. This is useful for understanding what configuration a test would see.

**Use cases:**
- Default (exclude test): Verifying production configuration, understanding what runs in deployed environments
- Include test (`-t`): Debugging test failures, understanding test behavior, validating test overrides

**Discovery paths:**
- Main: `{project}/src/main/resources/application*.yml`
- Test: `{project}/src/test/resources/application*.yml` (if `include_test=True`)
- Custom: Additional paths via `--resources` flag

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
    include_test: bool = typer.Option(False, "--include-test", "-t", help="Include test resources (they override main)"),
):
    """Compute effective Spring Boot configuration for given profiles."""
```

**Default Output Behavior:**
- If `--stdout` is specified: Output goes to stdout only
- If `--output` is specified: Write to `{output}/application-{profiles}-computed.yml`
- Otherwise: Write to `.computed/application-{profiles}-computed.yml` in the current working directory

The `.computed/` directory is created automatically if it doesn't exist. The filename uses the profile list joined by hyphens (e.g., `application-prod-aws-computed.yml` for `--profiles prod,aws`).

---

## Resolution Order (Critical)

The order of config application follows Spring Boot 2.4+ rules:

1. **Base config**: `application.yml` (all documents - unconditional + matching profile conditions)
2. **Profile-specific files**: For each profile in order:
   - `application-{profile}.yml` (all documents within the file)
3. **Test resources** (if enabled): Same pattern as above, applied last (overrides main)

**IMPORTANT**: Each file is processed as a complete unit. All documents within a file (including those with `on-profile` conditions) are evaluated when that file is loaded. Files are not interleaved.

**Example with `--profiles prod,aws`:**
```
Main resources:
1. src/main/resources/application.yml
   - Processes ALL documents in order:
     a. Base documents (no activation condition)
     b. Documents with spring.config.activate.on-profile: prod
     c. Documents with spring.config.activate.on-profile: aws
   - Only includes documents matching active profiles or with no condition

2. src/main/resources/application-prod.yml
   - Processes ALL documents in this file

3. src/main/resources/application-aws.yml
   - Processes ALL documents in this file

Test resources (only when --include-test is specified):
4. src/test/resources/application.yml
   - Same multi-document processing as main application.yml

5. src/test/resources/application-prod.yml
   - All documents in test prod override

6. src/test/resources/application-aws.yml
   - All documents in test aws override
```

**Key principle**: Later files and later documents within the same file override earlier ones for the same configuration keys.

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

### `test-fixtures/edge-cases/`
Edge case scenarios:
- **`circular-groups/`**: Circular profile group references (e.g., `prod → proddb → prod`)
- **`invalid-yaml/`**: Malformed YAML files to test error handling
- **`empty-files/`**: Empty application files and empty documents
- **`missing-profiles/`**: Requested profiles with no corresponding files
- **`unicode/`**: Configuration with Unicode characters, emoji, multi-byte strings
- **`deep-nesting/`**: Very deeply nested configuration structures
- **`yaml-features/`**: YAML anchors, aliases, and custom tags

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
