"""Match stats remember where they came from, so an estimate is never mistaken
for a record.

Regression: when no real provider had a match, LLM-estimated (or randomly
generated) stats were cached forever and shown as if official; entries cached
before the ESPN parser was fixed kept the old 40%-of-shots guess for shots on
target. Such entries are now re-checked against the real providers.
"""

import pytest

# roster_store transitively imports rag_engine, which loads the embedding model.
pytestmark = pytest.mark.slow

ESPN_SUMMARY = {"boxscore": {"teams": [
    {"team": {"displayName": "Bournemouth"}, "homeAway": "home", "statistics": [
        {"name": "possessionPct", "displayValue": "46.2"}, {"name": "totalShots", "displayValue": "9"},
        {"name": "shotsOnTarget", "displayValue": "2"}, {"name": "totalPasses", "displayValue": "382"}]},
    {"team": {"displayName": "Liverpool"}, "homeAway": "away", "statistics": [
        {"name": "possessionPct", "displayValue": "53.8"}, {"name": "totalShots", "displayValue": "12"},
        {"name": "shotsOnTarget", "displayValue": "3"}, {"name": "totalPasses", "displayValue": "474"}]},
]}}


@pytest.fixture
def rs(monkeypatch):
    from backend import roster_store

    store = {}
    calls = {"espn": 0, "llm": 0}

    def fake_summary(*args, **kwargs):
        calls["espn"] += 1
        return calls.get("summary")

    def fake_llm(*args, **kwargs):
        calls["llm"] += 1
        return None

    monkeypatch.setattr(roster_store, "load_cache", lambda: dict(store))
    monkeypatch.setattr(roster_store, "update_cache_entry", lambda k, v: store.__setitem__(k, v))
    monkeypatch.setattr(roster_store, "_fetch_espn_summary", fake_summary)
    monkeypatch.setattr(roster_store, "get_dynamic_match_stats_via_llm", fake_llm)
    monkeypatch.setattr(roster_store.settings, "API_FOOTBALL_KEY", None)
    monkeypatch.setattr(roster_store, "_real_stats_retry_at", {})
    monkeypatch.setattr(roster_store, "_live_fetched_at", {})
    return roster_store, store, calls


def _key(rs_mod):
    return rs_mod._match_cache_key("matchstats", "Bournemouth", "Liverpool", "20 sep 2026")[0]


def test_cached_estimate_is_replaced_once_a_real_source_has_the_match(rs):
    mod, store, calls = rs
    store[_key(mod)] = {"shots": [15, 4], "shotsOnTarget": [6, 2], "source": "estimate"}
    calls["summary"] = ESPN_SUMMARY

    stats = mod.get_match_stats("Bournemouth", "Liverpool", "20 Sep 2026", 0, 1)

    assert stats["source"] == "espn"
    assert stats["shots"] == [9, 12] and stats["shotsOnTarget"] == [2, 3]
    assert stats["passes"] == [382, 474]
    assert store[_key(mod)]["source"] == "espn"


def test_untagged_legacy_entry_is_rechecked(rs):
    mod, store, calls = rs
    store[_key(mod)] = {"shots": [9, 12], "shotsOnTarget": [4, 5]}  # old 40% guess
    calls["summary"] = ESPN_SUMMARY

    stats = mod.get_match_stats("Bournemouth", "Liverpool", "20 Sep 2026", 0, 1)
    assert stats["shotsOnTarget"] == [2, 3] and stats["source"] == "espn"


def test_estimate_kept_without_rerunning_the_llm_when_no_real_source(rs):
    mod, store, calls = rs
    store[_key(mod)] = {"shots": [15, 4], "shotsOnTarget": [6, 2], "source": "estimate"}
    calls["summary"] = None

    first = mod.get_match_stats("Bournemouth", "Liverpool", "20 Sep 2026", 0, 1)
    assert first["source"] == "estimate" and calls["llm"] == 0 and calls["espn"] == 1

    # Within the retry window the providers aren't asked again
    mod.get_match_stats("Bournemouth", "Liverpool", "20 Sep 2026", 0, 1)
    assert calls["espn"] == 1


def test_real_cached_stats_are_served_without_refetching(rs):
    mod, store, calls = rs
    store[_key(mod)] = {"shots": [9, 12], "shotsOnTarget": [2, 3], "source": "espn"}

    stats = mod.get_match_stats("Bournemouth", "Liverpool", "20 Sep 2026", 0, 1)
    assert stats["shots"] == [9, 12] and calls["espn"] == 0


def test_reverse_fixture_order_is_swapped(rs):
    mod, store, calls = rs
    calls["summary"] = ESPN_SUMMARY
    mod.get_match_stats("Bournemouth", "Liverpool", "20 Sep 2026", 0, 1)

    stats = mod.get_match_stats("Liverpool", "Bournemouth", "20 Sep 2026", 1, 0)
    assert stats["shots"] == [12, 9] and stats["source"] == "espn"


def _af_event(elapsed, ev_type, detail, team, player, assist=None):
    return {"time": {"elapsed": elapsed, "extra": None}, "type": ev_type, "detail": detail,
            "team": {"name": team}, "player": {"name": player}, "assist": {"name": assist}}


def test_api_football_var_cancelled_goal_is_dropped():
    from backend.roster_store import _parse_api_football_incidents
    raw = {"response": [
        _af_event(17, "Goal", "Normal Goal", "Andorra", "Guillaume Lopez"),
        _af_event(40, "Goal", "Normal Goal", "Malta", "Irvin Cardona", "Teddy Teuma"),
        _af_event(42, "Var", "Goal cancelled", "Malta", "Irvin Cardona"),
        _af_event(81, "Goal", "Normal Goal", "Malta", "Teddy Teuma"),
        _af_event(85, "Goal", "Missed Penalty", "Malta", "Ylyas Chouaref"),
        _af_event(86, "Var", "Penalty confirmed", "Malta", "Ylyas Chouaref"),
    ]}
    goals, _ = _parse_api_football_incidents(raw)
    assert [(g["scorer"], g["missed"]) for g in goals] == [
        ("Guillaume Lopez", False), ("Teddy Teuma", False), ("Ylyas Chouaref", True)]
