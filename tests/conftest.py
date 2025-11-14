"""Pytest configuration and shared fixtures."""

import os
from pathlib import Path

import pytest
from dotenv import load_dotenv

# Load environment variables from project root
project_root = Path(__file__).parent.parent
env_path = project_root / ".env"
load_dotenv(env_path)


@pytest.fixture(scope="session")
def project_root_path():
    """Return the project root path."""
    return project_root


@pytest.fixture(scope="session")
def azure_openai_env_vars():
    """Check and return Azure OpenAI environment variables."""
    required_vars = {
        "AZURE_OPENAI_ENDPOINT": os.getenv("AZURE_OPENAI_ENDPOINT"),
        "AZURE_OPENAI_KEY": os.getenv("AZURE_OPENAI_KEY"),
        "AZURE_OPENAI_API_VERSION": os.getenv("AZURE_OPENAI_API_VERSION"),
        "AZURE_MODEL_DEPLOYMENT": os.getenv("AZURE_MODEL_DEPLOYMENT"),
    }
    return required_vars


@pytest.fixture(scope="session")
def azure_openai_configured(azure_openai_env_vars):
    """Check if Azure OpenAI is properly configured."""
    missing_vars = [var for var, value in azure_openai_env_vars.items() if not value]
    if missing_vars:
        pytest.skip(f"Azure OpenAI not configured. Missing: {', '.join(missing_vars)}")
    return azure_openai_env_vars
