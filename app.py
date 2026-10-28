import os
import sqlite3
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation

from flask import Flask, abort, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash

from database.db import (
    CATEGORIES,
    create_expense,
    create_user,
    get_category_totals,
    get_expense,
    get_expense_summary,
    get_recent_expenses,
    get_user_by_email,
    get_user_by_id,
    init_db,
    seed_db,
    update_expense,
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


MAX_AMOUNT = Decimal("1000000")
MAX_DESCRIPTION_LENGTH = 200


def _validate_amount(raw):
    raw = (raw or "").strip()
    if not raw:
        return None, "Amount is required."
    try:
        amount = Decimal(raw)
    except InvalidOperation:
        return None, "Amount must be a number."
    if not amount.is_finite():
        return None, "Amount must be a number."
    if amount <= 0:
        return None, "Amount must be greater than 0."
    # bound check first so quantize never sees a huge exponent
    if amount > MAX_AMOUNT:
        return None, "Amount cannot exceed 1,000,000."
    if amount != amount.quantize(Decimal("0.01")):
        return None, "Amount can have at most 2 decimal places."
    return float(amount), None


def _validate_expense(form):
    """Return (clean, error); clean is None when error is set."""
    amount, error = _validate_amount(form.get("amount"))
    if error:
        return None, error

    category = form.get("category", "").strip()
    if category not in CATEGORIES:
        return None, "Please choose a valid category."

    raw_date = form.get("date", "").strip()
    if not raw_date:
        return None, "Date is required."
    expense_date, date_error = _parse_date(raw_date)
    if date_error:
        return None, f"Date is {date_error}."
    if expense_date > date.today().isoformat():
        return None, "Date cannot be in the future."

    description = form.get("description", "").strip()
    if len(description) > MAX_DESCRIPTION_LENGTH:
        return None, f"Description must be {MAX_DESCRIPTION_LENGTH} characters or fewer."

    return {
        "amount": amount,
        "category": category,
        "date": expense_date,
        "description": description or None,
    }, None


@app.route("/expenses/add", methods=["GET", "POST"])
def add_expense():
    user = _get_current_user()
    if user is None:
        return redirect(url_for("login"))

    today = date.today().isoformat()
    if request.method == "GET":
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            today=today,
            form={"date": today},
            error=None,
            editing=False,
        )

    clean, error = _validate_expense(request.form)
    if error:
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            today=today,
            form=request.form,
            error=error,
            editing=False,
        )

    create_expense(
        user["id"],
        clean["amount"],
        clean["category"],
        clean["date"],
        clean["description"],
    )
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/edit", methods=["GET", "POST"])
def edit_expense(id):
    user = _get_current_user()
    if user is None:
        return redirect(url_for("login"))

    expense = get_expense(id, user["id"])
    if expense is None:
        abort(404)

    today = date.today().isoformat()
    if request.method == "GET":
        form = dict(expense)
        form["description"] = form["description"] or ""
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            today=today,
            form=form,
            error=None,
            editing=True,
            expense=expense,
        )

    clean, error = _validate_expense(request.form)
    if error:
        return render_template(
            "add_expense.html",
            categories=CATEGORIES,
            today=today,
            form=request.form,
            error=error,
            editing=True,
            expense=expense,
        )

    updated = update_expense(
        id,
        user["id"],
        clean["amount"],
        clean["category"],
        clean["date"],
        clean["description"],
    )
    if not updated:
        abort(404)
    return redirect(url_for("profile"))


@app.route("/expenses/<int:id>/delete")
def delete_expense(id):
    return "Delete expense — coming in Step 9"


if __name__ == "__main__":
    app.run(debug=True, port=5001)
