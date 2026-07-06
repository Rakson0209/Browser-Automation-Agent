---

description: "Task list for implementing the Browser Automation Agent feature"
---

# Tasks: Browser Automation Agent

**Input**: Design documents from `D:\code\specs\001-browser-automation-agent\`

**Prerequisites**: [plan.md](./plan.md) (required), [spec.md](./spec.md) (required for user stories), [research.md](./research.md), [data-model.md](./data-model.md), [contracts/](./contracts/), [quickstart.md](./quickstart.md)

**Tests**: Tests are included — spec.md's FR-016/SC-008 and constitution Principle III explicitly require a layered automated test suite (unit, offline integration, LLM-adapter, web) that must pass in full before deployment.

**Organization**: Tasks are grouped by user story (from spec.md: US1=P1, US2=P2, US3=P3) to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks)
- **[Story]**: Which user story this task belongs to (US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

Single project per [plan.md](./plan.md) Structure Decision: `app/` at repository root (with `app/agent/`, `app/web/`, `app/samples/`), `tests/` at repository root (`tests/unit`, `tests/integration`, `tests/llm`, `tests/web`).

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [X] T001 Create project directory structure per [plan.md](./plan.md): `app/agent/`, `app/web/templates/`, `app/samples/`, `tests/unit/`, `tests/integration/`, `tests/llm/`, `tests/web/`, `.claude/skills/`
- [X] T002 Create `requirements.txt` at repository root listing `playwright`, `anthropic`, `openai`, `fastapi`, `uvicorn`, `jinja2`, `python-dotenv`, `pytest`, `pytest-asyncio`
- [X] T003 [P] Create `.env.example` at repository root documenting `LLM_PROVIDER`, `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `DAILY_RUN_LIMIT`, `MAX_STEPS_PER_RUN` (data-model.md Configuration; constitution Principle II)
- [X] T004 [P] Add `.env`, `app/runs/`, `__pycache__/`, `.pytest_cache/` to `.gitignore` at repository root (constitution Principle II)

**Checkpoint**: Repository skeleton exists; no secrets committed.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The core engine (config, LLM abstraction, browser snapshot, action dispatch, artifact logging, run concurrency/quota) that every user story's trigger surface depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

- [X] T005 [P] Implement configuration loader in `app/config.py` reading `LLM_PROVIDER`, `ANTHROPIC_API_KEY`/`OPENAI_API_KEY`, `DAILY_RUN_LIMIT`, `MAX_STEPS_PER_RUN` from environment/`.env`, exposing an `is_provider_ready()` check that is `false` when the selected provider's API key is missing (data-model.md Configuration; constitution Principle II; FR-017)
- [X] T006 [P] Unit test for the config loader (missing key, invalid provider, defaults, `is_provider_ready()` returning `false` when the selected provider's key is absent) in `tests/unit/test_config.py` — write first, must fail before T005 is complete
- [X] T007 Define neutral turn/action types — `UserTurn`, `AssistantTurn`, `ToolResultsTurn`, `Action`, `PageSnapshot`, `ElementSnapshot` — in `app/agent/llm.py` (data-model.md; contracts/agent-tools.md; constitution Principle IV)
- [X] T008 Implement the Anthropic tool-use adapter translating neutral turns to/from Anthropic's API in `app/agent/llm.py` (research.md §1) — depends on T007
- [X] T009 Implement the OpenAI function-calling adapter translating neutral turns to/from OpenAI's API in `app/agent/llm.py` (research.md §1) — depends on T007
- [X] T010 [P] Adapter tests: neutral-turn round-trip through both Anthropic and OpenAI formats, plus provider/model resolution, in `tests/llm/test_llm_adapters.py` — write first, must fail before T008/T009 complete
- [X] T011 [P] Implement the Playwright browser wrapper with numbered-element-snapshot capture (`data-agent-id` tagging of visible interactive elements) in `app/agent/browser.py` (constitution Principle VI; contracts/agent-tools.md)
- [X] T012 [P] Offline integration tests against local embedded HTML fixtures verifying visible elements are tagged, hidden elements are excluded, and stale/missing `data-agent-id` targets are handled gracefully, in `tests/integration/test_browser_snapshot.py` — write first, must fail before T011 complete
- [X] T013 [P] Implement the neutral action schema and dispatch-to-browser logic for `navigate`/`click`/`type_text`/`scroll`/`read_page`/`go_back`/`finish` in `app/agent/tools.py` (contracts/agent-tools.md FR-002)
- [X] T014 [P] Unit tests for action dispatch, including `finish` validity rules and stale-element error handling, in `tests/unit/test_tools_dispatch.py` — write first, must fail before T013 complete
- [X] T015 [P] Write the system prompt (honest reporting requirement, public-pages-only / no-login boundary) in `app/agent/prompts.py` (constitution Principle II, V; contracts/agent-tools.md no-login boundary)
- [X] T016 Implement `RunLogger` managing the `run.json` / `log.jsonl` / `screenshots/` / `report.md` / `data.json` artifact lifecycle in `app/agent/logger.py` (data-model.md ArtifactSet; constitution Principle V), ensuring no exception text or request/response payload written to any artifact ever contains the configured API key value (data-model.md ArtifactSet validation rules; SC-007) — depends on T007, T013
- [X] T017 [P] Unit tests confirming all five artifact files exist and are internally consistent for completed, failed, and incomplete runs, AND that none of the five files contain the configured API key value (scan artifact contents for the secret string), in `tests/unit/test_logger.py` — write first, must fail before T016 complete
- [X] T018 Implement `RunManager` — single-concurrency lock, daily quota tracking, provider-readiness check (rejecting a new run before any browser/LLM call if `config.is_provider_ready()` is `false`), run history query, and seeded-sample injection at startup — in `app/runner.py` (data-model.md RunManager; constitution Principle VII; research.md §3–4; FR-017) — depends on T005, T016
- [X] T019 [P] Unit tests for `RunManager` concurrency rejection, quota rejection, provider-not-ready rejection (clear configuration-error message, no browser/LLM call attempted), and seeded-sample injection in `tests/unit/test_runner.py` — write first, must fail before T018 complete
- [X] T020 Add one real, previously-executed run's full artifact set under `app/samples/` for startup seeding (research.md §4; FR-006) — depends on T016

**Checkpoint**: Foundation ready — config, LLM abstraction, resilient browser snapshotting, action dispatch, verifiable artifact logging, and run throttling all exist and are independently tested. User story implementation can now begin.

---

## Phase 3: User Story 1 - Run a Goal-Driven Browsing Task and Get a Verifiable Report (Priority: P1) 🎯 MVP

**Goal**: The agent autonomously drives a browser from a natural-language goal + start URL to a verifiable artifact set (report, data, screenshots, log), ending in `completed`, `failed`, or `incomplete` as appropriate — never a false success.

**Independent Test**: Per [quickstart.md](./quickstart.md) §2 — invoke a custom goal end-to-end and confirm all five artifact files exist under `app/runs/<run_id>/` and are mutually consistent.

### Tests for User Story 1

- [X] T021 [P] [US1] Integration test: full observe→decide→act loop completes a goal against a local multi-page HTML fixture, producing a `completed` run with consistent `run.json`/`log.jsonl`/`screenshots/`/`report.md`/`data.json`, in `tests/integration/test_agent_loop_success.py`
- [X] T022 [P] [US1] Integration test: agent reaches `MAX_STEPS_PER_RUN` without a `finish` action and the run ends `incomplete` (not falsely `completed`), in `tests/integration/test_agent_loop_incomplete.py` (FR-008)
- [X] T023 [P] [US1] Integration test: an unreachable/invalid start URL ends the run `failed` with a diagnostic message, in `tests/integration/test_agent_loop_failed_url.py` (edge case)
- [X] T024 [P] [US1] Integration test: a fixture page requiring login ends the run `failed` without any authentication attempt, in `tests/integration/test_agent_loop_login_boundary.py` (constitution Principle II; FR-009)

### Implementation for User Story 1

- [X] T025 [US1] Implement the `Run`/`Step` state model and status transitions (`pending → in_progress → {completed|failed|incomplete}`) in `app/agent/agent.py` (data-model.md Run/Step) — depends on T007, T013, T016
- [X] T026 [US1] Implement the observe→decide→act main loop in `app/agent/agent.py`: capture a `PageSnapshot` via `browser.py`, request the next `Action` via `llm.py`, dispatch it via `tools.py`, and log the resulting `Step` via `logger.py`, repeating until `finish` or the step limit — depends on T025
- [X] T027 [US1] Implement the step-limit→`incomplete`, unreachable-URL→`failed`, and login-detected→`failed` transitions in `app/agent/agent.py` (FR-008, FR-009) — depends on T026
- [X] T028 [US1] Implement `report.md` and `data.json` generation from the completed `Run`/`Step` sequence in `app/agent/logger.py` (FR-003) — depends on T016, T026
- [X] T029 [US1] Wire `RunManager` to invoke the agent loop synchronously for a given goal/start_url in `app/runner.py` (FR-001) — depends on T018, T026
- [X] T030 [US1] Implement a minimal CLI custom-goal invocation (`python -m app.cli --goal "..." --start-url "..."`) exercising the full loop in `app/cli.py` (contracts/cli.md) — depends on T029

**Checkpoint**: User Story 1 is fully functional and independently testable — a custom goal can be run via the CLI end-to-end and produces a verifiable artifact set.

---

## Phase 4: User Story 2 - Browse Run History and Live Progress (Priority: P2)

**Goal**: A web dashboard where a user can trigger a run, watch its live per-step progress, and browse historical runs (including a seeded example visible on first load).

**Independent Test**: Per [quickstart.md](./quickstart.md) §3 — a fresh instance shows the seeded sample run with no prior interaction, and a triggered run's detail page updates with new steps without a manual reload.

### Tests for User Story 2

- [X] T031 [P] [US2] Web test: `GET /` lists the seeded sample run on a fresh instance with zero user-triggered runs, in `tests/web/test_dashboard_home.py` (contracts/web-api.md; FR-006/SC-004)
- [X] T032 [P] [US2] Web test: `POST /run` is rejected (not queued) while a run is `in_progress`, the daily quota is exhausted, or the configured provider's API key is missing (clear configuration-error message, no run started), in `tests/web/test_run_trigger.py` (contracts/web-api.md; FR-012/FR-013/FR-017)
- [X] T033 [P] [US2] Web test: `GET /runs/{id}`, `GET /api/runs`, `GET /api/runs/{id}`, and `GET /artifacts/{run_id}/{path}` return correct data, 404 on unknown IDs, and reject path traversal, in `tests/web/test_run_detail_api.py` (contracts/web-api.md)
- [X] T034 [P] [US2] Web test: `GET /healthz` returns 200 with no credentials required, in `tests/web/test_health.py` (FR-015)

### Implementation for User Story 2

- [X] T035 [P] [US2] Create the shared Jinja2 base template in `app/web/templates/base.html`
- [X] T036 [US2] Create the dashboard home template (trigger form, preset-button placeholders, history list) in `app/web/templates/index.html` — depends on T035
- [X] T037 [US2] Create the run detail template (status, steps, screenshots) in `app/web/templates/run.html` — depends on T035
- [X] T038 [US2] Implement the FastAPI app with `GET /`, `GET /runs/{run_id}`, `POST /run`, `GET /api/status` (including a `provider_ready` field), `GET /api/runs`, `GET /api/runs/{run_id}`, `GET /artifacts/{run_id}/{path}`, `GET /healthz` in `app/web/server.py` (contracts/web-api.md) — depends on T018, T029, T036, T037
- [X] T039 [US2] Wire `POST /run` to `RunManager` with start-URL validation and synchronous rejection when busy, quota-exhausted, or the provider is not ready (missing API key), in `app/web/server.py` (FR-012/FR-013/FR-017) — depends on T038
- [X] T040 [US2] Implement client-side polling of `GET /api/runs/{run_id}` on an interval in `app/web/templates/run.html` so the detail page reflects new steps without a manual reload (User Story 2, Acceptance Scenario 2) — depends on T037, T038
- [X] T041 [US2] Ensure `app/web/server.py` startup injects the seeded sample run from `app/samples/` via `RunManager` before serving requests — depends on T018, T020, T038

**Checkpoint**: User Stories 1 AND 2 both work — dashboard trigger, live progress, and history (with seeded content) are all functional.

---

## Phase 5: User Story 3 - Trigger a Demo Task via One Click or Command Line (Priority: P3)

**Goal**: Preset (goal, start_url) tasks are triggerable both from a dashboard button and from the CLI, producing the same artifact set as a custom run.

**Independent Test**: Per [quickstart.md](./quickstart.md) §2 and §3 — `python -m app.cli --preset <key>` and clicking a dashboard preset button both start the same run type and produce a full artifact set.

### Tests for User Story 3

- [X] T042 [P] [US3] Unit tests for preset task definitions (key/label/goal/start_url fields present and valid) in `tests/unit/test_presets.py` (FR-007)
- [X] T043 [P] [US3] CLI tests: `--list-presets` prints available presets without triggering a run; `--preset <key>` exits 0 and produces the full artifact set; invoking any run-triggering flag with no configured provider API key exits non-zero with a clear message and starts no run, in `tests/unit/test_cli.py` (contracts/cli.md; FR-017)

### Implementation for User Story 3

- [X] T044 [P] [US3] Define preset tasks (e.g. a quote-scraping preset and a Hacker News preset) in `app/tasks.py`, targeting stable public pages (data-model.md PresetTask; research.md §6)
- [X] T045 [US3] Implement `--preset`, `--goal`/`--start-url`, and `--list-presets` CLI flags dispatching through `RunManager` (including the provider-readiness rejection) in `app/cli.py` (contracts/cli.md; FR-017) — depends on T029, T044
- [X] T046 [US3] Add preset-task buttons to `app/web/templates/index.html`, submitting via `data-*` attributes and `addEventListener` rather than inline `onclick` (avoids the quoting bug documented in the reference PDF) — depends on T036, T044
- [X] T047 [US3] Wire preset-button submissions to `POST /run` with the preset's goal/start_url pre-filled in `app/web/server.py` — depends on T038, T044, T046

**Checkpoint**: All three user stories are independently functional — FR-007's one-click and CLI entry points are both complete.

---

## Phase 6: Polish & Cross-Cutting Concerns

**Purpose**: Deployment readiness and documentation spanning all user stories

- [X] T048 [P] Write `Dockerfile` at repository root based on `mcr.microsoft.com/playwright/python` (arm64-compatible), running via `uvicorn` and honoring an injected `$PORT` (constitution Technology & Platform Constraints; research.md §5)
- [X] T049 [P] Write `README.md` at repository root covering run/verify instructions, key assumptions, and how the AI-only workflow was used (constitution Development Workflow & Documentation)
- [X] T050 [P] Package "run one browser-automation goal end to end" as a Claude Code Agent Skill under `.claude/skills/` (constitution Principle I)
- [X] T051 Run the full test suite (`tests/unit`, `tests/integration`, `tests/llm`, `tests/web`) and confirm 100% pass with zero failures (FR-016; SC-008) — 63/63 passed
- [X] T052 Execute the full [quickstart.md](./quickstart.md) validation end-to-end (CLI, dashboard, throttling, failure boundaries, health check, Docker arm64 sanity check) and record results — see quickstart.md's Validation Log; Docker/live-LLM steps deferred (no Docker daemon / API key in this sandbox)
- [ ] T053 Deploy the container to Zeabur (or an equivalent PaaS), inject secrets via platform environment variables, and verify the public URL and `/healthz` respond (constitution Technology & Platform Constraints; Principle VII) — **requires user's Zeabur account/credentials; not executable autonomously**

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: No dependencies — start immediately.
- **Foundational (Phase 2)**: Depends on Setup completion — BLOCKS all user stories.
- **User Story 1 (Phase 3)**: Depends on Foundational completion. No dependency on US2/US3.
- **User Story 2 (Phase 4)**: Depends on Foundational completion; reuses US1's `agent.py` loop and `RunManager` wiring (T026, T029) but adds no new dependency on US1's CLI (T030) or US3.
- **User Story 3 (Phase 5)**: Depends on Foundational completion and on `RunManager`/CLI wiring from US1 (T029) and templates from US2 (T036); this is an intentional integration point since presets are, by definition, a pre-filled trigger for the same engine.
- **Polish (Phase 6)**: Depends on all desired user stories being complete.

### User Story Dependencies

- **User Story 1 (P1)**: No dependency on other stories — can be fully verified via the CLI alone.
- **User Story 2 (P2)**: Builds the dashboard on top of the Foundational engine and US1's `agent.py`/`RunManager` wiring; independently testable via its own acceptance scenarios (dashboard-only, no preset tasks required).
- **User Story 3 (P3)**: Builds on US1's CLI wiring (T029/T030) and US2's dashboard template (T036); independently testable via its own acceptance scenarios (presets only, no custom-goal composition required).

### Within Each User Story

- Tests MUST be written and FAIL before implementation (constitution Principle III).
- Data/state model before the main loop; main loop before status-transition edge cases.
- Engine wiring (`RunManager`) before the trigger surface that calls it (CLI or web).
- Story complete before moving to the next priority.

### Parallel Opportunities

- All Setup tasks marked [P] (T003, T004) can run in parallel once T001/T002 exist.
- Within Foundational: T005/T006 (config), T007→T008/T009/T010 (LLM abstraction), T011/T012 (browser), T013/T014 (tools), T015 (prompts) are independent file groups and can proceed in parallel; T016/T017 and T018/T019/T020 depend on the earlier groups finishing first.
- All four US1 test tasks (T021–T024) are separate files and can run in parallel once written.
- All four US2 test tasks (T031–T034) are separate files and can run in parallel.
- Both US3 test tasks (T042–T043) are separate files and can run in parallel.
- T048, T049, T050 in Polish are independent files and can run in parallel.

---

## Parallel Example: User Story 1

```bash
# Launch all tests for User Story 1 together (write first, confirm they fail):
Task: "Integration test: full agent loop success in tests/integration/test_agent_loop_success.py"
Task: "Integration test: step-limit incomplete in tests/integration/test_agent_loop_incomplete.py"
Task: "Integration test: unreachable URL failed in tests/integration/test_agent_loop_failed_url.py"
Task: "Integration test: login boundary failed in tests/integration/test_agent_loop_login_boundary.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational (CRITICAL — blocks all stories)
3. Complete Phase 3: User Story 1
4. **STOP and VALIDATE**: Run [quickstart.md](./quickstart.md) §2 (CLI custom goal) independently
5. This is already a demonstrable MVP: a goal-driven agent producing verifiable artifacts via the CLI

### Incremental Delivery

1. Setup + Foundational → engine ready, fully unit/integration tested
2. Add User Story 1 → verify via CLI → MVP demonstrable
3. Add User Story 2 → verify via dashboard (trigger + live progress + history) → richer demo
4. Add User Story 3 → verify via preset button/CLI flag → lowest-friction demo
5. Polish → containerize, document, package as an Agent Skill, deploy publicly

### Parallel Team Strategy

With multiple developers:

1. Team completes Setup + Foundational together (the engine is shared and must be solid first).
2. Once Foundational is done:
   - Developer A: User Story 1 (agent loop + minimal CLI)
   - Developer B: User Story 2 (dashboard), starting once T026/T029 stubs exist
   - Developer C: User Story 3 (presets), starting once T029 and T036 exist
3. Stories integrate at the noted intentional dependency points (US3 → US1's CLI wiring and US2's template).

---

## Notes

- [P] tasks = different files, no unmet dependencies.
- [Story] label maps task to specific user story for traceability.
- Tests are required by FR-016/SC-008 — write them first and confirm they fail before implementing.
- Commit after each task or logical group, following semantic commit style (constitution Principle I).
- Stop at any checkpoint to validate a story independently via [quickstart.md](./quickstart.md).
- Avoid: vague tasks, same-file conflicts marked [P], cross-story dependencies that break independent testability beyond the two intentional integration points noted above.
