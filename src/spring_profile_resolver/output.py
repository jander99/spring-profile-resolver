"""Computed YAML output generation with source attribution comments."""

from collections import defaultdict
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap, CommentedSeq
from ruamel.yaml.error import YAMLError

from .models import ConfigSource


def validate_yaml(yaml_string: str) -> tuple[bool, str | None]:
    """Validate that a YAML string is parseable.

    Args:
        yaml_string: The YAML content to validate

    Returns:
        Tuple of (is_valid, error_message). error_message is None if valid.
    """
    yaml = YAML()
    try:
        yaml.load(StringIO(yaml_string))
        return True, None
    except YAMLError as e:
        return False, f"Invalid YAML output: {e}"


def generate_computed_yaml(
    config: dict[str, Any],
    sources: dict[str, ConfigSource],
    base_properties: set[str] | None = None,
    output_path: Path | None = None,
    to_stdout: bool = False,
) -> tuple[str, str | None, list[str]]:
    """Generate the computed YAML with refined comments and warnings.

    Args:
        config: Merged configuration dictionary
        sources: Source tracking map (path -> ConfigSource)
        base_properties: Set of property paths from base application config
        output_path: Optional path to write output file
        to_stdout: If True, also print to stdout

    Returns:
        Tuple of (yaml_string, validation_error, warnings). validation_error is None if valid.
    """
    new_property_warnings: list[str] = []
    base_props = base_properties or set()

    # Build a CommentedMap with source annotations
    commented_config = _build_commented_map(config, sources, base_props, new_property_warnings)

    # Generate YAML string
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=4, offset=2)

    stream = StringIO()
    yaml.dump(commented_config, stream)
    result = stream.getvalue()

    # Validate the generated YAML
    is_valid, validation_error = validate_yaml(result)

    # Only write to file if valid
    if output_path and is_valid:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result)

    # Print to stdout if requested
    if to_stdout:
        print(result)

    return result, validation_error, new_property_warnings


def _is_base_only_property(path: str, source: ConfigSource) -> bool:
    """Check if property comes only from base application config."""
    filename = source.file_path.name
    return filename in ("application.yml", "application.yaml", "application.properties")


def _should_add_comment(
    path: str,
    current_source: ConfigSource,
    base_properties: set[str],
) -> tuple[bool, bool]:
    """Determine if comment should be added and if it's a warning.

    Returns: (should_comment, is_warning)
    """
    # Base-only property: no comment
    if _is_base_only_property(path, current_source):
        return (False, False)

    # New property (not in base): warning comment
    if path not in base_properties:
        return (True, True)

    # Override: regular comment
    return (True, False)


def _format_comment(is_warning: bool, source: ConfigSource) -> str:
    """Format inline comment for property."""
    if is_warning:
        return "WARNING: New property not in base config"
    return source.file_path.name


def _add_property_warning(path: str, warnings: list[str]) -> None:
    """Add warning for new property to warnings list."""
    warnings.append(f"Property '{path}' not found in base application config")


def _build_commented_map(
    config: dict[str, Any],
    sources: dict[str, ConfigSource],
    base_properties: set[str],
    warnings: list[str],
    path_prefix: str = "",
) -> CommentedMap:
    """Build a CommentedMap with refined source attribution.

    Comment rules:
    1. No comment if property only exists in base config
    2. Comment if property exists in base AND is overridden
    3. Warning if property is new (not in base config)
    """
    result = CommentedMap()

    for key, value in config.items():
        current_path = f"{path_prefix}.{key}" if path_prefix else key

        if isinstance(value, dict):
            # Recursively build nested map
            nested = _build_commented_map(
                value, sources, base_properties, warnings, current_path
            )
            result[key] = nested

            # Check if comment needed for this section
            section_source = _get_section_source(current_path, sources)
            if section_source:
                source_obj = next(
                    (src for path, src in sources.items() if str(src) == section_source),
                    None
                )
                if source_obj:
                    should_comment, is_warning = _should_add_comment(
                        current_path, source_obj, base_properties
                    )
                    if should_comment:
                        comment = _format_comment(is_warning, source_obj)
                        result.yaml_add_eol_comment(comment, key)
                        if is_warning:
                            _add_property_warning(current_path, warnings)

        elif isinstance(value, list):
            result[key] = _build_commented_seq(
                value, sources, base_properties, warnings, current_path
            )

            if current_path in sources:
                should_comment, is_warning = _should_add_comment(
                    current_path, sources[current_path], base_properties
                )
                if should_comment:
                    comment = _format_comment(is_warning, sources[current_path])
                    result.yaml_add_eol_comment(comment, key)
                    if is_warning:
                        _add_property_warning(current_path, warnings)

        else:
            result[key] = value

            if current_path in sources:
                should_comment, is_warning = _should_add_comment(
                    current_path, sources[current_path], base_properties
                )
                if should_comment:
                    comment = _format_comment(is_warning, sources[current_path])
                    result.yaml_add_eol_comment(comment, key)
                    if is_warning:
                        _add_property_warning(current_path, warnings)

    return result


def _build_commented_seq(
    items: list[Any],
    sources: dict[str, ConfigSource],
    base_properties: set[str],
    warnings: list[str],
    path_prefix: str,
) -> CommentedSeq:
    """Build a CommentedSeq, recursively converting nested dicts and lists.

    Args:
        items: List of values
        sources: Source tracking map
        base_properties: Set of property paths from base application config
        warnings: List to collect warnings for new properties
        path_prefix: Path prefix for source lookups (e.g., 'authority-mappings')

    Returns:
        CommentedSeq with properly structured nested content
    """
    result = CommentedSeq()

    for idx, item in enumerate(items):
        item_path = f"{path_prefix}[{idx}]"

        if isinstance(item, dict):
            # Recursively convert dict to CommentedMap
            result.append(_build_commented_map(item, sources, base_properties, warnings, item_path))
        elif isinstance(item, list):
            # Recursively convert nested list
            result.append(_build_commented_seq(item, sources, base_properties, warnings, item_path))
        else:
            result.append(item)

    return result


def _get_section_source(path: str, sources: dict[str, ConfigSource]) -> str | None:
    """Get the predominant source for a config section.

    For a dict section, returns the source if all leaf values come from
    the same source. For a leaf value, returns its source.
    """
    # Check if this exact path has a source (leaf value or list)
    if path in sources:
        return str(sources[path])

    # Find all sources under this path
    prefix = path + "."
    child_sources = {
        str(source)
        for key, source in sources.items()
        if key.startswith(prefix) or key == path
    }

    if len(child_sources) == 1:
        return child_sources.pop()
    elif len(child_sources) > 1:
        # Multiple sources - return the most common one
        source_counts: dict[str, int] = defaultdict(int)
        for key, source in sources.items():
            if key.startswith(prefix) or key == path:
                source_counts[str(source)] += 1
        if source_counts:
            return max(source_counts, key=source_counts.get)  # type: ignore

    return None


def _get_parent_source(path: str, sources: dict[str, ConfigSource]) -> str | None:
    """Get the source of the parent section, if determinable."""
    if "." not in path:
        return None

    parent_path = path.rsplit(".", 1)[0]
    return _get_section_source(parent_path, sources)


def format_output_filename(profiles: list[str]) -> str:
    """Generate output filename from profile list.

    Args:
        profiles: List of active profiles

    Returns:
        Filename like 'application-prod-aws-computed.yml'
    """
    if profiles:
        profile_str = "-".join(profiles)
        return f"application-{profile_str}-computed.yml"
    return "application-computed.yml"
