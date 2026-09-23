"""Compare the system's routing with the jury columns of the organisers' dataset.

    uv run python -m scripts.evaluate

For each simulated update (R001..R008): classify it with the current pipeline (mock or LLM),
compare `functional_teams` with `jury_expected_routing_team` ("Legal + Product + Engineering").
Reports per-row Jaccard, precision, recall and the overall agreement score.
The jury columns are read here only - never by the pipeline itself.
TODO(ws2): also compare urgency, and check the priority reason / inclusion topics
           (children data, accessibility, nonprofit vulnerability) are recognised.
"""
from app.ai import classify
from app.ingest import dataset


def teams(s: str | None) -> set[str]:
    return {t.strip() for t in (s or "").split("+") if t.strip()}


def main() -> None:
    jury = {r["update_id"]: r for r in dataset.read_rows()}
    rows, total_j, total_p, total_r = [], 0.0, 0.0, 0.0
    for item in dataset.load_items():
        cls = classify.classify(item)
        got, want = set(cls["functional_teams"]), teams(jury[item["external_id"]]["jury_expected_routing_team"])
        inter = got & want
        j = len(inter) / len(got | want) if got | want else 1.0
        p = len(inter) / len(got) if got else 0.0
        r = len(inter) / len(want) if want else 1.0
        total_j, total_p, total_r = total_j + j, total_p + p, total_r + r
        rows.append((item["external_id"], j, sorted(got), sorted(want)))
    n = len(rows)
    print(f"{'id':5} {'jacc':>5}  system -> jury")
    for rid, j, got, want in rows:
        print(f"{rid:5} {j:5.2f}  {', '.join(got)}  ->  {', '.join(want)}")
    print(f"\nAgreement (mean Jaccard): {total_j / n:.2f}   precision: {total_p / n:.2f}   recall: {total_r / n:.2f}")
    print(f"Model: {cls['model_version']}  prompt: {cls['prompt_version']}")


if __name__ == "__main__":
    main()
