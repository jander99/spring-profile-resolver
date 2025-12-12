"""Environment variable handling for Spring Boot configuration.

Supports:
- Loading .env files
- Converting env var names to Spring property paths
- Env vars as property sources for placeholder resolution
"""

import os
import re
from pathlib import Path
from typing import Any


def load_env_file(path: Path) -> dict[str, str]:
    """Load environment variables from a .env file.

    Supports:
    - KEY=value format
    - KEY="quoted value" format
    - Comments starting with #
    - Empty lines

    Args:
        path: Path to the .env file

    Returns:
        Dictionary of environment variable name to value

    Raises:
        FileNotFoundError: If the file doesn't exist
    """
    env_vars: dict[str, str] = {}

    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("#"):
                continue

            # Parse KEY=value
            if "=" not in line:
                continue

            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()

            # Remove quotes if present
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]

            env_vars[key] = value

    return env_vars


def parse_env_overrides(overrides: list[str]) -> dict[str, str]:
    """Parse command-line environment variable overrides.

    Args:
        overrides: List of "KEY=value" strings

    Returns:
        Dictionary of env var name to value
    """
    env_vars: dict[str, str] = {}

    for override in overrides:
        if "=" not in override:
            continue

        key, _, value = override.partition("=")
        env_vars[key.strip()] = value

    return env_vars


def env_var_to_property_path(env_var: str) -> str:
    """Convert an environment variable name to a Spring property path.

    Spring Boot's relaxed binding rules:
    - SPRING_DATASOURCE_URL -> spring.datasource.url
    - MY_APP_NAME -> my.app.name
    - server_port -> server.port

    Args:
        env_var: Environment variable name

    Returns:
        Spring property path (dot-notation)
    """
    # Convert underscores to dots and lowercase
    # Handle double underscores as literal underscores (Spring Boot convention)
    # First, protect double underscores
    protected = env_var.replace("__", "\x00")
    # Convert single underscores to dots
    dotted = protected.replace("_", ".")
    # Restore double underscores as single underscores
    result = dotted.replace("\x00", "_")
    # Lowercase
    return result.lower()


def property_path_to_env_vars(property_path: str) -> list[str]:
    """Get possible environment variable names for a property path.

    Generates multiple possible env var names that could map to a property.

    Args:
        property_path: Spring property path (e.g., "spring.datasource.url")

    Returns:
        List of possible env var names, in order of precedence
    """
    # Standard conversion: dots to underscores, uppercase
    standard = property_path.replace(".", "_").upper()

    # Also try with dashes converted
    with_dashes = property_path.replace("-", "_").replace(".", "_").upper()

    # Return unique values in order
    result = [standard]
    if with_dashes != standard:
        result.append(with_dashes)

    return result


def get_env_value(
    property_path: str,
    env_vars: dict[str, str],
    system_env: bool = True,
) -> str | None:
    """Get the value for a property path from environment variables.

    Checks both provided env_vars dict and system environment.

    Args:
        property_path: Spring property path (e.g., "database.host")
        env_vars: Dictionary of loaded env vars
        system_env: Whether to also check os.environ

    Returns:
        The env var value, or None if not found
    """
    # Try standard env var names
    possible_names = property_path_to_env_vars(property_path)

    for name in possible_names:
        # Check provided env vars first (higher precedence)
        if name in env_vars:
            return env_vars[name]

        # Check system environment
        if system_env and name in os.environ:
            return os.environ[name]

    return None


def env_vars_to_nested_dict(env_vars: dict[str, str]) -> dict[str, Any]:
    """Convert environment variables to a nested configuration dict.

    Converts env var names to property paths and builds a nested structure.

    Args:
        env_vars: Dictionary of env var name to value

    Returns:
        Nested configuration dictionary
    """
    result: dict[str, Any] = {}

    for env_var, value in env_vars.items():
        property_path = env_var_to_property_path(env_var)
        _set_nested_value(result, property_path, _convert_value(value))

    return result


def _set_nested_value(d: dict[str, Any], path: str, value: Any) -> None:
    """Set a value in a nested dict using dot-notation path."""
    parts = path.split(".")
    current = d

    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]

    current[parts[-1]] = value


def _convert_value(value: str) -> Any:
    """Convert a string value to appropriate Python type."""
    # Boolean conversion
    if value.lower() == "true":
        return True
    if value.lower() == "false":
        return False

    # Integer conversion
    try:
        return int(value)
    except ValueError:
        pass

    # Float conversion
    try:
        return float(value)
    except ValueError:
        pass

    return value
