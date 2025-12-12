"""Tests for spring.config.import handling."""

from pathlib import Path

import pytest

from spring_profile_resolver.imports import (
    ImportLocation,
    extract_imports,
    load_imports,
    parse_import_value,
    resolve_import_paths,
)


class TestParseImportValue:
    """Tests for parsing import values."""

    def test_simple_file_import(self):
        result = parse_import_value("file:./config/extra.yml")
        assert len(result) == 1
        assert result[0].path == "./config/extra.yml"
        assert result[0].prefix == "file"
        assert result[0].optional is False

    def test_optional_import(self):
        result = parse_import_value("optional:file:./config/maybe.yml")
        assert len(result) == 1
        assert result[0].optional is True
        assert result[0].prefix == "file"
        assert result[0].path == "./config/maybe.yml"

    def test_classpath_import(self):
        result = parse_import_value("classpath:config/default.yml")
        assert len(result) == 1
        assert result[0].prefix == "classpath"
        assert result[0].path == "config/default.yml"

    def test_no_prefix(self):
        result = parse_import_value("./config/local.yml")
        assert len(result) == 1
        assert result[0].prefix is None
        assert result[0].path == "./config/local.yml"

    def test_comma_separated(self):
        result = parse_import_value("file:a.yml,file:b.yml")
        assert len(result) == 2
        assert result[0].path == "a.yml"
        assert result[1].path == "b.yml"

    def test_list_input(self):
        result = parse_import_value(["file:a.yml", "file:b.yml"])
        assert len(result) == 2
        assert result[0].path == "a.yml"
        assert result[1].path == "b.yml"

    def test_empty_string(self):
        result = parse_import_value("")
        assert len(result) == 0


class TestExtractImports:
    """Tests for extracting imports from config."""

    def test_single_import(self):
        config = {
            "spring": {
                "config": {
                    "import": "file:extra.yml"
                }
            }
        }
        result = extract_imports(config)
        assert result == ["file:extra.yml"]

    def test_list_imports(self):
        config = {
            "spring": {
                "config": {
                    "import": ["file:a.yml", "file:b.yml"]
                }
            }
        }
        result = extract_imports(config)
        assert result == ["file:a.yml", "file:b.yml"]

    def test_no_imports(self):
        config = {"server": {"port": 8080}}
        result = extract_imports(config)
        assert result is None

    def test_partial_path(self):
        config = {"spring": {"datasource": {"url": "jdbc:..."}}}
        result = extract_imports(config)
        assert result is None


class TestResolveImportPaths:
    """Tests for resolving import paths."""

    def test_file_import_relative(self, tmp_path):
        # Create a test file
        config_dir = tmp_path / "config"
        config_dir.mkdir()
        test_file = config_dir / "extra.yml"
        test_file.write_text("key: value")

        imports = [ImportLocation(path="config/extra.yml", prefix="file")]
        result = resolve_import_paths(imports, tmp_path)

        assert len(result) == 1
        assert result[0][0] == test_file
        assert result[0][1] is False  # not optional

    def test_optional_missing_file(self, tmp_path):
        imports = [ImportLocation(path="nonexistent.yml", prefix="file", optional=True)]
        result = resolve_import_paths(imports, tmp_path)

        # Should return empty list since file doesn't exist
        assert len(result) == 0

    def test_classpath_import(self, tmp_path):
        # Create a test file in a "resource dir"
        resource_dir = tmp_path / "resources"
        resource_dir.mkdir()
        test_file = resource_dir / "extra.yml"
        test_file.write_text("key: value")

        imports = [ImportLocation(path="extra.yml", prefix="classpath")]
        result = resolve_import_paths(imports, tmp_path, resource_dirs=[resource_dir])

        assert len(result) == 1
        assert result[0][0] == test_file


class TestLoadImports:
    """Tests for the full load_imports function."""

    def test_basic_import(self, tmp_path):
        # Create config with import
        config = {
            "spring": {
                "config": {
                    "import": "file:extra.yml"
                }
            }
        }

        # Create the imported file
        extra_file = tmp_path / "extra.yml"
        extra_file.write_text("extra: value")

        source_file = tmp_path / "application.yml"
        source_file.write_text("")  # dummy

        result = load_imports(config, source_file)

        assert len(result) == 1
        assert result[0][0] == extra_file

    def test_no_imports(self, tmp_path):
        config = {"server": {"port": 8080}}
        source_file = tmp_path / "application.yml"
        source_file.write_text("")

        result = load_imports(config, source_file)
        assert len(result) == 0


class TestIntegrationWithResolver:
    """Integration tests with the resolver."""

    def test_imported_config_merged(self, tmp_path):
        """Imported configs should be merged into the final result."""
        from spring_profile_resolver.resolver import resolve_profiles

        # Create directory structure
        resources = tmp_path / "src" / "main" / "resources"
        resources.mkdir(parents=True)

        # Create main application.yml with import
        main_config = resources / "application.yml"
        main_config.write_text("""
server:
  port: 8080
spring:
  config:
    import: file:extra-config.yml
""")

        # Create imported file
        extra_config = resources / "extra-config.yml"
        extra_config.write_text("""
database:
  host: localhost
  port: 5432
""")

        # Run resolver
        result = resolve_profiles(tmp_path, ["default"])

        # Check that both configs are merged
        assert result.config["server"]["port"] == 8080
        assert result.config["database"]["host"] == "localhost"
        assert result.config["database"]["port"] == 5432

    def test_optional_missing_import_no_error(self, tmp_path):
        """Optional imports that don't exist should not cause errors."""
        from spring_profile_resolver.resolver import resolve_profiles

        resources = tmp_path / "src" / "main" / "resources"
        resources.mkdir(parents=True)

        main_config = resources / "application.yml"
        main_config.write_text("""
server:
  port: 8080
spring:
  config:
    import: optional:file:nonexistent.yml
""")

        result = resolve_profiles(tmp_path, ["default"])

        # Should work without errors
        assert result.config["server"]["port"] == 8080
        # No warning for optional missing file
        assert not any("nonexistent" in w for w in result.warnings)
