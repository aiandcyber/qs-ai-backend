"""LLM explanations for valuation / payment response drafts (OpenAI primary)."""
from __future__ import annotations

import logging
from typing import Any

from app import config
from app.schemas import LineItem, RiskCard, ValuationSummary

logger = logging.getLogger(__name__)


def _fallback(locale: str, summary: ValuationSummary, card: RiskCard) -> tuple[str, str]:
    if locale == "zh-Hant":
        explanation = (
            f"已完成付款估值核對。風險等級為 {card.band.upper()}。"
            f"本期申索 {summary.claimed_this_period:,.0f} 港元，建議評核 {summary.assessed_this_period:,.0f} 港元。"
            f"主要原因：{'；'.join(card.drivers[:3])}。"
            "最終核證須由獲授權工料測量師確認。"
        )
        response = (
            "付款回應草稿：\n"
            f"1. 承認金額：港幣 {summary.amount_due:,.2f}（已扣本期保留金）。\n"
            f"2. 差額／扣減原因：{'; '.join(card.drivers[:3])}。\n"
            "3. 請承建商於七日內補交證明文件。"
        )
        return explanation, response

    explanation = (
        f"Payment valuation checks completed. Package risk is {card.band.upper()}. "
        f"Claimed this period HKD {summary.claimed_this_period:,.0f}; "
        f"proposed assessment HKD {summary.assessed_this_period:,.0f}. "
        f"Key drivers: {'; '.join(card.drivers[:3])}. "
        "Final certification remains with the authorised QS."
    )
    response = (
        "Draft payment response:\n"
        f"1. Admitted amount: HKD {summary.amount_due:,.2f} (after retention on this period).\n"
        f"2. Reasons for difference: {'; '.join(card.drivers[:3])}.\n"
        "3. Please provide missing evidence within 7 days."
    )
    return explanation, response


def _exception_text(lines: list[LineItem]) -> str:
    exception_lines = [l for l in lines if l.risk != "green"][:12]
    return "\n".join(
        (
            f"- {l.item_no}: claimed {l.claimed_amount:.2f}, assessed {l.assessed_amount:.2f}, "
            f"risk={l.risk}, issues={' | '.join(l.issues)}"
        )
        for l in exception_lines
    ) or "- No exception lines"


def _prompt(
    *,
    project_name: str,
    locale: str,
    lines: list[LineItem],
    summary: ValuationSummary,
    card: RiskCard,
    cpecs_summary: str,
    benchmarks: list[dict[str, Any]],
) -> str:
    lang = "Traditional Chinese" if locale == "zh-Hant" else "English"
    return f"""You are a Hong Kong quantity surveying assistant helping with interim payment valuation.
Write in {lang}. Be concise and professional. Do not invent contractual clauses.
Do not claim the AI certifies payment. QS remains the decision maker.

Project: {project_name}
Risk band: {card.band}
Drivers: {card.drivers}
CPECS: {cpecs_summary}
Summary: claimed={summary.claimed_this_period}, assessed={summary.assessed_this_period}, amount_due={summary.amount_due}
Benchmarks: {benchmarks[:3]}
Exception lines:
{_exception_text(lines)}

Return exactly two sections:
EXPLANATION:
<short paragraph for QS>
PAYMENT_RESPONSE:
<numbered draft payment response / pay-less style notes>
"""


def _parse_sections(text: str, locale: str, summary: ValuationSummary, card: RiskCard) -> tuple[str, str]:
    explanation = text
    response = ""
    if "PAYMENT_RESPONSE:" in text:
        explanation, response = text.split("PAYMENT_RESPONSE:", 1)
        explanation = explanation.replace("EXPLANATION:", "").strip()
        response = response.strip()
    else:
        explanation, response = _fallback(locale, summary, card)
        explanation = text or explanation
    return explanation, response


async def explain_valuation(
    *,
    project_name: str,
    locale: str,
    lines: list[LineItem],
    summary: ValuationSummary,
    card: RiskCard,
    cpecs_summary: str,
    benchmarks: list[dict[str, Any]],
    use_llm: bool = True,
) -> tuple[str, str]:
    if not use_llm:
        return _fallback(locale, summary, card)

    prompt = _prompt(
        project_name=project_name,
        locale=locale,
        lines=lines,
        summary=summary,
        card=card,
        cpecs_summary=cpecs_summary,
        benchmarks=benchmarks,
    )

    from app.services import llm_client

    result = llm_client.chat(
        system="You are a Hong Kong quantity surveying assistant. Follow the user instructions exactly.",
        messages=[{"role": "user", "content": prompt}],
    )
    if result.get("used_llm") and result.get("content"):
        return _parse_sections(result["content"], locale, summary, card)
    if result.get("error"):
        logger.warning("LLM explanation failed: %s", result.get("error"))
    return _fallback(locale, summary, card)
