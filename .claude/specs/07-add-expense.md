# Spec: Add Expense

## Overview
Logged-in users can record a new expense through a form at `/expenses/add`. Until now the only expenses in the app are seed data; this step lets users create their own, which then show up in the profile summary, category breakdown and recent list. It replaces the Step 7 stub and is the first write path for the `expenses` table.

## Depends on
- Step 1 — Database setup (`expenses` table, `get_db()`)
- Step 3 — Login and logout (`_get_current_user()`, session)
- Step 4/5 — Profile page (where new expenses appear and where the entry link lives)

## Routes
- `GET /expenses/add` — render the empty add-expense form (date defaults to today) — logged-in (redirect to `/login` if logged out)
- `POST /expenses/add` — validate the form, insert the expense for the current user, redirect to `/profile` — logged-in (redirect to `/login` if logged out)

The existing `add_expense` function is changed to accept `GET` and `POST`. `edit_expense` and `delete_expense` stubs stay untouched.

Validation (on failure re-render the form with status 200, an inline error and the submitted values preserved):
- `amount` — required, numeric, finite, greater than 0, at most 2 decimal places, max 1,000,000
- `category` — required, must be one of the fixed list: Food, Transport, Bills, Health, Entertainment, Shopping, Other
- `date` — required, valid `YYYY-MM-DD`, not in the future (reuse `_parse_date`)
- `description` — optional, stripped, max 200 characters

## Database changes
No schema changes (`expenses` already has `user_id`, `amount`, `category`, `date`, `description`).

Add to `database/db.py`:
- `CATEGORIES` — tuple of the allowed category names (single source of truth for validation and the form `<select>`)
- `create_expense(user_id, amount, category, date, description)` — parameterised `INSERT`, commits, returns `lastrowid`; `description` stored as `NULL` when blank

## Templates
- **Create:** `templates/add_expense.html` — extends `base.html`; form with amount (`type="number" step="0.01" min="0.01"`), category `<select>`, date (`type="date"`, `max` today), description; Cancel link back to profile; inline error block
- **Modify:** `templates/profile.html` — add an "Add expense" button/link using `url_for('add_expense')`, shown in the header area and in the empty state

## Files to change
- `app.py` — implement `add_expense()` (GET/POST), add `_validate_expense()` helper, import `create_expense` and `CATEGORIES`
- `database/db.py` — `CATEGORIES`, `create_expense()`
- `templates/profile.html` — link to the add form
- `static/css/style.css` — only if shared form styles are needed; otherwise page-specific styles go in the new CSS file

## Files to create
- `templates/add_expense.html`
- `static/css/add_expense.css` — page-specific styles (loaded via a block in the template, no inline `<style>`)
- `tests/test_add_expense.py`

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (no password handling changes in this step)
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; the route only validates, calls `create_expense`, and redirects
- `user_id` always comes from the session, never from form data
- Use `url_for()` for every link and redirect; no hardcoded URLs
- Do not implement the edit or delete stub routes
- Vanilla JS only (none is required for this step)
- Redirect after successful POST (PRG); no flash dependency required

## Definition of done
- [ ] Visiting `/expenses/add` while logged out redirects to `/login`
- [ ] Logged in, `/expenses/add` shows the form with today's date prefilled and all seven categories in the dropdown
- [ ] Submitting a valid expense redirects to `/profile` and the new expense appears in the recent list, with the total and category breakdown updated
- [ ] Blank/zero/negative/non-numeric amount shows an inline error and keeps the other entered values
- [ ] Amount with more than 2 decimals or above 1,000,000 is rejected with an error
- [ ] A category outside the allowed list (e.g. tampered POST) is rejected
- [ ] Invalid or future date is rejected with an error
- [ ] Description over 200 characters is rejected; blank description is accepted
- [ ] Expense is saved against the logged-in user and is not visible to other users
- [ ] Profile page has an "Add expense" link that works
- [ ] `pytest` passes, including new tests in `tests/test_add_expense.py`
