"""CPECS adapter: local CPECS payload now; remote endpoint when configured."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx

from app import config
from app.schemas import CpecsFinding, CpecsResult


def _payload_path(project_id: str) -> Path:
    return config.FIXTURES_DIR / project_id / "cpecs_response.json"


def load_local(project_id: str) -> CpecsResult:
    path = _payload_path(project_id)
    # Backward-compatible filename during transition
    if not path.exists():
        alt = config.FIXTURES_DIR / project_id / "cpecs_mock_response.json"
        path = alt if alt.exists() else path
    if not path.exists():
        return CpecsResult(
            mode="cpecs",
            summary="No CPECS findings available for this payment pack.",
            findings=[],
        )
    raw = json.loads(path.read_text(encoding="utf-8"))
    findings = [CpecsFinding(**f) for f in raw.get("findings", [])]
    return CpecsResult(
        mode="cpecs",
        findings=findings,
        extracted_documents=raw.get("extracted_documents", []),
        summary=raw.get("summary", "CPECS payment check completed."),
    )


async def check_payment_pack(project_id: str, payload: dict[str, Any] | None = None) -> CpecsResult:
    """Return CPECS findings from live endpoint or local project payload."""
    if config.CPECS_MODE == "live" and config.CPECS_BASE_URL:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{config.CPECS_BASE_URL}/v1/payment-check",
                json={"project_id": project_id, **(payload or {})},
            )
            response.raise_for_status()
            raw = response.json()
            findings = [CpecsFinding(**f) for f in raw.get("findings", [])]
            return CpecsResult(
                mode="cpecs",
                findings=findings,
                extracted_documents=raw.get("extracted_documents", []),
                summary=raw.get("summary", "CPECS payment check completed."),
            )
    return load_local(project_id)
