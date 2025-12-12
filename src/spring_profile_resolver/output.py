"""Computed YAML output generation with source attribution comments."""

from collections import defaultdict
from io import StringIO
from pathlib import Path
from typing import Any

from ruamel.yaml import YAML
from ruamel.yaml.comments import CommentedMap

from .models import ConfigSource


def generate_computed_yaml(
    config: dict[str, Any],
    sources: dict[str, ConfigSource],
    output_path: Path | None = None,
    to_stdout: bool = False,
) -> str:
    """Generate the computed YAML with source comments.

    Args:
        config: Merged configuration dictionary
        sources: Source tracking map (path -> ConfigSource)
        output_path: Optional path to write output file
        to_stdout: If True, also print to stdout

    Returns:
        The generated YAML string
    """
    # Build a CommentedMap with source annotations
    commented_config = _build_commented_map(config, sources)

    # Generate YAML string
    yaml = YAML()
    yaml.default_flow_style = False
    yaml.indent(mapping=2, sequence=2, offset=2)

    stream = StringIO()
    yaml.dump(commented_config, stream)
    result = stream.getvalue()

    # Write to file if path provided
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(result)

    # Print to stdout if requested
    if to_stdout:
        print(result)

    return result


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
