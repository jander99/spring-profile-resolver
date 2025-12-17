"""Tests for configuration validation."""


from spring_profile_resolver.validation import (
    ValidationIssue,
    validate_configuration,
)


def test_mutually_exclusive_datasource_properties():
    """Test detection of mutually exclusive datasource properties."""
    config = {
        "spring": {
            "datasource": {
                "url": "jdbc:postgresql://localhost/db",
                "jndi-name": "java:/comp/env/jdbc/mydb",
            }
        }
    }

    issues = validate_configuration(config)

    # Should find the mutual exclusion issue
    assert len(issues) > 0
    assert any("url" in i.property_path and "jndi" in i.property_path for i in issues)


def test_ssl_enabled_without_keystore():
    """Test detection of SSL enabled without keystore."""
    config = {
        "server": {
            "ssl": {
                "enabled": True,
            }
        }
    }

    issues = validate_configuration(config)

    # Should warn about missing key-store
    assert len(issues) > 0
    assert any("key-store" in i.message.lower() for i in issues)


def test_dangerous_ddl_auto_in_production():
    """Test detection of dangerous DDL auto settings in production."""
    config = {
        "spring": {
            "jpa": {
                "hibernate": {
                    "ddl-auto": "create-drop",
                }
            },
            "profiles": {
                "active": "prod",
            },
        }
    }

    issues = validate_configuration(config)

    # Should find the dangerous configuration
    assert len(issues) > 0
    assert any("ddl" in i.message.lower() or "database" in i.message.lower() for i in issues)
    assert any(i.severity == "error" for i in issues)


def test_h2_console_in_production():
    """Test detection of H2 console enabled in production."""
    config = {
        "spring": {
            "h2": {
                "console": {
                    "enabled": True,
                }
            },
            "profiles": {
                "active": "production",
            },
        }
    }

    issues = validate_configuration(config)

    # Should find the H2 console issue
    assert len(issues) > 0
    assert any("h2" in i.message.lower() for i in issues)


def test_common_typo_detection():
    """Test detection of common property typos."""
    config = {
        "server": {
            "prot": 8080,  # Typo: should be "port"
        }
    }

    issues = validate_configuration(config)

    # Should suggest the correct property name
    assert len(issues) > 0
    assert any("server.prot" in i.property_path for i in issues)
    assert any("server.port" in (i.suggestion or "") for i in issues)


def test_actuator_exposure_without_base_path():
    """Test detection of actuator endpoints exposed without custom base path."""
    config = {
        "management": {
            "endpoints": {
                "web": {
                    "exposure": {
                        "include": "*",
                    }
                }
            }
        }
    }

    issues = validate_configuration(config)

    # Should warn about actuator exposure
    assert len(issues) > 0
    assert any("actuator" in i.message.lower() or "endpoints" in i.message.lower() for i in issues)


def test_valid_configuration_no_issues():
    """Test that a valid configuration produces no issues."""
    config = {
        "server": {
            "port": 8080,
        },
        "spring": {
            "datasource": {
                "url": "${DATABASE_URL}",
                "driver-class-name": "org.postgresql.Driver",
            }
        },
    }

    issues = validate_configuration(config)

    # Should have no critical issues
    assert all(i.severity != "error" for i in issues)


def test_ssl_with_keystore_valid():
    """Test that SSL with keystore is valid."""
    config = {
        "server": {
            "ssl": {
                "enabled": True,
                "key-store": "/path/to/keystore.jks",
                "key-store-password": "${KEYSTORE_PASSWORD}",
            }
        }
    }

    issues = validate_configuration(config)

    # Should not have the missing keystore issue
    assert not any("key-store" in i.message.lower() and i.severity == "error" for i in issues)


def test_validation_issue_structure():
    """Test that ValidationIssue has expected structure."""
    issue = ValidationIssue(
        severity="error",
        property_path="test.property",
        message="Test message",
        suggestion="Test suggestion",
    )

    assert issue.severity == "error"
    assert issue.property_path == "test.property"
    assert issue.message == "Test message"
    assert issue.suggestion == "Test suggestion"


def test_devtools_in_production():
    """Test detection of devtools in production profile."""
    config = {
        "spring": {
            "devtools": {
                "remote": {
                    "secret": "my-secret",
                }
            },
            "profiles": {
                "active": "prod",
            },
        }
    }

    issues = validate_configuration(config)

    # Should warn about devtools in production
    assert len(issues) > 0
    assert any("devtools" in i.message.lower() for i in issues)
