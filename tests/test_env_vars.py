"""Tests for environment variable handling."""


import pytest

from spring_profile_resolver.env_vars import (
    env_var_to_property_path,
    env_vars_to_nested_dict,
    get_env_value,
    load_env_file,
    parse_env_overrides,
    property_path_to_env_vars,
)


class TestEnvVarToPropertyPath:
    """Tests for converting env var names to property paths."""

    def test_simple_conversion(self):
        assert env_var_to_property_path("SERVER_PORT") == "server.port"

    def test_nested_path(self):
        assert env_var_to_property_path("SPRING_DATASOURCE_URL") == "spring.datasource.url"

    def test_double_underscore_literal(self):
        # Double underscores should become single underscore
        assert env_var_to_property_path("MY__VAR_NAME") == "my_var.name"

    def test_lowercase_preservation(self):
        assert env_var_to_property_path("MyVar") == "myvar"


class TestPropertyPathToEnvVars:
    """Tests for converting property paths to env var names."""

    def test_simple_path(self):
        result = property_path_to_env_vars("server.port")
        assert "SERVER_PORT" in result

    def test_with_dashes(self):
        result = property_path_to_env_vars("spring.datasource.maximum-pool-size")
        assert "SPRING_DATASOURCE_MAXIMUM-POOL-SIZE" in result
        assert "SPRING_DATASOURCE_MAXIMUM_POOL_SIZE" in result


class TestGetEnvValue:
    """Tests for getting env values from property paths."""

    def test_from_provided_env_vars(self):
        env_vars = {"DATABASE_HOST": "myhost.local"}
        result = get_env_value("database.host", env_vars, system_env=False)
        assert result == "myhost.local"

    def test_from_system_env(self, monkeypatch):
        monkeypatch.setenv("MY_TEST_VAR", "test_value")
        result = get_env_value("my.test.var", {}, system_env=True)
        assert result == "test_value"

    def test_provided_overrides_system(self, monkeypatch):
        monkeypatch.setenv("DATABASE_HOST", "system_host")
        env_vars = {"DATABASE_HOST": "provided_host"}
        result = get_env_value("database.host", env_vars, system_env=True)
        assert result == "provided_host"

    def test_not_found(self):
        result = get_env_value("nonexistent.var", {}, system_env=False)
        assert result is None

    def test_system_env_disabled(self, monkeypatch):
        monkeypatch.setenv("MY_VAR", "system_value")
        result = get_env_value("my.var", {}, system_env=False)
        assert result is None


class TestLoadEnvFile:
    """Tests for loading .env files."""

    def test_simple_env_file(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("DATABASE_HOST=localhost\nDATABASE_PORT=5432")

        result = load_env_file(env_file)
        assert result == {"DATABASE_HOST": "localhost", "DATABASE_PORT": "5432"}

    def test_with_quotes(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text('MY_VAR="quoted value"\nOTHER=\'single quotes\'')

        result = load_env_file(env_file)
        assert result == {"MY_VAR": "quoted value", "OTHER": "single quotes"}

    def test_with_comments(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("# Comment\nVAR=value\n# Another comment")

        result = load_env_file(env_file)
        assert result == {"VAR": "value"}

    def test_empty_lines(self, tmp_path):
        env_file = tmp_path / ".env"
        env_file.write_text("\nVAR1=value1\n\nVAR2=value2\n")

        result = load_env_file(env_file)
        assert result == {"VAR1": "value1", "VAR2": "value2"}

    def test_nonexistent_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_env_file(tmp_path / "nonexistent.env")


class TestParseEnvOverrides:
    """Tests for parsing command-line env overrides."""

    def test_single_override(self):
        result = parse_env_overrides(["DATABASE_HOST=myhost"])
        assert result == {"DATABASE_HOST": "myhost"}

    def test_multiple_overrides(self):
        result = parse_env_overrides(["VAR1=value1", "VAR2=value2"])
        assert result == {"VAR1": "value1", "VAR2": "value2"}

    def test_value_with_equals(self):
        result = parse_env_overrides(["URL=jdbc:postgresql://host:5432/db"])
        assert result == {"URL": "jdbc:postgresql://host:5432/db"}

    def test_empty_value(self):
        result = parse_env_overrides(["EMPTY="])
        assert result == {"EMPTY": ""}

    def test_invalid_format_ignored(self):
        result = parse_env_overrides(["VALID=value", "invalid_no_equals"])
        assert result == {"VALID": "value"}


class TestEnvVarsToNestedDict:
    """Tests for converting env vars to nested dict."""

    def test_simple_conversion(self):
        env_vars = {"SERVER_PORT": "8080"}
        result = env_vars_to_nested_dict(env_vars)
        assert result == {"server": {"port": 8080}}

    def test_multiple_vars(self):
        env_vars = {
            "DATABASE_HOST": "localhost",
            "DATABASE_PORT": "5432",
            "SERVER_PORT": "8080",
        }
        result = env_vars_to_nested_dict(env_vars)
        assert result == {
            "database": {"host": "localhost", "port": 5432},
            "server": {"port": 8080},
        }


class TestPlaceholderIntegration:
    """Integration tests with placeholder resolution."""

    def test_env_var_overrides_config(self):
        """Environment variables should override config values."""
        from spring_profile_resolver.placeholders import resolve_placeholders

        config = {
            "database": {"host": "localhost"},
            "connection": {"url": "jdbc:postgresql://${database.host}:5432/db"},
        }
        env_vars = {"DATABASE_HOST": "production-db.example.com"}

        result, warnings = resolve_placeholders(
            config, env_vars=env_vars, use_system_env=False
        )

        # The placeholder should resolve to the env var value
        assert result["connection"]["url"] == "jdbc:postgresql://production-db.example.com:5432/db"

    def test_default_with_env_var(self):
        """Env var should override a default value."""
        from spring_profile_resolver.placeholders import resolve_placeholders

        config = {"cache": {"host": "${CACHE_HOST:redis.local}"}}
        env_vars = {"CACHE_HOST": "production-redis.example.com"}

        result, warnings = resolve_placeholders(
            config, env_vars=env_vars, use_system_env=False
        )

        assert result["cache"]["host"] == "production-redis.example.com"

    def test_fallback_to_config_value(self):
        """If env var not found, should use config value."""
        from spring_profile_resolver.placeholders import resolve_placeholders

        config = {
            "database": {"host": "localhost"},
            "connection": {"url": "jdbc:postgresql://${database.host}:5432/db"},
        }

        result, warnings = resolve_placeholders(config, env_vars={}, use_system_env=False)

        assert result["connection"]["url"] == "jdbc:postgresql://localhost:5432/db"
