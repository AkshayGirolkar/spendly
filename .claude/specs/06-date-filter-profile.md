# Spec: Date Filter for Profile Page

## Overview
The profile page currently shows all-time totals, category breakdown and the 10 most recent expenses. This step adds a date-range filter (start date / end date) so users can see their spending for a chosen period. The filter is applied server-side via GET query parameters (`/profile?start=YYYY-MM-DD&end=YYYY-MM-DD`) and affects the summary, category totals and expense list together. Quick presets (This month, Last 30 days, All time) make common ranges one click.

## Depends on
- Step 1 — Database setup
- Step 3 — Login and logout (`_get_current_user()`)
- Step 4 — Profile page (`get_expense_summary`, `get_category_totals`, `get_recent_expenses`)
- Step 5 — Backend routes for profile

## Routes
No new routes. Existing route extended:
- `GET /profile?start=<YYYY-MM-DD>&end=<YYYY-MM-DD>` — both params optional; filters all profile data to the inclusive date range — logged-in

Behaviour:
- Missing/blank param = unbounded on that side (no params = current all-time behaviour)
- Invalid date format → ignore that param and show an inline error message (page still renders 200)
- `start` later than `end` → show an inline error and fall back to unfiltered data

## Database changes
No schema changes. In `database/db.py`, extend the three helpers with optional `start_date=None, end_date=None` arguments:
- `get_expense_summary(user_id, start_date=None, end_date=None)`
- `get_category_totals(user_id, start_date=None, end_date=None)`
- `get_recent_expenses(user_id, limit=10, start_date=None, end_date=None)`

Each adds `AND date >= ?` / `AND date <= ?` clauses only when the value is provided, always parameterised and always still filtered by `user_id`. Dates are stored as ISO `YYYY-MM-DD` text, so string comparison is correct.

## Templates
- **Create:** none
- **Modify:** `templates/profile.html`
  - Add a filter form (`method="get"`, `action="{{ url_for('profile') }}"`) with start/end `<input type="date">`, an Apply button and a Clear link
  - Add preset links (This month, Last 30 days, All time) built with `url_for('profile', start=..., end=...)`
  - Show the active range label and an inline error when the input is invalid
  - Empty state text distinguishes "No expenses yet." from "No expenses in this date range."

## Files to change
- `app.py` — `profile()` reads and validates `start`/`end` (small helper `_parse_date_range`), passes them to the db helpers and template
- `database/db.py` — optional date-range arguments on the three helpers
- `templates/profile.html` — filter form, presets, messages
- `static/css/profile.css` — filter form and preset styles (CSS variables only)

## Files to create
- `tests/test_profile_date_filter.py` — pytest coverage for filtering, invalid input, boundaries and user isolation

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only — never build the date clauses from user input via f-strings (only the fixed clause text may be concatenated)
- Passwords hashed with werkzeug — never pass `password_hash` to a template
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; the route parses params, fetches, renders
- Validate dates with `datetime.strptime(value, "%Y-%m-%d")` in the route before they reach the db layer
- Use `url_for()` for every link, including presets
- Vanilla JS only; the filter must work with no JavaScript (plain GET form)
- Do not implement `/expenses/add`, `/expenses/<id>/edit`, or `/expenses/<id>/delete`
- Do not change the port (5001)

## Definition of done
- [ ] `/profile` with no params behaves exactly as before (demo user: 8 expenses, 323.04 total)
- [ ] `/profile?start=<date>&end=<date>` shows only expenses within the inclusive range; total, count, categories and table all reflect it
- [ ] Only `start` or only `end` given filters one-sided
- [ ] Expenses dated exactly on the start and end dates are included
- [ ] Invalid date (e.g. `start=abc`) returns 200 with an inline error and unfiltered/ignored value, no crash
- [ ] `start` after `end` shows an error and does not filter
- [ ] A range with no expenses shows zero totals and "No expenses in this date range."
- [ ] The date inputs keep the selected values after applying the filter
- [ ] Preset links (This month, Last 30 days, All time) produce the expected ranges
- [ ] User A never sees user B's expenses under any filter
- [ ] Logged-out `GET /profile?start=...` still redirects to `/login`
- [ ] `pytest tests/test_profile_date_filter.py` passes and existing tests still pass
- [ ] App starts on port 5001 without errors
