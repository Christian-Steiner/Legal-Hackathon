"""Refresh data/fedlex_cache.json from the live Fedlex SPARQL endpoint (used by DEMO_MODE).

    uv run python -m scripts.fetch_fedlex_cache
"""
from app.ingest import fedlex


def main() -> None:
    items = fedlex.fetch_live()
    fedlex.save_cache(items)
    by_type: dict[str, int] = {}
    for it in items:
        by_type[it["update_type"]] = by_type.get(it["update_type"], 0) + 1
    print(f"Cached {len(items)} items: {by_type}")
    print(f"With text: {sum(1 for i in items if i.get('source_text'))}")


if __name__ == "__main__":
    main()
