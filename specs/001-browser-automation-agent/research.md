# Phase 0 Research: Browser Automation Agent

All technology choices are already mandated by the ratified constitution (v1.1.0), so no
`NEEDS CLARIFICATION` markers remain in the Technical Context. This document instead records
the design-level decisions needed to turn those mandated technologies into a working system,
each following Decision / Rationale / Alternatives Considered.

## 1. LLM decision-making pattern

**Decision**: Use native tool-use / function-calling on both providers (Anthropic tool-use,
OpenAI function-calling), mediated by a neutral turn representation
(`UserTurn` / `AssistantTurn` / `ToolResultsTurn`) that the agent loop emits and consumes.
Each provider adapter translates neutral turns to/from its wire format; the agent loop never
imports a provider SDK type directly.

**Rationale**: Both providers natively support structured tool calls, which is far more
reliable for extracting a discrete next-action (navigate/click/type_text/scroll/read_page/
go_back/finish) than parsing free-form text. A neutral turn layer is what makes Principle IV
(provider-agnostic abstraction) achievable without duplicating the agent loop per provider.

**Alternatives considered**: Free-text instruction parsing (rejected — fragile, requires
custom parsing/repair logic per provider); a single hard-coded provider (rejected — violates
Principle IV and constitution's explicit vendor-neutrality requirement).

## 2. Element targeting for reliability

**Decision**: On each observation, run a page-injected script that scans visible interactive
elements (`a`, `button`, `input`, `[role]`, etc.), assigns each a stable `data-agent-id`
attribute for the lifetime of that page state, and returns a condensed list (tag, visible
text/label, id) to the LLM. Actions reference elements purely by `data-agent-id`.

**Rationale**: This is the mechanism required by constitution Principle VI. It decouples the
LLM's targeting decision from the page's actual CSS/class structure, so redesigns or
dynamically generated class names don't break in-flight automation. It also shrinks the
token footprint versus passing raw HTML/DOM.

**Alternatives considered**: LLM-authored CSS selectors (rejected — brittle against dynamic
classes, explicitly what Principle VI exists to avoid); full accessibility-tree dump
(rejected — higher token cost, more noise for the model to reason over).

## 3. Run concurrency & daily quota enforcement

**Decision**: A single in-process `RunManager` owns an execution lock (only one run may be
"in progress" at a time) and a daily counter (reset by calendar day, configurable via
`DAILY_RUN_LIMIT`). New run requests while a run is active, or after the quota is reached,
are rejected synchronously with a clear status/message rather than queued silently.

**Rationale**: Satisfies Principle VII (single concurrency + throttling) with the simplest
mechanism that fits a single-container, single-tenant deployment — no external queue or
distributed lock is warranted at this scale (Scale/Scope in Technical Context).

**Alternatives considered**: External job queue (Redis/Celery) (rejected — unnecessary
operational complexity for a single-container CPU-only arm64 deployment; would also add a
dependency not in the mandated stack); silently queuing extra requests (rejected — spec edge
cases require a clear rejection, not silent delay).

## 4. Persisting a visible history under ephemeral storage

**Decision**: Ship one real, previously-executed run's full artifact set under `app/samples/`
in the repository; on process startup, copy it into `app/runs/` if not already present.

**Rationale**: Directly satisfies spec FR-006/SC-004 and the constitution's documented known
limitation (ephemeral filesystem on redeploy) — the dashboard always has verifiable content
on first load without requiring a user-triggered run first.

**Alternatives considered**: External persistent storage/bucket (rejected — adds
infrastructure and cost disproportionate to a single-tenant demo tool; also not in the
mandated stack); generating a fake/synthetic seed run (rejected — would violate Principle V's
non-fabrication rule, since it wouldn't correspond to a real execution).

## 5. arm64 / CPU-only compatibility

**Decision**: Base the container image on the official `mcr.microsoft.com/playwright/python`
image, which publishes multi-arch (amd64 + arm64) manifests, and pin the Playwright Python
package version known to have a matching arm64 browser build. No GPU-accelerated rendering
flags are used; Chromium runs in standard headless CPU mode.

**Rationale**: Directly satisfies the constitution's Compute Profile constraint (Arm Ampere
A1, CPU-only, no GPU) while still reusing the vendor-maintained image that bundles matching
browser binaries, avoiding a hand-rolled arm64 Chromium build.

**Alternatives considered**: A custom Dockerfile installing Chromium from scratch (rejected
— higher maintenance burden, risk of missing arm64 system dependencies that the official
image already resolves); GPU-accelerated headless mode (not applicable — no GPU exists on
the target compute).

## 6. Offline-first browser test strategy

**Decision**: Browser-integration tests serve local, embedded HTML fixtures (via a local file
URL or an in-test static file server) instead of hitting any live third-party website; only
manual/demo runs (preset tasks, seeded sample) touch real public sites.

**Rationale**: Required by Principle III and directly informed by the project's own
documented incident (an external site becoming unreliable mid-development); a deterministic
suite cannot depend on third-party uptime.

**Alternatives considered**: Recorded HTTP/network fixtures (VCR-style) (rejected — Playwright
drives a real browser process, not just HTTP calls, so network-level recording doesn't
capture the DOM/JS behavior being tested as faithfully as a real local page does).

## Open Questions

None — all decisions above are fully determined by the ratified constitution and the feature
spec; nothing here blocks proceeding to Phase 1.
