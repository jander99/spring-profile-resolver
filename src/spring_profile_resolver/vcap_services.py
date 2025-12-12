"""Cloud Foundry VCAP_SERVICES and VCAP_APPLICATION support.

Cloud Foundry injects bound services configuration via the VCAP_SERVICES
environment variable, which contains a JSON object with service bindings.
Similarly, VCAP_APPLICATION contains application metadata.

Spring Boot's cloud connectors expose these as properties under:
- vcap.services.{service-name}.* (from VCAP_SERVICES)
- vcap.application.* (from VCAP_APPLICATION)

Since VCAP_SERVICES only exists in Cloud Foundry environments (not on localhost),
this module provides:
1. Parsing of VCAP environment variables to nested config dicts
2. Detection of VCAP-related placeholders for warning purposes
3. Warnings when VCAP placeholders are used but VCAP_SERVICES is not available
"""

import json
import os
import re
from typing import Any

__all__ = [
    "is_vcap_placeholder",
    "detect_vcap_placeholders",
    "parse_vcap_services",
    "parse_vcap_application",
    "get_vcap_config",
    "is_vcap_available",
    "check_vcap_placeholders_availability",
]


# Pattern to detect VCAP-related placeholders
VCAP_PLACEHOLDER_PATTERN = re.compile(r"\$\{(vcap\.(services|application)\.[^}:]+)(?::[^}]*)?\}")


def is_vcap_placeholder(placeholder: str) -> bool:
    """Check if a placeholder references VCAP properties.

    Args:
        placeholder: The placeholder string (e.g., "vcap.services.mydb.credentials.uri")

    Returns:
        True if the placeholder is a VCAP-related property path
    """
    return placeholder.startswith("vcap.services.") or placeholder.startswith("vcap.application.")


def detect_vcap_placeholders(value: str) -> list[str]:
    """Find all VCAP-related placeholder references in a value.

    Args:
        value: String that may contain ${vcap.*} placeholders

    Returns:
        List of VCAP property paths found (without ${} wrapper)
    """
    if "${" not in value:
        return []

    vcap_refs = []
    for match in VCAP_PLACEHOLDER_PATTERN.finditer(value):
        vcap_refs.append(match.group(1))
    return vcap_refs


def parse_vcap_services(vcap_json: str | None = None) -> dict[str, Any]:
    """Parse VCAP_SERVICES JSON into a nested configuration dict.

    VCAP_SERVICES contains an array of service bindings keyed by service type:
    {
        "user-provided": [
            {
                "name": "my-service",
                "credentials": {"uri": "..."},
                "label": "user-provided"
            }
        ],
        "p.mysql": [
            {
                "name": "my-mysql",
                "credentials": {"hostname": "...", "port": 3306, ...}
            }
        ]
    }

    This is converted to Spring's vcap.services.{name}.* structure.

    Args:
        vcap_json: JSON string from VCAP_SERVICES env var.
                   If None, reads from os.environ.

    Returns:
        Nested dict with vcap.services.{service-name}.* structure
    """
    if vcap_json is None:
        vcap_json = os.environ.get("VCAP_SERVICES")

    if not vcap_json:
        return {}

    try:
        vcap_data = json.loads(vcap_json)
    except json.JSONDecodeError:
        return {}

    if not isinstance(vcap_data, dict):
        return {}

    services: dict[str, Any] = {}

    # VCAP_SERVICES is keyed by service type, with arrays of service instances
    for _service_type, instances in vcap_data.items():
        if not isinstance(instances, list):
            continue

        for instance in instances:
            if not isinstance(instance, dict):
                continue

            # Use the "name" field as the service identifier
            service_name = instance.get("name")
            if not service_name:
                continue

            # Store the entire service instance data
            services[service_name] = instance

    return {"vcap": {"services": services}} if services else {}


def parse_vcap_application(vcap_json: str | None = None) -> dict[str, Any]:
    """Parse VCAP_APPLICATION JSON into a nested configuration dict.

    VCAP_APPLICATION contains application metadata:
    {
        "application_name": "my-app",
        "application_id": "...",
        "space_name": "development",
        "organization_name": "my-org",
        "uris": ["my-app.cfapps.io"],
        ...
    }

    This is converted to Spring's vcap.application.* structure.

    Args:
        vcap_json: JSON string from VCAP_APPLICATION env var.
                   If None, reads from os.environ.

    Returns:
        Nested dict with vcap.application.* structure
    """
    if vcap_json is None:
        vcap_json = os.environ.get("VCAP_APPLICATION")

    if not vcap_json:
        return {}

    try:
        vcap_data = json.loads(vcap_json)
    except json.JSONDecodeError:
        return {}

    if not isinstance(vcap_data, dict):
        return {}

    return {"vcap": {"application": vcap_data}} if vcap_data else {}


def get_vcap_config(
    vcap_services_json: str | None = None,
    vcap_application_json: str | None = None,
) -> dict[str, Any]:
    """Get combined VCAP configuration from both environment variables.

    Args:
        vcap_services_json: VCAP_SERVICES JSON (reads from env if None)
        vcap_application_json: VCAP_APPLICATION JSON (reads from env if None)

    Returns:
        Combined nested dict with vcap.services.* and vcap.application.*
    """
    services = parse_vcap_services(vcap_services_json)
    application = parse_vcap_application(vcap_application_json)

    # Merge the two structures
    if not services and not application:
        return {}

    result: dict[str, Any] = {"vcap": {}}

    if services:
        result["vcap"]["services"] = services.get("vcap", {}).get("services", {})

    if application:
        result["vcap"]["application"] = application.get("vcap", {}).get("application", {})

    return result


def is_vcap_available() -> bool:
    """Check if VCAP environment variables are available.

    Returns:
        True if either VCAP_SERVICES or VCAP_APPLICATION is set
    """
    return bool(os.environ.get("VCAP_SERVICES") or os.environ.get("VCAP_APPLICATION"))


def check_vcap_placeholders_availability(
    config: dict[str, Any],
    vcap_available: bool,
) -> list[str]:
    """Check for VCAP placeholders when VCAP environment is not available.

    This is useful to warn developers that their configuration references
    Cloud Foundry services that won't be available in local development.

    Args:
        config: Configuration dict to scan for VCAP placeholders
        vcap_available: Whether VCAP environment variables are set

    Returns:
        List of warning messages for VCAP placeholders without VCAP environment
    """
    if vcap_available:
        return []

    warnings: list[str] = []
    vcap_refs = _find_all_vcap_references(config)

    if vcap_refs:
        # Group by type (services vs application)
        service_refs = [r for r in vcap_refs if r.startswith("vcap.services.")]
        app_refs = [r for r in vcap_refs if r.startswith("vcap.application.")]

        if service_refs:
            warnings.append(
                f"Configuration references Cloud Foundry VCAP_SERVICES properties "
                f"({len(service_refs)} references) but VCAP_SERVICES environment variable "
                f"is not set. These placeholders will not resolve in local development. "
                f"Consider providing defaults or using an env file."
            )

        if app_refs:
            warnings.append(
                f"Configuration references Cloud Foundry VCAP_APPLICATION properties "
                f"({len(app_refs)} references) but VCAP_APPLICATION environment variable "
                f"is not set. These placeholders will not resolve in local development."
            )

    return warnings


def _find_all_vcap_references(
    config: dict[str, Any],
    path_prefix: str = "",
) -> list[str]:
    """Recursively find all VCAP placeholder references in config.

    Returns:
        List of VCAP property paths referenced
    """
    refs: list[str] = []

    for key, value in config.items():
        current_path = f"{path_prefix}.{key}" if path_prefix else key

        if isinstance(value, dict):
            refs.extend(_find_all_vcap_references(value, current_path))
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    refs.extend(detect_vcap_placeholders(item))
                elif isinstance(item, dict):
                    refs.extend(_find_all_vcap_references(item, current_path))
        elif isinstance(value, str):
            refs.extend(detect_vcap_placeholders(value))

    return refs
