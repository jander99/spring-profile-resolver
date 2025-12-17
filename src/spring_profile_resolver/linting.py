"""Configuration linting for Spring Boot properties."""

import re
from dataclasses import dataclass
from typing import Any

# Version tracking for rule updates
SPRING_BOOT_VERSION = "3.2"  # Rules tested against this Spring Boot version
LAST_UPDATED = "2024-12"  # Last time rules were reviewed/updated

# NOTE: Linting rules are generally version-agnostic, but naming conventions
# may change with new Spring Boot versions. Review official documentation.


@dataclass
class LintIssue:
    """Represents a linting issue found in configuration."""

    severity: str  # "error", "warning", "info"
    property_path: str
    issue_type: str
    message: str
    suggestion: str | None = None


def _is_kebab_case(s: str) -> bool:
    """Check if a string follows kebab-case naming convention."""
    return bool(re.match(r"^[a-z0-9]+(-[a-z0-9]+)*$", s))


def _is_camel_case(s: str) -> bool:
    """Check if a string follows camelCase naming convention."""
    return bool(re.match(r"^[a-z][a-zA-Z0-9]*$", s))


def _is_snake_case(s: str) -> bool:
    """Check if a string follows snake_case naming convention."""
    return bool(re.match(r"^[a-z0-9]+(_[a-z0-9]+)*$", s))


def _get_nesting_depth(config: dict[str, Any], current_depth: int = 0) -> int:
    """Get the maximum nesting depth of a configuration dictionary."""
    if not isinstance(config, dict):
        return current_depth

    if not config:
        return current_depth

    max_depth = current_depth
    for value in config.values():
        if isinstance(value, dict):
            depth = _get_nesting_depth(value, current_depth + 1)
            max_depth = max(max_depth, depth)

    return max_depth


def _all_property_paths_with_values(
    config: dict[str, Any], prefix: str = ""
) -> list[tuple[str, Any]]:
    """Get all property paths with their values."""
    items = []

    for key, value in config.items():
        current_path = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            items.extend(_all_property_paths_with_values(value, current_path))
        else:
            items.append((current_path, value))

    return items


def _extract_keys_from_path(path: str) -> list[str]:
    """Extract individual key components from a property path."""
    # Handle array indices like [0], [1], etc.
    path = re.sub(r"\[\d+\]", "", path)
    return path.split(".")


def check_naming_conventions(config: dict[str, Any]) -> list[LintIssue]:
    """Check if property names follow Spring Boot naming conventions.

    Spring Boot recommends kebab-case for property names.

    Args:
        config: Configuration dictionary

    Returns:
        List of linting issues related to naming conventions
    """
    issues: list[LintIssue] = []
    all_items = _all_property_paths_with_values(config)

    for path, _ in all_items:
        keys = _extract_keys_from_path(path)

        for key in keys:
            # Skip numeric keys
            if key.isdigit():
                continue

            # Skip Spring Boot known properties that use other conventions
            # (Spring Boot itself is inconsistent, e.g., "springdoc", "server")
            if key in ["springdoc", "server", "spring", "logging", "management"]:
                continue

            # Check if the key follows any standard convention
            if not (_is_kebab_case(key) or _is_camel_case(key) or _is_snake_case(key)):
                issues.append(
                    LintIssue(
                        severity="warning",
                        property_path=path,
                        issue_type="naming_convention",
                        message=f"Key '{key}' does not follow a standard naming convention",
                        suggestion="Use kebab-case (recommended), camelCase, or snake_case",
                    )
                )
            # Warn if using snake_case (less common in Spring Boot)
            elif _is_snake_case(key) and not _is_kebab_case(key):
                issues.append(
                    LintIssue(
                        severity="info",
                        property_path=path,
                        issue_type="naming_style",
                        message=f"Key '{key}' uses snake_case",
                        suggestion="Spring Boot recommends kebab-case for property names",
                    )
                )

    return issues


def check_empty_values(config: dict[str, Any]) -> list[LintIssue]:
    """Check for empty or null configuration values.

    Args:
        config: Configuration dictionary

    Returns:
        List of linting issues for empty values
    """
    issues: list[LintIssue] = []
    all_items = _all_property_paths_with_values(config)

    for path, value in all_items:
        # Check for empty strings
        if value == "":
            issues.append(
                LintIssue(
                    severity="warning",
                    property_path=path,
                    issue_type="empty_value",
                    message="Property has empty string value",
                    suggestion="Consider removing the property or setting a default value",
                )
            )
        # Check for None/null values that might be unintentional
        elif value is None:
            issues.append(
                LintIssue(
                    severity="info",
                    property_path=path,
                    issue_type="null_value",
                    message="Property explicitly set to null",
                    suggestion="Verify this is intentional",
                )
            )

    return issues


def check_nesting_depth(config: dict[str, Any], max_depth: int = 10) -> list[LintIssue]:
    """Check for overly deep nesting in configuration.

    Args:
        config: Configuration dictionary
        max_depth: Maximum recommended nesting depth (default: 10)

    Returns:
        List of linting issues for excessive nesting
    """
    issues: list[LintIssue] = []
    depth = _get_nesting_depth(config)

    if depth > max_depth:
        issues.append(
            LintIssue(
                severity="warning",
                property_path="(root)",
                issue_type="excessive_nesting",
                message=f"Configuration has {depth} levels of nesting (max recommended: {max_depth})",
                suggestion="Consider flattening the structure or using profile groups",
            )
        )

    return issues


def check_duplicate_keys(config: dict[str, Any]) -> list[LintIssue]:
    """Check for potential duplicate keys (case-insensitive).

    Spring Boot property binding is case-insensitive in some contexts,
    so having properties that differ only in case can be confusing.

    Args:
        config: Configuration dictionary

    Returns:
        List of linting issues for duplicate keys
    """
    issues: list[LintIssue] = []
    all_items = _all_property_paths_with_values(config)

    # Group paths by lowercase version
    paths_by_lower: dict[str, list[str]] = {}
    for path, _ in all_items:
        lower_path = path.lower()
        if lower_path not in paths_by_lower:
            paths_by_lower[lower_path] = []
        paths_by_lower[lower_path].append(path)

    # Find duplicates
    for _lower_path, paths in paths_by_lower.items():
        if len(paths) > 1:
            issues.append(
                LintIssue(
                    severity="warning",
                    property_path=", ".join(paths),
                    issue_type="duplicate_keys",
                    message=f"Properties differ only in case: {', '.join(paths)}",
                    suggestion="Use consistent casing to avoid confusion",
                )
            )

    return issues


def check_redundant_properties(config: dict[str, Any]) -> list[LintIssue]:
    """Check for redundant or deprecated property patterns.

    Args:
        config: Configuration dictionary

    Returns:
        List of linting issues for redundant properties
    """
    issues: list[LintIssue] = []
    all_items = _all_property_paths_with_values(config)

    # Check for both enabled and disabled flags for the same feature
    enabled_props = {}
    for path, value in all_items:
        if path.endswith(".enabled"):
            base = path[:-8]  # Remove ".enabled"
            enabled_props[base] = value

    for path, _value in all_items:
        if path.endswith(".disabled"):
            base = path[:-9]  # Remove ".disabled"
            if base in enabled_props:
                issues.append(
                    LintIssue(
                        severity="warning",
                        property_path=f"{base}.enabled, {base}.disabled",
                        issue_type="redundant_flags",
                        message="Both .enabled and .disabled flags are set for the same feature",
                        suggestion="Use only one flag (preferably .enabled)",
                    )
                )

    return issues


def lint_configuration(config: dict[str, Any], strict: bool = False) -> list[LintIssue]:
    """Perform comprehensive linting of configuration.

    Args:
        config: Merged configuration dictionary
        strict: If True, applies stricter rules (e.g., enforce kebab-case)

    Returns:
        List of all linting issues found
    """
    issues: list[LintIssue] = []

    # Run all checks
    issues.extend(check_naming_conventions(config))
    issues.extend(check_empty_values(config))
    issues.extend(check_nesting_depth(config))
    issues.extend(check_duplicate_keys(config))
    issues.extend(check_redundant_properties(config))

    # In strict mode, upgrade some warnings to errors
    if strict:
        for issue in issues:
            if issue.issue_type in ["naming_convention", "duplicate_keys"]:
                issue.severity = "error"

    return issues
