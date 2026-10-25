import pytest
from werkzeug.security import check_password_hash

import app as app_module
from database import db


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _count_users(email=None):
    conn = db.get_db()
    try:
        if email is None:
            return conn.execute("SELECT COUNT(*) FROM users").fetchone()[0]
        return conn.execute(
            "SELECT COUNT(*) FROM users WHERE email = ?", (email,)
        ).fetchone()[0]
    finally:
        conn.close()


def _post(client, name="Jane", email="jane@example.com", password="password123"):
    return client.post(
        "/register", data={"name": name, "email": email, "password": password}
    )


def test_get_renders_form(client):
    resp = client.get("/register")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert 'name="name"' in html
    assert 'name="email"' in html
    assert 'name="password"' in html
    assert 'action="/register"' in html


def test_valid_registration_redirects_and_hashes(client):
    resp = _post(client)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    user = db.get_user_by_email("jane@example.com")
    assert user is not None
    assert user["password_hash"] != "password123"
    assert check_password_hash(user["password_hash"], "password123")


def test_email_is_stripped_and_lowercased(client):
    _post(client, email="  Jane@Example.COM ")
    assert db.get_user_by_email("jane@example.com") is not None


def test_duplicate_email_case_insensitive(client):
    _post(client, email="new@x.com")
    resp = _post(client, email="New@X.com")
    assert resp.status_code == 200
    assert "already registered" in resp.get_data(as_text=True)
    assert _count_users("new@x.com") == 1


def test_demo_user_cannot_be_reregistered(client):
    before = _count_users()
    resp = _post(client, email="demo@spendly.com")
    assert resp.status_code == 200
    assert "already registered" in resp.get_data(as_text=True)
    assert _count_users() == before


def test_short_password_rejected(client):
    resp = _post(client, password="1234567")
    assert resp.status_code == 200
    assert "at least 8" in resp.get_data(as_text=True)
    assert db.get_user_by_email("jane@example.com") is None


@pytest.mark.parametrize("name", ["", "   "])
def test_blank_name_rejected(client, name):
    resp = _post(client, name=name)
    assert resp.status_code == 200
    assert "Name is required" in resp.get_data(as_text=True)
    assert db.get_user_by_email("jane@example.com") is None


def test_email_without_at_rejected(client):
    resp = _post(client, email="not-an-email")
    assert resp.status_code == 200
    assert "valid email" in resp.get_data(as_text=True)
    assert _count_users("not-an-email") == 0


def test_failed_submit_keeps_name_and_email_not_password(client):
    resp = _post(client, name="Jane", email="jane@example.com", password="short")
    html = resp.get_data(as_text=True)
    assert 'value="Jane"' in html
    assert 'value="jane@example.com"' in html
    assert "short\"" not in html.replace('placeholder="Min. 8 characters"', "")
