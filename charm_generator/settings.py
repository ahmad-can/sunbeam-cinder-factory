"""Minimal settings for the charm generator."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.resolve()
DRIVER_SPECS_DIR = PROJECT_ROOT / "driver-specs"
GENERATED_CHARMS_DIR = PROJECT_ROOT / "generated-charms"
REFERENCE_DIR = PROJECT_ROOT / "purestorage-reference"

# OpenAI API
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o")
MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", "16000"))
TEMPERATURE = float(os.getenv("OPENAI_TEMPERATURE", "0.3"))
API_TIMEOUT = int(os.getenv("OPENAI_API_TIMEOUT", "120"))
API_RETRY_ATTEMPTS = int(os.getenv("OPENAI_API_RETRY_ATTEMPTS", "3"))

# Validation
REQUIRED_CHARM_FILES = [
    "charmcraft.yaml",
    "src/charm.py",
    "pyproject.toml",
    "README.md",
    "backend/backend.py",
    "backend/__init__.py",
]

OPTIONAL_CHARM_FILES = [
    "tests/unit/test_charm.py",
    "tests/unit/__init__.py",
]


def get_settings_summary() -> dict:
    """Return settings summary for CLI info command."""
    return {
        "project_root": str(PROJECT_ROOT),
        "openai_model": OPENAI_MODEL,
        "max_tokens": MAX_TOKENS,
        "temperature": TEMPERATURE,
        "api_timeout": API_TIMEOUT,
        "api_key_configured": bool(OPENAI_API_KEY),
    }

