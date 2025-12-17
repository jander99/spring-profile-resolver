"""Tests for configuration linting."""


from spring_profile_resolver.linting import (
    LintIssue,
    check_duplicate_keys,
    check_empty_values,
    check_naming_conventions,
    check_nesting_depth,
    check_redundant_properties,
    lint_configuration,
)


def test_kebab_case_valid():
    """Test that kebab-case property names are valid."""
    config = {
        "server": {
            "port": 8080,
            "servlet-path": "/api",
        }
    }

    issues = check_naming_conventions(config)

    # Kebab-case should be accepted
    assert len(issues) == 0


def test_camel_case_valid():
    """Test that camelCase property names are valid."""
    config = {
        "myApp": {
            "serverPort": 8080,
        }
    }

    issues = check_naming_conventions(config)

    # CamelCase should be accepted (though less common)
    assert len(issues) == 0


def test_snake_case_info():
    """Test that snake_case generates info message."""
    config = {
        "my_app": {
            "server_port": 8080,
        }
    }

    issues = check_naming_conventions(config)

    # Should suggest kebab-case
    assert len(issues) > 0
    assert any(i.severity == "info" for i in issues)
    assert any("kebab-case" in (i.suggestion or "").lower() for i in issues)


def test_invalid_naming_convention():
    """Test detection of invalid naming conventions."""
    config = {
        "My-App": {  # Mixed case with dash - invalid
            "ServerPort": 8080,
        }
    }

    issues = check_naming_conventions(config)

    # Should warn about invalid naming
    assert len(issues) > 0


def test_empty_string_values():
    """Test detection of empty string values."""
    config = {
        "server": {
            "name": "",
        }
    }

    issues = check_empty_values(config)

    # Should flag empty string
    assert len(issues) > 0
    assert any("empty" in i.message.lower() for i in issues)


def test_null_values():
    """Test detection of explicit null values."""
    config = {
        "server": {
            "description": None,
        }
    }

    issues = check_empty_values(config)

    # Should flag null value as info
    assert len(issues) > 0
    assert any("null" in i.message.lower() for i in issues)
    assert any(i.severity == "info" for i in issues)


def test_excessive_nesting():
    """Test detection of excessive nesting depth."""
    # Create deeply nested config
    config: dict = {"level1": {}}
    current = config["level1"]
    for i in range(2, 15):  # Create 14 levels deep
        current[f"level{i}"] = {}
        current = current[f"level{i}"]
    current["value"] = "deep"

    issues = check_nesting_depth(config, max_depth=10)

    # Should warn about excessive nesting
    assert len(issues) > 0
    assert any("nesting" in i.message.lower() for i in issues)


def test_reasonable_nesting():
    """Test that reasonable nesting is accepted."""
    config = {
        "spring": {
            "datasource": {
                "hikari": {
                    "connection-timeout": 30000,
                }
            }
        }
    }

    issues = check_nesting_depth(config, max_depth=10)

    # Should be fine
    assert len(issues) == 0


def test_duplicate_keys_case_insensitive():
    """Test detection of duplicate keys differing only in case."""
    config = {
        "server": {
            "Port": 8080,
        },
        "SERVER": {
            "port": 8081,
        },
    }

    issues = check_duplicate_keys(config)

    # Should detect case-insensitive duplicates
    assert len(issues) > 0
    assert any("case" in i.message.lower() for i in issues)


def test_no_duplicate_keys():
    """Test that distinct keys are not flagged."""
    config = {
        "server": {
            "port": 8080,
        },
        "client": {
            "port": 9090,
        },
    }

    issues = check_duplicate_keys(config)

    # These are different paths, not duplicates
    assert len(issues) == 0


def test_redundant_enabled_disabled_flags():
    """Test detection of both .enabled and .disabled flags."""
    config = {
        "feature": {
            "enabled": True,
            "disabled": False,
        }
    }

    issues = check_redundant_properties(config)

    # Should warn about redundancy
    assert len(issues) > 0
    assert any("enabled" in i.message.lower() and "disabled" in i.message.lower() for i in issues)


def test_no_redundant_flags():
    """Test that single flags are not flagged."""
    config = {
        "feature": {
            "enabled": True,
        },
        "other-feature": {
            "disabled": True,
        },
    }

    issues = check_redundant_properties(config)

    # Should be fine
    assert len(issues) == 0


def test_lint_configuration_comprehensive():
    """Test comprehensive linting with multiple issues."""
    config = {
        "my_app": {  # snake_case
            "serverPort": "",  # empty value
            "enabled": True,
            "disabled": False,  # redundant
        }
    }

    issues = lint_configuration(config)

    # Should find multiple issues
    assert len(issues) >= 3
    # Should have snake_case issue, empty value issue, and redundant flags issue


def test_strict_linting_upgrades_warnings():
    """Test that strict mode upgrades certain warnings to errors."""
    config = {
        "My-Invalid": {  # Invalid naming
            "value": 123,
        }
    }

    normal_issues = lint_configuration(config, strict=False)
    strict_issues = lint_configuration(config, strict=True)

    # Strict mode should have more errors
    normal_errors = [i for i in normal_issues if i.severity == "error"]
    strict_errors = [i for i in strict_issues if i.severity == "error"]

    assert len(strict_errors) >= len(normal_errors)


def test_lint_issue_structure():
    """Test that LintIssue has expected structure."""
    issue = LintIssue(
        severity="warning",
        property_path="test.property",
        issue_type="naming_convention",
        message="Test message",
        suggestion="Test suggestion",
    )

    assert issue.severity == "warning"
    assert issue.property_path == "test.property"
    assert issue.issue_type == "naming_convention"
    assert issue.message == "Test message"
    assert issue.suggestion == "Test suggestion"


def test_spring_boot_standard_properties_accepted():
    """Test that standard Spring Boot properties are accepted."""
    config = {
        "spring": {
            "datasource": {
                "url": "jdbc:postgresql://localhost/db",
            }
        },
        "server": {
            "port": 8080,
        },
        "logging": {
            "level": {
                "root": "INFO",
            }
        },
        "management": {
            "endpoints": {
                "web": {
                    "exposure": {
                        "include": "health,info",
                    }
                }
            }
        },
    }

    issues = lint_configuration(config)

    # Standard Spring Boot config should have no errors
    assert all(i.severity != "error" for i in issues)


def test_nested_empty_values():
    """Test detection of empty values in nested structures."""
    config = {
        "app": {
            "features": {
                "feature1": {
                    "name": "",
                    "description": None,
                }
            }
        }
    }

    issues = check_empty_values(config)

    # Should find both empty string and null
    assert len(issues) >= 2


def test_numeric_keys_ignored():
    """Test that numeric keys are not subject to naming convention checks."""
    config = {
        "items": {
            "0": "first",
            "1": "second",
        }
    }

    issues = check_naming_conventions(config)

    # Numeric keys should be ignored
    assert len(issues) == 0


def test_no_issues_for_clean_config():
    """Test that a clean configuration produces no issues."""
    config = {
        "server": {
            "port": 8080,
            "servlet": {
                "context-path": "/api",
            }
        },
        "spring": {
            "application": {
                "name": "my-app",
            }
        },
    }

    issues = lint_configuration(config)

    # Should be clean
    assert len(issues) == 0
