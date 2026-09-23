"""Fedlex SPARQL ingest (workstream 1).

Three kinds of change, as in the spec:
  1. new publications in the Official Compilation (AS / "oc")
  2. acts with an upcoming entry-into-force date
  3. open consultations (Vernehmlassungen)

`fetch_live()` hits https://fedlex.data.admin.ch/sparqlendpoint (no auth) and returns plain
dicts ("raw items"). `scripts/fetch_fedlex_cache.py` writes them to data/fedlex_cache.json;
in DEMO_MODE the ingest reads that file instead of the live endpoint.
"""
import json
import re
from datetime import date, datetime, timedelta, timezone

import requests
from bs4 import BeautifulSoup

from app.config import settings

PREFIXES = """
PREFIX jolux: <http://data.legilux.public.lu/resource/ontology/jolux#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
"""
LANG_URI = {
    "DE": "http://publications.europa.eu/resource/authority/language/DEU",
    "FR": "http://publications.europa.eu/resource/authority/language/FRA",
    "IT": "http://publications.europa.eu/resource/authority/language/ITA",
}
HTML_FORMAT = "http://publications.europa.eu/resource/authority/file-type/HTML"


def sparql(query: str, timeout: int = 60) -> list[dict]:
    resp = requests.post(
        settings.fedlex_endpoint,
        data={"query": PREFIXES + query},
        headers={"Accept": "application/sparql-results+json"},
        timeout=timeout,
    )
    resp.raise_for_status()
    rows = resp.json()["results"]["bindings"]
    return [{k: v["value"] for k, v in row.items()} for row in rows]


def _acts_query(filter_clause: str, order: str, limit: int, lang: str) -> str:
    return f"""
SELECT ?act ?pub ?eif ?modified ?title ?html WHERE {{
  ?act a jolux:Act ; jolux:publicationDate ?pub .
  FILTER(STRSTARTS(STR(?act), "https://fedlex.data.admin.ch/eli/oc/"))
  OPTIONAL {{ ?act jolux:dateEntryInForce ?eif }}
  OPTIONAL {{ ?act <http://purl.org/dc/terms/modified> ?modified }}
  OPTIONAL {{
    ?act jolux:isRealizedBy ?expr . ?expr jolux:language <{LANG_URI[lang]}> ; jolux:title ?title .
    OPTIONAL {{ ?expr jolux:isEmbodiedBy ?m . ?m jolux:format <{HTML_FORMAT}> ; jolux:isExemplifiedBy ?html }}
  }}
  {filter_clause}
}} ORDER BY {order} LIMIT {limit}
"""


def fetch_new_publications(since: date, limit: int = 40, lang: str = "DE") -> list[dict]:
    q = _acts_query(f'FILTER(?pub >= "{since.isoformat()}"^^xsd:date)', "DESC(?pub)", limit, lang)
    return [_act_row_to_item(r, "as_publication", lang) for r in _dedupe_rows(sparql(q))]


def fetch_upcoming_entry_into_force(today: date, horizon_days: int = 180, limit: int = 40, lang: str = "DE") -> list[dict]:
    until = today + timedelta(days=horizon_days)
    f = f'FILTER(BOUND(?eif) && ?eif > "{today.isoformat()}"^^xsd:date && ?eif <= "{until.isoformat()}"^^xsd:date)'
    q = _acts_query(f, "?eif", limit, lang)
    return [_act_row_to_item(r, "entry_into_force", lang) for r in _dedupe_rows(sparql(q))]


def fetch_open_consultations(today: date, limit: int = 30, lang: str = "DE") -> list[dict]:
    q = f"""
SELECT ?c ?start ?end ?title ?desc WHERE {{
  ?c a jolux:Consultation ; jolux:hasSubTask ?phase .
  ?phase jolux:eventStartDate ?start ; jolux:eventEndDate ?end .
  FILTER(?end >= "{today.isoformat()}"^^xsd:date)
  OPTIONAL {{ ?c jolux:eventTitle ?title FILTER(lang(?title) = "{lang.lower()}") }}
  OPTIONAL {{ ?c jolux:eventDescription ?desc FILTER(lang(?desc) = "{lang.lower()}") }}
}} ORDER BY ?end LIMIT {limit}
"""
    items = []
    for r in _dedupe_rows(sparql(q), key="c"):
        items.append({
            "source": "fedlex",
            "external_id": r["c"].removeprefix("https://fedlex.data.admin.ch/eli/"),
            "update_type": "consultation",
            "eli_uri": r["c"],
            "title": r.get("title") or r["c"],
            "publication_date": r.get("start"),
            "entry_into_force_date": None,
            "consultation_deadline": r.get("end"),
            "source_language": lang,
            "source_text": r.get("desc"),
            "source_text_url": None,
            "source_url": r["c"],
            "source_version": None,
        })
    return items


def _dedupe_rows(rows: list[dict], key: str = "act") -> list[dict]:
    seen, out = set(), []
    for r in rows:
        if r[key] not in seen:
            seen.add(r[key])
            out.append(r)
    return out


def _act_row_to_item(r: dict, update_type: str, lang: str) -> dict:
    return {
        "source": "fedlex",
        "external_id": r["act"].removeprefix("https://fedlex.data.admin.ch/eli/"),
        "update_type": update_type,
        "eli_uri": r["act"],
        "title": r.get("title") or r["act"],
        "publication_date": r.get("pub"),
        "entry_into_force_date": r.get("eif"),
        "consultation_deadline": None,
        "source_language": lang,
        "source_text": None,
        "source_text_url": r.get("html"),
        "source_url": r["act"],
        # dcterms:modified of the act = the Fedlex source version we saw
        "source_version": r.get("modified"),
    }


def fetch_text(item: dict, max_chars: int = 30000) -> None:
    """Download the HTML from the filestore and split it into citable articles (in place)."""
    url = item.get("source_text_url")
    if not url:
        return
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.content, "html.parser")
    articles = []
    for art in soup.find_all("article"):
        heading = art.find(re.compile("^h[1-6]$"))
        ref = heading.get_text(" ", strip=True) if heading else art.get("id", "")
        text = art.get_text(" ", strip=True)
        if text:
            articles.append({"ref": _short_ref(ref), "text": text[:3000]})
    body = soup.find("main") or soup.body or soup
    item["source_text"] = body.get_text("\n", strip=True)[:max_chars]
    item["source_articles"] = articles[:60]


def _short_ref(heading: str) -> str:
    heading = heading.replace("\xa0", " ")
    m = re.match(r"^(Art\.\s*\d+[a-z]*|Ziff\.\s*[IVX\d]+)", heading)
    return m.group(1) if m else heading[:60]


def fetch_live(today: date | None = None, with_text: bool = True) -> list[dict]:
    today = today or date.today()
    items = (
        fetch_new_publications(today - timedelta(days=21))
        + fetch_upcoming_entry_into_force(today)
        + fetch_open_consultations(today)
    )
    now = datetime.now(timezone.utc).isoformat()
    for it in items:
        it["fetched_at"] = now
        if with_text and it["source_text_url"]:
            try:
                fetch_text(it)
            except requests.RequestException as e:  # text is optional; metadata still useful
                it["text_error"] = str(e)
    return items


def load_cache() -> list[dict]:
    return json.loads(settings.fedlex_cache_file.read_text())["items"]


def save_cache(items: list[dict]) -> None:
    payload = {"fetched_at": datetime.now(timezone.utc).isoformat(), "items": items}
    settings.fedlex_cache_file.write_text(json.dumps(payload, ensure_ascii=False, indent=1))


# TODO(ws1): resolve the SR number of the consolidated act an AS publication amends
#            (jolux:impacts -> cc/...). Useful for dedup across sources and for clients.
# TODO(ws1): fetch FR/IT titles too so the reviewer can pick the client's language.
