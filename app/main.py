from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import config
from app.api.routes import router

for candidate in (
    Path(__file__).resolve().parent.parent.parent / ".env",
    Path("/home/tar_a/ai_engineer/.env"),
):
    if candidate.exists():
        load_dotenv(dotenv_path=candidate, override=False)

app = FastAPI(
    title="QS AI Payment Valuation Copilot",
    version="0.1.0",
    description="Hong Kong QS interim payment valuation with CPECS and DATA.GOV.HK context.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)
