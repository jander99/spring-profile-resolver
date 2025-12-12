"""Profile resolution and group expansion for Spring Boot configurations."""

from typing import Any

from .exceptions import CircularProfileGroupError
from .models import ConfigDocument

# Re-export for backwards compatibility
__all__ = [
    "CircularProfileGroupError",
    "parse_profile_groups",
    "expand_profiles",
    "get_applicable_documents",
]


def parse_profile_groups(config: dict[str, Any]) -> dict[str, list[str]]:
    """Extract profile group definitions from config.

    Looks for spring.profiles.group.* entries and returns a mapping
    of group name to list of member profiles.

    Args:
        config: Parsed YAML configuration dictionary

    Returns:
        Dictionary mapping group names to their member profiles

    Example:
        Input config:
            spring:
              profiles:
                group:
                  prod: proddb,prodmq
                  proddb: postgres,hikari

        Output:
            {"prod": ["proddb", "prodmq"], "proddb": ["postgres", "hikari"]}
    """
    groups: dict[str, list[str]] = {}

    try:
        spring = config.get("spring", {})
        if not isinstance(spring, dict):
            return groups

        profiles = spring.get("profiles", {})
        if not isinstance(profiles, dict):
            return groups

        group = profiles.get("group", {})
        if not isinstance(group, dict):
            return groups

        for name, members in group.items():
            if members is None:
                continue
            if isinstance(members, str):
                # Comma-separated string: "proddb,prodmq"
                groups[str(name)] = [m.strip() for m in members.split(",") if m.strip()]
            elif isinstance(members, list):
                # List format: [proddb, prodmq]
                groups[str(name)] = [str(m) for m in members if m]
            # Ignore other types

    except (AttributeError, TypeError):
        pass

    return groups


def expand_profiles(
    requested: list[str],
    groups: dict[str, list[str]],
) -> list[str]:
    """Expand profile list, resolving groups recursively.

    Algorithm (matches Spring Boot 2.4+):
    1. Process profiles in the order specified
    2. For each profile, if it's a group, expand it depth-first
    3. Maintain insertion order, avoiding duplicates
    4. Detect circular references and raise error

    Args:
        requested: List of profile names requested by user
        groups: Dictionary of group definitions

    Returns:
        Expanded list maintaining proper precedence order

    Raises:
        CircularProfileGroupError: If circular group references are detected

    Example:
        With groups = {"prod": ["proddb", "prodmq"], "proddb": ["postgres", "hikari"]}
        expand_profiles(["prod"], groups) returns:
        ["prod", "proddb", "postgres", "hikari", "prodmq"]
    """
    result: list[str] = []
    seen: set[str] = set()

    def expand_single(profile: str, path: list[str]) -> None:
        """Recursively expand a single profile."""
        # Check for circular reference
        if profile in path:
            raise CircularProfileGroupError(path + [profile])

        # Skip if already processed
        if profile in seen:
            return

        # Add the profile itself first
        seen.add(profile)
        result.append(profile)

        # If it's a group, expand its members depth-first
        if profile in groups:
            for member in groups[profile]:
                expand_single(member, path + [profile])

    for profile in requested:
        expand_single(profile, [])

    return result


def get_applicable_documents(
    documents: list[ConfigDocument],
    active_profiles: list[str],
) -> list[ConfigDocument]:
    """Filter and order documents applicable to active profiles.

    Args:
        documents: List of all parsed config documents
        active_profiles: List of active profile names (already expanded)

    Returns:
        Filtered list of documents that apply to the active profiles,
        maintaining their original order
    """
    return [doc for doc in documents if doc.matches_profiles(active_profiles)]
