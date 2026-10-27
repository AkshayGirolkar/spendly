# Spec: Backend Routes for Profile Page

## Overview
Step 04 already connected `GET /profile` to live data (summary, category totals, recent expenses). This step finishes the backend side of the profile page: it makes the route's data flow robust and verifiable without changing the page's design. It standardises auth handling and error handling on the profile route, guarantees strict per-user data isolation, and fills the remaining test gaps so the later expense steps (add/edit/delete) can rely on a trusted profile backend.

## Depends on
- Step 1 — Database setup
- Step 2 — Registration
- Step 3 — Login and logout (`session["user_id"]`, `_get_current_user()`)
- Step 4 — Profile page (`get_expense_summary`, `get_category_totals`, `get_recent_expenses`)

## Routes
No new routes. Existing behaviour tightened:
- `GET /profile` — render profile for the current user; redirect to `/login` if logged out or if the session user no longer exists — logged-in

## Database changes
No schema changes. In `database/db.py`, review the three profile helpers and ensure:
- Every query is parameterised and filtered by `user_id`
- `get_recent_expenses` clamps/validates `limit` (positive int) before use
- Helpers return plain, template-safe values (no `password_hash` ever reaches the template)

## Templates
- **Create:** none
- **Modify:** `templates/profile.html` — only if needed to format amounts to two decimals consistently and render the empty state for zero totals

## Files to change
- `app.py` — tidy `profile()` to one responsibility (fetch, render); stale-session users redirect to login; remove the outdated "Placeholder routes" comment above it
- `database/db.py` — `limit` validation in `get_recent_expenses`
- `templates/profile.html` — two-decimal formatting / empty state only if gaps are found
- `CLAUDE.md` — note Step 05 in the routes table notes if appropriate

## Files to create
- `tests/test_profile_backend.py` — pytest coverage for auth redirect, stale session, user isolation, empty-state user, and db helper edge cases

## New dependencies
No new dependencies.

## Rules for implementation
- No SQLAlchemy or ORMs
- Parameterised queries only
- Passwords hashed with werkzeug — never pass `password_hash` to a template
- Use CSS variables — never hardcode hex values
- All templates extend `base.html`
- DB logic lives in `database/db.py` only; the route fetches data, renders, done
- Use `url_for()` for every link and redirect
- Use `abort()` for HTTP errors, not raw string returns
- Do not implement `/expenses/add`, `/expenses/<id>/edit`, or `/expenses/<id>/delete`
- Do not change the port (5001)

## Definition of done
- [ ] `GET /profile` while logged out returns 302 to `/login`
- [ ] A session pointing at a deleted/non-existent user redirects to `/login` and the stale `user_id` is cleared
- [ ] Logged in as `demo@spendly.com` / `demo123`, `/profile` returns 200 with 8 expenses and 323.04 total
- [ ] User A never sees user B's expenses, categories, or totals on `/profile`
- [ ] A newly registered user with no expenses sees zero totals and an empty state, with no errors
- [ ] `get_recent_expenses` rejects or clamps a non-positive `limit`
- [ ] The rendered profile HTML never contains the password hash
- [ ] `pytest tests/test_profile_backend.py` passes and existing tests still pass
- [ ] App starts on port 5001 without errors
