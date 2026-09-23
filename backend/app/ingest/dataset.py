"""Organisers' simulated dataset (Dataset_Legal.xlsx, sheet Reg_Change_Monitor).

The jury_* columns are the EVALUATION set. They are deliberately dropped here and never
stored or fed into a prompt or rule; scripts/evaluate.py reads them straight from the xlsx.
"""
from datetime import datetime, timezone

import openpyxl

from app.config import settings

JURY_COLUMNS = {"jury_expected_routing_team", "jury_expected_priority_reason"}


def read_rows(path=None) -> list[dict]:
    wb = openpyxl.load_workbook(path or settings.dataset_file, data_only=True, read_only=True)
    ws = wb["Reg_Change_Monitor"]
    rows = list(ws.iter_rows(values_only=True))
    header = [str(h) for h in rows[0]]
    return [dict(zip(header, r)) for r in rows[1:] if r and r[0]]


def load_items() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    items = []
    for row in read_rows():
        pipeline_meta = {k: v for k, v in row.items() if k not in JURY_COLUMNS and v is not None}
        items.append({
            "source": "organisers_dataset",
            "external_id": row["update_id"],
            "update_type": "simulated",
            "eli_uri": None,
            "title": row["title"],
            "jurisdiction": "EU" if row["jurisdiction"] == "EU" else "CH",
            "publication_date": str(row["publication_date"])[:10],
            "entry_into_force_date": None,
            "consultation_deadline": None,
            "source_language": "EN",
            "source_text": row["plain_language_summary"],
            "source_articles": [{"ref": row["update_id"], "text": row["plain_language_summary"]}],
            "source_text_url": None,
            "source_url": None,
            "source_version": "Dataset_Legal.xlsx v1.1",
            "is_simulated": True,
            "metadata_extra": pipeline_meta,
            "fetched_at": now,
        })
    return items
