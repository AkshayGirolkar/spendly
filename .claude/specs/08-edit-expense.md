# Spec: Edit Expense

## Overview
Logged-in users can change an existing expense through a pre-filled form at `/expenses/<id>/edit`. Step 7 let users create expenses; this step lets them correct mistakes (wrong amount, category, date or description). It replaces the Step 8 stub and is the first update path for the `expenses` table. It reuses the Step 7 validation and form layout so add and edit behave identically.

## Depends on
- Step 1 — Database setup (`expenses` table, `get_db()`)
- Step 3 — Login and logout (`_get_current_user()`, session)
- Step 4/5 — Profile page (recent expenses list where the edit link lives)
- Step 7 — Add expense (`_validate_expense()`, `CATEGORIES`, form template and CSS)

## Routes
- `GET /expenses/<int:id>/edit` — render the add/edit form pre-filled with the expense's current values — logged-in (redirect to `/login` if logged out; `abort(404)` if the expense does not exist or belongs to another user)
- `POST /expenses/<int:id>/edit` — validate the form, update the expense, redirect to `/profile` — logged-in (redirect to `/login` if logged out; `abort(404)` if not found or not owned)

The existing `edit_expense` function is changed to accept `GET` and `POST`. `delete_expense` stub stays untouched.

Validation is identical to Step 7 (reuse `_validate_expense()`); on failure re-render the form with status 200, an inline error and the submitted values preserved:
- `amount` — required, numeric, finite, > 0, at most 2 decimal places, max 1,000,000
- `category` — one of `CATEGORIES`
- `date` — required, valid `YYYY-MM-DD`, not in the future
- `description` — optional, stripped, max 200 characters

Ownership returns 404 (not 403) so expense ids of other users are not revealed.

## Database changes
No schema changes.

Add to `database/db.py`:
- `get_expense(expense_id, user_id)` — parameterised `SELECT id, amount, category, date, description FROM expenses WHERE id = ? AND user_id = ?`; returns a row or `None`
- `update_expense(expense_id, user_id, amount, category, date, description)` — parameterised `UPDATE ... WHERE id = ? AND user_id = ?`, commits, returns `True` if a row was updated (`rowcount > 0`); `description` stored as `NULL` when blank

## Templates
- **Create:** none (reuse the add form to avoid duplication)
- **Modify:**
  - `templates/add_expense.html` — make it serve both modes: heading, subtitle, form `action` and submit label switch on an `expense` / `editing` variable passed by the route (`Edit expense` / `Save changes` vs `Add expense` / `Save expense`); `url_for('edit_expense', id=...)` for the edit action
  - `templates/profile.html` — add an "Edit" link per row in the expenses table using `url_for('edit_expense', id=e.id)`

## Files to change
- `app.py` — implement `edit_expense()` (GET/POST), import `abort`, `get_expense`, `update_expense`; pass mode variables from `add_expense()` and `edit_expense()`
- `database/db.py` — `get_expense()`, `update_expense()`
- `templates/add_expense.html` — dual-mode form
- `templates/profile.html` — Edit link per row (add an Actions column header to match)
- `static/css/profile.css` — style for the row edit link (only if existing classes are insufficient)

## Files to create
- `tests/test_edit_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (no password handling changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; the route fetches, validates, calls `update_expense`, and redirects
- `user_id` always comes from the session, never from form data; every query filters on both `id` and `user_id`
- Use `abort(404)` for missing/foreign expenses — no raw string returns
- Use `url_for()` for every link and redirect; no hardcoded URLs
- Do not implement the delete stub route
- Vanilla JS only (none is required for this step)
- Redirect after successful POST (PRG)
- Page-specific styles go in CSS files, not inline `<style>` tags

## Definition of done
- [ ] Visiting `/expenses/<id>/edit` while logged out redirects to `/login`
- [ ] Logged in, each row in the profile expenses table has an "Edit" link that opens `/expenses/<id>/edit`
- [ ] The edit form is pre-filled with the expense's current amount, category, date and description
- [ ] Heading and submit button read "Edit expense" / "Save changes"; `/expenses/add` still reads "Add expense" / "Save expense"
- [ ] Submitting valid changes redirects to `/profile` and the updated values appear in the list, with total and category breakdown recalculated
- [ ] Clearing the description saves successfully and shows no description
- [ ] Blank/zero/negative/non-numeric amount shows an inline error and keeps the entered values
- [ ] Amount with more than 2 decimals or above 1,000,000 is rejected
- [ ] A category outside the allowed list (tampered POST) is rejected
- [ ] Invalid or future date is rejected; description over 200 characters is rejected
- [ ] Editing a non-existent expense id returns 404
- [ ] Editing another user's expense (GET or POST) returns 404 and does not change the data
- [ ] Cancel link returns to `/profile` without saving
- [ ] `pytest` passes, including new tests in `tests/test_edit_expense.py`
