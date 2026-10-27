import os
import sqlite3
from datetime import date, datetime, timedelta

from flask import Flask, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    create_user,
    get_category_totals,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
)

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "dev-only-insecure-secret-key-change-me")

with app.app_context():
    init_db()
    seed_db()


def _get_current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    user = get_user_by_id(user_id)
    if user is None:
        session.pop("user_id", None)
    return user


@app.context_processor
def inject_current_user():
    return {"current_user": _get_current_user()}


# ------------------------------------------------------------------ #
# Routes                                                              #
# ------------------------------------------------------------------ #

@app.route("/")
def landing():
    return render_template("landing.html")


def _validate_registration(name, email, password):
    if not name:
        return "Name is required."
    if not email or "@" not in email:
        return "Enter a valid email address."
    if len(password) < 8:
        return "Password must be at least 8 characters."
    return None


@app.route("/register", methods=["GET", "POST"])
def register():
    if _get_current_user():
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("register.html")

    name = request.form.get("name", "").strip()
    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    error = _validate_registration(name, email, password)
    if error is None and get_user_by_email(email):
        error = "That email is already registered."
    if error is None:
        try:
            create_user(name, email, password)
        except sqlite3.IntegrityError:
            error = "That email is already registered."
    if error:
        return render_template("register.html", error=error, name=name, email=email)

    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if _get_current_user():
        return redirect(url_for("profile"))
    if request.method == "GET":
        return render_template("login.html")

    email = request.form.get("email", "").strip().lower()
    password = request.form.get("password", "")

    user = get_user_by_email(email) if email else None
    if user is None or not check_password_hash(user["password_hash"], password):
        return render_template(
            "login.html", error="Invalid email or password.", email=email
        )

    session.clear()
    session["user_id"] = user["id"]
    return redirect(url_for("profile"))


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("landing"))


@app.route("/terms")
def terms():
    return render_template("terms.html")


@app.route("/privacy")
def privacy():
    return render_template("privacy.html")


# ------------------------------------------------------------------ #
# Placeholder routes — students will implement these                  #
# ------------------------------------------------------------------ #

def _format_member_since(raw):
    try:
        return datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").strftime("%B %Y")
    except (ValueError, TypeError):
        return raw[:10] if raw else ""


INVALID_DATE_MESSAGE = "not a valid date (use YYYY-MM-DD)"


def _parse_date(raw):
    value = (raw or "").strip()
    if not value:
        return None, None
    try:
        parsed = datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return None, INVALID_DATE_MESSAGE
    # strptime accepts loose forms like 2024-1-5; the round trip rejects them
    if parsed.strftime("%Y-%m-%d") != value:
        return None, INVALID_DATE_MESSAGE
    return value, None


def _parse_date_range(start_raw, end_raw):
    """Return (start, end, errors) with start/end as ISO strings or None.

    An invalid side is dropped (None) while a valid side still applies.
    If start is after end, both are dropped so the page shows unfiltered data.
    """
    errors = []
    start, start_error = _parse_date(start_raw)
    end, end_error = _parse_date(end_raw)
    if start_error:
        errors.append(f"Start date is {start_error}.")
    if end_error:
        errors.append(f"End date is {end_error}.")
    if start and end and start > end:
        errors.append("Start date must not be after end date.")
        return None, None, errors
    return start, end, errors


def _build_presets(today, start, end):
    today_iso = today.isoformat()
    # 29 days back plus today = 30 days inclusive
    last_30_start = (today - timedelta(days=29)).isoformat()
    ranges = [
        ("This month", today.replace(day=1).isoformat(), today_iso),
        ("Last 30 days", last_30_start, today_iso),
        ("All time", None, None),
    ]
    presets = []
    for label, p_start, p_end in ranges:
        if p_start:
            url = url_for("profile", start=p_start, end=p_end)
        else:
            url = url_for("profile")
        presets.append(
            {"label": label, "url": url, "active": (p_start, p_end) == (start, end)}
        )
    return presets


@app.route("/profile")
def profile():
    user = _get_current_user()
    if user is None:
        return redirect(url_for("login"))
    start, end, errors = _parse_date_range(
        request.args.get("start"), request.args.get("end")
    )
    filtered = bool(start or end)
    summary = get_expense_summary(user["id"], start, end)
    has_any_expenses = summary["count"] > 0
    if filtered and not has_any_expenses:
        has_any_expenses = get_expense_summary(user["id"])["count"] > 0
    return render_template(
        "profile.html",
        user=user,
        member_since=_format_member_since(user["created_at"]),
        summary=summary,
        categories=get_category_totals(user["id"], start, end),
        recent=get_recent_expenses(user["id"], start_date=start, end_date=end),
        start=start,
        end=end,
        errors=errors,
        filtered=filtered,
        has_any_expenses=has_any_expenses,
        presets=_build_presets(date.today(), start, end),
    )


@app.route("/expenses/add")
def add_expense():
    return "Add expense — coming in Step 7"


@app.route("/expenses/<int:id>/edit")
def edit_expense(id):
    return "Edit expense — coming in Step 8"


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
