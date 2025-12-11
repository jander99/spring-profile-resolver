"""Tests for the models module."""

from pathlib import Path

from spring_profile_resolver.models import ConfigDocument, ConfigSource, ResolverResult


class TestConfigSource:
    """Tests for ConfigSource dataclass."""

    def test_str_with_line_number(self) -> None:
        """Test string representation includes line number when present."""
        source = ConfigSource(file_path=Path("/path/to/application.yml"), line_number=42)
        assert str(source) == "application.yml:42"

    def test_str_without_line_number(self) -> None:
        """Test string representation without line number."""
        source = ConfigSource(file_path=Path("/path/to/application-prod.yml"))
        assert str(source) == "application-prod.yml"


class TestConfigDocument:
    """Tests for ConfigDocument dataclass."""

    def test_matches_profiles_no_activation(self) -> None:
        """Test that document with no activation matches any profiles."""
        doc = ConfigDocument(
            content={"server": {"port": 8080}},
            source_file=Path("application.yml"),
            activation_profile=None,
        )
        assert doc.matches_profiles([]) is True
        assert doc.matches_profiles(["dev"]) is True
        assert doc.matches_profiles(["prod", "aws"]) is True

    def test_matches_profiles_with_activation(self) -> None:
        """Test that document with activation only matches specified profile."""
        doc = ConfigDocument(
            content={"server": {"port": 80}},
            source_file=Path("application.yml"),
            activation_profile="prod",
        )
        assert doc.matches_profiles([]) is False
        assert doc.matches_profiles(["dev"]) is False
        assert doc.matches_profiles(["prod"]) is True
        assert doc.matches_profiles(["dev", "prod"]) is True
        assert doc.matches_profiles(["prod", "aws"]) is True


class TestResolverResult:
    """Tests for ResolverResult dataclass."""

    def test_default_warnings_empty(self) -> None:
        """Test that warnings default to empty list."""
        result = ResolverResult(
            config={"server": {"port": 8080}},
            sources={"server.port": ConfigSource(Path("app.yml"))},
        )
        assert result.warnings == []

    def test_with_warnings(self) -> None:
        """Test creating result with warnings."""
        result = ResolverResult(
            config={},
            sources={},
            warnings=["Missing profile: staging", "Unresolved placeholder: ${DB_HOST}"],
        )
        assert len(result.warnings) == 2
