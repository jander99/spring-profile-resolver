"""Tests for the profiles module."""

from pathlib import Path

import pytest

from spring_profile_resolver.models import ConfigDocument
from spring_profile_resolver.profiles import (
    CircularProfileGroupError,
    expand_profiles,
    get_applicable_documents,
    parse_profile_groups,
)


class TestParseProfileGroups:
    """Tests for parse_profile_groups function."""

    def test_parse_comma_separated_groups(self) -> None:
        """Test parsing groups defined as comma-separated strings."""
        config = {
            "spring": {
                "profiles": {
                    "group": {
                        "prod": "proddb,prodmq",
                        "dev": "h2,mock",
                    }
                }
            }
        }
        groups = parse_profile_groups(config)

        assert groups == {
            "prod": ["proddb", "prodmq"],
            "dev": ["h2", "mock"],
        }

    def test_parse_list_groups(self) -> None:
        """Test parsing groups defined as lists."""
        config = {
            "spring": {
                "profiles": {
                    "group": {
                        "prod": ["proddb", "prodmq"],
                    }
                }
            }
        }
        groups = parse_profile_groups(config)

        assert groups == {"prod": ["proddb", "prodmq"]}

    def test_parse_nested_groups(self) -> None:
        """Test parsing nested group definitions."""
        config = {
            "spring": {
                "profiles": {
                    "group": {
                        "prod": "proddb,prodmq",
                        "proddb": "postgres,hikari",
                    }
                }
            }
        }
        groups = parse_profile_groups(config)

        assert groups == {
            "prod": ["proddb", "prodmq"],
            "proddb": ["postgres", "hikari"],
        }

    def test_parse_empty_config(self) -> None:
        """Test parsing config with no groups."""
        assert parse_profile_groups({}) == {}
        assert parse_profile_groups({"spring": {}}) == {}
        assert parse_profile_groups({"spring": {"profiles": {}}}) == {}

    def test_parse_with_whitespace(self) -> None:
        """Test that whitespace in comma-separated values is trimmed."""
        config = {
            "spring": {
                "profiles": {
                    "group": {
                        "prod": "  proddb , prodmq  ",
                    }
                }
            }
        }
        groups = parse_profile_groups(config)

        assert groups == {"prod": ["proddb", "prodmq"]}

    def test_parse_none_value(self) -> None:
        """Test that None values are skipped."""
        config = {
            "spring": {
                "profiles": {
                    "group": {
                        "prod": None,
                        "dev": "h2",
                    }
                }
            }
        }
        groups = parse_profile_groups(config)

        assert groups == {"dev": ["h2"]}


class TestExpandProfiles:
    """Tests for expand_profiles function."""

    def test_expand_no_groups(self) -> None:
        """Test expansion when no groups are defined."""
        result = expand_profiles(["prod", "aws"], {})
        assert result == ["prod", "aws"]

    def test_expand_simple_group(self) -> None:
        """Test expanding a simple group."""
        groups = {"prod": ["proddb", "prodmq"]}
        result = expand_profiles(["prod"], groups)

        # Profile itself comes first, then group members
        assert result == ["prod", "proddb", "prodmq"]

    def test_expand_nested_groups(self) -> None:
        """Test expanding nested groups depth-first."""
        groups = {
            "prod": ["proddb", "prodmq"],
            "proddb": ["postgres", "hikari"],
        }
        result = expand_profiles(["prod"], groups)

        # prod -> proddb -> postgres, hikari -> prodmq
        assert result == ["prod", "proddb", "postgres", "hikari", "prodmq"]

    def test_expand_multiple_profiles(self) -> None:
        """Test expanding multiple requested profiles."""
        groups = {"prod": ["proddb"]}
        result = expand_profiles(["prod", "aws"], groups)

        assert result == ["prod", "proddb", "aws"]

    def test_expand_avoids_duplicates(self) -> None:
        """Test that duplicate profiles are not repeated."""
        groups = {
            "prod": ["common", "proddb"],
            "staging": ["common", "stagingdb"],
        }
        result = expand_profiles(["prod", "staging"], groups)

        # common should only appear once
        assert result.count("common") == 1
        assert result == ["prod", "common", "proddb", "staging", "stagingdb"]

    def test_expand_circular_reference_simple(self) -> None:
        """Test that circular references are detected."""
        groups = {"a": ["b"], "b": ["a"]}

        with pytest.raises(CircularProfileGroupError) as exc_info:
            expand_profiles(["a"], groups)

        assert exc_info.value.cycle_path == ["a", "b", "a"]

    def test_expand_circular_reference_self(self) -> None:
        """Test that self-referential groups are detected."""
        groups = {"a": ["a"]}

        with pytest.raises(CircularProfileGroupError) as exc_info:
            expand_profiles(["a"], groups)

        assert exc_info.value.cycle_path == ["a", "a"]

    def test_expand_circular_reference_chain(self) -> None:
        """Test detecting circular reference in longer chain."""
        groups = {"a": ["b"], "b": ["c"], "c": ["a"]}

        with pytest.raises(CircularProfileGroupError) as exc_info:
            expand_profiles(["a"], groups)

        assert exc_info.value.cycle_path == ["a", "b", "c", "a"]

    def test_expand_profile_not_in_groups(self) -> None:
        """Test that profiles not in groups are still included."""
        groups = {"prod": ["proddb"]}
        result = expand_profiles(["dev"], groups)

        assert result == ["dev"]


class TestGetApplicableDocuments:
    """Tests for get_applicable_documents function."""

    def test_filter_unconditional_documents(self) -> None:
        """Test that documents without activation condition always match."""
        docs = [
            ConfigDocument(
                content={"a": 1},
                source_file=Path("app.yml"),
                activation_profile=None,
            )
        ]
        result = get_applicable_documents(docs, [])
        assert len(result) == 1

        result = get_applicable_documents(docs, ["prod"])
        assert len(result) == 1

    def test_filter_by_profile(self) -> None:
        """Test filtering documents by activation profile."""
        docs = [
            ConfigDocument(
                content={"a": 1},
                source_file=Path("app.yml"),
                activation_profile=None,
            ),
            ConfigDocument(
                content={"b": 2},
                source_file=Path("app.yml"),
                activation_profile="prod",
            ),
            ConfigDocument(
                content={"c": 3},
                source_file=Path("app.yml"),
                activation_profile="dev",
            ),
        ]

        result = get_applicable_documents(docs, ["prod"])

        assert len(result) == 2
        assert result[0].content == {"a": 1}
        assert result[1].content == {"b": 2}

    def test_maintains_order(self) -> None:
        """Test that document order is maintained."""
        docs = [
            ConfigDocument(
                content={"order": 1},
                source_file=Path("app.yml"),
                activation_profile=None,
            ),
            ConfigDocument(
                content={"order": 2},
                source_file=Path("app.yml"),
                activation_profile="prod",
            ),
            ConfigDocument(
                content={"order": 3},
                source_file=Path("app.yml"),
                activation_profile=None,
            ),
        ]

        result = get_applicable_documents(docs, ["prod"])

        assert [d.content["order"] for d in result] == [1, 2, 3]
