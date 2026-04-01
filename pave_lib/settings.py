"""Application settings loaded from environment variables."""

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# LLM
LLM_MODEL: str = os.getenv("LLM_MODEL", "openai/glm-4.7")
LLM_API_BASE: str = os.getenv("LLM_API_BASE", "http://localhost:8000/v1")
LLM_API_KEY: str = os.getenv("LLM_API_KEY", "")

# Oracle DB
ORACLE_DSN: str = os.getenv("ORACLE_DSN", "localhost:1521/pavedb")
ORACLE_USER: str = os.getenv("ORACLE_USER", "pave")
ORACLE_PASSWORD: str = os.getenv("ORACLE_PASSWORD", "")

# ChromaDB
CHROMA_PERSIST_DIR: str = os.getenv("CHROMA_PERSIST_DIR", "./chroma_data")

# Paths
PROJECT_ROOT: Path = Path(__file__).parent
SKILLS_DIR: Path = PROJECT_ROOT / "skills"

# Logging
LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
