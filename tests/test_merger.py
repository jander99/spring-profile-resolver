"""Tests for the merger module."""

from pathlib import Path

from spring_profile_resolver.merger import deep_merge, merge_configs
from spring_profile_resolver.models import ConfigDocument, ConfigSource


class TestDeepMerge:
    """Tests for deep_merge function."""

    def test_merge_disjoint_keys(self) -> None:
        """Test merging configs with non-overlapping keys."""
        base = {"a": 1}
        override = {"b": 2}
        source = ConfigSource(Path("override.yml"))

        result, sources = deep_merge(base, override, {}, source)

        assert result == {"a": 1, "b": 2}
        assert "b" in sources
        assert sources["b"].file_path == Path("override.yml")

    def test_merge_override_scalar(self) -> None:
        """Test that scalar values are overridden."""
        base = {"port": 8080}
        base_sources = {"port": ConfigSource(Path("base.yml"))}
        override = {"port": 80}
        source = ConfigSource(Path("override.yml"))

        result, sources = deep_merge(base, override, base_sources, source)

        assert result == {"port": 80}
        assert sources["port"].file_path == Path("override.yml")

    def test_merge_nested_dicts(self) -> None:
        """Test deep merging of nested dictionaries."""
        base = {
            "server": {
                "port": 8080,
                "host": "localhost",
            }
        }
        base_sources = {
            "server.port": ConfigSource(Path("base.yml")),
            "server.host": ConfigSource(Path("base.yml")),
        }
        override = {
            "server": {
                "port": 80,
            }
        }
        source = ConfigSource(Path("override.yml"))

        result, sources = deep_merge(base, override, base_sources, source)

        assert result == {
            "server": {
                "port": 80,
                "host": "localhost",
            }
        }
        assert sources["server.port"].file_path == Path("override.yml")
        assert sources["server.host"].file_path == Path("base.yml")

    def test_merge_add_nested_key(self) -> None:
        """Test adding new nested keys."""
        base = {"server": {"port": 8080}}
        override = {"server": {"ssl": {"enabled": True}}}
        source = ConfigSource(Path("override.yml"))

        result, sources = deep_merge(base, override, {}, source)

        assert result == {
            "server": {
                "port": 8080,
                "ssl": {"enabled": True},
            }
        }
        assert "server.ssl.enabled" in sources

    def test_merge_replace_list(self) -> None:
        """Test that lists are replaced entirely, not merged."""
        base = {"endpoints": ["/health", "/info"]}
        base_sources = {"endpoints": ConfigSource(Path("base.yml"))}
        override = {"endpoints": ["/health", "/metrics"]}
        source = ConfigSource(Path("override.yml"))

        result, sources = deep_merge(base, override, base_sources, source)

        assert result == {"endpoints": ["/health", "/metrics"]}
        assert sources["endpoints"].file_path == Path("override.yml")

    def test_merge_dict_replaces_scalar(self) -> None:
        """Test that a dict can replace a scalar value."""
        base = {"config": "simple"}
        base_sources = {"config": ConfigSource(Path("base.yml"))}
        override = {"config": {"nested": "value"}}
        source = ConfigSource(Path("override.yml"))

        result, sources = deep_merge(base, override, base_sources, source)

        assert result == {"config": {"nested": "value"}}
        assert "config" not in sources  # Old scalar source removed
        assert sources["config.nested"].file_path == Path("override.yml")

    def test_merge_scalar_replaces_dict(self) -> None:
        """Test that a scalar can replace a dict value."""
        base = {"config": {"nested": "value"}}
        base_sources = {"config.nested": ConfigSource(Path("base.yml"))}
        override = {"config": "simple"}
        source = ConfigSource(Path("override.yml"))

        result, sources = deep_merge(base, override, base_sources, source)

        assert result == {"config": "simple"}
        assert "config.nested" not in sources  # Old nested source removed
        assert sources["config"].file_path == Path("override.yml")


class TestMergeConfigs:
    """Tests for merge_configs function."""

    def test_merge_empty_list(self) -> None:
        """Test merging empty document list."""
        result, sources = merge_configs([])
        assert result == {}
        assert sources == {}

    def test_merge_single_document(self) -> None:
        """Test merging single document."""
        docs = [
            ConfigDocument(
                content={"server": {"port": 8080}},
                source_file=Path("application.yml"),
            )
        ]

        result, sources = merge_configs(docs)

        assert result == {"server": {"port": 8080}}
        assert sources["server.port"].file_path == Path("application.yml")

    def test_merge_multiple_documents(self) -> None:
        """Test merging multiple documents in order."""
        docs = [
            ConfigDocument(
                content={"server": {"port": 8080, "host": "localhost"}},
                source_file=Path("application.yml"),
            ),
            ConfigDocument(
                content={"server": {"port": 80}},
                source_file=Path("application-prod.yml"),
            ),
        ]

        result, sources = merge_configs(docs)

        assert result == {"server": {"port": 80, "host": "localhost"}}
        assert sources["server.port"].file_path == Path("application-prod.yml")
        assert sources["server.host"].file_path == Path("application.yml")

    def test_merge_three_documents(self) -> None:
        """Test merging chain of three documents."""
        docs = [
            ConfigDocument(
                content={"a": 1, "b": 1, "c": 1},
                source_file=Path("first.yml"),
            ),
            ConfigDocument(
                content={"b": 2, "c": 2},
                source_file=Path("second.yml"),
            ),
            ConfigDocument(
                content={"c": 3},
                source_file=Path("third.yml"),
            ),
        ]

        result, sources = merge_configs(docs)

        assert result == {"a": 1, "b": 2, "c": 3}
        assert sources["a"].file_path == Path("first.yml")
        assert sources["b"].file_path == Path("second.yml")
        assert sources["c"].file_path == Path("third.yml")

    def test_merge_preserves_unrelated_keys(self) -> None:
        """Test that keys not in override are preserved."""
        docs = [
            ConfigDocument(
                content={
                    "server": {"port": 8080},
                    "logging": {"level": "INFO"},
                },
                source_file=Path("application.yml"),
            ),
            ConfigDocument(
                content={"server": {"port": 80}},
                source_file=Path("application-prod.yml"),
            ),
        ]

        result, sources = merge_configs(docs)

        assert result["logging"] == {"level": "INFO"}
        assert sources["logging.level"].file_path == Path("application.yml")
