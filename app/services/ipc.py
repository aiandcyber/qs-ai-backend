"""Draft Interim Payment Certificate (IPC) generator.

Builds a review-ready draft IPC from the latest cached valuation, with links to
capture evidence. The authorised QS reviews, edits and certifies — the draft is
never a certification. Amounts come from the deterministic valuation engine.
"""
from __future__ import annotations

from datetime import datetime

from app.schemas import IpcDraft, ProjectInfo, ValuationResult
from app.services import capture


def build_ipc(project: ProjectInfo, result: ValuationResult) -> IpcDraft:
    s = result.summary
    cur = project.currency
    cert_no = f"IPC-{project.id}-{s.green_count + s.amber_count + s.red_count:02d}"
    captures = capture.list_captures(project.id)
    ev_line = (
        f"{len(captures)} capture record(s) linked"
        if captures
        else "No capture evidence linked yet"
    )

    def m(n: float) -> str:
        return f"{cur} {n:,.2f}"

    lines = [
        "INTERIM PAYMENT CERTIFICATE (DRAFT — for QS review and certification)",
        "AI advises; the authorised Quantity Surveyor decides and certifies.",
        "",
        f"Certificate No.:      {cert_no}",
        f"Project:              {project.name}",
        f"Employer:             {project.employer}",
        f"Contractor:           {project.contractor}",
        f"Contract form:        {project.contract_form}",
        f"Valuation date:       {project.valuation_date}",
        "",
        "VALUATION (this interim period)",
        f"  Contract sum:              {m(s.contract_sum)}",
        f"  Previously certified:      {m(s.previous_certified)}",
        f"  Claimed this period:       {m(s.claimed_this_period)}",
        f"  Assessed this period:      {m(s.assessed_this_period)}",
        f"  Cumulative assessed:       {m(s.cumulative_assessed)}",
        f"  Less retention:            {m(s.retention)}",
        f"  ------------------------------------------",
        f"  NET AMOUNT DUE:            {m(s.amount_due)}",
        "",
        f"Payment confidence:   {result.risk_card.band.upper()} — {result.risk_card.title}",
        f"Recommended action:   {result.risk_card.recommended_action}",
        f"Capture evidence:     {ev_line}",
        "",
        "Statutory / contractual note:",
        "  Certify within 21 days and pay within 21 days (HAGCC Building Works 2013),",
        "  subject also to the CISOP Ordinance (Cap. 652) payment response/payment windows.",
        "",
        "Prepared by (AI draft):  QS AI Payment Valuation Copilot",
        "Certified by:            ____________________  (Authorised Quantity Surveyor)",
    ]
    return IpcDraft(
        project_id=project.id,
        certificate_no=cert_no,
        ipc_text="\n".join(lines),
        amount_due=s.amount_due,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )
