# Deferred: Starlette 1.x major upgrade

**Status:** deferred from the 2026-08-12 dependency-hardening PR.

**Why deferred:** two open Dependabot **high** alerts on Starlette have no fix in
the 0.x line — the vulnerable range is `>= 0.4.1, < 1.3.1`, so the only patch is
Starlette **1.3.1+**:

- SSRF + NTLM credential theft via UNC paths (patched 1.1.0) — Windows-specific;
  production runs Linux, so low real exposure.
- `request.form()` size limits silently ignored (patched 1.3.1) — DoS-ish.

Upgrading Starlette 0.52 → 1.6 is a **major framework bump**. It passed app import
(FastAPI 0.133 + Starlette 1.6, 113 routes) and 1105/1106 unit tests, but
introduced a **flaky test**: `test_linear_webhook.py::test_webhook_missing_delivery_header_rejected`
fails only under full-suite ordering with `ConnectionError('unexpected
connection_lost() call')` — a Starlette 1.x `TestClient` teardown race (the 1.x
TestClient deprecated its httpx transport: "install httpx2 instead"). The file
passes 18/18 in isolation, 3× consecutively.

**To do this properly (its own PR):**
1. Bump Starlette to >= 1.3.1 (target latest 1.x) via `uv lock --upgrade-package starlette`.
2. Fix the TestClient teardown flake — likely migrate the webhook tests' TestClient
   usage, or address the httpx→httpx2 deprecation, or ensure webhook background
   tasks cancel cleanly before teardown.
3. Smoke-test in production beyond unit tests: real webhook delivery (Linear/GitHub/
   Slack signature paths), SSE streaming endpoints, and the auth middleware — all
   sit on Starlette internals.
4. langchain-core 1.2 → 1.5 was also held back in the same conservative pass; bump
   it here or in its own step and re-run the LLM-path tests.
