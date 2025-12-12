"""Support for spring.config.import directive.

Allows importing additional configuration files from:
- file: paths (absolute or relative)
- classpath: resources
- optional: prefix for non-required imports
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ImportLocation:
    """A parsed import location."""

    path: str
    optional: bool = False
    prefix: str | None = None  # file, classpath, etc.


def parse_import_value(value: str | list[str]) -> list[ImportLocation]:
    """Parse spring.config.import value(s).

    Handles:
    - Single string: "file:./config/extra.yml"
    - Comma-separated: "file:a.yml,file:b.yml"
    - YAML list: ["file:a.yml", "file:b.yml"]

    Args:
        value: Import value (string or list)

    Returns:
        List of ImportLocation objects
    """
    if isinstance(value, list):
        locations = []
        for item in value:
            locations.extend(parse_import_value(str(item)))
        return locations

    # Handle comma-separated values
    parts = [p.strip() for p in value.split(",") if p.strip()]
    locations = []

    for part in parts:
        location = _parse_single_import(part)
        if location:
            locations.append(location)

    return locations


def _parse_single_import(value: str) -> ImportLocation | None:
    """Parse a single import location string.

    Format: [optional:][prefix:]path

    Examples:
        - "file:./config/extra.yml"
        - "optional:file:./config/maybe.yml"
        - "classpath:config/default.yml"
        - "./config/local.yml" (assumes file:)
    """
    if not value:
        return None

    optional = False
    prefix = None
    path = value

    # Check for optional: prefix
    if path.startswith("optional:"):
        optional = True
        path = path[len("optional:") :]

    # Check for location prefix (file:, classpath:, etc.)
    if ":" in path and not path.startswith("/") and not (len(path) > 1 and path[1] == ":"):
        # Has a prefix (but not a Windows absolute path like C:\)
        prefix_end = path.index(":")
        prefix = path[:prefix_end]
        path = path[prefix_end + 1 :]

    return ImportLocation(path=path, optional=optional, prefix=prefix)


def resolve_import_paths(
    imports: list[ImportLocation],
    base_dir: Path,
    resource_dirs: list[Path] | None = None,
) -> list[tuple[Path, bool]]:
    """Resolve import locations to actual file paths.

    Args:
        imports: List of ImportLocation objects
        base_dir: Base directory for relative paths
        resource_dirs: Resource directories for classpath: imports

    Returns:
        List of (resolved_path, optional) tuples
    """
    resolved: list[tuple[Path, bool]] = []

    for imp in imports:
        paths = _resolve_single_import(imp, base_dir, resource_dirs)
        for path in paths:
            resolved.append((path, imp.optional))

    return resolved


def _resolve_single_import(
    imp: ImportLocation,
    base_dir: Path,
    resource_dirs: list[Path] | None,
) -> list[Path]:
    """Resolve a single import location to file path(s)."""
    paths: list[Path] = []

    if imp.prefix == "classpath" or imp.prefix is None:
        # Look in resource directories
        dirs_to_check = resource_dirs or [base_dir]
        for resource_dir in dirs_to_check:
            candidate = resource_dir / imp.path
            if candidate.exists():
                paths.append(candidate)
                break  # Take first match

    elif imp.prefix == "file":
        # File path (relative to base_dir or absolute)
        if imp.path.startswith("/") or (len(imp.path) > 1 and imp.path[1] == ":"):
            # Absolute path
            candidate = Path(imp.path)
        else:
            # Relative path
            candidate = base_dir / imp.path

        if candidate.exists():
            paths.append(candidate)

    return paths


def extract_imports(config: dict[str, Any]) -> list[str] | None:
    """Extract spring.config.import values from config.

    Args:
        config: Parsed config dictionary

    Returns:
        List of import strings, or None if not present
    """
    try:
        spring = config.get("spring", {})
        if not isinstance(spring, dict):
            return None

        cfg = spring.get("config", {})
        if not isinstance(cfg, dict):
            return None

        imports = cfg.get("import")
        if imports is None:
            return None

        if isinstance(imports, str):
            return [imports]
        elif isinstance(imports, list):
            return [str(i) for i in imports]

        return None
    except (AttributeError, TypeError):
        return None


def load_imports(
    config: dict[str, Any],
    source_file: Path,
    resource_dirs: list[Path] | None = None,
    loaded_files: set[Path] | None = None,
) -> list[tuple[Path, bool]]:
    """Extract and resolve imports from a config.

    Note: Circular import detection is handled by the caller (_process_imports).
    This function just extracts and resolves import paths.

    Args:
        config: Parsed config dictionary
        source_file: Path to the config file (for relative resolution)
        resource_dirs: Resource directories for classpath: imports
        loaded_files: Set of already-loaded files (unused, kept for API compat)

    Returns:
        List of (resolved_path, optional) tuples
    """
    # Extract import values
    import_values = extract_imports(config)
    if not import_values:
        return []

    # Parse and resolve
    base_dir = source_file.parent
    locations = []
    for val in import_values:
        locations.extend(parse_import_value(val))

    return resolve_import_paths(locations, base_dir, resource_dirs)
