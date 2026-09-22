"""API-Football team resolution: shorthand aliases, caching and the rate limiter.

No test here touches the network - the HTTP layer (_get) is always stubbed.
"""

import time

import pytest

from backend.loaders import api_football_client as afc
from backend.loaders.api_football_client import APIFootballClient


@pytest.fixture
def client(db, monkeypatch):
    """A client with an API key set, a clean negative cache, and no real HTTP."""
    monkeypatch.setattr(afc.settings, "API_FOOTBALL_KEY", "test-key")
    monkeypatch.setattr(afc, "_unresolved_teams", {})
    return APIFootballClient()


def _stub_teams_response(monkeypatch, client, by_name=None, by_search=None):
    """Stubs _get so 'name' lookups and 'search' lookups can return different results,
    mirroring API-Football's two-step resolution."""
    calls = []

    def fake_get(endpoint, params=None):
        params = params or {}
        calls.append(params)
        if "name" in params:
            return {"response": by_name} if by_name else {"response": []}
        return {"response": by_search} if by_search else {"response": []}

    monkeypatch.setattr(client, "_get", fake_get)
    return calls


def _team(team_id, name):
    return {"team": {"id": team_id, "name": name}}


def test_resolves_a_team_by_exact_name(client, monkeypatch):
    _stub_teams_response(monkeypatch, client, by_name=[_team(42, "Arsenal")])

    assert client.resolve_team_id("Arsenal") == 42


@pytest.mark.parametrize(
    "shorthand,official",
    [
        ("Man City", "Manchester City"),
        ("Man Utd", "Manchester United"),
        ("Man United", "Manchester United"),
        ("Spurs", "Tottenham"),
        ("PSG", "Paris Saint Germain"),
        ("Barca", "Barcelona"),
    ],
)
def test_shorthand_club_names_are_queried_under_their_official_name(
    client, monkeypatch, shorthand, official
):
    """Regression: API-Football has no alias handling, so searching "Man City" used to
    return an unrelated Ghanaian club ("Techiman City") instead of Manchester City."""
    calls = _stub_teams_response(monkeypatch, client, by_name=[_team(50, official)])

    client.resolve_team_id(shorthand)

    assert calls, "expected a lookup to be attempted"
    assert calls[0]["name"] == official


def test_shorthand_lookup_is_case_insensitive(client, monkeypatch):
    calls = _stub_teams_response(monkeypatch, client, by_name=[_team(50, "Manchester City")])

    client.resolve_team_id("MAN CITY")

    assert calls[0]["name"] == "Manchester City"


def test_resolved_id_is_cached_and_skips_further_lookups(client, monkeypatch):
    calls = _stub_teams_response(monkeypatch, client, by_name=[_team(42, "Arsenal")])

    assert client.resolve_team_id("Arsenal") == 42
    first_call_count = len(calls)
    assert client.resolve_team_id("Arsenal") == 42

    assert len(calls) == first_call_count, "second lookup should have been served from cache"


def test_shorthand_and_official_name_share_one_cache_entry(client, monkeypatch):
    calls = _stub_teams_response(monkeypatch, client, by_name=[_team(50, "Manchester City")])

    assert client.resolve_team_id("Manchester City") == 50
    calls.clear()

    assert client.resolve_team_id("Man City") == 50
    assert calls == [], "alias should hit the cache entry stored under the official name"


def test_unresolvable_team_returns_none(client, monkeypatch):
    _stub_teams_response(monkeypatch, client)

    assert client.resolve_team_id("Not A Real Team") is None


def test_failed_lookup_is_not_retried_during_its_cooldown(client, monkeypatch):
    """Failures are cached briefly so they don't keep spending rate-limit budget."""
    calls = _stub_teams_response(monkeypatch, client)

    assert client.resolve_team_id("Not A Real Team") is None
    assert calls, "first attempt should hit the API"
    calls.clear()

    assert client.resolve_team_id("Not A Real Team") is None
    assert calls == [], "second attempt should be short-circuited by the negative cache"


def test_failed_lookup_is_retried_after_the_cooldown_expires(client, monkeypatch):
    calls = _stub_teams_response(monkeypatch, client)
    client.resolve_team_id("Not A Real Team")
    calls.clear()

    # Pretend the failure happened longer ago than the cooldown allows.
    stale = time.time() - (afc._UNRESOLVED_TEAM_COOLDOWN_SECONDS + 1)
    afc._unresolved_teams["not a real team"] = stale

    client.resolve_team_id("Not A Real Team")
    assert calls, "cooldown had expired, so the API should be tried again"


def test_empty_team_name_resolves_to_nothing(client):
    assert client.resolve_team_id("") is None
    assert client.resolve_team_id("   ") is None


class TestRateLimiter:
    """API-Football's free tier allows 10 requests/minute; we budget 9."""

    @pytest.fixture(autouse=True)
    def _clean_window(self, monkeypatch):
        monkeypatch.setattr(afc, "_REQUEST_TIMESTAMPS", afc.collections.deque())

    def test_requests_within_budget_do_not_block(self, monkeypatch):
        slept = []
        monkeypatch.setattr(afc.time, "sleep", lambda s: slept.append(s))

        for _ in range(afc._MAX_REQUESTS_PER_MINUTE):
            afc._throttle_api_football_request()

        assert slept == []
        assert len(afc._REQUEST_TIMESTAMPS) == afc._MAX_REQUESTS_PER_MINUTE

    def test_exceeding_the_budget_waits_for_the_window_to_free_up(self, monkeypatch):
        """Regression: a burst of logo lookups used to fire uncoordinated and 429."""
        slept = []

        def fake_sleep(seconds):
            slept.append(seconds)
            # Simulate time passing so the oldest timestamp falls out of the window.
            afc._REQUEST_TIMESTAMPS.popleft()

        monkeypatch.setattr(afc.time, "sleep", fake_sleep)

        for _ in range(afc._MAX_REQUESTS_PER_MINUTE + 1):
            afc._throttle_api_football_request()

        assert len(slept) == 1, "the request over budget should have waited exactly once"
        assert 0 < slept[0] <= 61

    def test_timestamps_older_than_a_minute_are_evicted(self, monkeypatch):
        monkeypatch.setattr(afc.time, "sleep", lambda s: None)
        afc._REQUEST_TIMESTAMPS.extend([time.time() - 120] * afc._MAX_REQUESTS_PER_MINUTE)

        afc._throttle_api_football_request()

        # The stale entries are dropped, leaving only the request just made.
        assert len(afc._REQUEST_TIMESTAMPS) == 1

    def test_every_api_request_goes_through_the_throttle(self, client, monkeypatch):
        """The limiter is only useful if _get actually calls it."""
        throttled = []
        monkeypatch.setattr(
            afc, "_throttle_api_football_request", lambda: throttled.append(1)
        )

        class _Response:
            status_code = 200

            @staticmethod
            def json():
                return {"response": []}

        monkeypatch.setattr(afc.requests, "get", lambda *a, **kw: _Response())

        client._get("teams", params={"name": "Arsenal"})

        assert throttled == [1]
