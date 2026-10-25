# Spec: Login and Logout

## Overview
Turn the existing `GET /login` page into a working sign-in flow and replace the `/logout` stub. A visitor submits email and password; the server verifies them against the stored werkzeug hash, stores the user id in Flask's signed `session`, and redirects. Logout clears the session. This is the step that makes "who is the current user" available to later steps (profile, expenses).

## Depends on
- Step 1 — Database setup (`users` table, `get_db()`)
- Step 2 — Registration (`create_user()`, `get_user_by_email()`, users with hashed passwords)

## Routes
- `GET /login` — render the sign-in form (already implemented; redirects to `/` if already logged in) — public
- `POST /login` — validate credentials, set `session["user_id"]`, redirect to `/` on success; re-render form with a generic error on failure — public
- `GET /logout` — clear the session and redirect to `/` (replaces the stub) — logged-in (harmless if not)

No other new routes. `/profile` and `/expenses/*` stay stubs.

## Database changes
No database changes. Add one helper to `database/db.py`:
- `get_user_by_id(user_id)` — returns the matching `sqlite3.Row` or `None` (parameterised query; used to resolve the current user for templates).

`get_user_by_email()` from Step 2 is reused for credential lookup.

## Templates
- **Create:** none
- **Modify:**
  - `templates/login.html` — form `action` uses `url_for('login')` instead of hardcoded `/login`; re-populate `email` after a failed submit (never the password).
  - `templates/base.html` — navbar shows "Sign in" / "Get started" when logged out, and the user's name plus a "Sign out" link (`url_for('logout')`) when logged in. Uses a `current_user` variable supplied by a context processor.

## Files to change
- `app.py` — import `session`, `check_password_hash`, `get_user_by_id`; set `app.secret_key`; make `login` accept `GET` and `POST`; implement `logout`; add a context processor exposing `current_user`
- `database/db.py` — add `get_user_by_id()`
- `templates/login.html` — as above
- `templates/base.html` — as above
- `CLAUDE.md` — update routes table: `POST /login` and `GET /logout` implemented

## Files to create
- `tests/test_login_logout.py` — pytest coverage for login and logout

## New dependencies
No new dependencies. Sessions use Flask's built-in signed cookie; password checks use `werkzeug.security.check_password_hash` (already installed).

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — verify with `check_password_hash`; never compare plaintext, store it, or log it
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; routes read the form, call helpers, and render or redirect
- Use `url_for()` for every link and redirect — no hardcoded URLs
- `app.secret_key` read from the `SECRET_KEY` environment variable with a clearly-named development fallback; do not commit a real secret
- Strip and lower-case the email before lookup (matches registration)
- On failure, show one generic message ("Invalid email or password.") for both unknown email and wrong password — do not reveal which was wrong. Re-render `login.html` with `error=` and HTTP 200
- Store only `user_id` in the session — never the hash or password
- Logout must call `session.clear()`
- Do not implement `/profile`, `/expenses/*` or any route-protection decorator — out of scope
- Do not change the port (5001)

## Definition of done
- [ ] `GET /login` renders the form; form action in the HTML comes from `url_for('login')`
- [ ] Logging in as `demo@spendly.com` / `demo123` redirects (302) to `/`
- [ ] After login the navbar shows the user's name and a "Sign out" link, and no longer shows "Sign in" / "Get started"
- [ ] Wrong password and unknown email both re-render the form with the same "Invalid email or password." error (HTTP 200) and no session is set
- [ ] Email matching is case-insensitive and ignores surrounding whitespace (`  DEMO@Spendly.com ` works)
- [ ] After a failed submit the email field keeps its value; the password field is empty
- [ ] A user registered via `/register` can immediately log in with the same credentials
- [ ] Visiting `GET /login` while logged in redirects to `/`
- [ ] `GET /logout` clears the session, redirects (302) to `/`, and the navbar returns to "Sign in" / "Get started"
- [ ] `GET /logout` while logged out does not error
- [ ] The session cookie contains no password or hash
- [ ] `pytest tests/test_login_logout.py` passes (and existing tests still pass)
- [ ] App starts on port 5001 without errors
