"""Shared valuation runner used by API routes and the QS agent."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import HTTPException

from app import config
from app.schemas import AnalyzeRequest, ProjectInfo, ValuationResult
from app.services import cpecs, excel_engine, hk_data, llm, valuation

# In-memory cache of last analysis per project (agent + UI reuse)
_ANALYSIS_CACHE: dict[str, ValuationResult] = {}


def project_dir(project_id: str) -> Path:
    path = config.FIXTURES_DIR / project_id
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Unknown project {project_id}")
    return path


def load_project_info(project_id: str) -> ProjectInfo:
    meta_path = project_dir(project_id) / "project.json"
    raw = json.loads(meta_path.read_text(encoding="utf-8"))
    return ProjectInfo(**raw)


def claim_path(project_id: str) -> Path:
    return project_dir(project_id) / "payment_claim.xlsx"


def get_cached_analysis(project_id: str) -> ValuationResult | None:
    return _ANALYSIS_CACHE.get(project_id)


async def run_analysis(
    project_id: str,
    body: AnalyzeRequest | None = None,
) -> ValuationResult:
    body = body or AnalyzeRequest(project_id=project_id)
    project = load_project_info(project_id)
    claim = claim_path(project_id)
    if not claim.exists():
        raise HTTPException(status_code=404, detail="payment_claim.xlsx missing")

    raw_lines = excel_engine.read_lines(claim)
    cpecs_result = await cpecs.check_payment_pack(project_id)
    benchmarks = await hk_data.fetch_benchmarks()
    lines, summary, card = valuation.assess_lines(
        raw_lines,
        cpecs_result,
        retention_percent=project.retention_percent,
        retention_limit=project.retention_limit_hkd,
    )
    card = valuation.apply_benchmark_context(card, benchmarks)

    explanation, draft = await llm.explain_valuation(
        project_name=project.name,
        locale=body.locale,
        lines=lines,
        summary=summary,
        card=card,
        cpecs_summary=cpecs_result.summary,
        benchmarks=[b.model_dump() for b in benchmarks],
        use_llm=body.use_llm,
    )

    out_path = config.SESSIONS_ROOT / project_id / "valuation_assessment.xlsx"
    excel_engine.write_valuation(
        out_path,
        [line.model_dump() for line in lines],
        summary.model_dump(),
    )

    warnings: list[str] = []
    if body.use_llm and not config.llm_configured():
        warnings.append("Language model is temporarily unavailable; rule-based explanation is shown.")

    result = ValuationResult(
        project=project,
        lines=lines,
        summary=summary,
        cpecs=cpecs_result,
        benchmarks=benchmarks,
        risk_card=card,
        llm_explanation=explanation,
        draft_payment_response=draft,
        warnings=warnings,
    )
    _ANALYSIS_CACHE[project_id] = result
    return result


def analysis_brief(result: ValuationResult) -> dict[str, Any]:
    return {
        "risk_band": result.risk_card.band,
        "risk_title": result.risk_card.title,
        "claimed": result.summary.claimed_this_period,
        "assessed": result.summary.assessed_this_period,
        "amount_due": result.summary.amount_due,
        "retention": result.summary.retention,
        "green": result.summary.green_count,
        "amber": result.summary.amber_count,
        "red": result.summary.red_count,
        "drivers": result.risk_card.drivers[:5],
        "ask_contractor": result.risk_card.ask_contractor[:5],
    }
