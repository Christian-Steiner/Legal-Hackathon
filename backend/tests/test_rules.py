"""Unit tests for the deterministic layer: applicability scopes vs the sector veto, deadline urgency."""
from datetime import date

from app.ai import rules

NIMBUS = {"flags": {"processes_personal_data": True}, "size_band": "11-50", "jurisdictions": ["CH"],
          "topics": [], "departments": [{"functions": ["Legal"]}]}
TODAY = date(2026, 9, 23)


def test_general_scope_overrides_sector_veto():
    # Beneficial-owner register: AML-motivated (finma flag) but binding on every legal entity.
    cls = {"triggered_flags": ["finma_supervised"], "applies_to": ["all_legal_entities"], "topics": []}
    hits = rules.profile_rules(NIMBUS, {"jurisdiction": "CH"}, cls)
    names = {h["rule"] for h in hits}
    assert "scope:all_legal_entities" in names and "sector:mismatch" not in names
    assert rules.score(hits) >= 0.4


def test_sector_veto_without_scope():
    cls = {"triggered_flags": ["finma_supervised"], "applies_to": [], "topics": []}
    hits = rules.profile_rules(NIMBUS, {"jurisdiction": "CH"}, cls)
    assert rules.score(hits) == 0 and any(h["rule"] == "sector:mismatch" for h in hits)


def test_scope_ignored_for_foreign_law_where_not_active():
    cls = {"triggered_flags": [], "applies_to": ["all_legal_entities"], "topics": []}
    hits = rules.profile_rules(NIMBUS, {"jurisdiction": "EU"}, cls)
    assert not any(h["rule"].startswith("scope:") for h in hits)


def test_employer_scope_needs_staff():
    solo = {**NIMBUS, "size_band": "1-10", "departments": []}
    assert "employers" not in rules.company_scopes(solo)
    assert "employers" in rules.company_scopes(NIMBUS)


def test_deadline_floor():
    u = {"update_type": "as_publication", "entry_into_force_date": "2026-10-01"}
    assert rules.apply_deadline_floor("low", u, TODAY)[0] == "high"  # 8 days
    assert rules.apply_deadline_floor("low", {**u, "entry_into_force_date": "2026-11-30"}, TODAY)[0] == "medium"
    assert rules.apply_deadline_floor("low", {**u, "entry_into_force_date": "2028-01-01"}, TODAY) == ("low", None)
    assert rules.apply_deadline_floor("low", {**u, "entry_into_force_date": "2026-09-15"}, TODAY)[0] == "high"  # in force
    # never lowers
    assert rules.apply_deadline_floor("high", {**u, "entry_into_force_date": "2028-01-01"}, TODAY)[0] == "high"
    # consultations: soon-closing deadline -> medium at most
    c = {"update_type": "consultation", "entry_into_force_date": "2026-10-01", "consultation_deadline": "2026-10-10"}
    assert rules.apply_deadline_floor("low", c, TODAY)[0] == "medium"
