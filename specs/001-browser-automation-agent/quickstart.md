# Quickstart Validation: Browser Automation Agent

Runnable steps to prove the feature works end-to-end, mapped back to the acceptance
scenarios in [spec.md](./spec.md) and the success criteria (SC-001..SC-008). This guide
references [data-model.md](./data-model.md) and [contracts/](./contracts/) rather than
duplicating their detail.

## Prerequisites

- Python 3.11 environment with project dependencies installed (`requirements.txt`) and
  Playwright's Chromium browser installed.
- `.env` populated from `.env.example` with `LLM_PROVIDER` set to `anthropic` or `openai` and
  the matching API key — per Principle II, never commit this file.
- No network dependency required for the automated test suite (Principle III); a live
  internet connection is only needed for manually triggering a real preset/custom run.

## 1. Layer-by-layer test gate (Principle III / FR-016)

Run in this order; each MUST pass before relying on the next layer:

1. `pytest tests/unit` — config parsing, artifact lifecycle, preset tasks, tool dispatch
   (incl. `finish`).
2. `pytest tests/integration` — offline browser tests against local HTML fixtures: numbered
   element snapshot correctness (visible elements tagged, hidden elements excluded), action
   dispatch by `data-agent-id`, error handling on stale/missing elements.
3. `pytest tests/llm` — neutral-turn ↔ Anthropic/OpenAI adapter conversion, provider/model
   resolution from configuration.
4. `pytest tests/web` — dashboard routes, JSON API, and error handling (e.g. `POST /run`
   rejected when no API key configured) via a test client.

**Expected outcome**: 100% pass, zero failures (SC-008), before proceeding to a live run.

## 2. Trigger a real run via the CLI (User Story 1 + 3)

```bash
python -m app.cli --list-presets
python -m app.cli --preset quotes_humor
```

**Expected outcome** (contracts/cli.md, contracts/agent-tools.md):
- Exit code `0`.
- `app/runs/<new_run_id>/` contains all five artifact files (`run.json`, `log.jsonl`,
  `screenshots/step-*.png`, `report.md`, `data.json`) — SC-003.
- `report.md`'s claims are each traceable to a step's screenshot — Acceptance Scenario 3 of
  User Story 1.

## 3. Trigger a run via the dashboard (User Story 1 + 2)

```bash
uvicorn app.web.server:app --reload
```

1. Open `http://localhost:8000/` — confirm the seeded sample run is already listed
   (Acceptance Scenario 1 of User Story 2 / SC-004), with no run triggered yet.
2. Click a preset-task button — confirm a new run starts immediately with the preset's goal
   and start URL pre-filled, no manual typing required (Acceptance Scenario 1 of User Story 3).
3. Watch `/runs/{run_id}` update with new steps/screenshots as they complete, without a
   manual page reload (Acceptance Scenario 2 of User Story 2) — should show the first
   in-progress step within 10 seconds of submission (SC-001).
4. Once finished, confirm the rendered report, downloadable `report.md` / `data.json` /
   `run.json` are all reachable via `GET /artifacts/...` (contracts/web-api.md).

**Expected outcome**: End-to-end, dashboard-to-report time under 2 minutes for a preset task
(SC-005).

## 4. Verify throttling (Principle VII / FR-012, FR-013)

1. While a run is `in_progress`, issue a second `POST /run` (or a second CLI invocation) —
   confirm it is rejected, not queued (edge case in spec.md).
2. Configure `DAILY_RUN_LIMIT=0` temporarily and confirm `POST /run` is rejected with a clear
   quota message, and `GET /api/status` reflects `runs_started_today >= daily_run_limit`.

## 5. Verify the no-login and failure boundaries (Principle II / FR-008, FR-009)

1. Submit a `start_url` that is unreachable (e.g. a non-routable host) — confirm the run ends
   `failed` with a diagnostic message, not `completed` (Acceptance Scenario 4 of User Story 1).
2. Submit a goal against a page requiring login — confirm the run ends `failed` rather than
   attempting to authenticate (edge cases in spec.md).

## 6. Health check (FR-015)

```bash
curl http://localhost:8000/healthz
```

**Expected outcome**: `200 { "status": "ok" }`, reachable without any credentials.

## Deployment sanity check (Technology & Platform Constraints)

Build and run the container locally to confirm arm64/CPU-only compatibility before deploying:

```bash
docker build -t browser-automation-agent .
docker run -p 8000:8000 --env-file .env browser-automation-agent
```

Confirm `/healthz` responds and a preset run completes inside the container with no
GPU-dependent code path invoked.
