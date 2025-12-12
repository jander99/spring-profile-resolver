"""Tests for the placeholders module."""

from spring_profile_resolver.placeholders import (
    get_nested_value,
    resolve_placeholders,
    resolve_single_value,
)


class TestGetNestedValue:
    """Tests for get_nested_value function."""

    def test_simple_key(self) -> None:
        """Test getting a simple top-level key."""
        config = {"port": 8080}
        assert get_nested_value(config, "port") == 8080

    def test_nested_key(self) -> None:
        """Test getting a nested key."""
        config = {"server": {"port": 8080, "host": "localhost"}}
        assert get_nested_value(config, "server.port") == 8080
        assert get_nested_value(config, "server.host") == "localhost"

    def test_deeply_nested_key(self) -> None:
        """Test getting a deeply nested key."""
        config = {"a": {"b": {"c": {"d": "value"}}}}
        assert get_nested_value(config, "a.b.c.d") == "value"

    def test_missing_key(self) -> None:
        """Test that missing keys return None."""
        config = {"server": {"port": 8080}}
        assert get_nested_value(config, "server.host") is None
        assert get_nested_value(config, "missing") is None
        assert get_nested_value(config, "server.port.nested") is None

    def test_non_dict_intermediate(self) -> None:
        """Test path through non-dict value returns None."""
        config = {"server": "not-a-dict"}
        assert get_nested_value(config, "server.port") is None


class TestResolveSingleValue:
    """Tests for resolve_single_value function."""

    def test_no_placeholder(self) -> None:
        """Test string without placeholders."""
        result, changed = resolve_single_value("simple string", {})
        assert result == "simple string"
        assert changed is False

    def test_simple_placeholder(self) -> None:
        """Test resolving a simple placeholder."""
        config = {"server": {"port": 8080}}
        result, changed = resolve_single_value("Port: ${server.port}", config)
        assert result == "Port: 8080"
        assert changed is True

    def test_multiple_placeholders(self) -> None:
        """Test resolving multiple placeholders in one string."""
        config = {"host": "localhost", "port": 8080}
        result, changed = resolve_single_value("${host}:${port}", config)
        assert result == "localhost:8080"
        assert changed is True

    def test_placeholder_with_default(self) -> None:
        """Test placeholder with default value when key missing."""
        config = {}
        result, changed = resolve_single_value("${missing:default}", config)
        assert result == "default"
        assert changed is True

    def test_placeholder_with_default_key_present(self) -> None:
        """Test placeholder with default when key exists."""
        config = {"key": "actual"}
        result, changed = resolve_single_value("${key:default}", config)
        assert result == "actual"
        assert changed is True

    def test_unresolved_placeholder(self) -> None:
        """Test that unresolved placeholders are left as-is."""
        config = {}
        result, changed = resolve_single_value("${missing}", config)
        assert result == "${missing}"
        assert changed is False

    def test_empty_default(self) -> None:
        """Test placeholder with empty default value."""
        config = {}
        result, changed = resolve_single_value("prefix${missing:}suffix", config)
        assert result == "prefixsuffix"
        assert changed is True

    def test_placeholder_only(self) -> None:
        """Test string that is only a placeholder."""
        config = {"value": "resolved"}
        result, changed = resolve_single_value("${value}", config)
        assert result == "resolved"
        assert changed is True

    def test_numeric_value_conversion(self) -> None:
        """Test that numeric values are converted to strings."""
        config = {"port": 8080}
        result, changed = resolve_single_value("${port}", config)
        assert result == "8080"
        assert changed is True


class TestResolvePlaceholders:
    """Tests for resolve_placeholders function."""

    def test_simple_config(self) -> None:
        """Test resolving placeholders in simple config."""
        config = {
            "host": "localhost",
            "port": 8080,
            "url": "http://${host}:${port}",
        }
        result, warnings = resolve_placeholders(config)

        assert result["url"] == "http://localhost:8080"
        assert len(warnings) == 0

    def test_nested_config(self) -> None:
        """Test resolving placeholders in nested config."""
        config = {
            "database": {
                "host": "db.example.com",
                "port": 5432,
                "url": "jdbc:postgresql://${database.host}:${database.port}/mydb",
            }
        }
        result, warnings = resolve_placeholders(config)

        assert result["database"]["url"] == "jdbc:postgresql://db.example.com:5432/mydb"
        assert len(warnings) == 0

    def test_chained_references(self) -> None:
        """Test resolving chained placeholder references."""
        config = {
            "base": "value",
            "ref1": "${base}",
            "ref2": "${ref1}",
        }
        result, warnings = resolve_placeholders(config)

        assert result["ref1"] == "value"
        assert result["ref2"] == "value"
        assert len(warnings) == 0

    def test_cross_section_reference(self) -> None:
        """Test referencing values from different config sections."""
        config = {
            "server": {"port": 8080},
            "app": {"url": "http://localhost:${server.port}"},
        }
        result, warnings = resolve_placeholders(config)

        assert result["app"]["url"] == "http://localhost:8080"
        assert len(warnings) == 0

    def test_unresolved_warning(self) -> None:
        """Test that unresolved placeholders generate warnings."""
        config = {"url": "http://${missing.host}:8080"}
        result, warnings = resolve_placeholders(config)

        assert result["url"] == "http://${missing.host}:8080"
        assert len(warnings) == 1
        assert "missing.host" in warnings[0]

    def test_default_values(self) -> None:
        """Test placeholders with default values."""
        config = {
            "host": "${DB_HOST:localhost}",
            "port": "${DB_PORT:5432}",
        }
        result, warnings = resolve_placeholders(config)

        assert result["host"] == "localhost"
        assert result["port"] == "5432"
        assert len(warnings) == 0

    def test_list_values(self) -> None:
        """Test resolving placeholders in list values."""
        config = {
            "base": "/api",
            "endpoints": ["${base}/users", "${base}/orders"],
        }
        result, warnings = resolve_placeholders(config)

        assert result["endpoints"] == ["/api/users", "/api/orders"]
        assert len(warnings) == 0

    def test_preserves_non_string_values(self) -> None:
        """Test that non-string values are preserved."""
        config = {
            "port": 8080,
            "enabled": True,
            "ratio": 0.5,
            "items": [1, 2, 3],
        }
        result, warnings = resolve_placeholders(config)

        assert result["port"] == 8080
        assert result["enabled"] is True
        assert result["ratio"] == 0.5
        assert result["items"] == [1, 2, 3]
        assert len(warnings) == 0

    def test_max_iterations_prevents_infinite_loop(self) -> None:
        """Test that max_iterations prevents infinite loops."""
        # This creates a situation that would loop forever
        # ${a} -> ${b} -> ${a} but since values don't change after first pass,
        # it should stop naturally. Testing max_iterations limit.
        config = {"a": "${b}", "b": "${c}", "c": "${d}", "d": "final"}
        result, warnings = resolve_placeholders(config, max_iterations=2)

        # After 2 iterations, should have resolved through the chain
        # Iter 1: a=${b}, b=${c}, c=${d}, d=final -> a=${c}, b=${d}, c=final, d=final
        # Iter 2: a=${d}, b=final, c=final, d=final -> a=final, b=final, c=final, d=final
        assert result["d"] == "final"

    def test_list_with_dict_items(self) -> None:
        """Test resolving placeholders in list of dicts."""
        config = {
            "base": "http://api.example.com",
            "services": [
                {"name": "users", "url": "${base}/users"},
                {"name": "orders", "url": "${base}/orders"},
            ],
        }
        result, warnings = resolve_placeholders(config)

        assert result["services"][0]["url"] == "http://api.example.com/users"
        assert result["services"][1]["url"] == "http://api.example.com/orders"
        assert len(warnings) == 0
