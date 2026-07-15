"""Pytest configuration and shared fixtures."""

from pathlib import Path

from dotenv import load_dotenv
import pytest

# Load environment variables from project root
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)


@pytest.fixture(scope="session")
def project_root_path():
    """Return the project root path."""
    return project_root
