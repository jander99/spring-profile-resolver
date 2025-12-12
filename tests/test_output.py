"""Tests for the output module."""

import tempfile
from pathlib import Path

from spring_profile_resolver.models import ConfigSource
from spring_profile_resolver.output import (
    format_output_filename,
    generate_computed_yaml,
)


class TestGenerateComputedYaml:
    """Tests for generate_computed_yaml function."""

    def test_simple_output(self) -> None:
        """Test generating output for simple config."""
        config = {"server": {"port": 8080}}
        sources = {"server.port": ConfigSource(Path("application.yml"))}

        result = generate_computed_yaml(config, sources)

        assert "server:" in result
        assert "port: 8080" in result

    def test_includes_source_comments(self) -> None:
        """Test that source comments are included."""
        config = {"server": {"port": 8080}}
        sources = {"server.port": ConfigSource(Path("application.yml"))}

        result = generate_computed_yaml(config, sources)

        assert "application.yml" in result

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

        result = generate_computed_yaml(config, sources)

        # Both sources should be mentioned
        assert "application-prod.yml" in result or "prod" in result
        assert "application.yml" in result

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

        result = generate_computed_yaml(config, sources)

        assert "spring:" in result
        assert "datasource:" in result
        assert "hikari:" in result
        assert "maximum-pool-size: 10" in result

    def test_list_values(self) -> None:
        """Test output with list values."""
        config = {"endpoints": ["/health", "/info", "/metrics"]}
        sources = {"endpoints": ConfigSource(Path("application.yml"))}

        result = generate_computed_yaml(config, sources)

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
            result = generate_computed_yaml(config, sources, output_path=output_path)

            assert output_path.exists()
            assert output_path.read_text() == result

    def test_creates_parent_directories(self) -> None:
        """Test that parent directories are created."""
        config = {"key": "value"}
        sources = {"key": ConfigSource(Path("application.yml"))}

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "nested" / "dir" / "output.yml"
            generate_computed_yaml(config, sources, output_path=output_path)

            assert output_path.exists()

    def test_empty_config(self) -> None:
        """Test generating output for empty config."""
        config: dict = {}
        sources: dict = {}

        result = generate_computed_yaml(config, sources)

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

        result = generate_computed_yaml(config, sources)

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

        result = generate_computed_yaml(config, sources)

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
