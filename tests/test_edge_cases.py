"""Tests for edge cases and error handling."""

from pathlib import Path

import pytest

from spring_profile_resolver.exceptions import CircularProfileGroupError, InvalidYAMLError
from spring_profile_resolver.parser import parse_yaml_file
from spring_profile_resolver.profiles import expand_profiles, parse_profile_groups
from spring_profile_resolver.resolver import resolve_profiles


@pytest.fixture
def edge_cases_dir() -> Path:
    """Return the path to edge-cases test fixtures."""
    return Path(__file__).parent.parent / "test-fixtures" / "edge-cases"


class TestCircularGroups:
    """Tests for circular profile group detection."""

    def test_circular_group_detected(self, edge_cases_dir: Path) -> None:
        """Test that circular profile groups are detected."""
        docs = parse_yaml_file(edge_cases_dir / "circular-groups" / "application.yml")
        groups = parse_profile_groups(docs[0].content)

        with pytest.raises(CircularProfileGroupError) as exc_info:
            expand_profiles(["a"], groups)

        assert exc_info.value.cycle_path == ["a", "b", "c", "a"]

    def test_circular_group_warning_in_resolver(self, edge_cases_dir: Path) -> None:
        """Test that circular groups generate warning in resolver."""
        result = resolve_profiles(
            project_path=edge_cases_dir / "circular-groups",
            profiles=["a"],
            resource_dirs=["."],
        )

        # Should have a warning about circular reference
        assert any("Circular" in w for w in result.warnings)
        # But should still return the base config
        assert result.config["server"]["port"] == 8080


class TestInvalidYAML:
    """Tests for invalid YAML handling."""

    def test_invalid_yaml_raises_error(self, edge_cases_dir: Path) -> None:
        """Test that invalid YAML raises an appropriate error."""
        with pytest.raises(InvalidYAMLError) as exc_info:
            parse_yaml_file(edge_cases_dir / "invalid-yaml" / "application.yml")

        # Should include file path and line number info
        assert "invalid-yaml" in str(exc_info.value.file_path)
        assert "Invalid YAML syntax" in str(exc_info.value)

    def test_invalid_yaml_collected_as_error_in_resolver(
        self, edge_cases_dir: Path
    ) -> None:
        """Test that invalid YAML errors are collected in resolver result."""
        result = resolve_profiles(
            project_path=edge_cases_dir / "invalid-yaml",
            profiles=["dev"],
            resource_dirs=["."],
        )

        # Should have an error about invalid YAML
        assert len(result.errors) >= 1
        assert any("Invalid YAML syntax" in e for e in result.errors)
        # Errors should include file path
        assert any("application.yml" in e for e in result.errors)


class TestEmptyFiles:
    """Tests for empty configuration files."""

    def test_empty_file_returns_empty_docs(self, edge_cases_dir: Path) -> None:
        """Test that empty files return empty document list."""
        docs = parse_yaml_file(edge_cases_dir / "empty-files" / "application.yml")
        # Empty file or comment-only file should produce no documents
        assert len(docs) == 0

    def test_resolver_handles_empty_config(self, edge_cases_dir: Path) -> None:
        """Test that resolver handles empty config gracefully."""
        result = resolve_profiles(
            project_path=edge_cases_dir / "empty-files",
            profiles=["dev"],
            resource_dirs=["."],
        )

        assert result.config == {}


class TestUnicode:
    """Tests for Unicode character handling."""

    def test_unicode_preserved(self, edge_cases_dir: Path) -> None:
        """Test that Unicode characters are preserved correctly."""
        result = resolve_profiles(
            project_path=edge_cases_dir / "unicode",
            profiles=[],
            resource_dirs=["."],
        )

        assert result.config["spring"]["application"]["name"] == "日本語アプリ"
        assert "émojis" in result.config["spring"]["application"]["description"]
        assert "🚀" in result.config["spring"]["application"]["description"]
        assert result.config["messages"]["greeting"] == "Привет мир"
        assert result.config["messages"]["farewell"] == "再见"
        assert "👋" in result.config["messages"]["emoji"]


class TestDeepNesting:
    """Tests for deeply nested configuration."""

    def test_deep_nesting_handled(self, edge_cases_dir: Path) -> None:
        """Test that deeply nested config is handled correctly."""
        result = resolve_profiles(
            project_path=edge_cases_dir / "deep-nesting",
            profiles=[],
            resource_dirs=["."],
        )

        # Navigate to deeply nested value
        nested = result.config
        for level in range(1, 11):
            nested = nested[f"level{level}"]

        assert nested["deeply-nested-value"] == "found it!"
        assert nested["another-value"] == 42

    def test_deep_nesting_source_tracking(self, edge_cases_dir: Path) -> None:
        """Test that source tracking works for deeply nested values."""
        result = resolve_profiles(
            project_path=edge_cases_dir / "deep-nesting",
            profiles=[],
            resource_dirs=["."],
        )

        # Check source tracking for deep path
        deep_path = ".".join(f"level{i}" for i in range(1, 11)) + ".deeply-nested-value"
        assert deep_path in result.sources


class TestYAMLFeatures:
    """Tests for advanced YAML features."""

    def test_anchors_and_aliases(self, edge_cases_dir: Path) -> None:
        """Test that YAML anchors and aliases are resolved."""
        result = resolve_profiles(
            project_path=edge_cases_dir / "yaml-features",
            profiles=[],
            resource_dirs=["."],
        )

        # Development should have defaults merged
        assert result.config["development"]["database"]["adapter"] == "postgres"
        assert result.config["development"]["database"]["host"] == "localhost"
        assert result.config["development"]["database"]["database"] == "dev_db"

        # Production should have overridden host
        assert result.config["production"]["database"]["adapter"] == "postgres"
        assert result.config["production"]["database"]["host"] == "prod-db.example.com"
        assert result.config["production"]["database"]["database"] == "prod_db"

    def test_multiline_strings(self, edge_cases_dir: Path) -> None:
        """Test that multi-line strings are handled correctly."""
        result = resolve_profiles(
            project_path=edge_cases_dir / "yaml-features",
            profiles=[],
            resource_dirs=["."],
        )

        # Literal block scalar (|) preserves newlines
        assert "multi-line" in result.config["description"]
        assert "\n" in result.config["description"]

        # Folded block scalar (>) combines lines
        assert "folded string" in result.config["inline-description"]
