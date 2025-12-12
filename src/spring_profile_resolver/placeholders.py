"""Property placeholder resolution for Spring Boot configurations."""

import re
from typing import Any

# Pattern to match ${property.name} or ${property.name:default}
PLACEHOLDER_PATTERN = re.compile(r"\$\{([^}:]+)(?::([^}]*))?\}")


def resolve_placeholders(
    config: dict[str, Any],
    max_iterations: int = 10,
    env_vars: dict[str, str] | None = None,
    use_system_env: bool = True,
) -> tuple[dict[str, Any], list[str]]:
    """Resolve all ${...} placeholders in config values.

    Iterates to handle chained references where one placeholder
    resolves to a value containing another placeholder.

    Resolution order (highest precedence first):
    1. Environment variables (env_vars parameter)
    2. System environment variables (if use_system_env=True)
    3. Config values

    Args:
        config: Configuration dictionary to process
        max_iterations: Maximum resolution iterations (prevents infinite loops)
        env_vars: Optional dict of environment variables for resolution
        use_system_env: Whether to also check system env vars (os.environ)

    Returns:
        Tuple of (resolved_config, warnings) where warnings contains
        messages about unresolved placeholders
    """
    result = _deep_copy_config(config)
    warnings: list[str] = []

    for _ in range(max_iterations):
        result, changed, new_warnings = _resolve_pass(
            result, result, env_vars=env_vars, use_system_env=use_system_env
        )
        warnings.extend(new_warnings)
        if not changed:
            break

    # Collect any remaining unresolved placeholders
    remaining = _find_unresolved_placeholders(result)
    for path, placeholder in remaining:
        warnings.append(f"Unresolved placeholder at {path}: {placeholder}")

    return result, warnings


def _resolve_pass(
    config: dict[str, Any],
    root_config: dict[str, Any],
    env_vars: dict[str, str] | None = None,
    use_system_env: bool = True,
) -> tuple[dict[str, Any], bool, list[str]]:
    """Single pass of placeholder resolution.

    Args:
        config: Current config section being processed
        root_config: Full config for value lookups
        env_vars: Optional dict of environment variables
        use_system_env: Whether to check system env vars

    Returns:
        Tuple of (processed_config, changed, warnings)
    """
    result: dict[str, Any] = {}
    changed = False
    warnings: list[str] = []

    for key, value in config.items():
        if isinstance(value, dict):
            new_value, sub_changed, sub_warnings = _resolve_pass(
                value, root_config, env_vars=env_vars, use_system_env=use_system_env
            )
            result[key] = new_value
            changed = changed or sub_changed
            warnings.extend(sub_warnings)
        elif isinstance(value, list):
            new_list: list[Any] = []
            for item in value:
                if isinstance(item, str):
                    resolved, item_changed = resolve_single_value(
                        item, root_config, env_vars=env_vars, use_system_env=use_system_env
                    )
                    new_list.append(resolved)
                    changed = changed or item_changed
                elif isinstance(item, dict):
                    resolved_dict, sub_changed, sub_warnings = _resolve_pass(
                        item, root_config, env_vars=env_vars, use_system_env=use_system_env
                    )
                    new_list.append(resolved_dict)
                    changed = changed or sub_changed
                    warnings.extend(sub_warnings)
                else:
                    new_list.append(item)
            result[key] = new_list
        elif isinstance(value, str):
            resolved, value_changed = resolve_single_value(
                value, root_config, env_vars=env_vars, use_system_env=use_system_env
            )
            result[key] = resolved
            changed = changed or value_changed
        else:
            result[key] = value

    return result, changed, warnings


def resolve_single_value(
    value: str,
    config: dict[str, Any],
    env_vars: dict[str, str] | None = None,
    use_system_env: bool = True,
) -> tuple[str, bool]:
    """Resolve placeholders in a single string value.

    Resolution order (highest precedence first):
    1. Environment variables (env_vars parameter)
    2. System environment variables (if use_system_env=True)
    3. Config values

    Args:
        value: String potentially containing ${...} placeholders
        config: Configuration to look up values from
        env_vars: Optional dict of environment variables
        use_system_env: Whether to check system env vars

    Returns:
        Tuple of (resolved_value, changed) where changed indicates
        if any substitution was made
    """
    if "${" not in value:
        return value, False

    changed = False

    def replace_match(match: re.Match[str]) -> str:
        nonlocal changed
        key_path = match.group(1)
        default_value = match.group(2)  # May be None

        # Try env vars first (highest precedence)
        env_value = _get_env_value(key_path, env_vars, use_system_env)
        if env_value is not None:
            changed = True
            return env_value

        # Try config values
        resolved = get_nested_value(config, key_path)
        if resolved is not None:
            changed = True
            return str(resolved)

        # Use default if provided
        if default_value is not None:
            changed = True
            return default_value

        # Leave unresolved placeholder as-is
        return match.group(0)

    result = PLACEHOLDER_PATTERN.sub(replace_match, value)
    return result, changed


def _get_env_value(
    key_path: str,
    env_vars: dict[str, str] | None,
    use_system_env: bool,
) -> str | None:
    """Get value from environment variables.

    Converts property path to env var name and checks both
    provided env_vars and system environment.
    """
    import os

    from .env_vars import get_env_value

    return get_env_value(key_path, env_vars or {}, system_env=use_system_env)


def get_nested_value(config: dict[str, Any], key_path: str) -> Any | None:
    """Get value by dot-notation path.

    Args:
        config: Configuration dictionary
        key_path: Dot-separated path like 'server.port' or 'database.host'

    Returns:
        Value at the path, or None if not found
    """
    parts = key_path.split(".")
    current: Any = config

    for part in parts:
        if not isinstance(current, dict):
            return None
        if part not in current:
            return None
        current = current[part]

    return current


def _deep_copy_config(config: dict[str, Any]) -> dict[str, Any]:
    """Create a deep copy of a config dictionary."""
    result: dict[str, Any] = {}
    for key, value in config.items():
        if isinstance(value, dict):
            result[key] = _deep_copy_config(value)
        elif isinstance(value, list):
            result[key] = [
                _deep_copy_config(item) if isinstance(item, dict) else item
                for item in value
            ]
        else:
            result[key] = value
    return result


def _find_unresolved_placeholders(
    config: dict[str, Any],
    path_prefix: str = "",
) -> list[tuple[str, str]]:
    """Find all remaining unresolved placeholders in config.

    Returns:
        List of (path, placeholder) tuples
    """
    results: list[tuple[str, str]] = []

    for key, value in config.items():
        current_path = f"{path_prefix}.{key}" if path_prefix else key

        if isinstance(value, dict):
            results.extend(_find_unresolved_placeholders(value, current_path))
        elif isinstance(value, list):
            for i, item in enumerate(value):
                item_path = f"{current_path}[{i}]"
                if isinstance(item, str):
                    for match in PLACEHOLDER_PATTERN.finditer(item):
                        results.append((item_path, match.group(0)))
                elif isinstance(item, dict):
                    results.extend(_find_unresolved_placeholders(item, item_path))
        elif isinstance(value, str):
            for match in PLACEHOLDER_PATTERN.finditer(value):
                results.append((current_path, match.group(0)))

    return results
