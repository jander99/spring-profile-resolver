"""Spring Profile Resolver - Compute effective Spring Boot configuration."""

from .exceptions import (
    CircularProfileGroupError,
    ConfigFileError,
    InvalidYAMLError,
    NoConfigurationFoundError,
    ProfileResolutionError,
    SpringProfileResolverError,
)
from .models import ConfigDocument, ConfigSource, ResolverResult
from .resolver import resolve_profiles, run_resolver

__version__ = "0.1.0"

__all__ = [
    # Main API
    "resolve_profiles",
    "run_resolver",
    # Models
    "ConfigDocument",
    "ConfigSource",
    "ResolverResult",
    # Exceptions
    "SpringProfileResolverError",
    "ConfigFileError",
    "InvalidYAMLError",
    "ProfileResolutionError",
    "CircularProfileGroupError",
    "NoConfigurationFoundError",
]
