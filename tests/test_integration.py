"""Integration tests for Spring Profile Resolver."""

from pathlib import Path

import pytest

from spring_profile_resolver.resolver import resolve_profiles, run_resolver


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test-fixtures directory."""
    return Path(__file__).parent.parent / "test-fixtures"


class TestResolveProfiles:
    """Integration tests for resolve_profiles function."""

    def test_simple_single_profile(self, fixtures_dir: Path) -> None:
        """Test resolving a simple single profile configuration."""
        result = resolve_profiles(
            project_path=fixtures_dir / "simple",
            profiles=["prod"],
            resource_dirs=[""],  # Use fixtures dir directly as resource dir
        )

        assert result.config["server"]["port"] == 80
        assert result.config["logging"]["level"]["root"] == "WARN"

    def test_simple_dev_profile(self, fixtures_dir: Path) -> None:
        """Test resolving dev profile configuration."""
        result = resolve_profiles(
            project_path=fixtures_dir / "simple",
            profiles=["dev"],
            resource_dirs=[""],
        )

        assert result.config["server"]["port"] == 8081
        assert result.config["logging"]["level"]["root"] == "DEBUG"
        assert result.config["logging"]["level"]["com.example"] == "TRACE"

    def test_multi_document_yaml(self, fixtures_dir: Path) -> None:
        """Test resolving multi-document YAML with on-profile conditions."""
        result = resolve_profiles(
            project_path=fixtures_dir / "multi-document",
            profiles=["prod"],
            resource_dirs=[""],
        )

        # Should have base + prod section applied
        assert result.config["server"]["port"] == 80
        assert result.config["logging"]["level"]["root"] == "WARN"
        assert result.config["spring"]["application"]["name"] == "multi-doc-app"

    def test_profile_groups(self, fixtures_dir: Path) -> None:
        """Test profile group expansion."""
        result = resolve_profiles(
            project_path=fixtures_dir / "with-groups",
            profiles=["prod"],
            resource_dirs=[""],
        )

        # prod group expands to: prod -> proddb -> postgres, hikari -> prodmq
        assert result.config["server"]["port"] == 80
        assert result.config["spring"]["datasource"]["url"] == "jdbc:postgresql://localhost:5432/mydb"
        assert result.config["spring"]["datasource"]["hikari"]["maximum-pool-size"] == 10
        assert result.config["spring"]["rabbitmq"]["host"] == "prod-mq.example.com"

    def test_placeholder_resolution(self, fixtures_dir: Path) -> None:
        """Test placeholder resolution in configs."""
        result = resolve_profiles(
            project_path=fixtures_dir / "with-placeholders",
            profiles=[],
            resource_dirs=[""],
        )

        # Placeholders should be resolved
        assert result.config["database"]["url"] == "jdbc:postgresql://localhost:5432/mydb"
        assert result.config["server"]["base-url"] == "http://localhost:8080"
        assert result.config["app"]["database-url"] == "jdbc:postgresql://localhost:5432/mydb"

        # Default values should be used
        assert result.config["cache"]["host"] == "redis.local"
        assert result.config["cache"]["port"] == "6379"

    def test_test_resources_excluded_by_default(self, fixtures_dir: Path) -> None:
        """Test that test resources are excluded by default."""
        result = resolve_profiles(
            project_path=fixtures_dir / "with-test-resources",
            profiles=["prod"],
            include_test=False,
        )

        # Should have main/prod config, not test overrides
        assert result.config["server"]["port"] == 80
        assert result.config["database"]["host"] == "prod-db.example.com"

    def test_test_resources_included(self, fixtures_dir: Path) -> None:
        """Test including test resources."""
        result = resolve_profiles(
            project_path=fixtures_dir / "with-test-resources",
            profiles=["prod"],
            include_test=True,
        )

        # Test resources should override main
        assert result.config["server"]["port"] == 8080  # Test override
        assert result.config["database"]["host"] == "test-prod-db.local"

    def test_source_tracking(self, fixtures_dir: Path) -> None:
        """Test that sources are properly tracked."""
        result = resolve_profiles(
            project_path=fixtures_dir / "simple",
            profiles=["prod"],
            resource_dirs=[""],
        )

        # Check that sources are tracked
        assert "server.port" in result.sources
        assert result.sources["server.port"].file_path.name == "application-prod.yml"

    def test_missing_profile_warning(self, fixtures_dir: Path) -> None:
        """Test warning for missing profile files."""
        result = resolve_profiles(
            project_path=fixtures_dir / "simple",
            profiles=["nonexistent"],
            resource_dirs=[""],
        )

        # Should still work with base config
        assert result.config["server"]["port"] == 8080  # From base


class TestRunResolver:
    """Integration tests for run_resolver function."""

    def test_generates_yaml_output(self, fixtures_dir: Path, tmp_path: Path) -> None:
        """Test that run_resolver generates YAML output."""
        result = run_resolver(
            project_path=fixtures_dir / "simple",
            profiles=["prod"],
            resource_dirs=[""],
            output_dir=tmp_path,
        )

        # File should be created
        output_file = tmp_path / "application-prod-computed.yml"
        assert output_file.exists()

        # Read the generated file
        output_yaml = output_file.read_text()

        # Output should contain the resolved values
        assert "port: 80" in output_yaml
        assert "WARN" in output_yaml

        # No errors expected
        assert result.errors == []

    def test_stdout_mode(self, fixtures_dir: Path, capsys: pytest.CaptureFixture) -> None:
        """Test stdout output mode."""
        result = run_resolver(
            project_path=fixtures_dir / "simple",
            profiles=["dev"],
            resource_dirs=[""],
            to_stdout=True,
        )

        captured = capsys.readouterr()
        assert "port: 8081" in captured.out
        assert result.errors == []

    def test_multiple_profiles(self, fixtures_dir: Path, tmp_path: Path) -> None:
        """Test with multiple profiles."""
        result = run_resolver(
            project_path=fixtures_dir / "with-groups",
            profiles=["prod"],
            resource_dirs=[""],
            output_dir=tmp_path,
        )

        # Filename should reflect profiles
        output_file = tmp_path / "application-prod-computed.yml"
        assert output_file.exists()
        assert result.errors == []
