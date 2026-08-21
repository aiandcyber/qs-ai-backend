"""Generate Hong Kong QS project data pack (Excel + JSON + contract extract)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

from openpyxl import Workbook

PROJECT_ID = "HKHA-PRJ-2026-0147"
ROOT = Path(__file__).resolve().parents[1] / "fixtures" / PROJECT_ID
OLD = Path(__file__).resolve().parents[1] / "fixtures" / "HKHA-DEMO-2026-01"

# item_no, description, unit, contract_qty, rate, previous_qty, claimed_qty, category
ROWS = [
    ("Prelim.1", "Site establishment and preliminaries (provisional)", "Sum", 1, 850000, 0.4, 0.15, "preliminaries"),
    ("A.1.1", "Excavation for foundation in soft material", "m3", 1200, 185, 900, 250, "works"),
    ("A.2.1", "Grade C40 concrete to pile caps", "m3", 480, 1420, 300, 120, "works"),
    ("A.2.2", "Formwork to pile caps", "m2", 1600, 290, 1000, 400, "works"),
    ("A.3.1", "High yield reinforcement bars to pile caps", "kg", 95000, 12.8, 60000, 28000, "works"),
    ("B.1.1", "Grade C35 concrete to ground floor slab", "m3", 620, 1280, 200, 180, "works"),
    ("B.2.1", "Brick wall 100mm internal", "m2", 3500, 310, 800, 600, "works"),
    ("B.3.1", "Ceramic wall tiles to toilets", "m2", 1800, 420, 200, 350, "works"),
    ("C.1.1", "MVAC ductwork (provisional)", "Sum", 1, 2200000, 0.2, 0.15, "mep"),
    ("C.2.1", "Electrical containment and cable tray", "m", 4200, 95, 1000, 800, "mep"),
    ("B.2.1A", "Brick wall 100mm internal — additional claim", "m2", 3500, 310, 0, 150, "works"),
    ("V.01", "VO-12 Extra concrete to transfer beam", "m3", 40, 1550, 0, 40, "variation"),
    ("V.02", "Additional night works premium", "Sum", 1, 180000, 0, 1, "variation"),
    ("MOS.1", "Materials on site - reinforcement steel", "Sum", 1, 320000, 0, 1, "materials_on_site"),
    ("A.2.1X", "Grade C40 concrete to pile caps — remeasurement", "m3", 100, 1420, 90, 30, "works"),
]


def _amount(qty: float, rate: float) -> float:
    return round(qty * rate, 2)


def write_workbook(path: Path, include_claim: bool, include_previous: bool) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Valuation"
    headers = [
        "Item No",
        "Description",
        "Unit",
        "Contract Qty",
        "Rate",
        "Contract Amount",
        "Previous Qty",
        "Previous Amount",
        "Claimed Qty",
        "Claimed Amount",
        "Category",
    ]
    ws.append(headers)
    for item_no, desc, unit, cqty, rate, pqty, clqty, category in ROWS:
        claimed_qty = clqty if include_claim else 0
        previous_qty = pqty if include_previous else 0
        claimed_amount = _amount(claimed_qty, rate)
        if include_claim and item_no == "A.3.1":
            claimed_amount = round(claimed_amount + 12500, 2)
        ws.append(
            [
                item_no,
                desc,
                unit,
                cqty,
                rate,
                _amount(cqty, rate),
                previous_qty,
                _amount(previous_qty, rate),
                claimed_qty,
                claimed_amount,
                category,
            ]
        )
    wb.save(path)


def main() -> None:
    if OLD.exists():
        shutil.rmtree(OLD)
    if ROOT.exists():
        shutil.rmtree(ROOT)
    ROOT.mkdir(parents=True, exist_ok=True)

    write_workbook(ROOT / "bq.xlsx", include_claim=False, include_previous=False)
    write_workbook(ROOT / "previous_certificate.xlsx", include_claim=False, include_previous=True)
    write_workbook(ROOT / "payment_claim.xlsx", include_claim=True, include_previous=True)

    wb = Workbook()
    ws = wb.active
    ws.title = "Variations"
    ws.append(["VO No", "Description", "Instructed", "Status", "Amount"])
    ws.append(["VO-12", "Extra concrete to transfer beam", "Yes", "Instructed", 62000])
    ws.append(["VO-18", "Additional night works premium", "No", "Pending instruction", 180000])
    wb.save(ROOT / "variation_register.xlsx")

    project = {
        "id": PROJECT_ID,
        "name": "Public Housing Development — Interim Payment No. 7",
        "contract_form": "Standard Form of Building Contract 2025 / Cap. 652",
        "employer": "Hong Kong Housing Authority",
        "contractor": "Chun Wo Construction & Engineering Co., Ltd.",
        "valuation_date": "2026-07-28",
        "currency": "HKD",
        "retention_percent": 5.0,
        "notes": "Interim valuation for foundation, structure, finishes and MEP packages.",
    }
    (ROOT / "project.json").write_text(json.dumps(project, indent=2), encoding="utf-8")

    cpecs = {
        "summary": "CPECS check completed. 3 anomalies identified in supporting documents.",
        "extracted_documents": [
            {"type": "invoice", "ref": "INV-77821", "amount": 356000, "vendor": "Steel Supply HK"},
            {"type": "delivery_note", "ref": "DN-9921", "amount": None, "vendor": "Steel Supply HK"},
            {
                "type": "progress_claim",
                "ref": "IPC-07",
                "amount": None,
                "vendor": "Chun Wo Construction & Engineering Co., Ltd.",
            },
        ],
        "findings": [
            {
                "code": "CPECS-DUP-02",
                "severity": "amber",
                "message": "Possible duplicate invoice amount pattern near materials-on-site claim.",
                "related_item": "MOS.1",
                "extracted_amount": 320000,
            },
            {
                "code": "CPECS-MISS-11",
                "severity": "red",
                "message": "Variation VO-18 has no signed instruction attached in document pack.",
                "related_item": "V.02",
                "extracted_amount": 180000,
            },
            {
                "code": "CPECS-ARITH-07",
                "severity": "amber",
                "message": "Rebar claim amount does not reconcile to extracted delivery quantities.",
                "related_item": "A.3.1",
                "extracted_amount": 12500,
            },
        ],
    }
    (ROOT / "cpecs_response.json").write_text(json.dumps(cpecs, indent=2), encoding="utf-8")

    contract = f"""CONTRACT EXTRACT — PAYMENT PROVISIONS
=====================================================

Project: Public Housing Development ({PROJECT_ID})
Form: Standard Form of Building Contract 2025
Employer: Hong Kong Housing Authority
Contractor: Chun Wo Construction & Engineering Co., Ltd.

1. Interim payments
1.1 The Contractor may submit a payment claim for work carried out and related goods/services in the valuation period.
1.2 A payment claim shall be in writing, identify the work, and state the claimed amount and how it is calculated.
1.3 The Employer / authorised person shall issue a payment response within the contractual period or 30 days, whichever is earlier.

2. Valuation
2.1 Work shall be valued using rates in the Bills of Quantities where applicable.
2.2 Variations shall be valued only where instructed in writing.
2.3 Materials on site are payable only with satisfactory evidence of ownership, delivery and protection.

3. Retention
3.1 Retention of 5% shall be deducted from cumulative assessed value, subject to the retention limit in the Contract Particulars.

4. Evidence
4.1 The Contractor shall submit measurement sheets, delivery notes, variation instructions and photos as reasonably required.
4.2 Amounts lacking evidence may be withheld in the payment response with reasons stated.

5. Decision authority
5.1 AI-assisted valuation supports the QS workflow. Certification remains with the authorised Quantity Surveyor / Project Manager.

END OF EXTRACT
"""
    (ROOT / "contract_extract.txt").write_text(contract, encoding="utf-8")
    print(f"Wrote project data to {ROOT}")


if __name__ == "__main__":
    main()
