from datetime import date, timedelta

import pytest

import app as app_module
from database import db

DEMO_EMAIL = "demo@spendly.com"
DEMO_PASSWORD = "demo123"
CATEGORIES = [
    "Food", "Transport", "Bills", "Health", "Entertainment", "Shopping", "Other",
]
TODAY = date.today().isoformat()
TOMORROW = (date.today() + timedelta(days=1)).isoformat()


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "test.db"))
    db.init_db()
    db.seed_db()
    app_module.app.config["TESTING"] = True
    return app_module.app.test_client()


def _login(client, email=DEMO_EMAIL, password=DEMO_PASSWORD):
    return client.post("/login", data={"email": email, "password": password})


def _demo_id():
    return db.get_user_by_email(DEMO_EMAIL)["id"]


def _all_rows():
    conn = db.get_db()
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM expenses").fetchall()]
    finally:
        conn.close()


def _count():
    return len(_all_rows())


def _form(**overrides):
    data = {
        "amount": "12.50",
        "category": "Food",
        "date": TODAY,
        "description": "Lunch",
    }
    data.update(overrides)
    return data


def _post(client, **overrides):
    return client.post("/expenses/add", data=_form(**overrides))


# ---------------------------------------------------------------- auth guard

def test_logged_out_get_redirects_to_login(client):
    resp = client.get("/expenses/add")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_logged_out_post_redirects_to_login_and_inserts_nothing(client):
    before = _count()
    resp = client.post("/expenses/add", data=_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    assert _count() == before, "Logged-out POST must not insert"


# ---------------------------------------------------------------- GET form

def test_get_form_renders_with_today_prefilled(client):
    _login(client)
    resp = client.get("/expenses/add")
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert TODAY in html, "Date should default to today"
    assert 'name="amount"' in html
    assert 'name="date"' in html
    assert 'name="description"' in html
    assert 'name="category"' in html


def test_get_form_lists_all_seven_categories(client):
    _login(client)
    html = client.get("/expenses/add").get_data(as_text=True)
    for cat in CATEGORIES:
        assert cat in html, f"Category {cat} missing from dropdown"


# ---------------------------------------------------------------- happy path

def test_valid_post_redirects_to_profile_and_inserts_row(client):
    _login(client)
    before = _count()
    resp = _post(client, amount="45.67", category="Health",
                 date=TODAY, description="Pharmacy run")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    rows = _all_rows()
    assert len(rows) == before + 1
    row = [r for r in rows if r["description"] == "Pharmacy run"][0]
    assert row["user_id"] == _demo_id()
    assert float(row["amount"]) == pytest.approx(45.67)
    assert row["category"] == "Health"
    assert row["date"] == TODAY


def test_new_expense_appears_on_profile(client):
    _login(client)
    _post(client, description="UniqueMarkerXYZ")
    html = client.get("/profile").get_data(as_text=True)
    assert "UniqueMarkerXYZ" in html


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_description_stored_as_null(client, blank):
    _login(client)
    before = _count()
    resp = _post(client, description=blank)
    assert resp.status_code == 302
    rows = _all_rows()
    assert len(rows) == before + 1
    newest = max(rows, key=lambda r: r["id"])
    assert newest["description"] is None, "Blank description must be NULL"


def test_description_is_stripped(client):
    _login(client)
    _post(client, description="  padded  ")
    newest = max(_all_rows(), key=lambda r: r["id"])
    assert newest["description"] == "padded"


def test_tampered_user_id_form_field_is_ignored(client):
    other_id, _ = db.create_user("Other", "other@example.com", "password123"), None
    _login(client)
    resp = client.post("/expenses/add", data=_form(user_id=str(other_id),
                                                   description="Tamper"))
    assert resp.status_code == 302
    row = [r for r in _all_rows() if r["description"] == "Tamper"][0]
    assert row["user_id"] == _demo_id()
    assert row["user_id"] != other_id


def test_other_user_cannot_see_expense(client):
    _login(client)
    _post(client, description="PrivateMarker123")
    client.get("/logout")
    db.create_user("Second User", "second@example.com", "password123")
    _login(client, email="second@example.com", password="password123")
    html = client.get("/profile").get_data(as_text=True)
    assert "PrivateMarker123" not in html


# ---------------------------------------------------------------- rejections

def _assert_rejected(client, before, resp, preserved=()):
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200, "Rejection must re-render with 200"
    assert _count() == before, "No row may be inserted on rejection"
    assert "error" in html.lower(), "Expected an inline error"
    for value in preserved:
        assert value in html, f"Submitted value {value!r} not preserved"


@pytest.mark.parametrize(
    "amount",
    ["", "   ", "0", "0.00", "-5", "-0.01", "abc", "NaN", "nan", "inf",
     "-inf", "Infinity", "1.234", "12.505", "1000000.01", "1e7"],
)
def test_invalid_amount_rejected(client, amount):
    _login(client)
    before = _count()
    resp = _post(client, amount=amount, description="KeepMe")
    _assert_rejected(client, before, resp, preserved=["KeepMe"])


@pytest.mark.parametrize("category", ["", "Groceries", "food", "Food; DROP TABLE expenses"])
def test_invalid_category_rejected(client, category):
    _login(client)
    before = _count()
    resp = _post(client, category=category, description="KeepMe")
    _assert_rejected(client, before, resp, preserved=["KeepMe", "12.50"])


@pytest.mark.parametrize(
    "bad_date", ["", "not-a-date", "2024-13-45", "2024-02-30", "01/02/2024", TOMORROW]
)
def test_invalid_or_future_date_rejected(client, bad_date):
    _login(client)
    before = _count()
    resp = _post(client, date=bad_date, description="KeepMe")
    _assert_rejected(client, before, resp, preserved=["KeepMe", "12.50"])


def test_description_over_200_chars_rejected(client):
    _login(client)
    before = _count()
    long_desc = "a" * 201
    resp = _post(client, description=long_desc)
    _assert_rejected(client, before, resp, preserved=["12.50"])


def test_rejection_preserves_submitted_date(client):
    _login(client)
    past = (date.today() - timedelta(days=3)).isoformat()
    before = _count()
    resp = _post(client, amount="abc", date=past)
    _assert_rejected(client, before, resp, preserved=[past])


# ---------------------------------------------------------------- boundaries

@pytest.mark.parametrize("amount", ["1000000", "1000000.00", "0.01", "5", "5.5"])
def test_accepted_amount_boundaries(client, amount):
    _login(client)
    before = _count()
    resp = _post(client, amount=amount, description="Boundary")
    assert resp.status_code == 302, f"Amount {amount} should be accepted"
    assert _count() == before + 1
    newest = max(_all_rows(), key=lambda r: r["id"])
    assert float(newest["amount"]) == pytest.approx(float(amount))


def test_description_of_exactly_200_chars_accepted(client):
    _login(client)
    before = _count()
    desc = "b" * 200
    resp = _post(client, description=desc)
    assert resp.status_code == 302
    assert _count() == before + 1
    newest = max(_all_rows(), key=lambda r: r["id"])
    assert newest["description"] == desc


def test_todays_date_accepted(client):
    _login(client)
    before = _count()
    resp = _post(client, date=TODAY)
    assert resp.status_code == 302
    assert _count() == before + 1


@pytest.mark.parametrize("category", CATEGORIES)
def test_each_category_accepted(client, category):
    _login(client)
    before = _count()
    resp = _post(client, category=category)
    assert resp.status_code == 302, f"{category} should be accepted"
    assert _count() == before + 1


def test_sql_injection_in_description_stored_literally(client):
    _login(client)
    payload = "x'); DROP TABLE expenses; --"
    resp = _post(client, description=payload)
    assert resp.status_code == 302
    newest = max(_all_rows(), key=lambda r: r["id"])
    assert newest["description"] == payload


# ---------------------------------------------------------------- profile link

def test_profile_has_add_expense_link(client):
    _login(client)
    html = client.get("/profile").get_data(as_text=True)
    assert 'href="/expenses/add"' in html


def test_profile_add_expense_link_leads_to_form(client):
    _login(client)
    resp = client.get("/expenses/add")
    assert resp.status_code == 200
