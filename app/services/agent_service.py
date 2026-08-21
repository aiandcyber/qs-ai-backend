"""QS product agent: questions, directions, and tool-backed actions."""
from __future__ import annotations

import json
import re
from typing import Any

from app.schemas import AnalyzeRequest
from app.services import analysis_runner, cpecs, llm_client, workspace

OPENAI_TOOLS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_project_overview",
            "description": "Get employer, contractor, contract form, valuation date for the active project.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_contract_profile",
            "description": "Get payment rules, retention, Cap. 652 timing windows.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_deadlines",
            "description": "Get SOP payment claim / response / payment deadlines.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_evidence_gaps",
            "description": "List linked and missing evidence for the payment claim.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_cpecs_findings",
            "description": "Run or fetch CPECS document-pack findings.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "run_valuation_analysis",
            "description": "Run Excel claim vs assessment valuation and payment confidence scoring.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_exception_lines",
            "description": "List amber/red valuation lines from the latest analysis.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "explain_item",
            "description": "Explain a specific BQ / claim item by item number.",
            "parameters": {
                "type": "object",
                "properties": {"item_no": {"type": "string"}},
                "required": ["item_no"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_draft_payment_response",
            "description": "Return the draft payment response from the latest analysis.",
            "parameters": {"type": "object", "properties": {}},
        },
    },
    {
        "type": "function",
        "function": {
            "name": "navigate_ui",
            "description": "Suggest opening a UI module for the QS user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {
                        "type": "string",
                        "enum": [
                            "dashboard",
                            "projects",
                            "contract",
                            "valuation",
                            "evidence",
                            "cpecs",
                            "market",
                            "intel",
                            "deadlines",
                            "reports",
                            "audit",
                            "settings",
                        ],
                    }
                },
                "required": ["page"],
            },
        },
    },
]

SYSTEM_PROMPT = """You are the QS AI Payment Valuation Copilot agent for Hong Kong quantity surveyors.
Help with interim payment valuation: Excel claims, CPECS findings, evidence gaps, Cap. 652 / SOP deadlines,
contract payment rules, and draft payment responses.

Rules:
- Be concise, professional, and bilingual-aware (reply in the user's language).
- Use tools for facts; do not invent amounts, clauses, or CPECS findings.
- Never claim the AI certifies payment. Authorised QS remains the decision maker.
- After tool results, give clear next steps the QS can take in the workspace.
- Prefer actionable guidance over long essays.
"""


async def _exec_tool(project_id: str, locale: str, name: str, args: dict[str, Any]) -> dict[str, Any]:
    project = analysis_runner.load_project_info(project_id)
    ws = workspace.build_workspace(project_id, project.model_dump())

    if name == "get_project_overview":
        return {"project": project.model_dump()}

    if name == "get_contract_profile":
        return {"contract_profile": ws["contract_profile"]}

    if name == "get_deadlines":
        return {"deadlines": ws["deadlines"]}

    if name == "get_evidence_gaps":
        missing = [e for e in ws["evidence"] if e["status"] == "missing"]
        linked = [e for e in ws["evidence"] if e["status"] == "linked"]
        return {"missing": missing, "linked_count": len(linked), "linked": linked[:8]}

    if name == "get_cpecs_findings":
        cached = analysis_runner.get_cached_analysis(project_id)
        if cached:
            return {"cpecs": cached.cpecs.model_dump()}
        result = await cpecs.check_payment_pack(project_id)
        return {"cpecs": result.model_dump()}

    if name == "run_valuation_analysis":
        result = await analysis_runner.run_analysis(
            project_id,
            AnalyzeRequest(project_id=project_id, locale=locale, use_llm=True),
        )
        return {
            "status": "ok",
            "brief": analysis_runner.analysis_brief(result),
            "ui_action": {"type": "refresh_analysis"},
            "navigate": "valuation",
        }

    if name == "get_exception_lines":
        cached = analysis_runner.get_cached_analysis(project_id)
        if not cached:
            return {"error": "No analysis yet. Call run_valuation_analysis first."}
        lines = [
            {
                "item_no": l.item_no,
                "description": l.description,
                "claimed": l.claimed_amount,
                "assessed": l.assessed_amount,
                "diff": l.difference_amount,
                "risk": l.risk,
                "issues": l.issues,
            }
            for l in cached.lines
            if l.risk != "green"
        ]
        return {"exceptions": lines, "brief": analysis_runner.analysis_brief(cached)}

    if name == "explain_item":
        item_no = str(args.get("item_no", "")).strip()
        cached = analysis_runner.get_cached_analysis(project_id)
        if not cached:
            return {"error": "No analysis yet. Call run_valuation_analysis first."}
        for line in cached.lines:
            if line.item_no.lower() == item_no.lower():
                return {"item": line.model_dump()}
        return {"error": f"Item {item_no} not found in latest analysis."}

    if name == "get_draft_payment_response":
        cached = analysis_runner.get_cached_analysis(project_id)
        if not cached:
            return {"error": "No analysis yet. Call run_valuation_analysis first."}
        return {
            "draft_payment_response": cached.draft_payment_response,
            "explanation": cached.llm_explanation,
            "navigate": "reports",
        }

    if name == "navigate_ui":
        page = str(args.get("page", "dashboard"))
        return {"ui_action": {"type": "navigate", "page": page}, "page": page}

    return {"error": f"Unknown tool {name}"}


def _collect_actions(tool_results: list[dict[str, Any]]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    seen: set[str] = set()
    for tr in tool_results:
        data = tr.get("result") or {}
        if data.get("navigate"):
            key = f"nav:{data['navigate']}"
            if key not in seen:
                seen.add(key)
                actions.append({"type": "navigate", "page": data["navigate"]})
        ua = data.get("ui_action")
        if isinstance(ua, dict):
            key = json.dumps(ua, sort_keys=True)
            if key not in seen:
                seen.add(key)
                actions.append(ua)
        if tr.get("name") == "run_valuation_analysis" and data.get("status") == "ok":
            if "download" not in seen:
                seen.add("download")
                actions.append({"type": "download_valuation"})
    return actions


def _rule_based(project_id: str, locale: str, message: str, ws: dict[str, Any]) -> dict[str, Any]:
    text = message.lower()
    zh = locale == "zh-Hant"
    actions: list[dict[str, Any]] = []

    if any(k in text for k in ("analy", "valuat", "run", "評估", "估值", "分析")):
        actions.append({"type": "run_analyze"})
        actions.append({"type": "navigate", "page": "valuation"})
        reply = (
            "我可以執行估值分析。請按下方「執行估值」，完成後會更新風險卡與評核明細。"
            if zh
            else "I can run valuation analysis for this project. Use **Run valuation** below — that refreshes the risk card and claim vs assessment lines."
        )
        return {"reply": reply, "actions": actions, "tool_trace": [], "mode": "rules"}

    if any(k in text for k in ("evidence", "missing", "證明", "證據", "欠")):
        missing = [e for e in ws["evidence"] if e["status"] == "missing"]
        actions.append({"type": "navigate", "page": "evidence"})
        if zh:
            lines = "\n".join(f"- {e['name']}（{e['type']}）· {', '.join(e['linked_items'])}" for e in missing)
            reply = f"目前欠證據項目：\n{lines or '無'}\n請開啟證據庫補齊。"
        else:
            lines = "\n".join(f"- {e['name']} ({e['type']}) · {', '.join(e['linked_items'])}" for e in missing)
            reply = f"Missing evidence:\n{lines or 'None'}\nOpen the Evidence room to chase these."
        return {"reply": reply, "actions": actions, "tool_trace": [], "mode": "rules"}

    if any(k in text for k in ("deadline", "sop", "cap. 652", "652", "期限", "付款回應")):
        actions.append({"type": "navigate", "page": "deadlines"})
        rows = "\n".join(
            f"- {d['label']}: {d['due_date']} ({d['status']}) — {d['owner']}" for d in ws["deadlines"]
        )
        reply = (f"SOP 期限：\n{rows}" if zh else f"SOP deadlines:\n{rows}")
        return {"reply": reply, "actions": actions, "tool_trace": [], "mode": "rules"}

    if any(k in text for k in ("cpecs", "document pack", "文件")):
        actions.append({"type": "navigate", "page": "cpecs"})
        reply = (
            "請開啟 CPECS 檢查模組；若尚未分析，先執行估值以帶入文件包發現。"
            if zh
            else "Open the CPECS check module. If analysis has not run yet, run valuation first to load pack findings."
        )
        return {"reply": reply, "actions": actions, "tool_trace": [], "mode": "rules"}

    if any(k in text for k in ("contract", "retention", "clause", "合約", "保留金", "條款")):
        actions.append({"type": "navigate", "page": "contract"})
        profile = ws["contract_profile"]
        reply = (
            f"合約付款規則摘要：回應期 {profile['response_window_days']} 日；付款期 {profile['payment_window_days']} 日；保留金 {profile['retention_percent']}%。"
            if zh
            else f"Contract payment rules: response window {profile['response_window_days']} days; payment window {profile['payment_window_days']} days; retention {profile['retention_percent']}%."
        )
        return {"reply": reply, "actions": actions, "tool_trace": [], "mode": "rules"}

    if any(k in text for k in ("draft", "response", "payment response", "回應", "草稿")):
        actions.append({"type": "navigate", "page": "reports"})
        actions.append({"type": "run_analyze"})
        reply = (
            "付款回應草稿在「報告與輸出」。若尚未分析，請先執行估值。"
            if zh
            else "The draft payment response sits under Reports & outputs. Run valuation first if it is empty."
        )
        return {"reply": reply, "actions": actions, "tool_trace": [], "mode": "rules"}

    # default help
    actions.append({"type": "navigate", "page": "dashboard"})
    reply = (
        "我可以協助：執行估值、查證據缺口、CPECS 發現、SOP 期限、合約付款規則、例外項目說明、付款回應草稿。請直接提問或指示。"
        if zh
        else "I can help with: run valuation, evidence gaps, CPECS findings, SOP deadlines, contract payment rules, exception line explanations, and draft payment responses. Ask a question or give a direction."
    )
    return {"reply": reply, "actions": actions, "tool_trace": [], "mode": "rules"}


async def chat_agent(
    *,
    project_id: str,
    message: str,
    locale: str = "en",
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    project = analysis_runner.load_project_info(project_id)
    ws = workspace.build_workspace(project_id, project.model_dump())
    history = history or []

    status = llm_client.provider_status()
    cached = analysis_runner.get_cached_analysis(project_id)
    context_note = (
        f"Active project: {project.id} — {project.name}. "
        f"Analysis cached: {'yes' if cached else 'no'}. "
        f"Missing evidence count: {sum(1 for e in ws['evidence'] if e['status'] == 'missing')}."
    )

    messages = [
        *[{"role": h["role"], "content": h["content"]} for h in history[-8:]],
        {"role": "user", "content": f"{context_note}\n\nUser: {message}"},
    ]

    if not status["configured"]:
        out = _rule_based(project_id, locale, message, ws)
        out["model"] = status
        out["notice"] = (
            "LLM not configured — using guided rules. Set MODEL_PROVIDER / MODEL_BASE_URL / keys."
            if locale != "zh-Hant"
            else "尚未設定語言模型 — 使用規則引導。請設定 MODEL_PROVIDER / MODEL_BASE_URL / 金鑰。"
        )
        return out

    first = llm_client.chat(
        system=SYSTEM_PROMPT + f"\nRespond in {'Traditional Chinese' if locale == 'zh-Hant' else 'English'}.",
        messages=messages,
        tools=OPENAI_TOOLS,
    )

    if not first.get("used_llm") or first.get("error"):
        out = _rule_based(project_id, locale, message, ws)
        out["model"] = {**status, "error": first.get("error")}
        out["notice"] = (
            "LLM call failed — using guided rules."
            if locale != "zh-Hant"
            else "語言模型呼叫失敗 — 使用規則引導。"
        )
        return out

    tool_trace: list[dict[str, Any]] = []
    tool_calls = first.get("tool_calls") or []

    if tool_calls:
        for tc in tool_calls[:6]:
            result = await _exec_tool(project_id, locale, tc["name"], tc.get("arguments") or {})
            tool_trace.append({"name": tc["name"], "arguments": tc.get("arguments") or {}, "result": result})

        tool_summary = json.dumps(tool_trace, ensure_ascii=False, default=str)[:12000]
        second = llm_client.chat(
            system=SYSTEM_PROMPT
            + f"\nRespond in {'Traditional Chinese' if locale == 'zh-Hant' else 'English'}.",
            messages=[
                *messages,
                {
                    "role": "assistant",
                    "content": first.get("content") or f"Calling tools: {[t['name'] for t in tool_calls]}",
                },
                {
                    "role": "user",
                    "content": f"Tool results JSON:\n{tool_summary}\n\nWrite the final answer for the QS. Mention concrete next steps.",
                },
            ],
            tools=None,
        )
        reply = (second.get("content") or first.get("content") or "").strip()
        if not reply:
            out = _rule_based(project_id, locale, message, ws)
            out["model"] = status
            out["tool_trace"] = tool_trace
            return out
        actions = _collect_actions(tool_trace)
        return {
            "reply": reply,
            "actions": actions,
            "tool_trace": [{"name": t["name"], "ok": "error" not in (t.get("result") or {})} for t in tool_trace],
            "model": status,
            "mode": "llm",
        }

    reply = (first.get("content") or "").strip()
    # Detect soft navigation hints in free text
    actions = _infer_actions_from_text(reply, message)
    if not reply:
        out = _rule_based(project_id, locale, message, ws)
        out["model"] = status
        return out
    return {
        "reply": reply,
        "actions": actions,
        "tool_trace": [],
        "model": status,
        "mode": "llm",
    }


def _infer_actions_from_text(reply: str, message: str) -> list[dict[str, Any]]:
    blob = f"{reply}\n{message}".lower()
    actions: list[dict[str, Any]] = []
    mapping = [
        (("evidence", "證據"), "evidence"),
        (("deadline", "sop", "期限"), "deadlines"),
        (("cpecs",), "cpecs"),
        (("valuation", "analy", "估值"), "valuation"),
        (("contract", "合約"), "contract"),
        (("report", "response", "報告", "回應"), "reports"),
    ]
    for keys, page in mapping:
        if any(k in blob for k in keys):
            actions.append({"type": "navigate", "page": page})
            break
    if re.search(r"run (the )?valuat|執行估值|analyze", blob):
        actions.insert(0, {"type": "run_analyze"})
    return actions
