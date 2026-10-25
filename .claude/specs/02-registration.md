# Spec: Registration

## Overview
Turn the existing `GET /register` page into a working sign-up flow. A visitor submits name, email and password; the server validates the input, hashes the password with werkzeug, inserts a row into `users`, and redirects to the login page. This is the first auth step on the Spendly roadmap and gives later steps (login, logout, profile, expenses) real users to work with.

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`, `init_db()`)

## Routes
- `GET /register` — render the registration form (already implemented; unchanged) — public
- `POST /register` — validate form, create user, redirect to `/login` on success; re-render form with an error message on failure — public

No other new routes. `/login` stays a GET-only page (login is a later step).

## Database changes
No database changes. The existing `users` table (`name`, `email UNIQUE`, `password_hash`) already covers this. Add helpers to `database/db.py`:
- `create_user(name, email, password)` — hashes the password with `generate_password_hash`, inserts the row with a parameterised query, returns the new user id. Raises `sqlite3.IntegrityError` on duplicate email (callers handle it).
- `get_user_by_email(email)` — returns the matching `sqlite3.Row` or `None` (used for the duplicate-email check).

## Templates
- **Create:** none
- **Modify:**
  - `templates/register.html` — form `action` uses `url_for('register')` instead of the hardcoded `/register`; re-populate `name` and `email` inputs after a failed submit (never the password); add `minlength="8"` to the password input.

## Files to change
- `app.py` — change `register` to accept `GET` and `POST`; add form handling; import `request`, `redirect`, `url_for`, and the new db helpers
- `database/db.py` — add `create_user()` and `get_user_by_email()`
- `templates/register.html` — as above
- `CLAUDE.md` — update the routes table: `POST /register` implemented

## Files to create
- `tests/test_registration.py` — pytest coverage for the registration flow

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug (`generate_password_hash`); never store or log plaintext
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; the route just reads the form, calls helpers, and renders or redirects
- Use `url_for()` for every link and redirect — no hardcoded URLs
- Validation (server-side, in this order): name non-empty after `strip()`; email non-empty, contains `@`, lower-cased and stripped before storing; password at least 8 characters; email not already registered
- On validation failure, re-render `register.html` with `error=<message>` and HTTP 200 (the template already renders `error`)
- Catch `sqlite3.IntegrityError` from `create_user()` to handle a race on duplicate email
- Do not log the user in or create a session — that belongs to the login step
- Do not implement any other stub route (`/logout`, `/profile`, `/expenses/*`)
- Do not change the port (5001)

## Definition of done
- [ ] `GET /register` still renders the form with name, email and password fields
- [ ] Submitting valid name, a new email and an 8+ character password redirects (302) to `/login`
- [ ] The new user appears in the `users` table with `password_hash` that is not the plaintext and verifies via `check_password_hash`
- [ ] Registering the same email again (including different letter case) re-renders the form with an "already registered" error and creates no second row
- [ ] Password shorter than 8 characters shows an error and creates no user
- [ ] Empty/whitespace-only name, or an email without `@`, shows an error and creates no user
- [ ] After a failed submit the name and email fields keep their values; the password field is empty
- [ ] The form action in the rendered HTML comes from `url_for('register')`
- [ ] The seeded demo user (`demo@spendly.com`) cannot be re-registered
- [ ] `pytest tests/test_registration.py` passes
- [ ] App starts on port 5001 without errors
