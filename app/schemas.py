from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


RiskBand = Literal["green", "amber", "red"]


class ProjectInfo(BaseModel):
    id: str
    name: str
    contract_form: str
    employer: str
    contractor: str
    valuation_date: str
    currency: str = "HKD"
    retention_percent: float = 5.0
    # Contract particulars (HAGCC Building Works 2013 v1.1) — configurable per contract.
    retention_limit_hkd: float = 0.0
    nsc_retention_percent: float = 5.0
    interim_period_days: int = 30
    minimum_amount_hkd: float = 0.0
    gcc_certify_days: int = 21
    gcc_pay_days: int = 21
    notes: str = ""


CaptureSource = Literal["mobile", "gov_platform", "drone_batch", "drone_api"]


class CaptureItem(BaseModel):
    id: str
    source: CaptureSource
    item_no: str = ""
    description: str = ""
    media_ref: str = ""
    percent_complete: Optional[float] = None
    note: str = ""
    captured_at: str = ""
    status: str = "captured"


class IpcDraft(BaseModel):
    project_id: str
    certificate_no: str
    ipc_text: str
    amount_due: float = 0.0
    generated_at: str = ""


class LineItem(BaseModel):
    item_no: str
    description: str
    unit: str
    contract_qty: float
    rate: float
    contract_amount: float
    previous_qty: float = 0.0
    previous_amount: float = 0.0
    claimed_qty: float = 0.0
    claimed_amount: float = 0.0
    assessed_qty: float = 0.0
    assessed_amount: float = 0.0
    difference_amount: float = 0.0
    risk: RiskBand = "green"
    issues: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = 1.0
    category: str = "works"


class BenchmarkContext(BaseModel):
    source: str
    label: str
    value: Optional[float] = None
    period: Optional[str] = None
    note: str = ""
    live: bool = False


class CpecsFinding(BaseModel):
    code: str
    severity: RiskBand
    message: str
    related_item: Optional[str] = None
    extracted_amount: Optional[float] = None


class CpecsResult(BaseModel):
    mode: str
    findings: list[CpecsFinding] = Field(default_factory=list)
    extracted_documents: list[dict[str, Any]] = Field(default_factory=list)
    summary: str = ""


class RiskCard(BaseModel):
    band: RiskBand
    title: str
    drivers: list[str]
    recommended_action: str
    ask_contractor: list[str]
    score: float


class ValuationSummary(BaseModel):
    contract_sum: float
    previous_certified: float
    claimed_this_period: float
    assessed_this_period: float
    cumulative_assessed: float
    retention: float
    amount_due: float
    green_count: int
    amber_count: int
    red_count: int


class ValuationResult(BaseModel):
    project: ProjectInfo
    lines: list[LineItem]
    summary: ValuationSummary
    cpecs: CpecsResult
    benchmarks: list[BenchmarkContext]
    risk_card: RiskCard
    llm_explanation: str
    draft_payment_response: str
    warnings: list[str] = Field(default_factory=list)


class AnalyzeRequest(BaseModel):
    project_id: str = "HKHA-PRJ-2026-0147"
    use_llm: bool = True
    locale: Literal["en", "zh-Hant"] = "en"
