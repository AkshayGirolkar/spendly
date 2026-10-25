import pytest

import app as app_module
from database import db

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def _add_expense(user_id, amount, category, day, description):
    conn = db.get_db()
    try:
        conn.execute(
            "INSERT INTO expenses (user_id, amount, category, date, description) "
            "VALUES (?, ?, ?, ?, ?)",
            (user_id, amount, category, day, description),
        )
        conn.commit()
    finally:
        conn.close()


def _demo_id():
    return db.get_user_by_email(DEMO_EMAIL)["id"]


def _new_user(name="Second User", email="second@example.com"):
    return db.create_user(name, email, "password123"), email


# ---------------------------------------------------------------- route

def test_logged_out_redirects_to_login(client):
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_stale_session_redirects_to_login(client):
    with client.session_transaction() as sess:
        sess["user_id"] = 9999
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_demo_profile_renders_account_and_totals(client):
    _login(client)
    resp = client.get("/profile")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "Demo User" in html
    assert DEMO_EMAIL in html
    assert "323.04" in html
    assert "Member since" in html
    assert 'href="/profile"' in html
    assert "css/profile.css" in html


def test_profile_never_leaks_password_hash(client):
    _login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert "pbkdf2" not in html
    assert "scrypt" not in html
    assert "password_hash" not in html


def test_categories_highest_first(client):
    _login(client)
    html = client.get("/profile").get_data(as_text=True)
    # Bills 120.00 > Shopping 64.99 > Transport 40.00
    assert html.index("Bills") < html.index("Shopping") < html.index("Transport")


def test_recent_expenses_newest_first(client):
    _login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert html.index("Groceries") < html.index("Lunch at cafe")


def test_empty_state_for_new_user(client):
    _new_user()
    _login(client, "second@example.com", "password123")
    resp = client.get("/profile")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "0.00" in html
    assert "No expenses yet" in html
    assert "<table" not in html


def test_users_only_see_their_own_expenses(client):
    other_id, other_email = _new_user()
    _add_expense(other_id, 777.77, "Other", "2026-01-05", "Secret purchase")

    _login(client)
    demo_html = client.get("/profile").get_data(as_text=True)
    assert "Secret purchase" not in demo_html
    assert "777.77" not in demo_html

    client.get("/logout")
    _login(client, other_email, "password123")
    other_html = client.get("/profile").get_data(as_text=True)
    assert "Secret purchase" in other_html
    assert "Lunch at cafe" not in other_html
    assert "323.04" not in other_html


# ---------------------------------------------------------- db helpers

def test_get_expense_summary(client):
    summary = db.get_expense_summary(_demo_id())
    assert summary["count"] == 8
    assert summary["total"] == pytest.approx(323.04)


def test_get_expense_summary_empty(client):
    user_id, _ = _new_user()
    assert db.get_expense_summary(user_id) == {"total": 0, "count": 0}


def test_get_category_totals_sorted_and_sum_to_total(client):
    rows = db.get_category_totals(_demo_id())
    totals = [r["total"] for r in rows]
    assert totals == sorted(totals, reverse=True)
    assert sum(totals) == pytest.approx(323.04)


def test_get_category_totals_scoped_by_user(client):
    user_id, _ = _new_user()
    assert db.get_category_totals(user_id) == []


def test_get_recent_expenses_limit_and_order(client):
    demo_id = _demo_id()
    rows = db.get_recent_expenses(demo_id, limit=3)
    assert len(rows) == 3
    dates = [r["date"] for r in rows]
    assert dates == sorted(dates, reverse=True)


def test_get_recent_expenses_id_tiebreak(client):
    user_id, _ = _new_user()
    _add_expense(user_id, 1.00, "Food", "2026-02-01", "first")
    _add_expense(user_id, 2.00, "Food", "2026-02-01", "second")
    rows = db.get_recent_expenses(user_id)
    assert [r["description"] for r in rows] == ["second", "first"]


def test_get_recent_expenses_scoped_by_user(client):
    user_id, _ = _new_user()
    assert db.get_recent_expenses(user_id) == []
