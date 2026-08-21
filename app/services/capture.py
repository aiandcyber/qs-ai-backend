"""Capture-ingestion: one pipeline behind four site-validation data-collection options.

Sources:
  mobile       - QS on site, mobile phone, real-time entry into the app
  gov_platform - government department platforms (SmartEye / CPECS / HA-PIMAP)
  drone_batch  - DJI drone, photo/video uploaded as a batch file
  drone_api    - DJI drone, photos/video fed in through the DJI API

Every source normalises to the same CaptureItem linked to a BQ line.
Records are stored per project under SESSIONS_ROOT. A vision model may later
populate percent_complete; here it stays advisory and QS-confirmed.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from app import config
from app.schemas import CaptureItem

SOURCES: dict[str, dict[str, str]] = {
    "mobile": {
        "label": "QS mobile (real-time)",
        "detail": "QS on site enters the verified quantity and attaches a photo/video, linked to the BQ line.",
    },
    "gov_platform": {
        "label": "Government platforms",
        "detail": "SmartEye point cloud / CPECS / HA-PIMAP via adapters.",
    },
    "drone_batch": {
        "label": "DJI drone — Upload",
        "detail": "Drone photos & video uploaded as a batch file, then ingested.",
    },
    "drone_api": {
        "label": "DJI drone — Cloud API",
        "detail": "Drone photos & video streamed into the app through the DJI Cloud API.",
    },
}


def _store_path(project_id: str) -> Path:
    root = config.SESSIONS_ROOT / project_id
    root.mkdir(parents=True, exist_ok=True)
    return root / "captures.json"


def list_captures(project_id: str) -> list[CaptureItem]:
    path = _store_path(project_id)
    if not path.exists():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [CaptureItem(**r) for r in raw]


def _write(project_id: str, items: list[CaptureItem]) -> None:
    _store_path(project_id).write_text(
        json.dumps([i.model_dump() for i in items], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def add_capture(
    project_id: str,
    source: str,
    item_no: str = "",
    description: str = "",
    percent_complete: float | None = None,
    note: str = "",
) -> CaptureItem:
    if source not in SOURCES:
        raise ValueError(f"Unknown capture source: {source}")
    media_ref = {
        "mobile": "mobile-photo",
        "gov_platform": "platform-feed",
        "drone_batch": "drone-batch-file",
        "drone_api": "drone-api-stream",
    }[source]
    item = CaptureItem(
        id=f"CAP-{uuid.uuid4().hex[:8].upper()}",
        source=source,  # type: ignore[arg-type]
        item_no=item_no,
        description=description or SOURCES[source]["label"],
        media_ref=f"{media_ref}/{uuid.uuid4().hex[:6]}",
        percent_complete=percent_complete,
        note=note,
        captured_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
        status="captured",
    )
    items = list_captures(project_id)
    items.append(item)
    _write(project_id, items)
    return item


def sources_payload() -> list[dict[str, Any]]:
    return [{"id": k, **v} for k, v in SOURCES.items()]
