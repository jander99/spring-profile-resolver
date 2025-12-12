"""Tests for Java .properties file parsing."""

from pathlib import Path

import pytest

from spring_profile_resolver.properties_parser import (
    _convert_value,
    _parse_property_line,
    _properties_to_nested_dict,
    _unescape_property_string,
    get_profile_from_properties_filename,
    parse_properties_content,
    parse_properties_file,
)


class TestParsePropertyLine:
    """Tests for parsing individual property lines."""

    def test_equals_separator(self):
        key, value = _parse_property_line("server.port=8080")
        assert key == "server.port"
        assert value == "8080"

    def test_colon_separator(self):
        key, value = _parse_property_line("server.port: 8080")
        assert key == "server.port"
        assert value == "8080"

    def test_colon_no_space(self):
        key, value = _parse_property_line("server.port:8080")
        assert key == "server.port"
        assert value == "8080"

    def test_equals_with_spaces(self):
        key, value = _parse_property_line("server.port = 8080")
        assert key == "server.port"
        assert value == "8080"

    def test_value_with_equals(self):
        key, value = _parse_property_line("url=jdbc:postgresql://host:5432/db")
        assert key == "url"
        assert value == "jdbc:postgresql://host:5432/db"

    def test_empty_value(self):
        key, value = _parse_property_line("empty.key=")
        assert key == "empty.key"
        assert value == ""


class TestUnescapePropertyString:
    """Tests for unescaping property strings."""

    def test_newline(self):
        assert _unescape_property_string("line1\\nline2") == "line1\nline2"

    def test_tab(self):
        assert _unescape_property_string("col1\\tcol2") == "col1\tcol2"

    def test_backslash(self):
        assert _unescape_property_string("path\\\\to\\\\file") == "path\\to\\file"

    def test_unicode(self):
        assert _unescape_property_string("\\u0048\\u0065\\u006C\\u006C\\u006F") == "Hello"

    def test_no_escape(self):
        assert _unescape_property_string("normal string") == "normal string"


class TestPropertiesToNestedDict:
    """Tests for converting flat properties to nested dicts."""

    def test_simple_nesting(self):
        props = {"server.port": "8080", "server.host": "localhost"}
        result = _properties_to_nested_dict(props)
        assert result == {"server": {"port": 8080, "host": "localhost"}}

    def test_deep_nesting(self):
        props = {"spring.datasource.hikari.maximum-pool-size": "10"}
        result = _properties_to_nested_dict(props)
        assert result == {
            "spring": {"datasource": {"hikari": {"maximum-pool-size": 10}}}
        }

    def test_multiple_branches(self):
        props = {
            "server.port": "8080",
            "database.host": "localhost",
            "database.port": "5432",
        }
        result = _properties_to_nested_dict(props)
        assert result == {
            "server": {"port": 8080},
            "database": {"host": "localhost", "port": 5432},
        }

    def test_single_key(self):
        props = {"name": "MyApp"}
        result = _properties_to_nested_dict(props)
        assert result == {"name": "MyApp"}


class TestConvertValue:
    """Tests for value type conversion."""

    def test_boolean_true(self):
        assert _convert_value("true") is True
        assert _convert_value("TRUE") is True

    def test_boolean_false(self):
        assert _convert_value("false") is False
        assert _convert_value("FALSE") is False

    def test_integer(self):
        assert _convert_value("8080") == 8080
        assert _convert_value("-1") == -1

    def test_float(self):
        assert _convert_value("3.14") == 3.14
        assert _convert_value("-0.5") == -0.5

    def test_string(self):
        assert _convert_value("hello") == "hello"
        assert _convert_value("localhost") == "localhost"


class TestParsePropertiesContent:
    """Tests for parsing properties file content."""

    def test_simple_file(self):
        content = """
server.port=8080
server.host=localhost
"""
        docs = parse_properties_content(content, Path("application.properties"))
        assert len(docs) == 1
        assert docs[0].content == {"server": {"port": 8080, "host": "localhost"}}

    def test_with_comments(self):
        content = """
# This is a comment
server.port=8080
! This is also a comment
server.host=localhost
"""
        docs = parse_properties_content(content, Path("application.properties"))
        assert len(docs) == 1
        assert docs[0].content == {"server": {"port": 8080, "host": "localhost"}}

    def test_multi_document(self):
        content = """
server.port=8080
#---
# spring.config.activate.on-profile=prod
server.port=80
"""
        docs = parse_properties_content(content, Path("application.properties"))
        assert len(docs) == 2
        assert docs[0].content == {"server": {"port": 8080}}
        assert docs[0].activation_profile is None
        assert docs[1].content == {"server": {"port": 80}}
        assert docs[1].activation_profile == "prod"

    def test_activation_comment(self):
        content = """
#---
#spring.config.activate.on-profile=dev
server.port=9000
"""
        docs = parse_properties_content(content, Path("application.properties"))
        # First doc is empty, second has activation
        assert len(docs) >= 1
        dev_doc = [d for d in docs if d.activation_profile == "dev"]
        assert len(dev_doc) == 1
        assert dev_doc[0].content == {"server": {"port": 9000}}

    def test_multiline_value(self):
        content = """
long.text=This is a \\
long value that \\
spans multiple lines
"""
        docs = parse_properties_content(content, Path("application.properties"))
        assert len(docs) == 1
        assert docs[0].content["long"]["text"] == "This is a long value that spans multiple lines"

    def test_blank_lines_ignored(self):
        content = """

server.port=8080

database.host=localhost

"""
        docs = parse_properties_content(content, Path("application.properties"))
        assert len(docs) == 1
        assert "server" in docs[0].content
        assert "database" in docs[0].content


class TestParsePropertiesFile:
    """Tests for parsing properties files from disk."""

    def test_parse_file(self, tmp_path):
        props_file = tmp_path / "application.properties"
        props_file.write_text("server.port=8080\napp.name=MyApp")

        docs = parse_properties_file(props_file)
        assert len(docs) == 1
        assert docs[0].content == {"server": {"port": 8080}, "app": {"name": "MyApp"}}
        assert docs[0].source_file == props_file

    def test_parse_nonexistent_file(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            parse_properties_file(tmp_path / "nonexistent.properties")


class TestGetProfileFromFilename:
    """Tests for extracting profile from filename."""

    def test_base_application(self):
        assert get_profile_from_properties_filename(Path("application.properties")) is None

    def test_profile_specific(self):
        assert get_profile_from_properties_filename(Path("application-prod.properties")) == "prod"
        assert get_profile_from_properties_filename(Path("application-dev.properties")) == "dev"

    def test_full_path(self):
        path = Path("/src/main/resources/application-staging.properties")
        assert get_profile_from_properties_filename(path) == "staging"


class TestIntegrationWithResolver:
    """Integration tests with the resolver."""

    def test_properties_only_project(self):
        """Test resolving a project with only .properties files."""
        from spring_profile_resolver.resolver import resolve_profiles

        project_path = Path(__file__).parent.parent / "test-fixtures" / "with-properties"
        result = resolve_profiles(project_path, ["prod"])

        assert result.config["server"]["port"] == 80
        assert result.config["database"]["host"] == "prod-db.example.com"
        assert result.config["app"]["name"] == "MyApplication"

    def test_mixed_yaml_and_properties(self):
        """Test that .properties overrides .yml for same keys."""
        from spring_profile_resolver.resolver import resolve_profiles

        project_path = Path(__file__).parent.parent / "test-fixtures" / "mixed-formats"
        result = resolve_profiles(project_path, [])

        # From YAML
        assert result.config["app"]["name"] == "MyApp"
        assert result.config["database"]["port"] == 5432

        # From properties (should override YAML)
        assert result.config["server"]["port"] == 9090

        # Only in properties
        assert result.config["app"]["description"] == "A sample application"
