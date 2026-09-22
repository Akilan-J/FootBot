"""End-to-end API tests against the real FastAPI app.

Marked slow: importing backend.main loads the sentence-transformers model and the
FAISS index (~15s). Run with `pytest -m slow` (or `pytest -m ""` for everything).
"""

import pytest

pytestmark = pytest.mark.slow


@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from backend.main import app

    # Not used as a context manager on purpose: that would fire the startup event,
    # which kicks off the background BBC auto-crawl.
    return TestClient(app)


@pytest.fixture
def auth(client, db):
    """Registers a user against the throwaway DB and returns its auth header."""
    resp = client.post("/register", json={"username": "coach", "password": "a-good-password"})
    assert resp.status_code == 201, resp.text
    return {"X-User-Token": resp.json()["token"]}


class TestWebUI:
    def test_root_serves_the_web_ui(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "FootBot" in resp.text

    def test_openapi_docs_are_available(self, client):
        assert client.get("/docs").status_code == 200


class TestAuth:
    def test_register_then_login_issues_working_tokens(self, client, db):
        client.post("/register", json={"username": "coach", "password": "a-good-password"})
        resp = client.post("/login", json={"username": "coach", "password": "a-good-password"})

        assert resp.status_code == 200
        assert client.get("/sessions", headers={"X-User-Token": resp.json()["token"]}).status_code == 200

    def test_short_passwords_are_rejected(self, client, db):
        resp = client.post("/register", json={"username": "coach", "password": "short"})
        assert resp.status_code == 422

    def test_login_with_a_bad_password_is_unauthorized(self, client, db):
        client.post("/register", json={"username": "coach", "password": "a-good-password"})
        resp = client.post("/login", json={"username": "coach", "password": "wrong-password"})
        assert resp.status_code == 401

    def test_protected_endpoint_requires_a_token(self, client, db):
        assert client.get("/sessions").status_code == 401

    def test_protected_endpoint_rejects_a_bogus_token(self, client, db):
        resp = client.get("/sessions", headers={"X-User-Token": "not-a-real-token"})
        assert resp.status_code == 401

    def test_logout_revokes_the_token(self, client, auth):
        assert client.get("/sessions", headers=auth).status_code == 200

        assert client.post("/logout", headers=auth).status_code == 200
        assert client.get("/sessions", headers=auth).status_code == 401

    def test_one_user_cannot_read_another_users_session(self, client, db, auth):
        from backend import database

        owner_token = auth["X-User-Token"]
        owner_id = database.resolve_session_token(owner_token)
        session_id = database.create_session("Private tactics", user_id=owner_id)

        intruder = client.post(
            "/register", json={"username": "intruder", "password": "a-good-password"}
        ).json()["token"]

        resp = client.get(
            f"/sessions/{session_id}/messages", headers={"X-User-Token": intruder}
        )
        # Regression: this used to be re-wrapped as a 500 by a catch-all handler.
        assert resp.status_code == 403


class TestPlayerImage:
    def test_directory_traversal_is_not_served(self, client):
        resp = client.get("/player/image", params={"filename": "../../../../etc/passwd"})

        assert resp.status_code == 200
        # Falls through to the silhouette rather than leaking a system file.
        assert resp.headers["content-type"].startswith("image/")
        assert b"root:" not in resp.content

    def test_unknown_player_falls_back_to_a_silhouette(self, client):
        resp = client.get("/player/image", params={"name": "Nobody At All", "pos": "GK"})

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("image/")

    def test_unknown_player_without_a_position_still_returns_an_image(self, client):
        """Regression: a cached roster entry without a "name" key raised a KeyError 500."""
        resp = client.get("/player/image", params={"name": "Nobody At All"})
        assert resp.status_code == 200


class TestTeamLogo:
    def test_cached_team_redirects_to_its_crest(self, client, db, monkeypatch):
        from backend.loaders import api_football_client as afc

        monkeypatch.setattr(afc.settings, "API_FOOTBALL_KEY", "test-key")
        db.save_api_team_id("Arsenal", 42)

        resp = client.get("/team/logo", params={"team_name": "Arsenal"}, follow_redirects=False)

        assert resp.status_code == 307
        assert resp.headers["location"].endswith("/teams/42.png")

    def test_uncached_team_answers_immediately_instead_of_blocking(
        self, client, db, monkeypatch
    ):
        """Regression: this endpoint used to run a live, rate-limited lookup inline,
        blocking for up to ~2 minutes. A page requests dozens of crests at once, so
        those held connections exhausted the browser's per-origin pool and stalled
        every other image on the page."""
        from backend.loaders import api_football_client as afc

        monkeypatch.setattr(afc.settings, "API_FOOTBALL_KEY", "test-key")

        def explode():
            raise AssertionError("the request path must not wait on the rate limiter")

        monkeypatch.setattr(afc, "_throttle_api_football_request", explode)
        prefetched = []
        monkeypatch.setattr(afc, "prefetch_team_id", prefetched.append)
        # main.py imports these names inside the handler, so patch the source module.
        monkeypatch.setattr(
            "backend.loaders.api_football_client.prefetch_team_id", prefetched.append
        )

        resp = client.get("/team/logo", params={"team_name": "Some Unknown Club"})

        assert resp.status_code == 404
        assert prefetched == ["Some Unknown Club"], "should queue a background lookup"


class TestHistoricalMatches:
    def test_listing_matches_returns_what_was_saved(self, client, db):
        db.save_historical_match("Arsenal", "Chelsea", 2, 1, "22 Sep 2024", "Premier League")

        resp = client.get("/historical-matches")

        assert resp.status_code == 200
        assert any(m["home_team"] == "Arsenal" for m in resp.json())
