"""Hong Kong open-data connectors (DATA.GOV.HK). No API key required."""
from __future__ import annotations

import logging
from typing import Any

import httpx

from app import config
from app.schemas import BenchmarkContext

logger = logging.getLogger(__name__)

# Public resource endpoints / CKAN package ids used for prototype context.
BWTPI_PACKAGE = "hk-archsd-archsddata-tpi-bw"
BSTPI_PACKAGE = "hk-archsd-archsddata-tpi-bs"
WAGE_PACKAGE = "hk-censtatd-tablechart-220-20001a"
CKAN_PACKAGE_SHOW = "https://data.gov.hk/en-data/api/3/action/package_show"


async def _package_show(package_id: str) -> dict[str, Any] | None:
    if not config.DATA_GOV_HK_ENABLED:
        return None
    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(CKAN_PACKAGE_SHOW, params={"id": package_id})
            resp.raise_for_status()
            body = resp.json()
            if not body.get("success"):
                return None
            return body.get("result") or {}
    except Exception as exc:  # noqa: BLE001 — prototype should degrade gracefully
        logger.warning("DATA.GOV.HK package_show failed for %s: %s", package_id, exc)
        return None


def _fallback_benchmarks() -> list[BenchmarkContext]:
    return [
        BenchmarkContext(
            source="ArchSD BWTPI",
            label="Building Works Tender Price Index",
            value=1842.0,
            period="2025 Q4",
            note="Offline value used when live fetch is unavailable.",
            live=False,
        ),
        BenchmarkContext(
            source="ArchSD BSTPI",
            label="Building Services Tender Price Index",
            value=156.0,
            period="2025 Q4",
            note="Offline value used when live fetch is unavailable.",
            live=False,
        ),
        BenchmarkContext(
            source="C&SD wages",
            label="Public-sector construction average daily wage context",
            value=None,
            period="latest published",
            note="Use for reasonableness context only — not contractual entitlement.",
            live=False,
        ),
    ]


async def fetch_benchmarks() -> list[BenchmarkContext]:
    """Fetch live metadata from DATA.GOV.HK; fall back to cached values."""
    results: list[BenchmarkContext] = []

    bwtpi = await _package_show(BWTPI_PACKAGE)
    if bwtpi:
        results.append(
            BenchmarkContext(
                source="DATA.GOV.HK / ArchSD",
                label="Building Works Tender Price Index (dataset live)",
                value=None,
                period="quarterly",
                note=(bwtpi.get("notes") or bwtpi.get("title") or "BWTPI dataset reachable")[:240],
                live=True,
            )
        )

    bstpi = await _package_show(BSTPI_PACKAGE)
    if bstpi:
        results.append(
            BenchmarkContext(
                source="DATA.GOV.HK / ArchSD",
                label="Building Services Tender Price Index (dataset live)",
                value=None,
                period="quarterly",
                note=(bstpi.get("notes") or bstpi.get("title") or "BSTPI dataset reachable")[:240],
                live=True,
            )
        )

    wages = await _package_show(WAGE_PACKAGE)
    if wages:
        results.append(
            BenchmarkContext(
                source="DATA.GOV.HK / C&SD",
                label="Public-sector construction wage series (dataset live)",
                value=None,
                period="published series",
                note=(wages.get("notes") or wages.get("title") or "Wage dataset reachable")[:240],
                live=True,
            )
        )

    if not results:
        return _fallback_benchmarks()

    results.append(
        BenchmarkContext(
            source="Cost-movement prior",
            label="Near-term building works movement band",
            value=1.5,
            period="prior %",
            note="Used for Payment Confidence scoring context.",
            live=False,
        )
    )
    return results
