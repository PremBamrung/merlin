"""Pytest configuration and shared fixtures."""

import os
from pathlib import Path

from dotenv import load_dotenv
import pytest

# Tracing stays off in tests whatever .env says (telemetry tests turn it on
# against a temp dir). load_dotenv below never overrides a set variable.
os.environ["TRACES_DIR"] = ""

# Load environment variables from project root
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)


@pytest.fixture(scope="session")
def project_root_path():
    """Return the project root path."""
    return project_root
