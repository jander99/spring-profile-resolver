"""Tests for security scanning."""


from spring_profile_resolver.security import (
    SecurityIssue,
    scan_configuration,
    scan_for_secrets,
    scan_insecure_configurations,
)


def test_hardcoded_password_detection():
    """Test detection of hardcoded passwords."""
    config = {
        "spring": {
            "datasource": {
                "password": "SuperSecret123!",
            }
        }
    }

    issues = scan_for_secrets(config)

    # Should detect hardcoded password
    assert len(issues) > 0
    assert any("password" in i.property_path.lower() for i in issues)
    assert any(i.severity in ["high", "critical"] for i in issues)


def test_placeholder_password_ignored():
    """Test that passwords using placeholders are not flagged."""
    config = {
        "spring": {
            "datasource": {
                "password": "${DATABASE_PASSWORD}",
            }
        }
    }

    issues = scan_for_secrets(config)

    # Should not flag placeholder values
    assert len(issues) == 0


def test_aws_access_key_detection():
    """Test detection of AWS access keys."""
    config = {
        "aws": {
            "accessKey": "AKIAIOSFODNN7EXAMPLE",
        }
    }

    issues = scan_for_secrets(config)

    # Should detect AWS access key pattern
    assert len(issues) > 0
    assert any("AWS" in i.message or "access" in i.message.lower() for i in issues)
    assert any(i.severity == "critical" for i in issues)


def test_jwt_token_detection():
    """Test detection of JWT tokens."""
    config = {
        "security": {
            "jwt": {
                "token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
            }
        }
    }

    issues = scan_for_secrets(config)

    # Should detect JWT token
    assert len(issues) > 0
    assert any("JWT" in i.message or "token" in i.message.lower() for i in issues)


def test_weak_password_detection():
    """Test detection of weak default passwords."""
    config = {
        "spring": {
            "security": {
                "user": {
                    "password": "admin",
                }
            }
        }
    }

    issues = scan_insecure_configurations(config)

    # Should detect weak password
    assert len(issues) > 0
    assert any("password" in i.message.lower() for i in issues)
    assert any(i.severity == "critical" for i in issues)


def test_h2_console_enabled():
    """Test detection of H2 console enabled."""
    config = {
        "spring": {
            "h2": {
                "console": {
                    "enabled": True,
                }
            }
        }
    }

    issues = scan_insecure_configurations(config)

    # Should flag H2 console as security risk
    assert len(issues) > 0
    assert any("h2" in i.message.lower() for i in issues)
    assert any(i.severity == "high" for i in issues)


def test_debug_logging_in_production():
    """Test detection of debug logging."""
    config = {
        "logging": {
            "level": {
                "root": "DEBUG",
            }
        }
    }

    issues = scan_insecure_configurations(config)

    # Should warn about debug logging
    assert len(issues) > 0
    assert any("DEBUG" in i.message or "logging" in i.message.lower() for i in issues)


def test_security_debug_logging():
    """Test detection of security debug logging."""
    config = {
        "logging": {
            "level": {
                "org": {
                    "springframework": {
                        "security": "DEBUG",
                    }
                }
            }
        }
    }

    issues = scan_insecure_configurations(config)

    # Should warn about security debug logging
    assert len(issues) > 0
    assert any("security" in i.message.lower() and "DEBUG" in i.message for i in issues)


def test_ssl_disabled():
    """Test detection of SSL disabled."""
    config = {
        "server": {
            "ssl": {
                "enabled": False,
            }
        }
    }

    issues = scan_insecure_configurations(config)

    # Should warn about disabled SSL
    assert len(issues) > 0
    assert any("ssl" in i.message.lower() or "tls" in i.message.lower() for i in issues)


def test_show_sql_enabled():
    """Test detection of show-sql enabled."""
    config = {
        "spring": {
            "jpa": {
                "show-sql": True,
            }
        }
    }

    issues = scan_insecure_configurations(config)

    # Should warn about SQL logging
    assert len(issues) > 0
    assert any("sql" in i.message.lower() for i in issues)


def test_api_key_in_url():
    """Test detection of API keys in property names."""
    config = {
        "external": {
            "api-key": "sk-1234567890abcdef",
        }
    }

    issues = scan_for_secrets(config)

    # Should detect API key
    assert len(issues) > 0
    assert any("api" in i.property_path.lower() for i in issues)


def test_secure_configuration_minimal_issues():
    """Test that a secure configuration has minimal issues."""
    config = {
        "server": {
            "port": 8443,
            "ssl": {
                "enabled": True,
                "key-store": "${SSL_KEYSTORE_PATH}",
                "key-store-password": "${SSL_KEYSTORE_PASSWORD}",
            },
        },
        "spring": {
            "datasource": {
                "url": "${DATABASE_URL}",
                "username": "${DATABASE_USERNAME}",
                "password": "${DATABASE_PASSWORD}",
            }
        },
        "logging": {
            "level": {
                "root": "INFO",
            }
        },
    }

    issues = scan_configuration(config)

    # Should have no high/critical issues
    assert not any(i.severity in ["high", "critical"] for i in issues)


def test_security_issue_structure():
    """Test that SecurityIssue has expected structure."""
    issue = SecurityIssue(
        severity="high",
        property_path="test.property",
        issue_type="hardcoded_secret",
        message="Test message",
        recommendation="Test recommendation",
    )

    assert issue.severity == "high"
    assert issue.property_path == "test.property"
    assert issue.issue_type == "hardcoded_secret"
    assert issue.message == "Test message"
    assert issue.recommendation == "Test recommendation"


def test_database_connection_string_with_credentials():
    """Test detection of database connection strings with embedded credentials."""
    config = {
        "spring": {
            "datasource": {
                "url": "jdbc:postgresql://user:password@localhost:5432/mydb",
            }
        }
    }

    issues = scan_for_secrets(config)

    # Should detect credentials in connection string
    assert len(issues) > 0
    assert any("database" in i.message.lower() or "connection" in i.message.lower() for i in issues)


def test_empty_or_null_values_not_flagged():
    """Test that empty or null sensitive values are not flagged."""
    config = {
        "spring": {
            "datasource": {
                "password": "",
            },
            "security": {
                "user": {
                    "password": None,
                }
            },
        }
    }

    issues = scan_for_secrets(config)

    # Should not flag empty/null values
    assert len(issues) == 0


def test_boolean_sensitive_properties_not_flagged():
    """Test that boolean values in sensitive property names are not flagged."""
    config = {
        "spring": {
            "security": {
                "oauth2": {
                    "client": {
                        "registration": {
                            "google": {
                                "client-secret": True,  # Boolean, not an actual secret
                            }
                        }
                    }
                }
            }
        }
    }

    issues = scan_for_secrets(config)

    # Boolean values should not be flagged
    # (though this is weird configuration, the scanner should ignore it)
    assert len(issues) == 0


def test_devtools_enabled():
    """Test detection of devtools enabled."""
    config = {
        "spring": {
            "devtools": {
                "restart": {
                    "enabled": True,
                }
            }
        }
    }

    issues = scan_insecure_configurations(config)

    # Should warn about devtools
    assert len(issues) > 0
    assert any("devtools" in i.message.lower() for i in issues)
