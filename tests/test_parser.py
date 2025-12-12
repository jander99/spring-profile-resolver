"""Tests for the YAML parser module."""

from pathlib import Path

import pytest

from spring_profile_resolver.parser import (
    discover_config_files,
    extract_activation_profile,
    get_profile_from_filename,
    parse_yaml_file,
)


class TestParseYamlFile:
    """Tests for parse_yaml_file function."""

    def test_parse_simple_yaml(self, simple_fixtures: Path) -> None:
        """Test parsing a simple single-document YAML file."""
        docs = parse_yaml_file(simple_fixtures / "application.yml")

        assert len(docs) == 1
        doc = docs[0]
        assert doc.content["server"]["port"] == 8080
        assert doc.content["spring"]["application"]["name"] == "my-app"
        assert doc.activation_profile is None
        assert doc.document_index == 0

    def test_parse_profile_specific_yaml(self, simple_fixtures: Path) -> None:
        """Test parsing a profile-specific YAML file."""
        docs = parse_yaml_file(simple_fixtures / "application-dev.yml")

        assert len(docs) == 1
        doc = docs[0]
        assert doc.content["server"]["port"] == 8081
        assert doc.content["logging"]["level"]["root"] == "DEBUG"
        assert doc.activation_profile is None  # No on-profile in file

    def test_parse_multi_document_yaml(self, multi_document_fixtures: Path) -> None:
        """Test parsing a multi-document YAML file with --- separators."""
        docs = parse_yaml_file(multi_document_fixtures / "application.yml")

        assert len(docs) == 3

        # First document - base config (no activation)
        assert docs[0].activation_profile is None
        assert docs[0].content["server"]["port"] == 8080
        assert docs[0].document_index == 0

        # Second document - dev profile
        assert docs[1].activation_profile == "dev"
        assert docs[1].content["server"]["port"] == 8081
        assert docs[1].document_index == 1

        # Third document - prod profile
        assert docs[2].activation_profile == "prod"
        assert docs[2].content["server"]["port"] == 80
        assert docs[2].document_index == 2

    def test_parse_nonexistent_file(self, simple_fixtures: Path) -> None:
        """Test that parsing a nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            parse_yaml_file(simple_fixtures / "nonexistent.yml")


class TestExtractActivationProfile:
    """Tests for extract_activation_profile function."""

    def test_extract_profile_present(self) -> None:
        """Test extracting profile when spring.config.activate.on-profile is set."""
        doc = {
            "spring": {
                "config": {
                    "activate": {
                        "on-profile": "prod"
                    }
                }
            },
            "server": {"port": 80}
        }
        assert extract_activation_profile(doc) == "prod"

    def test_extract_profile_absent(self) -> None:
        """Test extracting profile when on-profile is not set."""
        doc = {"server": {"port": 8080}}
        assert extract_activation_profile(doc) is None

    def test_extract_profile_partial_path(self) -> None:
        """Test extracting profile when spring.config exists but no activate."""
        doc = {
            "spring": {
                "config": {
                    "import": "optional:file:./config/"
                }
            }
        }
        assert extract_activation_profile(doc) is None

    def test_extract_profile_empty_spring(self) -> None:
        """Test extracting profile when spring key exists but is empty."""
        doc = {"spring": None}
        assert extract_activation_profile(doc) is None

    def test_extract_profile_numeric(self) -> None:
        """Test extracting profile when value is numeric (converts to string)."""
        doc = {
            "spring": {
                "config": {
                    "activate": {
                        "on-profile": 123
                    }
                }
            }
        }
        assert extract_activation_profile(doc) == "123"


class TestDiscoverConfigFiles:
    """Tests for discover_config_files function."""

    def test_discover_simple_configs(self, simple_fixtures: Path) -> None:
        """Test discovering config files in simple fixtures directory."""
        files = discover_config_files(simple_fixtures)

        assert len(files) == 3
        # Base config should come first
        assert files[0].name == "application.yml"
        # Profile-specific should follow alphabetically
        assert files[1].name == "application-dev.yml"
        assert files[2].name == "application-prod.yml"

    def test_discover_nonexistent_directory(self, fixtures_dir: Path) -> None:
        """Test discovering files in nonexistent directory returns empty list."""
        files = discover_config_files(fixtures_dir / "nonexistent")
        assert files == []

    def test_discover_multi_document(self, multi_document_fixtures: Path) -> None:
        """Test discovering config files in multi-document fixtures."""
        files = discover_config_files(multi_document_fixtures)

        assert len(files) == 1
        assert files[0].name == "application.yml"


class TestGetProfileFromFilename:
    """Tests for get_profile_from_filename function."""

    def test_base_application(self) -> None:
        """Test that application.yml returns None."""
        assert get_profile_from_filename(Path("application.yml")) is None
        assert get_profile_from_filename(Path("application.yaml")) is None

    def test_profile_specific(self) -> None:
        """Test extracting profile from profile-specific filename."""
        assert get_profile_from_filename(Path("application-dev.yml")) == "dev"
        assert get_profile_from_filename(Path("application-prod.yaml")) == "prod"
        assert get_profile_from_filename(Path("application-aws-prod.yml")) == "aws-prod"

    def test_full_path(self) -> None:
        """Test extracting profile from full path."""
        path = Path("/some/dir/application-staging.yml")
        assert get_profile_from_filename(path) == "staging"


class TestYamlDepthValidation:
    """Tests for YAML bomb protection via depth validation."""

    def test_normal_depth_accepted(self, tmp_path: Path) -> None:
        """Test that normal nesting depth is accepted."""
        yaml_content = """
server:
  config:
    settings:
      nested:
        value: "deep but acceptable"
"""
        yaml_file = tmp_path / "application.yml"
        yaml_file.write_text(yaml_content)

        docs = parse_yaml_file(yaml_file)
        assert len(docs) == 1
        assert docs[0].content["server"]["config"]["settings"]["nested"]["value"] == "deep but acceptable"

    def test_excessive_depth_rejected(self, tmp_path: Path) -> None:
        """Test that excessive nesting depth is rejected."""
        from spring_profile_resolver.exceptions import InvalidYAMLError
        from spring_profile_resolver.parser import MAX_YAML_DEPTH, _validate_yaml_depth

        # Build a deeply nested structure exceeding max depth
        deep_data: dict = {}
        current = deep_data
        for i in range(MAX_YAML_DEPTH + 5):
            current[f"level{i}"] = {}
            current = current[f"level{i}"]
        current["value"] = "too deep"

        with pytest.raises(InvalidYAMLError) as exc_info:
            _validate_yaml_depth(deep_data, path=tmp_path / "test.yml")

        assert "nesting depth exceeds maximum" in str(exc_info.value)

    def test_list_depth_counted(self, tmp_path: Path) -> None:
        """Test that list nesting counts toward depth limit."""
        from spring_profile_resolver.exceptions import InvalidYAMLError
        from spring_profile_resolver.parser import MAX_YAML_DEPTH, _validate_yaml_depth

        # Build deeply nested list structure
        deep_data: list = [[[[[[]]]]]]
        current = deep_data
        for _ in range(MAX_YAML_DEPTH + 5):
            current[0] = [[]]
            current = current[0]

        with pytest.raises(InvalidYAMLError) as exc_info:
            _validate_yaml_depth(deep_data, path=tmp_path / "test.yml")

        assert "nesting depth exceeds maximum" in str(exc_info.value)
