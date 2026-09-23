"""Push ONE incoming update through classify -> match -> draft with the configured LLM.

    # an update that is already in the DB (ids are shown on the Updates page / in the URL):
    uv run python -m scripts.process_one --id fedlex:oc/2026/322
    # a new "incoming" update from a JSON file (see data/samples/incoming_update.json):
    uv run python -m scripts.process_one --file data/samples/incoming_update.json
    # limit to some companies to save calls:
    uv run python -m scripts.process_one --id dataset:R005 --company 3 --company 4

Afterwards the drafts are in the lawyer review queue (http://localhost:5173/lawyer/review).
"""
import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from app.ai import llm
from app.db import SessionLocal, init_db
from app.services import pipeline


def main() -> None:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--id", help="existing update id, e.g. fedlex:oc/2026/322 or dataset:R005")
    g.add_argument("--file", help="JSON file with a new incoming update")
    ap.add_argument("--company", type=int, action="append", help="company id (repeatable); default all")
    args = ap.parse_args()

    init_db()
    db = SessionLocal()
    print(f"Model: {llm.model_version()}")

    update_id = args.id
    if args.file:
        item = json.loads(Path(args.file).read_text())
        item.setdefault("source", "manual")
        item.setdefault("fetched_at", datetime.now(timezone.utc).isoformat())
        pipeline.upsert_items(db, [item], actor="system:process_one")
        prefix = "dataset" if item["source"] == "organisers_dataset" else item["source"]
        update_id = f"{prefix}:{item['external_id']}"
        print(f"Ingested {update_id}")

    t = time.time()
    try:
        res = pipeline.process_update(db, update_id, args.company)
    except KeyError:
        sys.exit(f"No update with id {update_id!r}")
    except llm.LLMError as e:
        sys.exit(f"LLM call failed: {e}")

    c = res["classification"]
    print(f"\n{res['title']}\n  topics: {', '.join(c['topics'])}\n  teams:  {' + '.join(c['functional_teams'])}"
          f"\n  urgency: {c['urgency']}\n  why:    {c['rationale']}\n")
    for r in res["companies"]:
        if "skipped" in r:
            print(f"  - {r['company']}: skipped ({r['skipped']})")
            continue
        mark = "MATCH" if r["matched"] else "  -  "
        print(f"  {mark} {r['company']} ({r['score']:.2f}): {r['reason']}")
        if r["draft_id"]:
            print(f"        -> draft http://localhost:5173/lawyer/review/{r['draft_id']}")
    print(f"\nDone in {time.time() - t:.1f}s")


if __name__ == "__main__":
    main()
