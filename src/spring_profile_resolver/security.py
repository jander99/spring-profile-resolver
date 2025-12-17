"""Security scanning for Spring Boot configurations."""

# mypy: disable-error-code="arg-type,assignment,operator,index,attr-defined"

import re
from dataclasses import dataclass
from typing import Any

# Version tracking for rule updates
SPRING_BOOT_VERSION = "3.2"  # Rules tested against this Spring Boot version
LAST_UPDATED = "2024-12"  # Last time rules were reviewed/updated


@dataclass
class SecurityIssue:
    """Represents a security issue found in configuration."""

    severity: str  # "critical", "high", "medium", "low"
    property_path: str
    issue_type: str
    message: str
    recommendation: str | None = None


# Patterns for detecting hardcoded secrets
SECRET_PATTERNS = [
    {
        "name": "AWS Access Key",
        "pattern": re.compile(r"AKIA[0-9A-Z]{16}"),
        "severity": "critical",
    },
    {
        "name": "AWS Secret Key",
        "pattern": re.compile(r"(?i)aws[_-]?secret[_-]?(?:access[_-]?)?key"),
        "severity": "critical",
    },
    {
        "name": "Generic API Key",
        "pattern": re.compile(r"(?i)(api[_-]?key|apikey)"),
        "severity": "high",
    },
    {
        "name": "Generic Secret",
        "pattern": re.compile(r"(?i)(secret|password|passwd|pwd)"),
        "severity": "high",
    },
    {
        "name": "Private Key",
        "pattern": re.compile(r"-----BEGIN (?:RSA|DSA|EC|OPENSSH) PRIVATE KEY-----"),
        "severity": "critical",
    },
    {
        "name": "JWT Token",
        "pattern": re.compile(r"eyJ[A-Za-z0-9_-]*\.eyJ[A-Za-z0-9_-]*\.[A-Za-z0-9_-]*"),
        "severity": "high",
    },
    {
        "name": "Database Connection String",
        "pattern": re.compile(r"(?i)(jdbc|mongodb|postgresql|mysql)://[^:]+:[^@]+@"),
        "severity": "high",
    },
]

# Suspicious property keywords that often contain secrets
SUSPICIOUS_PROPERTY_KEYWORDS = [
    "password",
    "secret",
    "token",
    "api-key",
    "apikey",
    "api_key",
    "private-key",
    "privatekey",
    "access-key",
    "accesskey",
    "auth-token",
    "credentials",
    "oauth",
]

# Insecure configuration patterns
# NOTE: Review Spring Boot security documentation when updating versions for new security properties
INSECURE_CONFIGURATIONS = [
    {
        # Spring Boot 1.x+ - Weak passwords are a critical security issue
        "property": "spring.security.user.password",
        "pattern": re.compile(r"^(admin|password|123456|root|test)$", re.IGNORECASE),
        "message": "Weak or default password detected",
        "severity": "critical",
        "recommendation": "Use a strong password or preferably use environment variables",
    },
    {
        "property": "security.basic.enabled",
        "value": False,
        "message": "Basic security is disabled",
        "severity": "high",
        "recommendation": "Enable security for production environments",
    },
    {
        "property": "management.security.enabled",
        "value": False,
        "message": "Management endpoint security is disabled",
        "severity": "high",
        "recommendation": "Enable security for management endpoints",
    },
    {
        "property": "spring.h2.console.enabled",
        "value": True,
        "message": "H2 console is enabled - database exposed via web interface",
        "severity": "high",
        "recommendation": "Disable in production or restrict access with security rules",
    },
    {
        "property": "spring.jpa.show-sql",
        "value": True,
        "message": "SQL queries are being logged - may expose sensitive data",
        "severity": "medium",
        "recommendation": "Disable in production to prevent data leakage",
    },
    {
        "property": "logging.level.root",
        "value": "DEBUG",
        "message": "Root logging level set to DEBUG - may log sensitive information",
        "severity": "medium",
        "recommendation": "Use INFO or WARN in production",
    },
    {
        "property": "logging.level.org.springframework.security",
        "value": "DEBUG",
        "message": "Security logging at DEBUG level - may expose authentication details",
        "severity": "medium",
        "recommendation": "Use INFO or WARN in production",
    },
    {
        "property": "server.ssl.enabled",
        "value": False,
        "message": "SSL/TLS is disabled",
        "severity": "high",
        "recommendation": "Enable SSL for production environments",
    },
    {
        "property": "spring.devtools.restart.enabled",
        "value": True,
        "message": "DevTools restart is enabled - should not be used in production",
        "severity": "medium",
        "recommendation": "Ensure DevTools is excluded from production builds",
    },
]

# Properties that should use environment variables instead of hardcoded values
SHOULD_USE_ENV_VARS = [
    "spring.datasource.password",
    "spring.datasource.username",
    "spring.security.oauth2.client.registration.*.client-secret",
    "spring.security.oauth2.client.registration.*.client-id",
    "spring.mail.password",
    "spring.mail.username",
    "spring.rabbitmq.password",
    "spring.rabbitmq.username",
    "spring.redis.password",
    "spring.kafka.properties.sasl.jaas.config",
]


def _get_nested_value(config: dict[str, Any], path: str) -> Any:
    """Get a nested value from config using dot notation."""
    parts = path.split(".")
    current = config

    for part in parts:
        if not isinstance(current, dict):
            return None
        # Handle wildcard matching
        if part == "*":
            return current
        current = current.get(part)
        if current is None:
            return None

    return current


def _all_property_paths_with_values(
    config: dict[str, Any], prefix: str = ""
) -> list[tuple[str, Any]]:
    """Get all property paths with their values.

    Args:
        config: Configuration dictionary
        prefix: Current path prefix (used for recursion)

    Returns:
        List of (path, value) tuples
    """
    items = []

    for key, value in config.items():
        current_path = f"{prefix}.{key}" if prefix else key

        if isinstance(value, dict):
            items.extend(_all_property_paths_with_values(value, current_path))
        else:
            items.append((current_path, value))

    return items


def _contains_placeholder(value: Any) -> bool:
    """Check if a value contains a placeholder like ${...}."""
    if not isinstance(value, str):
        return False
    return "${" in value and "}" in value


def scan_for_secrets(config: dict[str, Any]) -> list[SecurityIssue]:
    """Scan configuration for hardcoded secrets and sensitive data.

    Args:
        config: Merged configuration dictionary

    Returns:
        List of security issues found
    """
    issues: list[SecurityIssue] = []
    all_items = _all_property_paths_with_values(config)

    for path, value in all_items:
        # Skip if value is a placeholder (likely using env var)
        if _contains_placeholder(value):
            continue

        # Skip null/None values
        if value is None:
            continue

        # Convert value to string for pattern matching
        value_str = str(value)

        # Check for secret patterns in the value
        for pattern_info in SECRET_PATTERNS:
            if pattern_info["pattern"].search(value_str):
                # For generic keywords like "password", only flag if path doesn't suggest it's a placeholder
                if pattern_info["name"] in ["Generic Secret", "Generic API Key"]:
                    # Check if the property name suggests it might contain a secret
                    path_lower = path.lower()
                    if not any(keyword in path_lower for keyword in SUSPICIOUS_PROPERTY_KEYWORDS):
                        continue

                issues.append(
                    SecurityIssue(
                        severity=pattern_info["severity"],
                        property_path=path,
                        issue_type="hardcoded_secret",
                        message=f"Possible hardcoded {pattern_info['name']} detected",
                        recommendation="Use environment variables or a secrets management system",
                    )
                )
                break  # Only report once per property

        # Check if suspicious properties have hardcoded values
        path_lower = path.lower()
        for keyword in SUSPICIOUS_PROPERTY_KEYWORDS:
            if keyword in path_lower and not _contains_placeholder(value):
                # Ignore boolean values and common safe values
                if isinstance(value, bool):
                    continue
                if value in ["", "none", "null", "false", "true"]:
                    continue

                issues.append(
                    SecurityIssue(
                        severity="high",
                        property_path=path,
                        issue_type="hardcoded_sensitive_value",
                        message=f"Property contains '{keyword}' with hardcoded value",
                        recommendation="Consider using environment variables: ${ENV_VAR_NAME}",
                    )
                )
                break

    return issues


def scan_insecure_configurations(config: dict[str, Any]) -> list[SecurityIssue]:
    """Scan for insecure configuration patterns.

    Args:
        config: Merged configuration dictionary

    Returns:
        List of security issues found
    """
    issues: list[SecurityIssue] = []

    for rule in INSECURE_CONFIGURATIONS:
        value = _get_nested_value(config, rule["property"])

        if value is None:
            continue

        # Check if value matches the insecure pattern
        is_insecure = False

        if "pattern" in rule:
            # Regex pattern matching
            if isinstance(value, str) and rule["pattern"].search(value):
                is_insecure = True
        elif "value" in rule:
            # Exact value matching
            if value == rule["value"]:
                is_insecure = True

        if is_insecure:
            issues.append(
                SecurityIssue(
                    severity=rule["severity"],
                    property_path=rule["property"],
                    issue_type="insecure_configuration",
                    message=rule["message"],
                    recommendation=rule.get("recommendation"),
                )
            )

    return issues


def scan_configuration(config: dict[str, Any]) -> list[SecurityIssue]:
    """Perform comprehensive security scan of configuration.

    Args:
        config: Merged configuration dictionary

    Returns:
        List of all security issues found
    """
    issues: list[SecurityIssue] = []

    # Scan for hardcoded secrets
    issues.extend(scan_for_secrets(config))

    # Scan for insecure configurations
    issues.extend(scan_insecure_configurations(config))

    # Remove duplicates (same property path and issue type)
    seen = set()
    unique_issues = []
    for issue in issues:
        key = (issue.property_path, issue.issue_type)
        if key not in seen:
            seen.add(key)
            unique_issues.append(issue)

    return unique_issues
