import re
from datetime import date

import pytest

import app as app_module
from database import db

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
USER_EMAIL = "filter@example.com"
USER_PASSWORD = "password123"

ERROR_WORDS = re.compile(r"invalid|error|must|before|after|cannot|not valid", re.I)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _login(client, email=USER_EMAIL, password=USER_PASSWORD):
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


@pytest.fixture
def user_id(client):
    """Fresh user with fixed-date expenses (total 100.00, 5 rows)."""
    uid = db.create_user("Filter User", USER_EMAIL, USER_PASSWORD)
    _add_expense(uid, 10.00, "Food", "2026-01-10", "JanTen")
    _add_expense(uid, 20.00, "Food", "2026-02-01", "FebFirst")
    _add_expense(uid, 30.00, "Bills", "2026-02-15", "FebMid")
    _add_expense(uid, 15.00, "Transport", "2026-02-28", "FebLast")
    _add_expense(uid, 25.00, "Bills", "2026-03-20", "MarTwenty")
    return uid


@pytest.fixture
def other_id(client):
    uid = db.create_user("Other User", "other@example.com", "password123")
    _add_expense(uid, 777.77, "Secret", "2026-02-10", "OtherSecret")
    return uid


def _get(client, **params):
    _login(client)
    resp = client.get("/profile", query_string=params)
    return resp, resp.get_data(as_text=True)


# ------------------------------------------------------------ db helpers

class TestHelpers:
    def test_summary_no_dates_is_all_time(self, user_id):
        s = db.get_expense_summary(user_id)
        assert s["count"] == 5
        assert s["total"] == pytest.approx(100.00)

    def test_summary_inclusive_range(self, user_id):
        s = db.get_expense_summary(user_id, start_date="2026-02-01", end_date="2026-02-28")
        assert s["count"] == 3
        assert s["total"] == pytest.approx(65.00)

    def test_summary_start_only(self, user_id):
        s = db.get_expense_summary(user_id, start_date="2026-02-15")
        assert s["count"] == 3
        assert s["total"] == pytest.approx(70.00)

    def test_summary_end_only(self, user_id):
        s = db.get_expense_summary(user_id, end_date="2026-02-01")
        assert s["count"] == 2
        assert s["total"] == pytest.approx(30.00)

    def test_summary_single_day_range(self, user_id):
        s = db.get_expense_summary(user_id, start_date="2026-02-15", end_date="2026-02-15")
        assert s["count"] == 1
        assert s["total"] == pytest.approx(30.00)

    def test_summary_empty_range(self, user_id):
        s = db.get_expense_summary(user_id, start_date="2025-01-01", end_date="2025-12-31")
        assert s["count"] == 0
        assert s["total"] == 0

    def test_category_totals_filtered(self, user_id):
        rows = db.get_category_totals(user_id, start_date="2026-02-01", end_date="2026-02-28")
        got = {r["category"]: r["total"] for r in rows}
        assert got == {"Bills": pytest.approx(30.00),
                       "Food": pytest.approx(20.00),
                       "Transport": pytest.approx(15.00)}
        totals = [r["total"] for r in rows]
        assert totals == sorted(totals, reverse=True)

    def test_category_totals_empty_range(self, user_id):
        assert db.get_category_totals(user_id, start_date="2030-01-01") == []

    def test_recent_expenses_filtered_and_ordered(self, user_id):
        rows = db.get_recent_expenses(user_id, start_date="2026-02-01", end_date="2026-03-01")
        assert [r["description"] for r in rows] == ["FebLast", "FebMid", "FebFirst"]

    def test_recent_expenses_limit_with_range(self, user_id):
        rows = db.get_recent_expenses(user_id, limit=2, start_date="2026-02-01")
        assert [r["description"] for r in rows] == ["MarTwenty", "FebLast"]

    def test_recent_expenses_empty_range(self, user_id):
        assert db.get_recent_expenses(user_id, end_date="2000-01-01") == []

    def test_helpers_isolate_users_under_filter(self, user_id, other_id):
        s = db.get_expense_summary(user_id, start_date="2026-02-01", end_date="2026-02-28")
        assert s["total"] == pytest.approx(65.00)
        cats = [r["category"] for r in db.get_category_totals(user_id, start_date="2026-02-01")]
        assert "Secret" not in cats
        descs = [r["description"] for r in db.get_recent_expenses(user_id, start_date="2026-02-01")]
        assert "OtherSecret" not in descs
        o = db.get_expense_summary(other_id, start_date="2026-02-01", end_date="2026-02-28")
        assert o["count"] == 1 and o["total"] == pytest.approx(777.77)

    def test_sql_injection_in_date_is_harmless(self, user_id):
        payload = "2026-01-01' OR '1'='1"
        s = db.get_expense_summary(user_id, start_date=payload)
        assert s["count"] <= 5
        assert s["total"] <= 100.00
        descs = [r["description"] for r in db.get_recent_expenses(user_id, end_date=payload)]
        assert "OtherSecret" not in descs
        assert db.get_expense_summary(user_id)["count"] == 5


# ------------------------------------------------------------ route

class TestProfileRoute:
    def test_logged_out_redirects_to_login(self, client):
        resp = client.get("/profile", query_string={"start": "2026-01-01"})
        assert resp.status_code == 302
        assert resp.headers["Location"].endswith("/login")

    def test_no_params_shows_all_time(self, client, user_id):
        resp, html = _get(client)
        assert resp.status_code == 200
        assert "100.00" in html
        for d in ("JanTen", "FebFirst", "FebMid", "FebLast", "MarTwenty"):
            assert d in html

    def test_demo_user_no_params_unchanged(self, client):
        _login(client, DEMO_EMAIL, DEMO_PASSWORD)
        resp = client.get("/profile")
        html = resp.get_data(as_text=True)
        assert resp.status_code == 200
        assert "323.04" in html

    def test_full_range_filters_everything(self, client, user_id):
        resp, html = _get(client, start="2026-02-01", end="2026-02-28")
        assert resp.status_code == 200
        assert "65.00" in html
        for d in ("FebFirst", "FebMid", "FebLast"):
            assert d in html
        for d in ("JanTen", "MarTwenty"):
            assert d not in html
        assert "100.00" not in html

    def test_boundary_dates_included(self, client, user_id):
        _, html = _get(client, start="2026-02-01", end="2026-02-28")
        assert "FebFirst" in html and "FebLast" in html

    def test_day_outside_boundary_excluded(self, client, user_id):
        _, html = _get(client, start="2026-02-02", end="2026-02-27")
        assert "FebFirst" not in html
        assert "FebLast" not in html
        assert "FebMid" in html

    def test_start_only(self, client, user_id):
        resp, html = _get(client, start="2026-02-15")
        assert resp.status_code == 200
        assert "70.00" in html
        assert "FebMid" in html and "MarTwenty" in html
        assert "JanTen" not in html and "FebFirst" not in html

    def test_end_only(self, client, user_id):
        resp, html = _get(client, end="2026-02-01")
        assert resp.status_code == 200
        assert "30.00" in html
        assert "JanTen" in html and "FebFirst" in html
        assert "FebMid" not in html and "MarTwenty" not in html

    def test_blank_params_treated_as_unbounded(self, client, user_id):
        resp, html = _get(client, start="", end="")
        assert resp.status_code == 200
        assert "100.00" in html
        assert "JanTen" in html and "MarTwenty" in html

    def test_category_breakdown_reflects_filter(self, client, user_id):
        _, html = _get(client, start="2026-03-01", end="2026-03-31")
        assert "Bills" in html
        assert "Transport" not in html
        assert "25.00" in html

    def test_empty_range_shows_zero_and_message(self, client, user_id):
        resp, html = _get(client, start="2025-01-01", end="2025-12-31")
        assert resp.status_code == 200
        assert "0.00" in html
        assert "No expenses in this date range." in html
        assert "No expenses yet." not in html
        assert "<table" not in html

    def test_new_user_without_filter_shows_no_expenses_yet(self, client):
        db.create_user("Empty", USER_EMAIL, USER_PASSWORD)
        resp, html = _get(client)
        assert resp.status_code == 200
        assert "No expenses yet." in html
        assert "No expenses in this date range." not in html

    def test_date_inputs_keep_selected_values(self, client, user_id):
        _, html = _get(client, start="2026-02-01", end="2026-02-28")
        assert 'type="date"' in html
        assert 'value="2026-02-01"' in html
        assert 'value="2026-02-28"' in html

    def test_filter_form_is_plain_get(self, client, user_id):
        _, html = _get(client)
        form = re.search(r"<form[^>]*>", html, re.I)
        assert form, "Expected a filter form"
        assert re.search(r'method="get"', form.group(0), re.I)
        assert 'action="/profile"' in form.group(0)

    @pytest.mark.parametrize("params", [
        {"start": "abc"},
        {"end": "abc"},
        {"start": "2026-13-45"},
        {"start": "2026/02/01"},
        {"start": "02-01-2026", "end": "nope"},
        {"start": "' OR 1=1 --"},
    ])
    def test_invalid_date_returns_200_with_error(self, client, user_id, params):
        resp, html = _get(client, **params)
        assert resp.status_code == 200, "Invalid input must not crash"
        assert ERROR_WORDS.search(html), "Expected an inline error message"

    def test_invalid_start_is_ignored_valid_end_still_applies(self, client, user_id):
        resp, html = _get(client, start="abc", end="2026-02-01")
        assert resp.status_code == 200
        assert "JanTen" in html and "FebFirst" in html
        assert "FebMid" not in html and "MarTwenty" not in html

    def test_invalid_start_only_shows_unfiltered(self, client, user_id):
        _, html = _get(client, start="abc")
        assert "100.00" in html
        assert "JanTen" in html and "MarTwenty" in html

    def test_start_after_end_shows_error_and_does_not_filter(self, client, user_id):
        resp, html = _get(client, start="2026-03-01", end="2026-02-01")
        assert resp.status_code == 200
        assert ERROR_WORDS.search(html), "Expected an inline error message"
        assert "100.00" in html
        for d in ("JanTen", "FebFirst", "FebMid", "FebLast", "MarTwenty"):
            assert d in html

    def test_start_equal_end_is_valid(self, client, user_id):
        resp, html = _get(client, start="2026-02-15", end="2026-02-15")
        assert resp.status_code == 200
        assert "FebMid" in html
        assert "FebFirst" not in html and "FebLast" not in html
        assert "30.00" in html

    def test_valid_filter_shows_no_error(self, client, user_id):
        _, html = _get(client, start="2026-02-01", end="2026-02-28")
        assert "Invalid" not in html

    def test_range_label_shows_active_dates(self, client, user_id):
        _, html = _get(client, start="2026-02-01", end="2026-02-28")
        assert html.count("2026-02-01") >= 2, "Expected input value plus a range label"

    def test_preset_links_present(self, client, user_id):
        _, html = _get(client)
        for label in ("This month", "Last 30 days", "All time"):
            assert label in html, f"Missing preset: {label}"

    def test_preset_this_month_range(self, client, user_id):
        _, html = _get(client)
        today = date.today()
        first = today.replace(day=1).isoformat()
        link = re.search(r'<a[^>]*href="([^"]*)"[^>]*>\s*This month', html)
        assert link, "This month link not found"
        href = link.group(1).replace("&amp;", "&")
        assert href.startswith("/profile")
        assert f"start={first}" in href
        assert "end=" in href

    def test_preset_last_30_days_range(self, client, user_id):
        _, html = _get(client)
        today = date.today()
        link = re.search(r'<a[^>]*href="([^"]*)"[^>]*>\s*Last 30 days', html)
        assert link, "Last 30 days link not found"
        href = link.group(1).replace("&amp;", "&")
        m = re.search(r"start=(\d{4}-\d{2}-\d{2})", href)
        assert m, "Expected a start date"
        start = date.fromisoformat(m.group(1))
        assert 29 <= (today - start).days <= 30
        assert f"end={today.isoformat()}" in href

    def test_preset_all_time_has_no_dates(self, client, user_id):
        _, html = _get(client)
        link = re.search(r'<a[^>]*href="([^"]*)"[^>]*>\s*All time', html)
        assert link, "All time link not found"
        href = link.group(1)
        assert href.startswith("/profile")
        assert "start=" not in href and "end=" not in href

    def test_clear_link_present(self, client, user_id):
        _, html = _get(client, start="2026-02-01")
        assert "Clear" in html

    @pytest.mark.parametrize("params", [
        {},
        {"start": "2026-02-01", "end": "2026-02-28"},
        {"start": "2026-02-10"},
        {"end": "2026-12-31"},
        {"start": "2026-03-01", "end": "2026-01-01"},
        {"start": "abc"},
    ])
    def test_user_isolation_under_any_filter(self, client, user_id, other_id, params):
        _, html = _get(client, **params)
        assert "OtherSecret" not in html
        assert "777.77" not in html
        assert "Secret" not in html

    def test_other_user_sees_only_own_data_under_filter(self, client, user_id, other_id):
        _login(client, "other@example.com", "password123")
        html = client.get("/profile", query_string={"start": "2026-02-01",
                                                    "end": "2026-02-28"}).get_data(as_text=True)
        assert "OtherSecret" in html
        assert "777.77" in html
        assert "FebMid" not in html

    def test_password_hash_not_leaked_with_filter(self, client, user_id):
        _, html = _get(client, start="2026-02-01")
        assert "pbkdf2" not in html and "scrypt" not in html and "password_hash" not in html
