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
PAST = (date.today() - timedelta(days=5)).isoformat()

ORIG = {
    "amount": 20.0,
    "category": "Transport",
    "date": PAST,
    "description": "OrigDescMarker",
}


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


def _row(expense_id):
    conn = db.get_db()
    try:
        r = conn.execute(
            "SELECT * FROM expenses WHERE id = ?", (expense_id,)
        ).fetchone()
        return dict(r) if r else None
    finally:
        conn.close()


def _max_id():
    conn = db.get_db()
    try:
        return conn.execute("SELECT MAX(id) FROM expenses").fetchone()[0]
    finally:
        conn.close()


def _make_expense(user_id=None, **overrides):
    """Create an expense via db.create_expense and return its id."""
    vals = dict(ORIG)
    vals.update(overrides)
    uid = user_id if user_id is not None else _demo_id()
    db.create_expense(uid, vals["amount"], vals["category"],
                      vals["date"], vals["description"])
    return _max_id()


def _url(expense_id):
    return f"/expenses/{expense_id}/edit"


def _form(**overrides):
    data = {
        "amount": "99.99",
        "category": "Health",
        "date": TODAY,
        "description": "Updated desc",
    }
    data.update(overrides)
    return data


def _assert_unchanged(expense_id):
    row = _row(expense_id)
    assert row is not None
    assert float(row["amount"]) == pytest.approx(ORIG["amount"])
    assert row["category"] == ORIG["category"]
    assert row["date"] == ORIG["date"]
    assert row["description"] == ORIG["description"]


@pytest.fixture
def owned(client):
    """Logged in as demo, with one expense owned by demo."""
    _login(client)
    return _make_expense()


def _second_user_expense(client):
    """Create an expense for a second user, leave client logged in as demo."""
    other_id = db.create_user("Second User", "second@example.com", "password123")
    eid = _make_expense(user_id=other_id)
    _login(client)
    return eid


# ---------------------------------------------------------------- auth guard

def test_logged_out_get_redirects_to_login(client):
    eid = _make_expense()
    resp = client.get(_url(eid))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")


def test_logged_out_post_redirects_to_login_and_changes_nothing(client):
    eid = _make_expense()
    resp = client.post(_url(eid), data=_form())
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/login")
    _assert_unchanged(eid)


# ---------------------------------------------------------------- 404s

def test_get_missing_expense_returns_404(client):
    _login(client)
    assert client.get(_url(999999)).status_code == 404


def test_post_missing_expense_returns_404(client):
    _login(client)
    assert client.post(_url(999999), data=_form()).status_code == 404


def test_get_other_users_expense_returns_404(client):
    _login(client)
    eid = _second_user_expense(client)
    assert client.get(_url(eid)).status_code == 404


def test_post_other_users_expense_returns_404_and_row_unchanged(client):
    _login(client)
    eid = _second_user_expense(client)
    resp = client.post(_url(eid), data=_form())
    assert resp.status_code == 404
    _assert_unchanged(eid)
    assert _row(eid)["user_id"] != _demo_id()


# ---------------------------------------------------------------- GET form

def test_get_form_prefilled_with_current_values(client, owned):
    resp = client.get(_url(owned))
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200
    assert "20" in html, "Amount should be prefilled"
    assert PAST in html, "Date should be prefilled"
    assert "OrigDescMarker" in html, "Description should be prefilled"
    assert 'name="amount"' in html
    assert 'name="category"' in html
    assert 'name="date"' in html
    assert 'name="description"' in html


def test_get_form_preselects_current_category(client, owned):
    html = client.get(_url(owned)).get_data(as_text=True)
    for cat in CATEGORIES:
        assert cat in html
    # The current category's option must carry the selected attribute.
    import re
    match = re.search(r"<option[^>]*value=\"Transport\"[^>]*>", html)
    assert match, "Transport option not found"
    assert "selected" in match.group(0), "Current category should be selected"


def test_get_form_shows_edit_labels_and_action(client, owned):
    html = client.get(_url(owned)).get_data(as_text=True)
    assert "Edit expense" in html
    assert "Save changes" in html
    assert f'action="{_url(owned)}"' in html
    assert "Save expense" not in html


def test_get_form_has_cancel_link_to_profile(client, owned):
    html = client.get(_url(owned)).get_data(as_text=True)
    assert 'href="/profile"' in html


def test_add_page_still_shows_add_labels(client):
    _login(client)
    html = client.get("/expenses/add").get_data(as_text=True)
    assert "Add expense" in html
    assert "Save expense" in html
    assert "Edit expense" not in html
    assert "Save changes" not in html


# ---------------------------------------------------------------- happy path

def test_valid_post_updates_row_and_redirects_to_profile(client, owned):
    resp = client.post(_url(owned), data=_form(amount="45.67", category="Health",
                                               description="Pharmacy run"))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/profile")
    row = _row(owned)
    assert float(row["amount"]) == pytest.approx(45.67)
    assert row["category"] == "Health"
    assert row["date"] == TODAY
    assert row["description"] == "Pharmacy run"
    assert row["user_id"] == _demo_id()


def test_valid_post_does_not_create_new_row(client, owned):
    conn = db.get_db()
    before = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    conn.close()
    client.post(_url(owned), data=_form())
    conn = db.get_db()
    after = conn.execute("SELECT COUNT(*) FROM expenses").fetchone()[0]
    conn.close()
    assert after == before


def test_updated_values_appear_on_profile(client, owned):
    client.post(_url(owned), data=_form(description="NewMarkerQ7"))
    html = client.get("/profile").get_data(as_text=True)
    assert "NewMarkerQ7" in html
    assert "OrigDescMarker" not in html


@pytest.mark.parametrize("blank", ["", "   "])
def test_blank_description_stored_as_null(client, owned, blank):
    resp = client.post(_url(owned), data=_form(description=blank))
    assert resp.status_code == 302
    assert _row(owned)["description"] is None


def test_description_is_stripped(client, owned):
    client.post(_url(owned), data=_form(description="  padded  "))
    assert _row(owned)["description"] == "padded"


def test_tampered_user_id_form_field_is_ignored(client, owned):
    other_id = db.create_user("Other", "other@example.com", "password123")
    resp = client.post(_url(owned), data=_form(user_id=str(other_id)))
    assert resp.status_code == 302
    assert _row(owned)["user_id"] == _demo_id()


def test_sql_injection_in_description_stored_literally(client, owned):
    payload = "x'); DROP TABLE expenses; --"
    resp = client.post(_url(owned), data=_form(description=payload))
    assert resp.status_code == 302
    assert _row(owned)["description"] == payload


@pytest.mark.parametrize("category", CATEGORIES)
def test_each_category_accepted(client, owned, category):
    resp = client.post(_url(owned), data=_form(category=category))
    assert resp.status_code == 302
    assert _row(owned)["category"] == category


# ---------------------------------------------------------------- rejections

def _assert_rejected(resp, expense_id, preserved=()):
    html = resp.get_data(as_text=True)
    assert resp.status_code == 200, "Rejection must re-render with 200"
    assert "error" in html.lower(), "Expected an inline error"
    _assert_unchanged(expense_id)
    for value in preserved:
        assert value in html, f"Submitted value {value!r} not preserved"


@pytest.mark.parametrize(
    "amount",
    ["", "   ", "0", "0.00", "-5", "-0.01", "abc", "nan", "NaN", "inf", "-inf",
     "1.234", "12.505", "1000000.01", "1000001"],
)
def test_invalid_amount_rejected(client, owned, amount):
    resp = client.post(_url(owned), data=_form(amount=amount, description="KeepMe"))
    _assert_rejected(resp, owned, preserved=["KeepMe"])


@pytest.mark.parametrize("category", ["", "Groceries", "food", "Food; DROP TABLE expenses"])
def test_invalid_category_rejected(client, owned, category):
    resp = client.post(_url(owned), data=_form(category=category,
                                               description="KeepMe", amount="77.77"))
    _assert_rejected(resp, owned, preserved=["KeepMe", "77.77"])


@pytest.mark.parametrize(
    "bad_date", ["", "not-a-date", "2024-13-45", "2024-02-30", "01/02/2024", TOMORROW]
)
def test_invalid_or_future_date_rejected(client, owned, bad_date):
    resp = client.post(_url(owned), data=_form(date=bad_date,
                                               description="KeepMe", amount="77.77"))
    _assert_rejected(resp, owned, preserved=["KeepMe", "77.77"])


def test_description_over_200_chars_rejected(client, owned):
    resp = client.post(_url(owned), data=_form(description="a" * 201, amount="77.77"))
    _assert_rejected(resp, owned, preserved=["77.77"])


def test_rejection_preserves_submitted_date(client, owned):
    other_past = (date.today() - timedelta(days=2)).isoformat()
    resp = client.post(_url(owned), data=_form(amount="abc", date=other_past))
    _assert_rejected(resp, owned, preserved=[other_past])


def test_rejection_keeps_edit_mode_labels(client, owned):
    resp = client.post(_url(owned), data=_form(amount="abc"))
    html = resp.get_data(as_text=True)
    assert "Edit expense" in html
    assert "Save changes" in html
    assert f'action="{_url(owned)}"' in html


# ---------------------------------------------------------------- boundaries

@pytest.mark.parametrize("amount", ["1000000", "1000000.00", "0.01", "5", "5.5"])
def test_accepted_amount_boundaries(client, owned, amount):
    resp = client.post(_url(owned), data=_form(amount=amount))
    assert resp.status_code == 302, f"Amount {amount} should be accepted"
    assert float(_row(owned)["amount"]) == pytest.approx(float(amount))


def test_description_of_exactly_200_chars_accepted(client, owned):
    desc = "b" * 200
    resp = client.post(_url(owned), data=_form(description=desc))
    assert resp.status_code == 302
    assert _row(owned)["description"] == desc


def test_todays_date_accepted(client, owned):
    resp = client.post(_url(owned), data=_form(date=TODAY))
    assert resp.status_code == 302
    assert _row(owned)["date"] == TODAY


# ---------------------------------------------------------------- profile link

def test_profile_has_edit_link_per_row(client):
    _login(client)
    first = _make_expense(description="RowOne")
    second = _make_expense(description="RowTwo")
    html = client.get("/profile").get_data(as_text=True)
    assert f'href="/expenses/{first}/edit"' in html
    assert f'href="/expenses/{second}/edit"' in html


def test_profile_does_not_link_to_other_users_expense(client):
    _login(client)
    other_eid = _second_user_expense(client)
    html = client.get("/profile").get_data(as_text=True)
    assert f'href="/expenses/{other_eid}/edit"' not in html


# ---------------------------------------------------------------- db helpers

def test_update_expense_wrong_user_returns_false_and_changes_nothing(client):
    eid = _make_expense()
    other_id = db.create_user("Other", "other@example.com", "password123")
    result = db.update_expense(eid, other_id, 1.0, "Food", TODAY, "hacked")
    assert result is False
    _assert_unchanged(eid)


def test_update_expense_missing_id_returns_false(client):
    assert db.update_expense(999999, _demo_id(), 1.0, "Food", TODAY, "x") is False


def test_update_expense_correct_user_returns_true_and_updates(client):
    eid = _make_expense()
    result = db.update_expense(eid, _demo_id(), 3.5, "Bills", TODAY, "")
    assert result is True
    row = _row(eid)
    assert float(row["amount"]) == pytest.approx(3.5)
    assert row["category"] == "Bills"
    assert row["date"] == TODAY
    assert row["description"] is None, "Blank description must be stored NULL"


def test_get_expense_scoped_to_user(client):
    eid = _make_expense()
    other_id = db.create_user("Other", "other@example.com", "password123")
    mine = db.get_expense(eid, _demo_id())
    assert mine is not None
    assert mine["description"] == ORIG["description"]
    assert db.get_expense(eid, other_id) is None
    assert db.get_expense(999999, _demo_id()) is None
