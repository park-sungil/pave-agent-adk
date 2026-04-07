"""Application settings loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# LLM
LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/glm-4.7")
LLM_MODEL_ANALYZE: str = os.getenv("LLM_MODEL_ANALYZE", "") or LLM_MODEL
LLM_MODEL_INTERPRET: str = os.getenv("LLM_MODEL_INTERPRET", "") or LLM_MODEL

# Auth method: "key" uses api_key, "header" uses extra_headers.
# Both sets of vars can coexist in .env — flip LLM_AUTH_METHOD to switch.
LLM_AUTH_METHOD: str = os.getenv("LLM_AUTH_METHOD", "key").lower()

# Method "key"
LLM_API_BASE_KEY: str = os.getenv("LLM_API_BASE_KEY", "")
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")

# Method "header"
LLM_API_BASE_HEADER: str = os.getenv("LLM_API_BASE_HEADER", "")
LLM_API_HEADER_NAME: str = os.getenv("LLM_API_HEADER_NAME", "Authorization")
LLM_API_HEADER_VALUE: str = os.getenv("LLM_API_HEADER_VALUE", "")

# Oracle DB
ORACLE_DSN: str = os.getenv("ORACLE_DSN", "localhost:1521/pavedb")
ORACLE_USER: str = os.getenv("ORACLE_USER", "pave")
ORACLE_PASSWORD: str = os.getenv("ORACLE_PASSWORD", "")

# Paths
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
SKILL_DIR: Path = Path(__file__).resolve().parent / "skills" / "pave-skill"

# Logging
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
