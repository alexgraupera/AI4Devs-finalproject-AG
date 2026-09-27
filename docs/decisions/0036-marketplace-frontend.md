# 0036. A marketplace frontend with its own web server instead of Streamlit

- **Status**: Accepted
- **Date**: 2026-09-27
- **Issue**: #89 (part of #83)
- **Amends**: [ADR 0001](0001-stack-and-project-structure.md) (the interface) and [ADR 0034](0034-shared-login-for-the-ui.md) (where the login lives)

## Context

The Streamlit client of [ADR 0001](0001-stack-and-project-structure.md) had three pages, one per tool: a form for the pipeline review, one for the regulation Q&A and one for the agent. Each tool worked, but side by side they read as three demos rather than as a product: nothing said who uses each one, when, or what happens after. The project's own framing (a compliance assistant for a Spanish rental marketplace) had no marketplace in it.

The owner asked for the tools inside a marketplace flow, with fake data and design and real tools. Two constraints came with it. The API must keep its access model ([ADR 0020](0020-access-spend-and-probes.md)): only a backend holds the service token and the API key, never a browser. And the deployment stays on Render's free tier, with the URL already given to the evaluator.

## Decision

**Umbral, a fictional rental marketplace in React, served by its own small web server in Python.**

- **The frontend** (`frontend/`: Vite, React, TypeScript, Tailwind) is a portal: landing, search with the filters in the URL, listing pages with photos, a page to publish, "Mis anuncios" and the moderation queue. The 16 listings, the agencies and the photos (public domain, credited) are fictional, and a notice on every page says so; every review and every answer is real. Each tool sits where a portal would use it:
  - the **regulation Q&A** (RAG) is the assistant of each listing page, with questions read from the listing and a search limited to the laws of its municipality;
  - the **pipeline review** (CAG) is "Comprobar anuncio" while writing, cheap enough to repeat after every correction;
  - the **agent review** is the gate of "Enviar a publicar": approved is published and searchable, changes requested go back with the corrected listing, and a paused review joins the queue;
  - the **human in the loop** is `/moderacion`, the quality team's queue, whose decision resumes the paused run in the API.
- **The web server** (`web/`: FastAPI and httpx, no new dependency) is the marketplace's backend. It serves the built frontend, so the browser talks to one origin and needs no CORS, and it forwards to the API **only the calls the frontend makes**, listed one by one, adding the service token and the API key. The browser never holds either.
- **The shared login moves to the web server** with the rules of ADR 0034: one user from the environment, constant-time comparison, five failures lock a client for a minute, and production fails closed. The pages are public (fictional listings cost nothing to show); every tool call needs a session, a cookie signed with HMAC-SHA256 over its expiry and the username (`SESSION_SECRET`), `HttpOnly`, `SameSite=Strict` and `Secure` in production.
- **The landlord's listings live in the browser** (`localStorage`). The demo has no marketplace database; the API keeps only what it needs to pause a review (its Postgres checkpointer).
- **Same image, same Render service, same URL.** A Node stage builds the frontend from its lockfile and only its output reaches the image; the service that ran Streamlit keeps its name and runs the web server. Streamlit, its pages, tests, theme and dependency are removed.

### Why not the alternatives

| Option | Why not |
|---|---|
| A themed Streamlit | Streamlit lays out forms and results well, not a portal: no real routing, no listing cards or galleries, no floating assistant, and every click reruns the page. The tools would still read as three forms |
| An SPA calling the API directly | The browser would need the service token and the API key, which is exactly what ADR 0020 keeps out of it: anyone could read them from the page and call the API without the login |
| Next.js (server routes as the backend) | A second server runtime (Node) in production for what a hundred lines of Python do, and a framework the rest of the project does not use. The image would carry Node, not only its build |
| The API serving the frontend and the login | It would merge the client and the service the architecture keeps apart ([ADR 0001](0001-stack-and-project-structure.md)): the API would learn about sessions and pages, and the token would stop meaning "a trusted backend" |

## Consequences

- The evaluator sees the product the README describes: who uses each tool, when, and what happens next. The Streamlit screenshots of the README are replaced by the marketplace's.
- **The API does not change.** The marketplace consumes the endpoints that already existed; section 9 of the README ("how it would plug into a real marketplace") is no longer a promise but what the demo does.
- One more thing to build: the frontend has its own checks (TypeScript, ESLint, 110 Vitest tests, the build), run by `make verify` and CI, and the image has a Node stage.
- The landlord's listings are per browser: another browser, or the evaluator on another machine, starts with an empty "Mis anuncios" and an empty moderation queue. A real marketplace would keep them in its database; a paused review is still resumable from any browser that knows its run id.
- The lock of the login is per client address and in memory: it slows a person, not a distributed script, and a restart forgets it. The length of the password is what stops a script, as in ADR 0034.
- A session outlives nothing on the server: changing `SESSION_SECRET` or `UI_USERNAME` signs everyone out, which is also how to revoke access.
