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

## Validation Log (2026-07-06, implementation sandbox)

Executed as part of `/speckit-implement` (T052). This sandbox had no live LLM API key
and no Docker daemon available, so results are split accordingly:

**Verified live in this environment:**

- §1 Layer-by-layer test gate: `pytest tests/unit tests/llm tests/integration tests/web`
  → **63/63 passed**, zero failures (SC-008).
- §2 CLI: `python -m app.cli --list-presets` → prints both presets, no run triggered.
  `python -m app.cli --preset quotes_humor` with no API key configured → rejected with
  `Run rejected: Configured provider 'anthropic' has no API key set`, exit code 1 (FR-017)
  — confirms the CLI's provider-readiness gate runs before any browser/LLM call.
- §3 Dashboard: started `uvicorn app.web.server:app`; `GET /` shows the seeded
  `seed-quotes-humor` run's goal text with zero prior interaction (SC-004); `GET
  /api/status` reflects `provider_ready: false` when no key is set.
- §4 Throttling: `POST /run` with no API key configured → `409` (FR-017); a malformed
  `start_url` → `400`. Busy/quota rejection paths are additionally covered by
  `tests/unit/test_runner.py` and `tests/web/test_run_trigger.py` (concurrency and quota
  are hard to trigger live without a real long-running run, so those two are verified via
  the automated suite instead of manually).
- §5 No-login/failure boundaries: covered live by the automated integration suite
  (`test_agent_loop_failed_url.py`, `test_agent_loop_login_boundary.py`) rather than a
  manual run, for the same reason as above (deterministic, offline, repeatable).
- §6 Health check: `GET /healthz` → `200 {"status": "ok"}`.

**Not executable in this sandbox — left for whoever has the missing credential/tool:**

- A full real, LLM-driven run via CLI or dashboard (steps 2–3's "expected outcome"
  sections describing a `completed` run) requires a real `ANTHROPIC_API_KEY` or
  `OPENAI_API_KEY`, which this sandbox does not have. The seeded sample run
  (`app/samples/seed-quotes-humor/`) is a genuine prior execution of this exact scenario
  (real Playwright session, real extracted quotes, real screenshots) and stands in as
  evidence that the artifact pipeline works end-to-end; only the *LLM decision-making*
  step itself is unverified live here (it is verified structurally via
  `tests/llm/test_llm_adapters.py` and the scripted-LLM integration tests).
- The Docker/arm64 sanity check requires a Docker daemon, which is not available in this
  sandbox (`docker --version` → command not found). The `Dockerfile` was authored per the
  constitution's Compute Profile constraint (official multi-arch Playwright base image,
  re-running `playwright install` to match the pinned pip version) but has not been
  build-tested.
- T053 (actual deployment to Zeabur) requires platform account credentials this sandbox
  does not have.
