"""Application settings loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# LLM
LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/glm-4.7")
LLM_MODEL_ANALYZE: str = os.getenv("LLM_MODEL_ANALYZE", "") or LLM_MODEL
LLM_MODEL_INTERPRET: str = os.getenv("LLM_MODEL_INTERPRET", "") or LLM_MODEL

# Auth: "key" or "header" — flip to switch
LLM_AUTH: str = os.getenv("LLM_AUTH", "key").lower()

# Method "key"
LLM_API_BASE_KEY: str = os.getenv("LLM_API_BASE_KEY", "")
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")

# Method "header" (vLLM)
LLM_API_BASE_HEADER: str = os.getenv("LLM_API_BASE_HEADER", "")
VLLM_DEP_TICKET: str = os.getenv("VLLM_DEP_TICKET", "")
VLLM_SEND_SYSTEM_NAME: str = os.getenv("VLLM_SEND_SYSTEM_NAME", "")
VLLM_USER_ID: str = os.getenv("VLLM_USER_ID", "")
VLLM_USER_TYPE: str = os.getenv("VLLM_USER_TYPE", "")

# Oracle DB
ORACLE_DSN: str = os.getenv("ORACLE_DSN", "localhost:1521/pavedb")
ORACLE_USER: str = os.getenv("ORACLE_USER", "pave")
ORACLE_PASSWORD: str = os.getenv("ORACLE_PASSWORD", "")

# Paths
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
SKILL_DIR: Path = Path(__file__).resolve().parent / "skills" / "pave-skill"

# Logging
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
