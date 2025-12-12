"""Deep merge configuration with source tracking."""

import copy
from typing import Any

from .models import ConfigDocument, ConfigSource


def deep_merge(
    base: dict[str, Any],
    override: dict[str, Any],
    base_sources: dict[str, ConfigSource],
    override_source: ConfigSource,
    path_prefix: str = "",
) -> tuple[dict[str, Any], dict[str, ConfigSource]]:
    """Deep merge override into base, tracking sources.

    Args:
        base: Base configuration dictionary
        override: Override configuration dictionary
        base_sources: Source tracking for base config
        override_source: Source for all values in override
        path_prefix: Current path prefix for source tracking keys

    Returns:
        Tuple of (merged_config, sources_map)
    """
    # Use deep copy to ensure nested structures are not shared references
    result = copy.deepcopy(base)
    sources = dict(base_sources)  # Source tracking is flat, shallow copy is fine

    for key, override_value in override.items():
        current_path = f"{path_prefix}.{key}" if path_prefix else key

        if key not in result:
            # New key - add it with source tracking
            result[key] = override_value
            _track_sources(override_value, current_path, override_source, sources)
        elif isinstance(result[key], dict) and isinstance(override_value, dict):
            # Both are dicts - recurse
            result[key], sources = deep_merge(
                result[key],
                override_value,
                sources,
                override_source,
                current_path,
            )
        else:
            # Override (including list replacement)
            result[key] = override_value
            # Remove old source entries for this path and descendants
            _remove_sources_under_path(current_path, sources)
            _track_sources(override_value, current_path, override_source, sources)

    return result, sources


def _track_sources(
    value: Any,
    path: str,
    source: ConfigSource,
    sources: dict[str, ConfigSource],
) -> None:
    """Track source for a value and all its descendants.

    For leaf values (non-dict), tracks the exact path.
    For dicts, recursively tracks all nested leaf values.
    For lists, tracks the list path (entire list attributed to source).
    """
    if isinstance(value, dict):
        for k, v in value.items():
            child_path = f"{path}.{k}" if path else k
            _track_sources(v, child_path, source, sources)
    elif isinstance(value, list):
        # Lists are replaced entirely - track at the list level
        sources[path] = source
    else:
        # Leaf value
        sources[path] = source


def _remove_sources_under_path(path: str, sources: dict[str, ConfigSource]) -> None:
    """Remove all source entries at or under the given path.

    This function has O(n) complexity where n is the number of entries in sources,
    as it must scan all keys to find those matching the path prefix. This is
    acceptable for typical Spring Boot configurations which have limited depth
    and key counts, but could be optimized with a trie-based structure if
    configurations grow very large.

    Args:
        path: The configuration path to remove (e.g., "server.ssl")
        sources: The sources map to modify in place
    """
    prefix = path + "."
    keys_to_remove = [k for k in sources if k == path or k.startswith(prefix)]
    for k in keys_to_remove:
        del sources[k]


def merge_configs(
    documents: list[ConfigDocument],
) -> tuple[dict[str, Any], dict[str, ConfigSource]]:
    """Merge multiple config documents in order.

    Later documents override earlier ones for the same keys.
    Source tracking maintains which file provided each value.

    Args:
        documents: List of ConfigDocument objects to merge in order

    Returns:
        Tuple of (merged_config, sources_map)
    """
    if not documents:
        return {}, {}

    # Start with first document
    result = dict(documents[0].content)
    sources: dict[str, ConfigSource] = {}
    first_source = ConfigSource(file_path=documents[0].source_file)
    _track_sources(result, "", first_source, sources)

    # Merge remaining documents
    for doc in documents[1:]:
        doc_source = ConfigSource(file_path=doc.source_file)
        result, sources = deep_merge(result, doc.content, sources, doc_source)

    return result, sources
