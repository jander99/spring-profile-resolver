"""Pytest fixtures for Spring Profile Resolver tests."""

from pathlib import Path

import pytest


@pytest.fixture
def fixtures_dir() -> Path:
    """Return the path to the test-fixtures directory."""
    return Path(__file__).parent.parent / "test-fixtures"


@pytest.fixture
def simple_fixtures(fixtures_dir: Path) -> Path:
    """Return the path to simple test fixtures."""
    return fixtures_dir / "simple"


@pytest.fixture
def multi_document_fixtures(fixtures_dir: Path) -> Path:
    """Return the path to multi-document test fixtures."""
    return fixtures_dir / "multi-document"
