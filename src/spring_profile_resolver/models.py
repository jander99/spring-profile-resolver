"""Data structures for Spring Profile Resolver."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .expressions import ProfileExpr
    from .linting import LintIssue
    from .security import SecurityIssue
    from .validation import ValidationIssue


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
    _parsed_expression: "ProfileExpr | None" = field(
        default=None, init=False, repr=False, compare=False
    )

    def matches_profiles(self, active_profiles: list[str]) -> bool:
        """Check if this document applies to the given active profiles.

        A document matches if:
        - It has no activation condition (always applies), OR
        - Its activation_profile expression evaluates to true

        Supports Spring Boot profile expressions:
        - Simple names: "prod"
        - NOT: "!prod"
        - AND: "prod & cloud"
        - OR: "prod | dev"
        - Parentheses: "(prod & cloud) | dev"
        """
        if self.activation_profile is None:
            return True

        # Import here to avoid circular imports
        from .expressions import (
            evaluate_profile_expression,
            is_simple_profile,
        )

        # Fast path for simple profile names (most common case)
        if is_simple_profile(self.activation_profile):
            return self.activation_profile in active_profiles

        # Full expression evaluation
        return evaluate_profile_expression(self.activation_profile, active_profiles)


@dataclass
class ResolverResult:
    """Result of profile resolution."""

    config: dict[str, Any]
    sources: dict[str, ConfigSource]
    base_properties: set[str] = field(default_factory=set)
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    validation_issues: list["ValidationIssue"] = field(default_factory=list)
    security_issues: list["SecurityIssue"] = field(default_factory=list)
    lint_issues: list["LintIssue"] = field(default_factory=list)
