"""Central configuration for QS Payment Valuation Copilot."""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = ROOT.parent
FIXTURES_DIR = Path(os.getenv("FIXTURES_DIR", str(ROOT / "fixtures")))

# Load qs-ai/.env first, then fall back to ai_engineer/.env for shared keys.
for candidate in (REPO_ROOT / ".env", Path("/home/tar_a/ai_engineer/.env")):
    if candidate.exists():
        load_dotenv(dotenv_path=candidate, override=False)

# Providers: openai | anthropic | openai_compatible (vLLM / Ollama / Azure-style / local gateway)
MODEL_PROVIDER = os.getenv("MODEL_PROVIDER", "openai").lower()
MODEL_BASE_URL = os.getenv("MODEL_BASE_URL", "").rstrip("/")
MODEL_API_KEY = os.getenv("MODEL_API_KEY", "")
MODEL_ID = os.getenv("MODEL_ID", "")
MODEL_MAX_TOKENS = int(os.getenv("MODEL_MAX_TOKENS", "4096"))

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "") or MODEL_API_KEY
ANTHROPIC_MODEL_ID = os.getenv("ANTHROPIC_MODEL_ID", "") or MODEL_ID or "claude-sonnet-4-6"
ANTHROPIC_MAX_TOKENS = int(os.getenv("ANTHROPIC_MAX_TOKENS", str(MODEL_MAX_TOKENS)))

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "") or MODEL_API_KEY
OPENAI_MODEL_ID = os.getenv("OPENAI_MODEL_ID", "") or MODEL_ID or "gpt-4o"
OPENAI_MAX_TOKENS = int(os.getenv("OPENAI_MAX_TOKENS", str(MODEL_MAX_TOKENS)))
# Only use a custom base URL for OpenAI-compatible / explicit OPENAI_BASE_URL.
# Do not inherit MODEL_BASE_URL when provider is plain "openai" (avoids leftover vLLM/Ollama lines).
_raw_openai_base = os.getenv("OPENAI_BASE_URL", "").rstrip("/")
if _raw_openai_base:
    OPENAI_BASE_URL = _raw_openai_base
elif MODEL_PROVIDER == "openai_compatible":
    OPENAI_BASE_URL = MODEL_BASE_URL
else:
    OPENAI_BASE_URL = ""

CPECS_MODE = os.getenv("CPECS_MODE", "mock").lower()
CPECS_BASE_URL = os.getenv("CPECS_BASE_URL", "").rstrip("/")
DATA_GOV_HK_ENABLED = os.getenv("DATA_GOV_HK_ENABLED", "true").lower() == "true"

AUTH_MODE = os.getenv("AUTH_MODE", "dev").lower()
AUTH0_DOMAIN = os.getenv("AUTH0_DOMAIN", "")
AUTH0_AUDIENCE = os.getenv("AUTH0_AUDIENCE", "")
DEV_OWNER_ID = os.getenv("DEV_OWNER_ID", "local-dev")

STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "local").lower()
S3_BUCKET = os.getenv("S3_BUCKET", "")
S3_PREFIX = os.getenv("S3_PREFIX", "qs-ai/")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

SESSIONS_ROOT = Path(
    os.getenv("SESSIONS_ROOT", str(ROOT / ".sessions"))
)
SESSIONS_ROOT.mkdir(parents=True, exist_ok=True)


def _csv_list(raw: str) -> list[str]:
    return [part.strip() for part in raw.split(",") if part.strip()]


CORS_ORIGINS = _csv_list(
    os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,https://qs.ai-forall.org",
    )
)

DEFAULT_PROJECT_ID = "HKHA-PRJ-2026-0147"


def resolved_model_id() -> str:
    if MODEL_PROVIDER == "anthropic":
        return ANTHROPIC_MODEL_ID
    return OPENAI_MODEL_ID


def llm_configured() -> bool:
    if MODEL_PROVIDER == "anthropic":
        return bool(ANTHROPIC_API_KEY)
    if MODEL_PROVIDER in {"openai", "openai_compatible"}:
        # Local gateways may not need a real key if base URL is set
        if MODEL_PROVIDER == "openai_compatible" and OPENAI_BASE_URL:
            return True
        return bool(OPENAI_API_KEY)
    return False
