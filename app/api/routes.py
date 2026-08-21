from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Literal

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from app import config
from app.identity import Principal, get_principal
from app.schemas import AnalyzeRequest, CaptureItem, IpcDraft, ProjectInfo, ValuationResult
from app.services import (
    agent_service,
    analysis_runner,
    capture,
    excel_engine,
    ipc,
    llm_client,
    workspace,
)

router = APIRouter()


class AgentChatRequest(BaseModel):
    project_id: str
    message: str
    locale: Literal["en", "zh-Hant"] = "en"
    history: list[dict[str, str]] = Field(default_factory=list)


class CaptureRequest(BaseModel):
    source: Literal["mobile", "gov_platform", "drone_batch", "drone_api"]
    item_no: str = ""
    description: str = ""
    percent_complete: float | None = None
    note: str = ""


def _project_dir(project_id: str) -> Path:
    return analysis_runner.project_dir(project_id)


def _load_project_info(project_id: str) -> ProjectInfo:
    return analysis_runner.load_project_info(project_id)


def _claim_path(project_id: str) -> Path:
    return analysis_runner.claim_path(project_id)


@router.get("/api/health")
def health() -> dict[str, Any]:
    status = llm_client.provider_status()
    return {
        "status": "ok",
        "service": "qs-ai-payment-copilot",
        "cpecs": "connected",
        "model_provider": status["provider"],
        "model_id": status["model_id"],
        "llm_configured": status["configured"],
        "data_gov_hk": config.DATA_GOV_HK_ENABLED,
    }


@router.get("/api/agent/status")
def agent_status() -> dict[str, Any]:
    return {"agent": "qs-payment-copilot", **llm_client.provider_status()}


@router.post("/api/agent/chat")
async def agent_chat(
    body: AgentChatRequest,
    principal: Principal = Depends(get_principal),  # noqa: ARG001 — enforces login (auth0 mode)
) -> dict[str, Any]:
    if not body.message.strip():
        raise HTTPException(status_code=400, detail="message required")
    _load_project_info(body.project_id)
    return await agent_service.chat_agent(
        project_id=body.project_id,
        message=body.message.strip(),
        locale=body.locale,
        history=body.history,
    )


@router.get("/api/projects")
def list_projects() -> dict[str, Any]:
    projects = []
    if config.FIXTURES_DIR.exists():
        for path in sorted(config.FIXTURES_DIR.iterdir()):
            meta = path / "project.json"
            if meta.exists():
                projects.append(json.loads(meta.read_text(encoding="utf-8")))
    return {"projects": projects}


@router.get("/api/projects/{project_id}")
def get_project(project_id: str) -> dict[str, Any]:
    info = _load_project_info(project_id)
    files = sorted(p.name for p in _project_dir(project_id).iterdir() if p.is_file())
    return {"project": info, "files": files}


@router.get("/api/projects/{project_id}/workspace")
def get_workspace(project_id: str) -> dict[str, Any]:
    info = _load_project_info(project_id)
    return workspace.build_workspace(project_id, info.model_dump())


@router.get("/api/projects/{project_id}/files/{filename}")
def download_fixture(project_id: str, filename: str) -> FileResponse:
    path = _project_dir(project_id) / filename
    if not path.exists() or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path)


@router.post("/api/projects/{project_id}/analyze", response_model=ValuationResult)
async def analyze_project(project_id: str, body: AnalyzeRequest | None = None) -> ValuationResult:
    return await analysis_runner.run_analysis(project_id, body)


@router.get("/api/projects/{project_id}/valuation.xlsx")
def download_valuation(project_id: str) -> FileResponse:
    path = config.SESSIONS_ROOT / project_id / "valuation_assessment.xlsx"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Run analyze first")
    return FileResponse(
        path,
        filename=f"{project_id}_valuation_assessment.xlsx",
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )


@router.get("/api/capture/sources")
def capture_sources() -> dict[str, Any]:
    return {"sources": capture.sources_payload()}


@router.get("/api/projects/{project_id}/captures")
def list_captures(project_id: str) -> dict[str, Any]:
    _load_project_info(project_id)
    items = capture.list_captures(project_id)
    return {"captures": [i.model_dump() for i in items]}


@router.post("/api/projects/{project_id}/captures", response_model=CaptureItem)
def add_capture(project_id: str, body: CaptureRequest) -> CaptureItem:
    _load_project_info(project_id)
    try:
        return capture.add_capture(
            project_id,
            source=body.source,
            item_no=body.item_no,
            description=body.description,
            percent_complete=body.percent_complete,
            note=body.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/projects/{project_id}/ipc", response_model=IpcDraft)
async def generate_ipc(project_id: str) -> IpcDraft:
    project = _load_project_info(project_id)
    result = analysis_runner.get_cached_analysis(project_id)
    if result is None:
        result = await analysis_runner.run_analysis(project_id, None)
    return ipc.build_ipc(project, result)


@router.post("/api/projects/{project_id}/upload-claim")
async def upload_claim(project_id: str, file: UploadFile = File(...)) -> dict[str, Any]:
    _project_dir(project_id)
    dest = config.SESSIONS_ROOT / project_id
    dest.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    target = dest / "uploaded_payment_claim.xlsx"
    target.write_bytes(content)
    session_claim = dest / "payment_claim.xlsx"
    session_claim.write_bytes(content)
    fixture_claim = _claim_path(project_id)
    backup = fixture_claim.with_suffix(".xlsx.bak")
    if fixture_claim.exists() and not backup.exists():
        backup.write_bytes(fixture_claim.read_bytes())
    fixture_claim.write_bytes(content)
    lines = excel_engine.read_lines(fixture_claim)
    return {"status": "ok", "items": len(lines), "filename": file.filename}
