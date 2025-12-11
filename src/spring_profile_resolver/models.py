"""Data structures for Spring Profile Resolver."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class ConfigSource:
    """Tracks where a configuration value originated."""

    file_path: Path
    line_number: int | None = None

    def __str__(self) -> str:
        if self.line_number is not None:
            return f"{self.file_path.name}:{self.line_number}"
        return self.file_path.name


@dataclass
class ConfigDocument:
    """A single YAML document with optional activation profile."""

    content: dict[str, Any]
    source_file: Path
    activation_profile: str | None = None
    document_index: int = 0  # Index within the source file (for multi-doc YAML)

    def matches_profiles(self, active_profiles: list[str]) -> bool:
        """Check if this document applies to the given active profiles.

        A document matches if:
        - It has no activation condition (always applies), OR
        - Its activation_profile is in the active_profiles list
        """
        if self.activation_profile is None:
            return True
        return self.activation_profile in active_profiles


@dataclass
class ResolverResult:
    """Result of profile resolution."""

    config: dict[str, Any]
    sources: dict[str, ConfigSource]
    warnings: list[str] = field(default_factory=list)
