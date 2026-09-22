"""User registration and the opaque session-token layer."""

import pytest


def test_register_returns_a_user_id_and_authenticates(db):
    user_id = db.register_user("coach", "a-good-password")
    assert user_id

    user = db.authenticate_user("coach", "a-good-password")
    assert user is not None
    assert user["id"] == user_id


def test_register_rejects_a_duplicate_username(db):
    assert db.register_user("coach", "a-good-password")
    assert db.register_user("coach", "another-password") is None


def test_authenticate_rejects_a_wrong_password(db):
    db.register_user("coach", "a-good-password")
    assert db.authenticate_user("coach", "wrong-password") is None


def test_authenticate_rejects_an_unknown_user(db):
    assert db.authenticate_user("nobody", "a-good-password") is None


def test_password_is_not_stored_in_plaintext(db):
    db.register_user("coach", "a-good-password")

    conn = db.get_db_connection()
    row = conn.execute("SELECT * FROM users WHERE username = 'coach'").fetchone()
    conn.close()

    assert "a-good-password" not in " ".join(str(v) for v in dict(row).values())


def test_session_token_is_opaque_and_not_the_user_id(db):
    """Regression: X-User-Token used to be the user's permanent DB row id."""
    user_id = db.register_user("coach", "a-good-password")
    token = db.create_session_token(user_id)

    assert token != user_id
    assert len(token) >= 32
    assert db.resolve_session_token(token) == user_id


def test_each_login_mints_a_distinct_token(db):
    user_id = db.register_user("coach", "a-good-password")

    first = db.create_session_token(user_id)
    second = db.create_session_token(user_id)

    assert first != second
    # Both stay valid - a user can be signed in on several devices at once.
    assert db.resolve_session_token(first) == user_id
    assert db.resolve_session_token(second) == user_id


def test_revoking_one_token_leaves_the_others_valid(db):
    user_id = db.register_user("coach", "a-good-password")
    first = db.create_session_token(user_id)
    second = db.create_session_token(user_id)

    db.delete_session_token(first)

    assert db.resolve_session_token(first) is None
    assert db.resolve_session_token(second) == user_id


def test_expired_token_does_not_resolve(db):
    user_id = db.register_user("coach", "a-good-password")
    token = db.create_session_token(user_id, ttl_seconds=-1)

    assert db.resolve_session_token(token) is None


@pytest.mark.parametrize("token", ["", None, "not-a-real-token"])
def test_garbage_tokens_resolve_to_nothing(db, token):
    assert db.resolve_session_token(token) is None


def test_session_ownership_is_enforced(db):
    owner = db.register_user("owner", "a-good-password")
    other = db.register_user("other", "a-good-password")
    session_id = db.create_session("My tactics", user_id=owner)

    assert db.verify_session_owner(session_id, owner) is True
    assert db.verify_session_owner(session_id, other) is False


def test_sessions_are_listed_per_user(db):
    owner = db.register_user("owner", "a-good-password")
    other = db.register_user("other", "a-good-password")
    db.create_session("My tactics", user_id=owner)

    assert len(db.get_sessions(owner)) == 1
    assert db.get_sessions(other) == []
