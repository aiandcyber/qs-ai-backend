"""Project workspace payload for the full QS application UI."""
from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from app import config


def _add_days(date_str: str, days: int) -> str:
    try:
        base = datetime.strptime(date_str, "%Y-%m-%d")
    except (TypeError, ValueError):
        base = datetime.now()
    return (base + timedelta(days=days)).strftime("%Y-%m-%d")


def build_workspace(project_id: str, project: dict[str, Any]) -> dict[str, Any]:
    root = config.FIXTURES_DIR / project_id
    files = sorted(p.name for p in root.iterdir() if p.is_file()) if root.exists() else []

    valuation_date = project.get("valuation_date", "2026-07-28")
    gcc_certify_days = int(project.get("gcc_certify_days", 21))
    gcc_pay_days = int(project.get("gcc_pay_days", 21))

    # Contractual (HAGCC 2013) cycle
    gcc_certify_due = _add_days(valuation_date, gcc_certify_days)
    gcc_pay_due = _add_days(gcc_certify_due, gcc_pay_days)
    # Statutory (CISOP Ordinance Cap. 652) windows
    cap652_response_due = _add_days(valuation_date, 30)
    cap652_pay_due = _add_days(valuation_date, 60)

    return {
        "project": project,
        "files": files,
        "contract_profile": {
            "contract_form": project.get("contract_form"),
            "payment_cycle": "Monthly interim valuation",
            "interim_period_days": project.get("interim_period_days", 30),
            "gcc_certify_days": gcc_certify_days,
            "gcc_pay_days": gcc_pay_days,
            "response_window_days": 30,
            "payment_window_days": 60,
            "retention_percent": project.get("retention_percent", 5.0),
            "retention_limit_hkd": project.get("retention_limit_hkd", 0.0),
            "nsc_retention_percent": project.get("nsc_retention_percent", 5.0),
            "minimum_amount_hkd": project.get("minimum_amount_hkd", 0.0),
            "materials_on_site": "Payable at contract rate with vesting / delivery evidence (Cl. 14.2)",
            "variations": "Valued by Cl. 11.3 hierarchy; only instructed variations payable",
            "fluctuation": "Per Cl. 20.2 if applicable",
            "currency": project.get("currency", "HKD"),
            "approver": "Authorised Quantity Surveyor",
            "cap652_applicable": True,
        },
        "deadlines": [
            {
                "id": "claim",
                "label": "Interim statement submitted (Contractor)",
                "due_date": valuation_date,
                "status": "completed",
                "owner": "Contractor",
            },
            {
                "id": "gcc_certify",
                "label": f"GCC: Surveyor value & certify (Cl. 14.2, {gcc_certify_days}d)",
                "due_date": gcc_certify_due,
                "status": "open",
                "owner": "Surveyor / QS",
            },
            {
                "id": "gcc_pay",
                "label": f"GCC: Employer pay certified sum ({gcc_pay_days}d after cert)",
                "due_date": gcc_pay_due,
                "status": "upcoming",
                "owner": "Employer (HA)",
            },
            {
                "id": "cap652_response",
                "label": "Cap. 652: Payment response (max 30d)",
                "due_date": cap652_response_due,
                "status": "open",
                "owner": "Employer / QS",
            },
            {
                "id": "cap652_pay",
                "label": "Cap. 652: Payment (max 60d)",
                "due_date": cap652_pay_due,
                "status": "upcoming",
                "owner": "Employer (HA)",
            },
        ],
        "evidence": [
            {
                "id": "EV-01",
                "name": "payment_claim.xlsx",
                "type": "Claim workbook",
                "status": "linked",
                "linked_items": ["All"],
            },
            {
                "id": "EV-02",
                "name": "previous_certificate.xlsx",
                "type": "Previous certificate",
                "status": "linked",
                "linked_items": ["All"],
            },
            {
                "id": "EV-03",
                "name": "variation_register.xlsx",
                "type": "Variation register",
                "status": "linked",
                "linked_items": ["V.01", "V.02"],
            },
            {
                "id": "EV-04",
                "name": "contract_extract.txt",
                "type": "Contract extract",
                "status": "linked",
                "linked_items": ["Rules"],
            },
            {
                "id": "EV-05",
                "name": "cpecs_response.json",
                "type": "CPECS pack result",
                "status": "linked",
                "linked_items": ["MOS.1", "V.02", "A.3.1"],
            },
            {
                "id": "EV-06",
                "name": "Delivery note DN-9921",
                "type": "Delivery note",
                "status": "missing",
                "linked_items": ["MOS.1"],
            },
            {
                "id": "EV-07",
                "name": "VO-18 instruction",
                "type": "Variation instruction",
                "status": "missing",
                "linked_items": ["V.02"],
            },
        ],
        "contract_intelligence": [
            {
                "topic": "Payment claim requirements",
                "clause_ref": "Cap. 652 / Contract payment provisions",
                "summary": "Claim must be in writing, identify the work, state amount and calculation method.",
            },
            {
                "topic": "Payment response window",
                "clause_ref": "Contract / Cap. 652",
                "summary": "Respond within contractual period or 30 days, whichever is earlier.",
            },
            {
                "topic": "Materials on site",
                "clause_ref": "Contract extract §2.3",
                "summary": "Payable only with ownership, delivery and protection evidence.",
            },
            {
                "topic": "Variations",
                "clause_ref": "Contract extract §2.2",
                "summary": "Only written instructed variations are included in interim valuation.",
            },
            {
                "topic": "Retention",
                "clause_ref": "Contract extract §3.1",
                "summary": "5% retention applies to cumulative assessed value subject to contract limit.",
            },
        ],
        "automated_checks": [
            "Arithmetic and formula validation",
            "Quantity overrun against contract BQ",
            "Duplicate / repeated claim detection",
            "Variation without instruction",
            "Materials-on-site evidence completeness",
            "Retention calculation",
            "Previous certificate reconciliation",
            "CPECS anomaly cross-check",
            "SOP deadline monitoring",
            "Benchmark reasonableness context",
        ],
        "outputs": [
            {"id": "valuation_xlsx", "label": "Valuation assessment Excel", "available_after": "analysis"},
            {"id": "payment_response", "label": "Draft payment response", "available_after": "analysis"},
            {"id": "exception_report", "label": "Exception / risk report", "available_after": "analysis"},
            {"id": "evidence_index", "label": "Evidence index", "available_after": "always"},
            {"id": "deadline_board", "label": "Deadline board", "available_after": "always"},
        ],
        "audit_trail": [
            {
                "time": f"{valuation_date} 09:12",
                "actor": "system",
                "action": "Project workspace loaded",
            },
            {
                "time": f"{valuation_date} 09:18",
                "actor": "contractor",
                "action": "Payment claim workbook submitted",
            },
            {
                "time": f"{valuation_date} 09:21",
                "actor": "cpecs",
                "action": "Document pack checked",
            },
            {
                "time": f"{valuation_date} 09:25",
                "actor": "qs.user",
                "action": "Awaiting valuation analysis",
            },
        ],
    }
