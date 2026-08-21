"""Deterministic valuation rules + Payment Confidence scoring."""
from __future__ import annotations

from typing import Any

from app.schemas import (
    BenchmarkContext,
    CpecsResult,
    LineItem,
    RiskBand,
    RiskCard,
    ValuationSummary,
)


def _band_from_score(score: float) -> RiskBand:
    if score >= 0.66:
        return "red"
    if score >= 0.33:
        return "amber"
    return "green"


def assess_lines(
    raw_lines: list[dict[str, Any]],
    cpecs: CpecsResult,
    retention_percent: float = 5.0,
    retention_limit: float = 0.0,
) -> tuple[list[LineItem], ValuationSummary, RiskCard]:
    cpecs_by_item = {
        f.related_item: f for f in cpecs.findings if f.related_item
    }
    lines: list[LineItem] = []
    risk_scores: list[float] = []
    drivers: list[str] = []
    ask: list[str] = []

    for raw in raw_lines:
        issues: list[str] = []
        evidence: list[str] = []
        score = 0.0

        contract_qty = float(raw["contract_qty"])
        rate = float(raw["rate"])
        previous_qty = float(raw["previous_qty"])
        claimed_qty = float(raw["claimed_qty"])
        claimed_amount = float(raw["claimed_amount"])
        expected_claim_amount = round(claimed_qty * rate, 2)

        # Default assessment: accept claim unless rule fails.
        assessed_qty = claimed_qty
        assessed_amount = expected_claim_amount

        if claimed_qty + previous_qty > contract_qty + 1e-6 and raw.get("category") != "variation":
            issues.append("Cumulative claimed quantity exceeds contract quantity.")
            assessed_qty = max(contract_qty - previous_qty, 0)
            assessed_amount = round(assessed_qty * rate, 2)
            score += 0.45
            drivers.append(f"{raw['item_no']}: quantity overrun")
            ask.append(f"Provide measurement backup for {raw['item_no']} overrun.")

        if abs(claimed_amount - expected_claim_amount) > 0.5:
            issues.append(
                f"Arithmetic mismatch: claimed {claimed_amount:.2f} vs qty×rate {expected_claim_amount:.2f}."
            )
            score += 0.25
            drivers.append(f"{raw['item_no']}: arithmetic error")

        if raw.get("category") == "variation" and "VO-" not in str(raw.get("description", "")).upper() and "VARIATION" not in str(raw.get("description", "")).upper():
            # still allow if item_no starts with V
            if not str(raw["item_no"]).upper().startswith("V"):
                issues.append("Variation-like claim lacks variation reference.")
                score += 0.2

        if raw.get("category") == "materials_on_site":
            issues.append("Materials on site require delivery notes / vesting evidence.")
            evidence.append("Await delivery note / vesting certificate")
            score += 0.2
            ask.append(f"Submit delivery notes for materials-on-site item {raw['item_no']}.")

        finding = cpecs_by_item.get(raw["item_no"])
        if finding:
            issues.append(f"CPECS: {finding.message}")
            if finding.severity == "red":
                score += 0.7
            elif finding.severity == "amber":
                score += 0.25
            drivers.append(f"CPECS {finding.code} on {raw['item_no']}")
            # Conservative: hold disputed portion
            if finding.severity == "red":
                assessed_qty = 0
                assessed_amount = 0

        if claimed_qty < 0 or claimed_amount < 0:
            issues.append("Negative claim values are invalid.")
            assessed_qty = 0
            assessed_amount = 0
            score += 0.5

        band = _band_from_score(score)
        if not issues:
            evidence.append("Consistent with previous certificate and contract rate")

        risk_scores.append(score)
        lines.append(
            LineItem(
                item_no=raw["item_no"],
                description=raw["description"],
                unit=raw["unit"],
                contract_qty=contract_qty,
                rate=rate,
                contract_amount=float(raw["contract_amount"]),
                previous_qty=previous_qty,
                previous_amount=float(raw["previous_amount"]),
                claimed_qty=claimed_qty,
                claimed_amount=claimed_amount,
                assessed_qty=assessed_qty,
                assessed_amount=assessed_amount,
                difference_amount=round(claimed_amount - assessed_amount, 2),
                risk=band,
                issues=issues,
                evidence=evidence,
                confidence=max(0.0, 1.0 - score),
                category=str(raw.get("category") or "works"),
            )
        )

    contract_sum = round(sum(l.contract_amount for l in lines), 2)
    previous_certified = round(sum(l.previous_amount for l in lines), 2)
    claimed_this_period = round(sum(l.claimed_amount for l in lines), 2)
    assessed_this_period = round(sum(l.assessed_amount for l in lines), 2)
    cumulative_assessed = round(previous_certified + assessed_this_period, 2)
    retention = round(cumulative_assessed * (retention_percent / 100.0), 2)
    retention_this_period = round(assessed_this_period * (retention_percent / 100.0), 2)
    # Cap cumulative retention at the contract retention limit (HAGCC Cl. 14.2(1)(i)).
    if retention_limit and retention > retention_limit:
        prev_retention = round(previous_certified * (retention_percent / 100.0), 2)
        retention = retention_limit
        retention_this_period = max(round(retention_limit - prev_retention, 2), 0.0)
        drivers.append(f"Retention capped at contract limit {retention_limit:,.0f}")
    amount_due = round(assessed_this_period - retention_this_period, 2)

    green = sum(1 for l in lines if l.risk == "green")
    amber = sum(1 for l in lines if l.risk == "amber")
    red = sum(1 for l in lines if l.risk == "red")

    avg_score = sum(risk_scores) / max(len(risk_scores), 1)
    # CPECS global findings lift package risk
    if any(f.severity == "red" for f in cpecs.findings):
        avg_score = max(avg_score, 0.7)
        drivers.append("Package contains CPECS red findings")
    band = _band_from_score(avg_score)

    if not drivers:
        drivers = ["No material anomalies detected in deterministic checks"]
    if not ask:
        ask = ["Confirm programme progress aligns with claimed percentages"]

    action = {
        "green": "Proceed to QS certification with light sampling.",
        "amber": "QS review required on amber/red lines before certification.",
        "red": "Hold disputed amounts; issue pay-less / payment response with reasons.",
    }[band]

    card = RiskCard(
        band=band,
        title={
            "green": "Low payment risk",
            "amber": "Moderate payment risk — review exceptions",
            "red": "High payment risk — evidence / CPECS issues",
        }[band],
        drivers=drivers[:5],
        recommended_action=action,
        ask_contractor=ask[:5],
        score=round(avg_score, 3),
    )

    summary = ValuationSummary(
        contract_sum=contract_sum,
        previous_certified=previous_certified,
        claimed_this_period=claimed_this_period,
        assessed_this_period=assessed_this_period,
        cumulative_assessed=cumulative_assessed,
        retention=retention,
        amount_due=amount_due,
        green_count=green,
        amber_count=amber,
        red_count=red,
    )
    return lines, summary, card


def apply_benchmark_context(card: RiskCard, benchmarks: list[BenchmarkContext]) -> RiskCard:
    live = [b for b in benchmarks if b.live]
    if live:
        card.drivers = list(card.drivers) + [
            f"HK open data context available: {live[0].label}"
        ]
    return card
