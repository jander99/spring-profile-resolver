"""Tests for Cloud Foundry VCAP_SERVICES support."""

import json

from spring_profile_resolver.vcap_services import (
    detect_vcap_placeholders,
    get_vcap_config,
    is_vcap_available,
    is_vcap_placeholder,
    parse_vcap_application,
    parse_vcap_services,
)


class TestIsVcapPlaceholder:
    """Tests for is_vcap_placeholder function."""

    def test_vcap_services_placeholder(self):
        assert is_vcap_placeholder("vcap.services.mydb.credentials.uri") is True

    def test_vcap_application_placeholder(self):
        assert is_vcap_placeholder("vcap.application.name") is True

    def test_non_vcap_placeholder(self):
        assert is_vcap_placeholder("server.port") is False
        assert is_vcap_placeholder("spring.datasource.url") is False

    def test_vcap_prefix_but_not_services_or_application(self):
        # vcap.* but not vcap.services.* or vcap.application.*
        assert is_vcap_placeholder("vcap.other.something") is False


class TestDetectVcapPlaceholders:
    """Tests for detect_vcap_placeholders function."""

    def test_single_vcap_placeholder(self):
        value = "${vcap.services.mydb.credentials.uri}"
        result = detect_vcap_placeholders(value)
        assert result == ["vcap.services.mydb.credentials.uri"]

    def test_multiple_vcap_placeholders(self):
        value = "${vcap.services.mydb.credentials.host}:${vcap.services.mydb.credentials.port}"
        result = detect_vcap_placeholders(value)
        assert "vcap.services.mydb.credentials.host" in result
        assert "vcap.services.mydb.credentials.port" in result

    def test_vcap_with_default(self):
        value = "${vcap.services.mydb.credentials.uri:jdbc:postgresql://localhost/db}"
        result = detect_vcap_placeholders(value)
        assert result == ["vcap.services.mydb.credentials.uri"]

    def test_no_vcap_placeholders(self):
        value = "${server.port:8080}"
        result = detect_vcap_placeholders(value)
        assert result == []

    def test_mixed_placeholders(self):
        value = "URL: ${vcap.services.mydb.credentials.uri}, port: ${server.port}"
        result = detect_vcap_placeholders(value)
        assert result == ["vcap.services.mydb.credentials.uri"]

    def test_no_placeholders(self):
        value = "just a plain string"
        result = detect_vcap_placeholders(value)
        assert result == []


class TestParseVcapServices:
    """Tests for parse_vcap_services function."""

    def test_empty_returns_empty(self):
        result, warnings = parse_vcap_services(None)
        assert result == {}
        assert warnings == []

        result, warnings = parse_vcap_services("")
        assert result == {}
        assert warnings == []

    def test_invalid_json_returns_empty(self):
        result, warnings = parse_vcap_services("not valid json")
        assert result == {}
        assert len(warnings) == 1
        assert "Invalid VCAP_SERVICES JSON" in warnings[0]

    def test_single_service(self):
        vcap_json = json.dumps({
            "user-provided": [
                {
                    "name": "my-config",
                    "credentials": {
                        "api-key": "secret123"
                    },
                    "label": "user-provided"
                }
            ]
        })
        result, warnings = parse_vcap_services(vcap_json)

        assert "vcap" in result
        assert "services" in result["vcap"]
        assert "my-config" in result["vcap"]["services"]
        assert result["vcap"]["services"]["my-config"]["credentials"]["api-key"] == "secret123"
        assert warnings == []

    def test_multiple_services(self):
        vcap_json = json.dumps({
            "user-provided": [
                {
                    "name": "config-service",
                    "credentials": {"key": "value1"}
                }
            ],
            "p.mysql": [
                {
                    "name": "my-mysql",
                    "credentials": {
                        "hostname": "mysql.example.com",
                        "port": 3306,
                        "username": "admin",
                        "password": "secret"
                    }
                }
            ]
        })
        result, warnings = parse_vcap_services(vcap_json)

        assert "config-service" in result["vcap"]["services"]
        assert "my-mysql" in result["vcap"]["services"]
        assert result["vcap"]["services"]["my-mysql"]["credentials"]["hostname"] == "mysql.example.com"
        assert result["vcap"]["services"]["my-mysql"]["credentials"]["port"] == 3306

    def test_multiple_instances_of_same_type(self):
        vcap_json = json.dumps({
            "p.mysql": [
                {"name": "db-primary", "credentials": {"host": "primary.db"}},
                {"name": "db-replica", "credentials": {"host": "replica.db"}}
            ]
        })
        result, warnings = parse_vcap_services(vcap_json)

        assert "db-primary" in result["vcap"]["services"]
        assert "db-replica" in result["vcap"]["services"]

    def test_service_without_name_ignored(self):
        vcap_json = json.dumps({
            "user-provided": [
                {"credentials": {"key": "value"}}  # No "name" field
            ]
        })
        result, warnings = parse_vcap_services(vcap_json)
        assert result == {}

    def test_non_dict_value_returns_empty(self):
        result, warnings = parse_vcap_services('"just a string"')
        assert result == {}
        assert len(warnings) == 1
        assert "not a JSON object" in warnings[0]


class TestParseVcapApplication:
    """Tests for parse_vcap_application function."""

    def test_empty_returns_empty(self):
        result, warnings = parse_vcap_application(None)
        assert result == {}
        assert warnings == []

        result, warnings = parse_vcap_application("")
        assert result == {}
        assert warnings == []

    def test_invalid_json_returns_empty(self):
        result, warnings = parse_vcap_application("not valid json")
        assert result == {}
        assert len(warnings) == 1
        assert "Invalid VCAP_APPLICATION JSON" in warnings[0]

    def test_application_metadata(self):
        vcap_json = json.dumps({
            "application_name": "my-app",
            "application_id": "app-123",
            "space_name": "development",
            "organization_name": "my-org",
            "uris": ["my-app.cfapps.io"]
        })
        result, warnings = parse_vcap_application(vcap_json)

        assert "vcap" in result
        assert "application" in result["vcap"]
        assert result["vcap"]["application"]["application_name"] == "my-app"
        assert result["vcap"]["application"]["space_name"] == "development"
        assert result["vcap"]["application"]["uris"] == ["my-app.cfapps.io"]
        assert warnings == []


class TestGetVcapConfig:
    """Tests for get_vcap_config function."""

    def test_empty_returns_empty(self):
        result, warnings = get_vcap_config(None, None)
        assert result == {}
        assert warnings == []

    def test_services_only(self):
        services_json = json.dumps({
            "user-provided": [{"name": "my-service", "credentials": {"key": "value"}}]
        })
        result, warnings = get_vcap_config(vcap_services_json=services_json)

        assert "vcap" in result
        assert "services" in result["vcap"]
        assert "my-service" in result["vcap"]["services"]
        assert warnings == []

    def test_application_only(self):
        app_json = json.dumps({"application_name": "my-app"})
        result, warnings = get_vcap_config(vcap_application_json=app_json)

        assert "vcap" in result
        assert "application" in result["vcap"]
        assert result["vcap"]["application"]["application_name"] == "my-app"
        assert warnings == []

    def test_both_services_and_application(self):
        services_json = json.dumps({
            "user-provided": [{"name": "my-service", "credentials": {"key": "value"}}]
        })
        app_json = json.dumps({"application_name": "my-app"})

        result, warnings = get_vcap_config(services_json, app_json)

        assert "vcap" in result
        assert "services" in result["vcap"]
        assert "application" in result["vcap"]
        assert "my-service" in result["vcap"]["services"]
        assert result["vcap"]["application"]["application_name"] == "my-app"
        assert warnings == []

    def test_invalid_json_returns_warnings(self):
        result, warnings = get_vcap_config("invalid json", "also invalid")
        assert result == {}
        assert len(warnings) == 2
        assert any("VCAP_SERVICES" in w for w in warnings)
        assert any("VCAP_APPLICATION" in w for w in warnings)


class TestIsVcapAvailable:
    """Tests for is_vcap_available function."""

    def test_not_available_when_not_set(self, monkeypatch):
        monkeypatch.delenv("VCAP_SERVICES", raising=False)
        monkeypatch.delenv("VCAP_APPLICATION", raising=False)
        assert is_vcap_available() is False

    def test_available_when_vcap_services_set(self, monkeypatch):
        monkeypatch.setenv("VCAP_SERVICES", '{"user-provided": []}')
        monkeypatch.delenv("VCAP_APPLICATION", raising=False)
        assert is_vcap_available() is True

    def test_available_when_vcap_application_set(self, monkeypatch):
        monkeypatch.delenv("VCAP_SERVICES", raising=False)
        monkeypatch.setenv("VCAP_APPLICATION", '{"application_name": "app"}')
        assert is_vcap_available() is True


class TestVcapPlaceholderResolution:
    """Integration tests for VCAP placeholder resolution."""

    def test_resolve_vcap_service_credential(self):
        """Test resolving a VCAP service credential placeholder."""
        from spring_profile_resolver.placeholders import resolve_placeholders

        config = {
            "spring": {
                "datasource": {
                    "url": "${vcap.services.my-mysql.credentials.uri}"
                }
            }
        }

        vcap_services = json.dumps({
            "p.mysql": [
                {
                    "name": "my-mysql",
                    "credentials": {
                        "uri": "jdbc:mysql://host:3306/db"
                    }
                }
            ]
        })

        result, warnings = resolve_placeholders(
            config,
            use_system_env=False,
            vcap_services_json=vcap_services,
        )

        assert result["spring"]["datasource"]["url"] == "jdbc:mysql://host:3306/db"
        # Should not have VCAP unavailable warning since we provided VCAP
        assert not any("VCAP_SERVICES" in w for w in warnings)

    def test_resolve_vcap_application_property(self):
        """Test resolving a VCAP application placeholder."""
        from spring_profile_resolver.placeholders import resolve_placeholders

        config = {
            "app": {
                "name": "${vcap.application.application_name:unknown}"
            }
        }

        vcap_application = json.dumps({
            "application_name": "my-cloud-app"
        })

        result, warnings = resolve_placeholders(
            config,
            use_system_env=False,
            vcap_application_json=vcap_application,
        )

        assert result["app"]["name"] == "my-cloud-app"

    def test_vcap_placeholder_with_default_when_not_available(self):
        """Test that VCAP placeholder with default uses default when VCAP not available."""
        from spring_profile_resolver.placeholders import resolve_placeholders

        config = {
            "database": {
                "url": "${vcap.services.mydb.credentials.uri:jdbc:postgresql://localhost/localdb}"
            }
        }

        result, warnings = resolve_placeholders(
            config,
            use_system_env=False,
        )

        # Should use default value
        assert result["database"]["url"] == "jdbc:postgresql://localhost/localdb"

    def test_vcap_unavailable_warning(self, monkeypatch):
        """Test that warning is generated when VCAP is referenced but not available."""
        from spring_profile_resolver.placeholders import resolve_placeholders

        # Ensure VCAP env vars are not set
        monkeypatch.delenv("VCAP_SERVICES", raising=False)
        monkeypatch.delenv("VCAP_APPLICATION", raising=False)

        config = {
            "database": {
                "url": "${vcap.services.mydb.credentials.uri}"
            }
        }

        result, warnings = resolve_placeholders(
            config,
            use_system_env=False,
        )

        # Should have VCAP unavailable warning
        vcap_warnings = [w for w in warnings if "VCAP_SERVICES" in w]
        assert len(vcap_warnings) == 1
        assert "Cloud Foundry" in vcap_warnings[0]


class TestIgnoreVcapWarnings:
    """Tests for the ignore_vcap_warnings functionality."""

    def test_ignore_vcap_warnings_suppresses_vcap_services_warning(self, monkeypatch):
        """Test that ignore_vcap_warnings=True suppresses VCAP_SERVICES warnings."""
        from spring_profile_resolver.placeholders import resolve_placeholders

        # Ensure VCAP env vars are not set
        monkeypatch.delenv("VCAP_SERVICES", raising=False)
        monkeypatch.delenv("VCAP_APPLICATION", raising=False)

        config = {
            "database": {
                "url": "${vcap.services.mydb.credentials.uri}"
            }
        }

        result, warnings = resolve_placeholders(
            config,
            use_system_env=False,
            ignore_vcap_warnings=True,
        )

        # Should NOT have VCAP unavailable warning
        vcap_warnings = [w for w in warnings if "VCAP_SERVICES" in w]
        assert len(vcap_warnings) == 0

    def test_ignore_vcap_warnings_suppresses_vcap_application_warning(self, monkeypatch):
        """Test that ignore_vcap_warnings=True suppresses VCAP_APPLICATION warnings."""
        from spring_profile_resolver.placeholders import resolve_placeholders

        # Ensure VCAP env vars are not set
        monkeypatch.delenv("VCAP_SERVICES", raising=False)
        monkeypatch.delenv("VCAP_APPLICATION", raising=False)

        config = {
            "app": {
                "name": "${vcap.application.application_name}"
            }
        }

        result, warnings = resolve_placeholders(
            config,
            use_system_env=False,
            ignore_vcap_warnings=True,
        )

        # Should NOT have VCAP unavailable warning
        vcap_warnings = [w for w in warnings if "VCAP_APPLICATION" in w]
        assert len(vcap_warnings) == 0

    def test_ignore_vcap_warnings_suppresses_all_vcap_warnings(self, monkeypatch):
        """Test that ignore_vcap_warnings suppresses ALL VCAP-related warnings."""
        from spring_profile_resolver.placeholders import resolve_placeholders

        # Ensure VCAP env vars are not set
        monkeypatch.delenv("VCAP_SERVICES", raising=False)
        monkeypatch.delenv("VCAP_APPLICATION", raising=False)

        config = {
            "database": {
                "url": "${vcap.services.mydb.credentials.uri}"
            }
        }

        result, warnings = resolve_placeholders(
            config,
            use_system_env=False,
            ignore_vcap_warnings=True,
        )

        # Should NOT have any VCAP-related warnings (including unresolved placeholder)
        vcap_warnings = [w for w in warnings if "vcap" in w.lower()]
        assert len(vcap_warnings) == 0

    def test_ignore_vcap_warnings_does_not_affect_other_warnings(self, monkeypatch):
        """Test that ignore_vcap_warnings doesn't suppress non-VCAP warnings."""
        from spring_profile_resolver.placeholders import resolve_placeholders

        monkeypatch.delenv("VCAP_SERVICES", raising=False)
        monkeypatch.delenv("VCAP_APPLICATION", raising=False)

        config = {
            "database": {
                "host": "${DATABASE_HOST}",
                "vcap_url": "${vcap.services.mydb.credentials.uri}"
            }
        }

        result, warnings = resolve_placeholders(
            config,
            use_system_env=False,
            ignore_vcap_warnings=True,
        )

        # Should still have warning about DATABASE_HOST having no default
        no_default_warnings = [w for w in warnings if "without default" in w and "DATABASE_HOST" in w]
        assert len(no_default_warnings) == 1

        # Should NOT have VCAP warning
        vcap_warnings = [w for w in warnings if "VCAP_SERVICES" in w and "Cloud Foundry" in w]
        assert len(vcap_warnings) == 0

    def test_ignore_vcap_false_shows_warnings(self, monkeypatch):
        """Test that ignore_vcap_warnings=False (default) shows VCAP warnings."""
        from spring_profile_resolver.placeholders import resolve_placeholders

        # Ensure VCAP env vars are not set
        monkeypatch.delenv("VCAP_SERVICES", raising=False)
        monkeypatch.delenv("VCAP_APPLICATION", raising=False)

        config = {
            "database": {
                "url": "${vcap.services.mydb.credentials.uri}"
            }
        }

        result, warnings = resolve_placeholders(
            config,
            use_system_env=False,
            ignore_vcap_warnings=False,  # Explicit default
        )

        # Should have VCAP unavailable warning
        vcap_warnings = [w for w in warnings if "VCAP_SERVICES" in w]
        assert len(vcap_warnings) == 1
