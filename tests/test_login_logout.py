import pytest

import app as app_module
from database import db

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
GENERIC_ERROR = "Invalid email or password."


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def _session(client):
    with client.session_transaction() as sess:
        return dict(sess)


def test_login_page_renders_with_url_for_action(client):
    resp = client.get("/login")
    assert resp.status_code == 200
    assert 'action="/login"' in resp.get_data(as_text=True)


def test_demo_login_redirects_and_sets_session(client):
    resp = _login(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    assert _session(client).get("user_id") is not None


def test_navbar_when_logged_in(client):
    _login(client)
    html = client.get("/").get_data(as_text=True)
    assert "Demo User" in html
    assert "Sign out" in html
    assert "Sign in" not in html
    assert "Get started" not in html


def test_wrong_password_and_unknown_email_give_same_error(client):
    bad_pw = _login(client, password="wrongpass")
    unknown = _login(client, email="nobody@example.com")
    for resp in (bad_pw, unknown):
        assert resp.status_code == 200
        assert GENERIC_ERROR in resp.get_data(as_text=True)
        assert "user_id" not in _session(client)


def test_email_is_trimmed_and_case_insensitive(client):
    resp = _login(client, email="  DEMO@Spendly.com ")
    assert resp.status_code == 302
    assert "user_id" in _session(client)


def test_failed_login_keeps_email_not_password(client):
    html = _login(client, password="wrongpass").get_data(as_text=True)
    assert f'value="{DEMO_EMAIL}"' in html
    assert "wrongpass" not in html


def test_registered_user_can_log_in(client):
    client.post(
        "/register",
        data={"name": "Jane", "email": "jane@example.com", "password": "password123"},
    )
    resp = _login(client, email="jane@example.com", password="password123")
    assert resp.status_code == 302
    assert "user_id" in _session(client)


def test_login_redirects_when_already_logged_in(client):
    _login(client)
    for resp in (client.get("/login"), _login(client)):
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/")


def test_logout_clears_session_and_navbar(client):
    _login(client)
    resp = client.get("/logout")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    assert _session(client) == {}
    html = client.get("/").get_data(as_text=True)
    assert "Sign in" in html
    assert "Get started" in html
    assert "Sign out" not in html


def test_logout_when_logged_out(client):
    resp = client.get("/logout")
    assert resp.status_code == 302


def test_session_holds_only_user_id(client):
    _login(client)
    assert list(_session(client)) == ["user_id"]


def test_stale_session_user_is_treated_as_logged_out(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 99999
    resp = client.get("/login")
    assert resp.status_code == 200
    assert "user_id" not in _session(client)


def test_empty_fields_show_generic_error(client):
    resp = _login(client, email="", password="")
    assert resp.status_code == 200
    assert GENERIC_ERROR in resp.get_data(as_text=True)
