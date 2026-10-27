from datetime import date, timedelta

import pytest

import app as app_module
from database import db

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
USER_EMAIL = "filter@example.com"


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


def _new_user(name="Filter User", email=USER_EMAIL):
    return db.create_user(name, email, "password123"), email


@pytest.fixture
def user(client):
    """Fresh user with fixed-date expenses, already logged in."""
    uid, email = _new_user()
    _add_expense(uid, 10.00, "Food", "2024-01-01", "jan-first")
    _add_expense(uid, 20.00, "Transport", "2024-01-15", "jan-mid")
    _add_expense(uid, 30.00, "Food", "2024-01-31", "jan-last")
    _add_expense(uid, 40.00, "Bills", "2024-02-10", "feb-tenth")
    _login(client, email, "password123")
    return uid


def _get(client, query=""):
    resp = client.get("/profile" + query)
    assert resp.status_code == 200
    return resp.get_data(as_text=True)


# ---------------------------------------------------------------- route

def test_no_params_shows_everything_for_demo(client):
    _login(client)
    html = _get(client)
    assert "323.04" in html
    assert "Recent expenses" in html


def test_both_bounds_filter(client, user):
    html = _get(client, "?start=2024-01-10&end=2024-01-31")
    assert "jan-mid" in html and "jan-last" in html
    assert "jan-first" not in html and "feb-tenth" not in html
    assert "50.00" in html
    assert "Expenses in range" in html


def test_start_only(client, user):
    html = _get(client, "?start=2024-01-31")
    assert "jan-last" in html and "feb-tenth" in html
    assert "jan-mid" not in html


def test_end_only(client, user):
    html = _get(client, "?end=2024-01-15")
    assert "jan-first" in html and "jan-mid" in html
    assert "jan-last" not in html


def test_boundaries_inclusive(client, user):
    html = _get(client, "?start=2024-01-01&end=2024-01-31")
    assert "jan-first" in html and "jan-last" in html
    assert "60.00" in html


def test_single_day_range(client, user):
    html = _get(client, "?start=2024-01-15&end=2024-01-15")
    assert "jan-mid" in html
    assert "jan-first" not in html and "jan-last" not in html


def test_category_totals_respect_filter(client, user):
    html = _get(client, "?start=2024-02-01&end=2024-02-28")
    assert "Bills" in html
    assert "Transport" not in html
    assert "Food" not in html


def test_empty_range_for_user_with_expenses(client, user):
    html = _get(client, "?start=2025-01-01&end=2025-01-31")
    assert "No expenses in this date range." in html
    assert "No expenses yet." not in html
    assert "0.00" in html


def test_new_user_without_expenses_sees_no_expenses_yet(client):
    _, email = _new_user("Empty", "empty@example.com")
    _login(client, email, "password123")
    assert "No expenses yet." in _get(client)
    html = _get(client, "?start=2024-01-01&end=2024-01-31")
    assert "No expenses yet." in html
    assert "No expenses in this date range." not in html


def test_invalid_start_is_ignored_with_error(client, user):
    html = _get(client, "?start=abc")
    assert "Start date is not a valid date" in html
    assert "jan-first" in html and "feb-tenth" in html


def test_invalid_start_keeps_valid_end(client, user):
    html = _get(client, "?start=abc&end=2024-01-15")
    assert "Start date is not a valid date" in html
    assert "jan-mid" in html and "jan-last" not in html


@pytest.mark.parametrize("value", ["2024-13-45", "2024-1-5", "2024-02-30"])
def test_non_canonical_or_impossible_dates_rejected(client, user, value):
    html = _get(client, f"?end={value}")
    assert "End date is not a valid date" in html
    assert "feb-tenth" in html


def test_both_invalid(client, user):
    html = _get(client, "?start=x&end=y")
    assert "Start date is not a valid date" in html
    assert "End date is not a valid date" in html
    assert "jan-first" in html and "feb-tenth" in html


def test_start_after_end_shows_error_and_does_not_filter(client, user):
    html = _get(client, "?start=2024-02-01&end=2024-01-01")
    assert "Start date must not be after end date." in html
    assert "jan-first" in html and "feb-tenth" in html


def test_blank_params_are_no_filter(client, user):
    html = _get(client, "?start=&end=")
    assert "filter-error" not in html
    assert "Recent expenses" in html
    assert "jan-first" in html


def test_inputs_keep_selected_values(client, user):
    html = _get(client, "?start=2024-01-01&end=2024-01-31")
    assert 'value="2024-01-01"' in html
    assert 'value="2024-01-31"' in html


def test_preset_links(client, user):
    html = _get(client)
    today = date.today()
    assert f"start={today.replace(day=1).isoformat()}&amp;end={today.isoformat()}" in html
    assert f"start={(today - timedelta(days=29)).isoformat()}&amp;end={today.isoformat()}" in html
    assert 'href="/profile"' in html


def test_user_isolation_under_filter(client, user):
    other_id, _ = _new_user("Other", "other@example.com")
    _add_expense(other_id, 999.00, "Other", "2024-01-15", "other-secret")
    html = _get(client, "?start=2024-01-01&end=2024-01-31")
    assert "other-secret" not in html
    assert "999.00" not in html


def test_logged_out_with_params_redirects(client):
    resp = client.get("/profile?start=2024-01-01")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_sql_injection_string_is_just_invalid(client, user):
    html = _get(client, "?start=' OR 1=1 --")
    assert "Start date is not a valid date" in html


# ---------------------------------------------------------------- db helpers

def test_helpers_combine_date_range_and_limit(client, user):
    rows = db.get_recent_expenses(
        user, limit=2, start_date="2024-01-01", end_date="2024-01-31"
    )
    assert [r["description"] for r in rows] == ["jan-last", "jan-mid"]
    summary = db.get_expense_summary(user, "2024-01-01", "2024-01-31")
    assert summary == {"total": 60.0, "count": 3}
    cats = {r["category"]: r["total"] for r in db.get_category_totals(user, end_date="2024-01-31")}
    assert cats == {"Food": 40.0, "Transport": 20.0}
