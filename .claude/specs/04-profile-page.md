# Spec: Profile Page

## Overview
Replace the `/profile` stub with a real page for the logged-in user. It shows an account summary (name, email, member since) and a read-only overview of their spending: total spent, number of expenses, a per-category breakdown, and a list of recent expenses. This is the first page that depends on knowing who the current user is, building on the session set up in Step 3, and it gives the later expense steps (add/edit/delete) a place to land and be seen.

## Depends on
- Step 1 — Database setup (`users` and `expenses` tables, `get_db()`, seed data)
- Step 2 — Registration (users with hashed passwords)
- Step 3 — Login and logout (`session["user_id"]`, `get_user_by_id()`, `current_user` context processor)

## Routes
- `GET /profile` — render the profile page for the current user; redirect to `/login` if not logged in — logged-in

No other new routes. `/expenses/*` stay stubs.

## Database changes
No schema changes. Add helpers to `database/db.py` (all parameterised, all scoped by `user_id`):
- `get_expense_summary(user_id)` — returns total amount and expense count for the user (`0` / `0` when none)
- `get_category_totals(user_id)` — returns `(category, total)` rows ordered by total descending
- `get_recent_expenses(user_id, limit=10)` — returns the user's newest expenses ordered by `date DESC, id DESC`

## Templates
- **Create:**
  - `templates/profile.html` — extends `base.html`; account card, summary stats, category breakdown, recent expenses table, empty state when the user has no expenses
- **Modify:**
  - `templates/base.html` — make the navbar user name a link to `url_for('profile')`; add a per-page stylesheet block in `<head>` if one does not already exist

## Files to change
- `app.py` — implement `profile()` (redirect to login when no user; call db helpers; render template)
- `database/db.py` — add the three helpers above
- `templates/base.html` — link the user name to the profile; add a head/styles block if needed
- `CLAUDE.md` — mark `GET /profile` as implemented in the routes table

## Files to create
- `templates/profile.html`
- `static/css/profile.css` — profile-only styles (no inline `<style>`)
- `tests/test_profile.py` — pytest coverage for the profile page and the new db helpers

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — never display, log, or pass `password_hash` to the template
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; the route fetches data, renders, done
- Use `url_for()` for every link and redirect — no hardcoded URLs
- Every expense query must filter by the current user's `user_id`; a user must never see another user's data
- Unauthenticated access redirects to `url_for('login')` (302); do not return a raw string
- Format amounts to two decimals in the template
- Vanilla JS only, and only if needed — the page should work without JS
- Do not implement `/expenses/add`, `/expenses/<id>/edit`, or `/expenses/<id>/delete` — out of scope
- Do not change the port (5001)

## Definition of done
- [ ] `GET /profile` while logged out redirects (302) to `/login`
- [ ] Logged in as `demo@spendly.com` / `demo123`, `GET /profile` returns 200 and renders through `base.html`
- [ ] The page shows the user's name, email, and member-since date, and never the password hash
- [ ] Total spent and expense count match the seeded data (8 expenses, 323.04 total)
- [ ] The category breakdown lists each category with its total, highest first
- [ ] Recent expenses are listed newest first with date, category, description and amount
- [ ] A newly registered user with no expenses sees an empty state and zero totals, with no errors
- [ ] User A cannot see user B's expenses on their profile
- [ ] The navbar user name links to the profile page via `url_for('profile')`
- [ ] Profile styles come from `static/css/profile.css`, with no hardcoded hex values and no inline `<style>`
- [ ] `pytest tests/test_profile.py` passes (and existing tests still pass)
- [ ] App starts on port 5001 without errors
