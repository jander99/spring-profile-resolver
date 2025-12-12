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

    def test_array_index_simple(self) -> None:
        """Test getting a value by array index."""
        config = {"items": ["first", "second", "third"]}
        assert get_nested_value(config, "items[0]") == "first"
        assert get_nested_value(config, "items[1]") == "second"
        assert get_nested_value(config, "items[2]") == "third"

    def test_array_index_out_of_bounds(self) -> None:
        """Test array index out of bounds returns None."""
        config = {"items": ["first", "second"]}
        assert get_nested_value(config, "items[5]") is None

    def test_array_index_with_nested_property(self) -> None:
        """Test array index followed by property access."""
        config = {
            "servers": [
                {"host": "server1.example.com", "port": 8080},
                {"host": "server2.example.com", "port": 8081},
            ]
        }
        assert get_nested_value(config, "servers[0].host") == "server1.example.com"
        assert get_nested_value(config, "servers[1].port") == 8081

    def test_multiple_array_indices(self) -> None:
        """Test multiple array index accesses in path."""
        config = {
            "matrix": [
                [1, 2, 3],
                [4, 5, 6],
            ]
        }
        assert get_nested_value(config, "matrix[0][1]") == 2
        assert get_nested_value(config, "matrix[1][2]") == 6

    def test_array_index_non_list(self) -> None:
        """Test array index on non-list returns None."""
        config = {"items": "not-a-list"}
        assert get_nested_value(config, "items[0]") is None


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
        result, warnings = resolve_placeholders(config, use_system_env=False)

        assert result["url"] == "http://${missing.host}:8080"
        # Should have warning about unresolved placeholder (and possibly no-default warning)
        unresolved_warnings = [w for w in warnings if "Unresolved placeholder" in w]
        assert len(unresolved_warnings) == 1
        assert "missing.host" in unresolved_warnings[0]

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

    def test_array_index_placeholder(self) -> None:
        """Test resolving placeholder with array index syntax."""
        config = {
            "servers": [
                {"host": "primary.example.com"},
                {"host": "secondary.example.com"},
            ],
            "primary_host": "${servers[0].host}",
            "secondary_host": "${servers[1].host}",
        }
        result, warnings = resolve_placeholders(config)

        assert result["primary_host"] == "primary.example.com"
        assert result["secondary_host"] == "secondary.example.com"
        assert len([w for w in warnings if "Unresolved" in w]) == 0


class TestPlaceholderWithoutDefaultWarnings:
    """Tests for warnings about placeholders without defaults."""

    def test_warning_for_placeholder_without_default_no_config_reference(self) -> None:
        """Test that placeholder without default generates warning when not in config."""
        config = {
            "database": {
                "url": "${DATABASE_URL}"
            }
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        # Should have warning about placeholder without default
        no_default_warnings = [w for w in warnings if "without default" in w]
        assert len(no_default_warnings) == 1
        assert "DATABASE_URL" in no_default_warnings[0]

    def test_no_warning_for_placeholder_with_default(self) -> None:
        """Test that placeholder with default does not generate warning."""
        config = {
            "database": {
                "url": "${DATABASE_URL:jdbc:postgresql://localhost/mydb}"
            }
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        # Should NOT have warning about placeholder without default
        no_default_warnings = [w for w in warnings if "without default" in w]
        assert len(no_default_warnings) == 0

    def test_no_warning_for_placeholder_referencing_existing_config(self) -> None:
        """Test that placeholder referencing existing config does not generate warning."""
        config = {
            "database": {
                "host": "localhost",
                "port": 5432,
                "url": "jdbc:postgresql://${database.host}:${database.port}/mydb"
            }
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        # Should NOT have warning about placeholder without default
        no_default_warnings = [w for w in warnings if "without default" in w]
        assert len(no_default_warnings) == 0

    def test_no_warning_when_env_var_provided(self) -> None:
        """Test that placeholder without default doesn't warn if env var is provided."""
        config = {
            "database": {
                "url": "${DATABASE_URL}"
            }
        }
        env_vars = {"DATABASE_URL": "jdbc:postgresql://prod-db/mydb"}

        result, warnings = resolve_placeholders(config, env_vars=env_vars, use_system_env=False)

        # Should NOT have warning about placeholder without default
        no_default_warnings = [w for w in warnings if "without default" in w]
        assert len(no_default_warnings) == 0

    def test_warning_for_nested_placeholder_without_default(self) -> None:
        """Test warning for placeholder without default in nested config."""
        config = {
            "app": {
                "services": {
                    "external": {
                        "api": {
                            "key": "${EXTERNAL_API_KEY}"
                        }
                    }
                }
            }
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        no_default_warnings = [w for w in warnings if "without default" in w]
        assert len(no_default_warnings) == 1
        assert "EXTERNAL_API_KEY" in no_default_warnings[0]

    def test_warning_for_placeholder_in_list(self) -> None:
        """Test warning for placeholder without default in list."""
        config = {
            "servers": ["${SERVER_1}", "${SERVER_2}"]
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        no_default_warnings = [w for w in warnings if "without default" in w]
        assert len(no_default_warnings) == 2

    def test_multiple_warnings_for_multiple_placeholders(self) -> None:
        """Test that multiple placeholders without defaults generate multiple warnings."""
        config = {
            "database": {
                "host": "${DB_HOST}",
                "port": "${DB_PORT}",
                "password": "${DB_PASSWORD}"
            }
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        no_default_warnings = [w for w in warnings if "without default" in w]
        assert len(no_default_warnings) == 3

    def test_warning_message_content(self) -> None:
        """Test that warning message contains helpful information."""
        config = {
            "api": {
                "key": "${MISSING_KEY}"
            }
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        no_default_warnings = [w for w in warnings if "without default" in w]
        assert len(no_default_warnings) == 1

        warning = no_default_warnings[0]
        # Should mention the path
        assert "api.key" in warning
        # Should mention the placeholder
        assert "MISSING_KEY" in warning
        # Should mention it needs env var
        assert "environment variable" in warning.lower()

    def test_empty_default_counts_as_default(self) -> None:
        """Test that empty default (${VAR:}) does not generate warning."""
        config = {
            "optional": {
                "value": "${OPTIONAL_VALUE:}"
            }
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        no_default_warnings = [w for w in warnings if "without default" in w]
        assert len(no_default_warnings) == 0


class TestCircularReferenceDetection:
    """Tests for circular reference detection in placeholders."""

    def test_simple_circular_reference(self) -> None:
        """Test detection of simple circular reference: a -> b -> a."""
        config = {
            "a": "${b}",
            "b": "${a}",
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        # Should detect circular reference
        circular_warnings = [w for w in warnings if "Circular" in w]
        assert len(circular_warnings) >= 1
        # Check that the cycle is mentioned
        assert any("a" in w and "b" in w for w in circular_warnings)

    def test_self_referential(self) -> None:
        """Test detection of self-referential placeholder: a -> a."""
        config = {
            "a": "${a}",
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        # Should detect circular reference
        circular_warnings = [w for w in warnings if "Circular" in w]
        assert len(circular_warnings) >= 1

    def test_longer_circular_chain(self) -> None:
        """Test detection of longer circular chain: a -> b -> c -> a."""
        config = {
            "a": "${b}",
            "b": "${c}",
            "c": "${a}",
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        # Should detect circular reference
        circular_warnings = [w for w in warnings if "Circular" in w]
        assert len(circular_warnings) >= 1

    def test_no_warning_for_valid_chain(self) -> None:
        """Test that valid chain without cycle does not generate warning."""
        config = {
            "a": "${b}",
            "b": "${c}",
            "c": "final_value",
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        # Should NOT detect circular reference
        circular_warnings = [w for w in warnings if "Circular" in w]
        assert len(circular_warnings) == 0

        # Should resolve correctly
        assert result["a"] == "final_value"
        assert result["b"] == "final_value"
        assert result["c"] == "final_value"

    def test_nested_circular_reference(self) -> None:
        """Test detection of circular reference in nested config."""
        config = {
            "server": {
                "host": "${server.url}",
                "url": "http://${server.host}:8080",
            }
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        # Should detect circular reference
        circular_warnings = [w for w in warnings if "Circular" in w]
        assert len(circular_warnings) >= 1

    def test_circular_warning_message_content(self) -> None:
        """Test that circular warning message is informative."""
        config = {
            "a": "${b}",
            "b": "${a}",
        }
        result, warnings = resolve_placeholders(config, use_system_env=False)

        circular_warnings = [w for w in warnings if "Circular" in w]
        assert len(circular_warnings) >= 1

        warning = circular_warnings[0]
        # Should mention it's circular
        assert "Circular" in warning
        # Should indicate it prevents resolution
        assert "prevent" in warning.lower() or "completing" in warning.lower()
