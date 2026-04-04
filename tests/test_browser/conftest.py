"""Shared test configuration."""

import pytest


def pytest_configure(config):
    config.addinivalue_line("markers", "integration: marks tests that require real API keys")


def pytest_collection_modifyitems(config, items):
    if not config.getoption("-m", default=None) or "integration" not in config.getoption("-m", default=""):
        skip_integration = pytest.mark.skip(reason="Needs -m integration flag")
        for item in items:
            if "integration" in item.keywords:
                item.add_marker(skip_integration)
