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
    output_path: Path | None = None,
    to_stdout: bool = False,
) -> tuple[str, str | None]:
    """Generate the computed YAML with source comments.

    Args:
        config: Merged configuration dictionary
        sources: Source tracking map (path -> ConfigSource)
        output_path: Optional path to write output file
        to_stdout: If True, also print to stdout

    Returns:
        Tuple of (yaml_string, validation_error). validation_error is None if valid.
    """
    # Build a CommentedMap with source annotations
    commented_config = _build_commented_map(config, sources)

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

    return result, validation_error


def _build_commented_map(
    config: dict[str, Any],
    sources: dict[str, ConfigSource],
    path_prefix: str = "",
) -> CommentedMap:
    """Build a CommentedMap with source attribution comments.

    Uses block comments for sections where all values come from the same source,
    and inline comments when individual keys differ.
    """
    result = CommentedMap()

    # Track which source we last emitted a block comment for
    last_block_source: str | None = None

    for key, value in config.items():
        current_path = f"{path_prefix}.{key}" if path_prefix else key

        # Determine the source for this key/section
        section_source = _get_section_source(current_path, sources)

        if isinstance(value, dict):
            # Recursively build nested CommentedMap
            nested = _build_commented_map(value, sources, current_path)
            result[key] = nested

            # Add block comment if source changes
            if section_source and section_source != last_block_source:
                result.yaml_set_comment_before_after_key(
                    key, before=f"From: {section_source}"
                )
                last_block_source = section_source
        elif isinstance(value, list):
            # Convert list items, recursively handling nested dicts
            result[key] = _build_commented_seq(value, sources, current_path)

            # Add block comment if source changes
            if section_source and section_source != last_block_source:
                result.yaml_set_comment_before_after_key(
                    key, before=f"From: {section_source}"
                )
                last_block_source = section_source
        else:
            result[key] = value

            # Determine comment style for this value
            if current_path in sources:
                value_source = str(sources[current_path])

                # Check if this differs from the expected section source
                parent_source = _get_parent_source(current_path, sources)

                if parent_source and value_source != parent_source:
                    # Different source than parent - use inline comment
                    result.yaml_add_eol_comment(value_source, key)
                elif not parent_source and section_source != last_block_source:
                    # Top-level key or new section
                    result.yaml_set_comment_before_after_key(
                        key, before=f"From: {value_source}"
                    )
                    last_block_source = section_source

    return result


def _build_commented_seq(
    items: list[Any],
    sources: dict[str, ConfigSource],
    path_prefix: str,
) -> CommentedSeq:
    """Build a CommentedSeq, recursively converting nested dicts and lists.

    Args:
        items: List of values
        sources: Source tracking map
        path_prefix: Path prefix for source lookups (e.g., 'authority-mappings')

    Returns:
        CommentedSeq with properly structured nested content
    """
    result = CommentedSeq()

    for idx, item in enumerate(items):
        item_path = f"{path_prefix}[{idx}]"

        if isinstance(item, dict):
            # Recursively convert dict to CommentedMap
            result.append(_build_commented_map(item, sources, item_path))
        elif isinstance(item, list):
            # Recursively convert nested list
            result.append(_build_commented_seq(item, sources, item_path))
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
