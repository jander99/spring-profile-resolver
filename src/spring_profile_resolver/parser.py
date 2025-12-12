"""Configuration file parsing for Spring Boot (YAML and Properties)."""

from pathlib import Path
from typing import Any

from ruamel.yaml import YAML, YAMLError

from .exceptions import InvalidYAMLError
from .models import ConfigDocument

# Maximum nesting depth for YAML documents (protection against YAML bombs)
MAX_YAML_DEPTH = 50


def _validate_yaml_depth(
    data: Any,
    max_depth: int = MAX_YAML_DEPTH,
    current_depth: int = 0,
    path: Path | None = None,
) -> None:
    """Validate that YAML data doesn't exceed maximum nesting depth.

    This protects against YAML bomb attacks that use deeply nested structures
    to exhaust resources.

    Args:
        data: The parsed YAML data to validate
        max_depth: Maximum allowed nesting depth (default: 50)
        current_depth: Current depth in the traversal (internal)
        path: File path for error messages (optional)

    Raises:
        InvalidYAMLError: If the nesting depth exceeds max_depth
    """
    if current_depth > max_depth:
        raise InvalidYAMLError(
            path or Path("unknown"),
            details=f"YAML nesting depth exceeds maximum allowed depth of {max_depth}. "
            f"This may indicate a YAML bomb attack or malformed configuration.",
        )

    if isinstance(data, dict):
        for value in data.values():
            _validate_yaml_depth(value, max_depth, current_depth + 1, path)
    elif isinstance(data, list):
        for item in data:
            _validate_yaml_depth(item, max_depth, current_depth + 1, path)


def create_yaml_parser() -> YAML:
    """Create a configured YAML parser instance."""
    yaml = YAML()
    yaml.preserve_quotes = True
    return yaml


def parse_config_file(path: Path) -> list[ConfigDocument]:
    """Parse a configuration file (YAML or Properties).

    Automatically detects file type by extension and uses
    the appropriate parser.

    Args:
        path: Path to the configuration file

    Returns:
        List of ConfigDocument objects

    Raises:
        FileNotFoundError: If the file doesn't exist
        ValueError: If the file type is not supported
    """
    suffix = path.suffix.lower()

    if suffix in (".yml", ".yaml"):
        return parse_yaml_file(path)
    elif suffix == ".properties":
        from .properties_parser import parse_properties_file

        return parse_properties_file(path)
    else:
        raise ValueError(f"Unsupported configuration file type: {suffix}")


def parse_yaml_file(path: Path) -> list[ConfigDocument]:
    """Parse a YAML file, handling multi-document format.

    Args:
        path: Path to the YAML file

    Returns:
        List of ConfigDocument objects, one per YAML document in the file

    Raises:
        FileNotFoundError: If the file doesn't exist
        InvalidYAMLError: If the YAML is malformed
    """
    yaml = create_yaml_parser()
    documents: list[ConfigDocument] = []

    try:
        with open(path, encoding="utf-8") as f:
            for index, doc in enumerate(yaml.load_all(f)):
                if doc is None:
                    # Skip empty documents
                    continue

                # Convert ruamel.yaml's CommentedMap to regular dict for easier handling
                content = dict(doc) if doc else {}

                # Validate depth to protect against YAML bombs
                _validate_yaml_depth(content, path=path)

                activation_profile = extract_activation_profile(content)

                documents.append(
                    ConfigDocument(
                        content=content,
                        source_file=path,
                        activation_profile=activation_profile,
                        document_index=index,
                    )
                )
    except YAMLError as e:
        # Extract line number from YAMLError if available
        line_num = None
        if hasattr(e, "problem_mark") and e.problem_mark is not None:
            line_num = e.problem_mark.line + 1  # Convert 0-indexed to 1-indexed
        raise InvalidYAMLError(path, line=line_num, details=str(e)) from e

    return documents


def extract_activation_profile(doc: dict[str, Any]) -> str | None:
    """Extract spring.config.activate.on-profile value if present.

    Args:
        doc: Parsed YAML document as a dictionary

    Returns:
        The profile name if spring.config.activate.on-profile is set, None otherwise
    """
    try:
        spring = doc.get("spring", {})
        if not isinstance(spring, dict):
            return None

        config = spring.get("config", {})
        if not isinstance(config, dict):
            return None

        activate = config.get("activate", {})
        if not isinstance(activate, dict):
            return None

        on_profile = activate.get("on-profile")
        if on_profile is not None:
            return str(on_profile)

        return None
    except (AttributeError, TypeError):
        return None


def discover_config_files(base_dir: Path) -> list[Path]:
    """Find all application config files (YAML and Properties) in a directory.

    Args:
        base_dir: Directory to search in

    Returns:
        List of paths to config files, sorted for consistent ordering.
        Base application.yml/yaml/properties comes first, followed by
        profile-specific files. Within the same profile, .properties
        files override .yml/.yaml files (Spring Boot behavior).
    """
    if not base_dir.exists():
        return []

    yml_files = list(base_dir.glob("application*.yml"))
    yaml_files = list(base_dir.glob("application*.yaml"))
    properties_files = list(base_dir.glob("application*.properties"))
    all_files = yml_files + yaml_files + properties_files

    # Sort with base config first, then alphabetically by profile name
    # Within same profile, .properties comes after .yml/.yaml (higher precedence)
    def sort_key(path: Path) -> tuple[int, str, int]:
        name = path.stem  # e.g., "application" or "application-prod"
        # .properties files have higher precedence (come later in merge order)
        extension_order = 1 if path.suffix == ".properties" else 0

        if name == "application":
            return (0, "", extension_order)  # Base config comes first
        return (1, name, extension_order)

    return sorted(all_files, key=sort_key)


def get_profile_from_filename(path: Path) -> str | None:
    """Extract profile name from a config filename.

    Args:
        path: Path to config file (e.g., application-prod.yml)

    Returns:
        Profile name (e.g., "prod") or None for base application.yml
    """
    stem = path.stem  # e.g., "application-prod"
    if stem == "application":
        return None
    if stem.startswith("application-"):
        return stem[len("application-") :]
    return None
