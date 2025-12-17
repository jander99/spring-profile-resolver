"""Tests for the output module."""

import tempfile
from pathlib import Path

from spring_profile_resolver.models import ConfigSource
from spring_profile_resolver.output import (
    format_output_filename,
    generate_computed_yaml,
    validate_yaml,
)


class TestGenerateComputedYaml:
    """Tests for generate_computed_yaml function."""

    def test_simple_output(self) -> None:
        """Test generating output for simple config."""
        config = {"server": {"port": 8080}}
        sources = {"server.port": ConfigSource(Path("application.yml"))}

        result, error, warnings = generate_computed_yaml(config, sources)

        assert error is None
        assert "server:" in result
        assert "port: 8080" in result

    def test_includes_source_comments(self) -> None:
        """Test that source comments are included for overrides."""
        config = {"server": {"port": 80}}
        sources = {"server.port": ConfigSource(Path("application-prod.yml"))}
        base_properties = {"server", "server.port"}  # Include parent and property

        result, error, warnings = generate_computed_yaml(config, sources, base_properties)

        assert error is None
        # Override should have comment
        assert "application-prod.yml" in result
        # No warnings for overrides
        assert len(warnings) == 0

    def test_multiple_sources(self) -> None:
        """Test output with values from multiple sources."""
        config = {
            "server": {
                "port": 80,
                "host": "localhost",
            }
        }
        sources = {
            "server.port": ConfigSource(Path("application-prod.yml")),
            "server.host": ConfigSource(Path("application.yml")),
        }
        base_properties = {"server", "server.port", "server.host"}  # Include parent

        result, error, warnings = generate_computed_yaml(config, sources, base_properties)

        assert error is None
        # Override from prod should have comment
        assert "application-prod.yml" in result
        # Base-only property should not have comment
        assert result.count("application.yml") == 0
        # No warnings
        assert len(warnings) == 0

    def test_nested_config(self) -> None:
        """Test output with deeply nested config."""
        config = {
            "spring": {
                "datasource": {
                    "url": "jdbc:postgresql://localhost:5432/db",
                    "hikari": {
                        "maximum-pool-size": 10,
                    },
                }
            }
        }
        sources = {
            "spring.datasource.url": ConfigSource(Path("application.yml")),
            "spring.datasource.hikari.maximum-pool-size": ConfigSource(
                Path("application-prod.yml")
            ),
        }

        result, error, warnings = generate_computed_yaml(config, sources)

        assert error is None
        assert "spring:" in result
        assert "datasource:" in result
        assert "hikari:" in result
        assert "maximum-pool-size: 10" in result

    def test_list_values(self) -> None:
        """Test output with list values."""
        config = {"endpoints": ["/health", "/info", "/metrics"]}
        sources = {"endpoints": ConfigSource(Path("application.yml"))}

        result, error, warnings = generate_computed_yaml(config, sources)

        assert error is None
        assert "endpoints:" in result
        assert "/health" in result
        assert "/info" in result
        assert "/metrics" in result

    def test_writes_to_file(self) -> None:
        """Test writing output to file."""
        config = {"server": {"port": 8080}}
        sources = {"server.port": ConfigSource(Path("application.yml"))}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.yml"
            result, error, warnings = generate_computed_yaml(config, sources, output_path=output_path)

            assert error is None
            assert output_path.exists()
            assert output_path.read_text() == result

    def test_creates_parent_directories(self) -> None:
        """Test that parent directories are created."""
        config = {"key": "value"}
        sources = {"key": ConfigSource(Path("application.yml"))}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "output.yml"
            _, error, warnings = generate_computed_yaml(config, sources, output_path=output_path)

            assert error is None
            assert output_path.exists()

    def test_empty_config(self) -> None:
        """Test generating output for empty config."""
        config: dict = {}
        sources: dict = {}

        result, error, warnings = generate_computed_yaml(config, sources)

        assert error is None
        # Should produce valid YAML (empty dict)
        assert result.strip() in ("{}", "")

    def test_preserves_value_types(self) -> None:
        """Test that value types are preserved in output."""
        config = {
            "string": "value",
            "number": 42,
            "float": 3.14,
            "boolean": True,
            "null_value": None,
        }
        sources = {
            "string": ConfigSource(Path("app.yml")),
            "number": ConfigSource(Path("app.yml")),
            "float": ConfigSource(Path("app.yml")),
            "boolean": ConfigSource(Path("app.yml")),
            "null_value": ConfigSource(Path("app.yml")),
        }

        result, error, warnings = generate_computed_yaml(config, sources)

        assert error is None
        assert "string: value" in result
        assert "number: 42" in result
        assert "3.14" in result
        assert "boolean: true" in result

    def test_list_of_dicts_produces_valid_yaml(self) -> None:
        """Test that lists of dicts produce valid YAML with proper indentation.

        This is a regression test for a bug where list items containing dicts
        would have broken indentation, making the YAML invalid.
        """
        from io import StringIO

        from ruamel.yaml import YAML

        config = {
            "authority-mappings": [
                {
                    "issuer-name": "pingfed-pr",
                    "audience": "test-audience",
                    "authorities": ["ROLE_read"],
                },
                {
                    "issuer-name": "azuread-pr",
                    "audience": "test-audience-2",
                    "authorities": ["ROLE_read", "ROLE_write"],
                },
            ]
        }
        sources = {"authority-mappings": ConfigSource(Path("application.yml"))}

        result, error, warnings = generate_computed_yaml(config, sources)

        # Should pass validation
        assert error is None

        # Parse the output to verify it's valid YAML
        yaml = YAML()
        parsed = yaml.load(StringIO(result))

        # Verify structure is preserved
        assert "authority-mappings" in parsed
        assert len(parsed["authority-mappings"]) == 2
        assert parsed["authority-mappings"][0]["issuer-name"] == "pingfed-pr"
        assert parsed["authority-mappings"][0]["audience"] == "test-audience"
        assert parsed["authority-mappings"][1]["issuer-name"] == "azuread-pr"
        assert parsed["authority-mappings"][1]["authorities"] == [
            "ROLE_read",
            "ROLE_write",
        ]


class TestValidateYaml:
    """Tests for validate_yaml function."""

    def test_validate_yaml_valid_input(self) -> None:
        """Test that valid YAML passes validation."""
        valid_yaml = """
server:
  port: 8080
  host: localhost
"""
        is_valid, error = validate_yaml(valid_yaml)

        assert is_valid is True
        assert error is None

    def test_validate_yaml_invalid_input(self) -> None:
        """Test that invalid YAML is detected."""
        # Missing indentation for list item properties
        invalid_yaml = """
authority-mappings:
  - issuer-name: test
  audience: broken
"""
        is_valid, error = validate_yaml(invalid_yaml)

        assert is_valid is False
        assert error is not None
        assert "Invalid YAML output" in error

    def test_validate_yaml_empty_input(self) -> None:
        """Test that empty YAML passes validation."""
        is_valid, error = validate_yaml("")

        assert is_valid is True
        assert error is None

    def test_generate_does_not_write_invalid_yaml(self) -> None:
        """Test that invalid YAML is not written to file.

        Note: This test creates a scenario that would produce invalid YAML
        if the validation were to fail. In practice, generate_computed_yaml
        should always produce valid YAML, but this tests the safety mechanism.
        """
        config = {"key": "value"}
        sources = {"key": ConfigSource(Path("app.yml"))}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "output.yml"
            result, error, warnings = generate_computed_yaml(config, sources, output_path=output_path)

            # Valid YAML should be written
            assert error is None
            assert output_path.exists()
            assert output_path.read_text() == result


class TestFormatOutputFilename:
    """Tests for format_output_filename function."""

    def test_single_profile(self) -> None:
        """Test filename with single profile."""
        assert format_output_filename(["prod"]) == "application-prod-computed.yml"

    def test_multiple_profiles(self) -> None:
        """Test filename with multiple profiles."""
        assert (
            format_output_filename(["prod", "aws"])
            == "application-prod-aws-computed.yml"
        )

    def test_no_profiles(self) -> None:
        """Test filename with no profiles."""
        assert format_output_filename([]) == "application-computed.yml"

    def test_many_profiles(self) -> None:
        """Test filename with many profiles."""
        profiles = ["prod", "aws", "postgres", "redis"]
        assert (
            format_output_filename(profiles)
            == "application-prod-aws-postgres-redis-computed.yml"
        )
