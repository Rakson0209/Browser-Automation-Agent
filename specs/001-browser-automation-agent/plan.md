# Implementation Plan: Browser Automation Agent

**Branch**: `001-browser-automation-agent` | **Date**: 2026-07-06 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-browser-automation-agent/spec.md`

**Note**: This template is filled in by the `/speckit-plan` command. See `.specify/templates/plan-template.md` for the execution workflow.

## Summary

Build an LLM-driven browser automation agent: given a natural-language goal and a starting
URL, the agent drives headless Chromium via Playwright through an observe → decide → act
loop (navigate / click / type_text / scroll / read_page / go_back / finish) until the goal is
achieved or a step limit is reached, producing a verifiable artifact set (report.md,
data.json, per-step screenshots, log.jsonl) for every run. A FastAPI + Jinja2 dashboard
exposes triggering, live progress, and run history; a CLI offers the same via preset tasks.
The LLM decision layer is provider-agnostic (Anthropic / OpenAI, switchable via
`LLM_PROVIDER`), element targeting uses a numbered-element-snapshot mechanism for resilience
to markup changes, and the whole system is containerized for arm64 CPU-only deployment
(Zeabur) with single-run concurrency and a daily run quota.

## Technical Context

**Language/Version**: Python 3.11 (mandated by constitution's Technology & Platform Constraints)

**Primary Dependencies**: Playwright (Chromium), Anthropic SDK, OpenAI SDK, FastAPI, Uvicorn,
Jinja2

**Storage**: Filesystem only — per-run directory (`app/runs/<run_id>/`) holding `run.json`,
`log.jsonl`, `screenshots/`, `report.md`, `data.json`; no database

**Testing**: pytest / pytest-asyncio — unit tests plus offline browser-integration tests
against local/embedded HTML fixtures (per constitution Principle III, no live third-party
site dependency in the suite)

**Target Platform**: Linux container, arm64 (Ampere A1, CPU-only, no GPU), deployed to
Zeabur; also runnable locally (Windows/macOS/Linux dev machines) via the same codebase

**Project Type**: Single-project web service with an embedded server-rendered dashboard and
a CLI entry point (no separate frontend build)

**Performance Goals**: First in-progress step visible within 10s of run submission (SC-001);
a preset task's completed report viewable within 2 minutes end-to-end (SC-005); representative
goals complete within a bounded step count without human intervention in ≥95% of attempts
(SC-002)

**Constraints**: CPU-only arm64 compute, no GPU fallback (constitution Technology & Platform
Constraints); exactly one run executing at a time (Principle VII); configurable daily run
quota enforced server-side (Principle VII); target pages must be public/no-login (Principle
II); run artifacts may be wiped on redeploy — a seeded example run guarantees dashboard
content on first load (spec FR-006, Assumptions)

**Scale/Scope**: Single-tenant demo/evaluation tool; a handful of preset tasks; one active run
at a time; historical runs bounded by filesystem retention, not by a target user count

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Gate | Status |
|-----------|------|--------|
| I. AI-Only Workflow with Semantic Commits | Procedural — enforced through the implementation process (Claude Code, semantic commits per layer), not a design artifact | PASS (process constraint, tracked during `/speckit-tasks` → implementation, not a plan-time blocker) |
| II. No Secrets, Environment-Only Configuration | Design MUST source all credentials from env/`.env` (git-ignored); contracts/data-model MUST NOT embed secrets; automation scope limited to public/no-login pages | PASS — config entity in data-model.md reads only from environment; no target requiring login is in scope |
| III. Layered, Test-Gated Development | Project structure MUST separate browser / agent / web layers, each independently testable; browser integration tests MUST use local fixtures | PASS — structure below mirrors this layering; quickstart.md's validation steps run layer tests in order |
| IV. Provider-Agnostic LLM Abstraction | Agent loop MUST NOT hard-code a vendor's request shape; neutral turn types + adapters required | PASS — data-model.md defines neutral `UserTurn`/`AssistantTurn`/`ToolResultsTurn`; contracts define adapter boundary, not vendor payloads |
| V. Verifiable, Non-Fabricated Artifacts | Every run MUST produce run.json/log.jsonl/screenshots/report.md/data.json reflecting real execution | PASS — data-model.md's `Run`/`Step`/`ArtifactSet` entities and the runs contract enforce this; no code path may synthesize an artifact without a matching real step |
| VI. Resilience via Numbered Element Snapshots | Element targeting MUST use numbered snapshots (`data-agent-id`), not brittle selectors | PASS — data-model.md's `ElementSnapshot`/`ElementHandle` entities and the browser-layer contract require this |
| VII. Security Boundaries & Resource Throttling | Public deployment MUST enforce daily run limit + single concurrency + containerization | PASS — data-model.md's `RunManager`/quota fields and the web contract's `/api/status` + `POST /run` behavior enforce this |
| Tech & Platform Constraints | Stack MUST be Python 3.11 / Playwright / Anthropic+OpenAI SDKs / FastAPI+Uvicorn / Jinja2 / Docker (`mcr.microsoft.com/playwright/python`) / Zeabur / pytest, arm64 CPU-only compatible | PASS — Technical Context above matches exactly; no substitution proposed |

No violations identified. Complexity Tracking table is not needed.

*Post-Phase-1 re-check*: Re-evaluated after producing data-model.md, contracts/, and
quickstart.md (see Phase 1 outputs) — no new gate violations introduced by the concrete
design; all rows above remain PASS.

## Project Structure

### Documentation (this feature)

```text
specs/001-browser-automation-agent/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
│   ├── web-api.md
│   ├── agent-tools.md
│   └── cli.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
app/
├── config.py             # Settings from env vars / .env (provider, keys, limits) — Principle II, VII
├── tasks.py               # Preset demo tasks (login-free, reproducible) — FR-007
├── runner.py              # RunManager: background execution, single concurrency, daily quota,
│                          #   history query, seeded demo-run injection — Principle VII, FR-006
├── cli.py                 # CLI entry point (preset tasks + custom goal/start-url) — FR-007
├── agent/
│   ├── browser.py         # Playwright wrapper + numbered-element-snapshot capture — Principle VI
│   ├── agent.py            # Provider-agnostic observe → decide → act loop — Principle IV
│   ├── llm.py              # Neutral turn types + Anthropic/OpenAI adapters — Principle IV
│   ├── tools.py             # Neutral tool/action definitions + dispatch to browser.py — FR-002
│   ├── prompts.py          # System prompt: honest reporting, public-pages-only — Principle II, V
│   └── logger.py           # run.json / log.jsonl / screenshots / report.md / data.json writer — FR-003, V
├── web/
│   ├── server.py           # FastAPI app: dashboard, trigger, live-progress API, health check — FR-005, FR-015
│   └── templates/          # Jinja2: base / index (history + trigger) / run (detail + live progress)
└── samples/                # Built-in seeded demo run injected into app/runs/ at startup — FR-006

tests/
├── unit/                   # config parsing, RunLogger artifact lifecycle, preset tasks,
│                          #   tool dispatch (incl. finish) — Principle III, FR-016
├── integration/             # Offline browser tests against local HTML fixtures — Principle III, FR-016
│                          #   (numbered-element snapshot correctness, error handling)
├── llm/                     # Neutral-turn ↔ Anthropic/OpenAI adapter conversion tests — FR-016
└── web/                     # Starlette TestClient: routes, API, error handling (e.g. missing key) — FR-016

Dockerfile                  # Base: mcr.microsoft.com/playwright/python (arm64-compatible) — Tech Constraints
requirements.txt
.claude/skills/             # Claude Code Agent Skill wrapping "run one browser-automation goal"
```

**Structure Decision**: Single Python project (no separate frontend — Jinja2 is
server-rendered inside `app/web/`). The layout mirrors the constitution's mandated module
boundaries (`app/agent/*`, `app/web/*`, `app/runner.py`, `app/cli.py`, `app/config.py`)
directly, so each architectural layer named in Principle III (browser → agent → web) has an
obvious home and can be tested independently before the next layer is built on it.

## Complexity Tracking

*No entries — Constitution Check reported no violations.*
