# Contract: Web Dashboard & API

Server-rendered dashboard (Jinja2) plus a small JSON API, exposed by `app/web/server.py`
(FastAPI). Satisfies spec FR-005, FR-006, FR-007 (dashboard half), FR-012, FR-013, FR-015.

## Pages (server-rendered)

| Method / Path | Purpose | Contract |
|---------------|---------|----------|
| `GET /` | Dashboard home | Renders: a form to submit a new run (goal + start_url), a row of preset-task buttons (FR-007), and a list of historical runs (newest first) including the seeded sample (FR-006) |
| `GET /runs/{run_id}` | Run detail page | Renders current `Run` state (status, steps so far, screenshots); MUST reflect newly completed steps on repeated polling without requiring the user to resubmit the page (User Story 2, AS2) |

## JSON API

| Method / Path | Request | Response | Contract |
|---------------|---------|----------|----------|
| `POST /run` | form fields: `goal` (string, required), `start_url` (string, required, valid URL) | `303` redirect to `/runs/{run_id}` on accept; `4xx` + error body if rejected | MUST reject (not queue) if `RunManager.active_run_id` is set (a run is already in progress) or the daily quota is exhausted (FR-012, FR-013); MUST reject if `start_url` is not a well-formed URL; MUST reject with a clear configuration-error message if the configured provider's API key is missing (FR-017), without ever echoing the key value itself |
| `GET /api/status` | — | `{ "busy": bool, "provider": "anthropic"\|"openai", "runs_started_today": int, "daily_run_limit": int, "provider_ready": bool }` | Reflects live `RunManager` state; `provider_ready` is `false` when the configured provider's API key is missing (FR-017); used by the dashboard to disable the trigger form while busy, over quota, or misconfigured |
| `GET /api/runs` | — | `[{ "run_id", "goal", "start_url", "status", "created_at", "finished_at" }, ...]` | Newest first; includes the seeded sample run |
| `GET /api/runs/{run_id}` | — | Full `Run` JSON including all `Step` entries | `404` if `run_id` unknown |
| `GET /artifacts/{run_id}/{path}` | — | Raw file bytes (screenshot / `report.md` / `data.json` / `log.jsonl`) | `404` if the run or file doesn't exist; MUST NOT allow path traversal outside that run's artifact directory |
| `GET /healthz` | — | `200 { "status": "ok" }` | No auth required; used as the public health-check indicator (FR-015) |

## Cross-cutting rules

- Every response reflecting a `Run` or `Step` MUST be sourced from the persisted `ArtifactSet`
  / `RunManager` state — never synthesized ad hoc by the web layer (Principle V).
- `POST /run` MUST NOT accept or require a login-page `start_url`; validation defers to the
  agent's own no-login boundary (Principle II) but obviously-authenticated URLs (e.g.
  containing common login-path patterns) MAY be rejected early as a best-effort UX
  improvement — this is optional hardening, not a substitute for the agent-level boundary.
- No endpoint ever accepts or returns an API key/credential value.
