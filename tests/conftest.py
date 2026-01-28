"""Pytest configuration and shared fixtures."""
import os
import sys

# Ensure app is on path when running tests from project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
