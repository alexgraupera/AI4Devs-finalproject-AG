# 0034. A shared username and password in front of the UI

- **Status**: Accepted
- **Date**: 2026-09-26
- **Issue**: #55 (part of #5)

## Context

The public deployment of [ADR 0021](0021-hosting-on-render.md) left the UI open: anyone with its URL could review listings and ask questions, and every one of those is a model call paid from the owner's provider balance. The API was already closed to everyone but the UI ([ADR 0020](0020-access-spend-and-probes.md)), and the daily spend cap bounds the damage to a day's cap; but the UI itself, the only door the API trusts, had no lock. The owner asked for one, with a single user shared with the evaluator.

## Decision

**A login form in the UI, one shared user, the credentials in the platform's environment** ([`ui_auth.py`](../../ui_auth.py)).

- `UI_USERNAME` and `UI_PASSWORD` are set on Render (`sync: false`: typed in the dashboard, never in the repository) and read at start-up like every other setting.
- **Every entry point is guarded.** The home page and each page call `require_login()` right after `set_page_config`, so a page opened by its own URL shows the login and nothing else.
- **It fails closed.** In production, a missing username or password shows an error and stops the page: a forgotten variable must not quietly leave the UI open. In development, no credentials means no login, so the project still runs on a laptop with an empty `.env`.
- Both values are compared in constant time, both always compared. Five wrong attempts lock the session for a minute; a new browser session resets the count, so the length of the password is what stops a script, and the lock only slows a person.
- The session stays signed in while the browser tab keeps its connection, with a sign-out button in the sidebar. Reloading the page asks again.

### Why not the alternatives

| Option | Why not |
|---|---|
| Streamlit's native login (`st.login`, OIDC) | Sign-in through Google or Microsoft: it needs an identity provider set up for one shared user, and the evaluator would need an account it accepts |
| An access gateway in front (Cloudflare Access or similar) | Needs a custom domain and another service to configure; out of proportion for one user |
| Users in the database | A user system (registration, hashing, resets) for two people |

## Consequences

- The evaluator gets the username and password with the delivery, through a one-time link (the course suggests onetimesecret), never in the repository or in an email in clear.
- The API is unchanged: its token, key, rate limit and spend cap still apply behind the login.
- One shared user means no per-person audit in the UI: the API's events still carry a `request_id` per request, but not who sent it. Per-person accounts would be the next step with more than a handful of users.
