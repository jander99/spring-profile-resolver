"""Schema validation and property conflict detection for Spring Boot configurations."""

# mypy: disable-error-code="arg-type,assignment,operator,index,attr-defined"

from dataclasses import dataclass
from typing import Any

# Version tracking for rule updates
SPRING_BOOT_VERSION = "3.2"  # Rules tested against this Spring Boot version
LAST_UPDATED = "2024-12"  # Last time rules were reviewed/updated


@dataclass
class ValidationIssue:
    """Represents a validation issue found in configuration."""

    severity: str  # "error" or "warning"
    property_path: str
    message: str
    suggestion: str | None = None


# Mutually exclusive property groups
# NOTE: When Spring Boot releases a new version, review the configuration reference
# for new mutually exclusive properties or changed behaviors
MUTUALLY_EXCLUSIVE_PROPERTIES = [
    {
        # Spring Boot 1.x+ - Datasource can use URL or JNDI, not both
        "properties": ["spring.datasource.url", "spring.datasource.jndi-name"],
        "message": "Cannot specify both datasource URL and JNDI name",
        "severity": "error",
    },
    {
        # Spring Boot 1.x+ - Database type can be auto-detected or explicit
        "properties": ["spring.jpa.database", "spring.jpa.database-platform"],
        "message": "Specifying both 'database' and 'database-platform' may cause conflicts",
        "severity": "warning",
    },
]

# Dangerous property combinations (properties that shouldn't be used together)
# NOTE: Review Spring Boot security best practices when updating versions
DANGEROUS_COMBINATIONS = [
    {
        # Spring Boot 1.x+ - Hibernate DDL auto in production is dangerous
        "condition": lambda config: (
            _get_nested_value(config, "spring.jpa.hibernate.ddl-auto") in ["create", "create-drop"]
            and _get_nested_value(config, "spring.profiles.active") in ["prod", "production"]
        ),
        "message": "DDL auto-create/drop is enabled with production profile - this will destroy your database!",
        "severity": "error",
        "suggestion": "Use 'validate' or 'none' for production environments",
    },
    {
        # Spring Boot 1.x+ - H2 console exposes database in production
        "condition": lambda config: (
            _get_nested_value(config, "spring.h2.console.enabled") is True
            and _get_nested_value(config, "spring.profiles.active") in ["prod", "production"]
        ),
        "message": "H2 console is enabled in production - this is a security risk",
        "severity": "error",
        "suggestion": "Disable H2 console in production profiles",
    },
    {
        # Spring Boot 2.x+ - Actuator endpoints should be secured
        "condition": lambda config: (
            _get_nested_value(config, "management.endpoints.web.exposure.include") == "*"
            and not _get_nested_value(config, "management.endpoints.web.base-path")
        ),
        "message": "All actuator endpoints are exposed without custom base path - potential security risk",
        "severity": "warning",
        "suggestion": "Limit exposed endpoints or set a custom base-path",
    },
    {
        # Spring Boot 1.x+ - DevTools should never be in production
        "condition": lambda config: (
            _get_nested_value(config, "spring.devtools.remote.secret") is not None
            and _get_nested_value(config, "spring.profiles.active") in ["prod", "production"]
        ),
        "message": "DevTools remote secret is set in production profile",
        "severity": "warning",
        "suggestion": "DevTools should not be used in production",
    },
]

# Properties that require certain other properties to be set
REQUIRED_DEPENDENCIES = [
    {
        "property": "server.ssl.enabled",
        "value": True,
        "requires": ["server.ssl.key-store"],
        "message": "SSL enabled but key-store path not configured",
        "severity": "error",
    },
    {
        "property": "spring.datasource.url",
        "requires_one_of": ["spring.datasource.driver-class-name", "spring.datasource.type"],
        "message": "Datasource URL specified but driver class may be needed",
        "severity": "warning",
    },
    {
        "property": "spring.kafka.producer.bootstrap-servers",
        "requires": ["spring.kafka.bootstrap-servers"],
        "message": "Kafka producer bootstrap-servers should typically use spring.kafka.bootstrap-servers",
        "severity": "warning",
        "suggestion": "Use spring.kafka.bootstrap-servers for consistency",
    },
]

# Common property typos and suggestions
# NOTE: When Spring Boot deprecates properties, add them here with the new property name
COMMON_TYPOS = {
    "server.prot": "server.port",  # Common typo
    "server.context-path": "server.servlet.context-path",  # Deprecated in Spring Boot 2.0
    "spring.datasource.driver-class": "spring.datasource.driver-class-name",  # Common typo
    "spring.jpa.show-sql": "spring.jpa.properties.hibernate.show_sql",  # Incorrect property path
    "logging.level": "logging.level.*",  # Requires specific logger name
    "management.security.enabled": "spring.security.user.name (property removed in Spring Boot 2.x)",  # Removed in 2.x
}


def _get_nested_value(config: dict[str, Any], path: str) -> Any:
    """Get a nested value from config using dot notation.

    Args:
        config: Configuration dictionary
        path: Dot-separated path (e.g., "server.port")

    Returns:
        The value at that path, or None if not found
    """
    parts = path.split(".")
    current = config

    for part in parts:
        if not isinstance(current, dict):
            return None
        current = current.get(part)
        if current is None:
            return None

    return current


def _set_nested_value(config: dict[str, Any], path: str, value: Any) -> None:
    """Set a nested value in config using dot notation (for testing)."""
    parts = path.split(".")
    current = config

    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]

    current[parts[-1]] = value


def _all_property_paths(config: dict[str, Any], prefix: str = "") -> list[str]:
    """Get all property paths in a config dict.

    Args:
        config: Configuration dictionary
        prefix: Current path prefix (used for recursion)

    Returns:
        List of all property paths in dot notation
    """
    paths = []

    for key, value in config.items():
        current_path = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            paths.extend(_all_property_paths(value, current_path))
        else:
            paths.append(current_path)

    return paths


def validate_configuration(config: dict[str, Any]) -> list[ValidationIssue]:
    """Validate a Spring Boot configuration.

    Checks for:
    - Mutually exclusive properties
    - Dangerous property combinations
    - Missing required dependencies
    - Common typos

    Args:
        config: Merged configuration dictionary

    Returns:
        List of validation issues found
    """
    issues: list[ValidationIssue] = []

    # Check for common typos
    all_paths = _all_property_paths(config)
    for path in all_paths:
        if path in COMMON_TYPOS:
            issues.append(
                ValidationIssue(
                    severity="warning",
                    property_path=path,
                    message="Possible typo or deprecated property",
                    suggestion=f"Did you mean '{COMMON_TYPOS[path]}'?",
                )
            )

    # Check mutually exclusive properties
    for rule in MUTUALLY_EXCLUSIVE_PROPERTIES:
        props = rule["properties"]
        found_props = [p for p in props if _get_nested_value(config, p) is not None]

        if len(found_props) >= 2:
            issues.append(
                ValidationIssue(
                    severity=rule["severity"],
                    property_path=", ".join(found_props),
                    message=rule["message"],
                    suggestion=rule.get("suggestion"),
                )
            )

    # Check dangerous combinations
    for rule in DANGEROUS_COMBINATIONS:
        if rule["condition"](config):
            # Try to determine which property triggered this
            property_path = "configuration"
            issues.append(
                ValidationIssue(
                    severity=rule["severity"],
                    property_path=property_path,
                    message=rule["message"],
                    suggestion=rule.get("suggestion"),
                )
            )

    # Check required dependencies
    for rule in REQUIRED_DEPENDENCIES:
        value = _get_nested_value(config, rule["property"])

        if value is None:
            continue

        # Check if specific value is required
        if "value" in rule and value != rule["value"]:
            continue

        # Check required properties
        if "requires" in rule:
            missing = [
                req for req in rule["requires"]
                if _get_nested_value(config, req) is None
            ]
            if missing:
                issues.append(
                    ValidationIssue(
                        severity=rule["severity"],
                        property_path=rule["property"],
                        message=f"{rule['message']} (missing: {', '.join(missing)})",
                        suggestion=rule.get("suggestion"),
                    )
                )

        # Check requires_one_of
        if "requires_one_of" in rule:
            has_any = any(
                _get_nested_value(config, req) is not None
                for req in rule["requires_one_of"]
            )
            if not has_any:
                issues.append(
                    ValidationIssue(
                        severity=rule["severity"],
                        property_path=rule["property"],
                        message=rule["message"],
                        suggestion=rule.get("suggestion"),
                    )
                )

    return issues
