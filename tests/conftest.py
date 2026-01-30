"""Pytest configuration and shared fixtures."""
import os
import sys

# Ensure app is on path when running tests from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Enable pytest-asyncio so async tests (e.g. test_ingest_path) run; requires pytest-asyncio in requirements
try:
    import pytest_asyncio  # noqa: F401
    pytest_plugins = ["pytest_asyncio"]
except ImportError:
    pass
