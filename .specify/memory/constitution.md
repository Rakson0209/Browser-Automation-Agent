<!--
Sync Impact Report
- Version change: 1.2.0 → 1.2.1 (container base-image correction — bug fix, no new
  principle/guidance, PATCH per versioning policy)
- Modified principles:
  - Technology & Platform Constraints — Containerization bullet corrected:
    `mcr.microsoft.com/playwright/python` is amd64-only (not multi-arch as previously
    assumed) and MUST NOT be used; switched to the genuinely multi-arch official
    `python` image + `playwright install --with-deps` at build time. Confirmed by an
    actual Zeabur deployment failing with `exec format error` on the previous image.
- Added sections: none
- Removed sections: none
- Templates requiring updates:
  - ✅ .specify/templates/plan-template.md (Constitution Check gate is generic — no edit needed)
  - ✅ .specify/templates/spec-template.md (no principle-specific references — no edit needed)
  - ✅ .specify/templates/tasks-template.md (no principle-specific references — no edit needed)
  - ✅ .specify/templates/commands/*.md — none present beyond the speckit command markdown already reviewed
- Follow-up TODOs: none
-->

# Browser Automation Agent Constitution

## Core Principles

### I. AI-Only Workflow with Semantic Commits

All implementation work MUST be produced through an AI coding agent workflow (Claude Code)
end-to-end — architecture decisions, code, tests, and documentation are all driven by the
agent loop of implement → run tests → fix, not by unreviewed hand-editing outside that loop.
Git history MUST read as a coherent, semantic narrative progressing through skeleton/config →
core agent loop → web layer → tests → docs/deployment, with each commit scoped to one
logical change (e.g. `feat(agent): ...`, `test: ...`, `docs+build: ...`). Reusable agent
behavior (e.g. "run one browser-automation goal end to end") SHOULD be packaged as a Claude
Code Agent Skill so it is callable as a repeatable capability, not just inline code.

**Rationale**: The project's grading and process integrity depend on the AI-only workflow
being visible and auditable through commit history, not asserted after the fact.

### II. No Secrets, Environment-Only Configuration (NON-NEGOTIABLE)

The operator's own credentials MUST be supplied only via environment variables / `.env`
(with `.env` excluded from version control) and MUST NEVER be committed, hard-coded, or
logged. As an alternative to the operator's default credential, a web user MAY optionally
supply their own LLM provider + API key for a single run ("bring your own key"); such a
key MUST be held only in memory for the duration of that one run, MUST NEVER be persisted
to disk, a session store, or any log/artifact on the server, and MUST be redacted with the
same rigor as the operator's own key wherever run output could contain it (Principle V).
Client-side remembering of a user-supplied key (e.g. browser `sessionStorage`) is
permitted since it never touches server-side storage. Automation targets are restricted to
publicly accessible, no-login pages and self-built test pages; the agent MUST NOT attempt
to bypass authentication or operate on systems requiring login or elevated access.

**Rationale**: The project is graded and deployed publicly; leaked keys or credential-bypass
behavior are unacceptable security and compliance failures, not stylistic concerns. A public
deployment that only ever runs on the operator's own key lets any visitor spend the
operator's quota/budget — letting a visitor supply their own key removes that exposure
without weakening the no-persistence guarantee that makes secret handling safe.

### III. Layered, Test-Gated Development

Each architectural layer — browser automation (`browser.py`) → agent loop (`agent.py`,
`llm.py`, `tools.py`) → web layer (`web/`, `runner.py`, `cli.py`) — MUST have passing
automated tests before the next layer is built on top of it. Any bug fix or behavior change
MUST be accompanied by a test that fails before the fix and passes after. Integration tests
that exercise the browser MUST run offline against embedded/local HTML fixtures so the suite
is deterministic and not dependent on third-party site availability.

**Rationale**: The project's own history shows an external dependency
(news.ycombinator.com) becoming unreliable mid-development; tests that depend on live
third-party sites are inherently flaky and MUST be avoided in favor of local fixtures.

### IV. Provider-Agnostic LLM Abstraction (NON-NEGOTIABLE)

The agent's core loop MUST NOT depend on any single LLM vendor's request/response shape. A
neutral turn representation (e.g. user turn / assistant turn / tool-results turn) MUST be
defined, with vendor-specific adapters (Anthropic tool-use, OpenAI function-calling)
translating to and from it. Vendor and model selection MUST be switchable purely through
configuration (e.g. an `LLM_PROVIDER` environment variable), with zero changes required to
the agent loop itself.

**Rationale**: Avoiding vendor lock-in lets the project run on whichever API key is
available and keeps grading/demo flexible across Anthropic and OpenAI.

### V. Verifiable, Non-Fabricated Artifacts (NON-NEGOTIABLE)

Every run MUST produce inspectable, structured artifacts: `run.json` (status/goal/step
summaries/result), `log.jsonl` (per-step think → act → observe events), per-step
screenshots, `report.md` (human-readable), and `data.json` (machine-readable extracted
data). Reported outcomes MUST reflect actions actually executed and page state actually
observed — fabricating, embellishing, or silently omitting failed steps is prohibited. Any
seeded/demo run MUST be clearly derived from a real execution, not synthesized.

**Rationale**: The deliverable's core value is that its output can be independently
verified by a human or a script; unverifiable or fabricated output defeats the project's
purpose.

### VI. Resilience via Numbered Element Snapshots

Interactive element targeting MUST use a numbered-element-snapshot mechanism (scanning
visible interactive elements and tagging them with a stable `data-agent-id`) rather than
hand-written CSS selectors tied to specific class names. The page state handed to the LLM
SHOULD be a condensed, accessibility-style view (not raw DOM/HTML) to control token cost
while preserving decision quality.

**Rationale**: Hand-written selectors break under site redesigns and dynamic class names;
numbered snapshots are the project's chosen mechanism for reliability against page changes,
and also reduce token spend versus raw markup.

### VII. Security Boundaries & Resource Throttling

Public-facing deployments MUST enforce a daily run limit and single-concurrency execution
(one run at a time) to bound cost and prevent resource exhaustion on constrained containers.
Any environment exposed publicly MUST be containerized (Docker, based on an official
Playwright browser image) rather than run bare. Automation scope remains limited to public,
no-login pages per Principle II.

**Rationale**: A publicly reachable trigger endpoint without throttling is an open invitation
to cost/resource abuse; containerization keeps browser + system dependencies reproducible
across local and deployed environments. Throttling to one run at a time is doubly important
given the CPU-only Arm compute profile (see Technology & Platform Constraints), which has no
GPU to fall back on for any parallelizable workload.

## Technology & Platform Constraints

The following stack is mandated for this project; substituting any element requires
explicit justification recorded in the relevant plan's Complexity Tracking section:

- **Language**: Python 3.11.
- **Browser automation**: Playwright (cross-browser, built-in auto-waiting).
- **LLM SDKs**: Anthropic and OpenAI SDKs, accessed only through the neutral abstraction
  required by Principle IV.
- **Web service**: FastAPI + Uvicorn (async, lightweight, matches the agent's async loop;
  built-in type validation).
- **Templating**: Jinja2 server-side templates for the dashboard (no separate frontend
  build pipeline).
- **Containerization**: Docker, based on the official `python` Docker Library image (a
  genuinely multi-arch manifest list), installing Chromium via `playwright install
  --with-deps` at build time rather than a pre-baked, architecture-specific browser
  layer. `mcr.microsoft.com/playwright/python` MUST NOT be used as the base image — it is
  amd64-only today and fails with `exec format error` on arm64 hosts (confirmed by an
  actual failed Zeabur deployment); any future base-image change MUST verify true
  multi-arch (arm64) support before adoption, not assume it from documentation alone.
- **Deployment platform**: Zeabur (or an equivalent PaaS that supports Dockerfile deploys,
  injected environment variables/secrets, and a generated public domain).
- **Compute profile**: The deployment target is Arm-based (Ampere A1) CPU-only compute — no
  GPU is available. All inference is performed remotely via the LLM provider APIs (Principle
  IV), so no local model inference is required; however, all local work (Playwright/Chromium
  rendering, image/screenshot handling, any other on-container processing) MUST run correctly
  on CPU-only arm64 hardware with no assumption of CUDA/GPU acceleration. Container base
  images and all dependencies MUST have arm64-compatible builds (e.g. the official Playwright
  image's multi-arch manifest); any dependency without arm64 support MUST be replaced or
  justified in the plan's Complexity Tracking section.
- **Testing**: pytest / pytest-asyncio, covering unit tests and offline integration tests
  per Principle III.

## Development Workflow & Documentation

- Development MUST proceed in the layered order: skeleton & config → core agent loop
  (browser + LLM tool-use + execution logging) → web dashboard + run coordinator + CLI →
  automated tests → docs & deployment — matching Principle III's test gate at each step.
- The README MUST explain how to run and verify the system, state key assumptions made
  during development, and describe how the AI workflow was used to build it.
- Known limitations (e.g. ephemeral filesystem storage on redeploy, single-run concurrency,
  no-login-only scope) MUST be documented explicitly rather than left implicit, along with
  any mitigation in place (e.g. a seeded demo run to guarantee content on first load).
- A one-click preset-task entry point and a CLI entry point MUST both remain available for
  demonstration and verification purposes.

## Governance

This constitution supersedes any conflicting ad-hoc practice for this project. All plans,
specs, and task lists produced by the speckit workflow MUST pass the Constitution Check
gate before implementation proceeds; any violation MUST be justified in the plan's
Complexity Tracking table or the design MUST be simplified to comply.

**Amendment procedure**: Amendments are made by editing this file directly, updating the
Sync Impact Report at the top of the file, and propagating any required changes to
dependent templates (`plan-template.md`, `spec-template.md`, `tasks-template.md`, command
files) in the same change.

**Versioning policy**: Semantic versioning applies to this document —
MAJOR for backward-incompatible principle removals/redefinitions, MINOR for new principles
or materially expanded guidance, PATCH for clarifications and wording fixes.

**Compliance review**: Every `/speckit-plan` run MUST re-check the Constitution Check gate
after Phase 1 design, and any reviewer of generated plans/tasks MUST verify they do not
violate Principles II, IV, or V (the NON-NEGOTIABLE items) before approving implementation.

**Version**: 1.2.1 | **Ratified**: 2026-07-06 | **Last Amended**: 2026-07-06
