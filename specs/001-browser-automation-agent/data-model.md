# Phase 1 Data Model: Browser Automation Agent

Entities derived from spec.md's Key Entities section, expanded with the fields needed to
satisfy the functional requirements and constitution principles referenced in brackets.

## Run

A single execution of the agent against one goal + start URL.

| Field | Type | Notes |
|-------|------|-------|
| `run_id` | string (UUID) | Stable identifier used in URLs and artifact paths |
| `goal` | string | Natural-language objective (FR-001) |
| `start_url` | string (URL) | Must be a public, no-login page (Principle II, FR-009) |
| `status` | enum: `pending`, `in_progress`, `completed`, `failed`, `incomplete` | `incomplete` = step limit reached without finishing (FR-008); `failed` = start URL unreachable or unrecoverable error (edge cases) |
| `provider` | enum: `anthropic`, `openai` | Recorded per run for traceability (Principle IV) |
| `created_at` / `finished_at` | timestamp | |
| `steps` | ordered list of `Step` | |
| `result_summary` | string \| null | Final human-readable outcome, only set from real step data (Principle V) |
| `is_seeded_sample` | boolean | True only for the built-in demo run injected at startup (FR-006); never true for a fabricated run |

**Validation rules**:
- `start_url` MUST be validated as a well-formed public URL before a run is created; rejected
  otherwise (edge case: unreachable/invalid URL → `failed`, not silently dropped).
- `status` transitions only forward: `pending → in_progress → {completed | failed | incomplete}`.
- A `Run` MUST NOT be marked `completed` unless every `Step` it references has a real
  `observation` and (for click/navigate-type actions) a real `screenshot_path` (Principle V).

## Step

One iteration of the observe → decide → act loop within a run.

| Field | Type | Notes |
|-------|------|-------|
| `run_id` | string | Parent run |
| `index` | integer | 1-based sequence order |
| `observation` | `PageSnapshot` | What the agent saw before deciding (see below) |
| `decision` | string | The model's stated reasoning/thought for this step (Principle V transparency) |
| `action` | `Action` | The action actually dispatched (see below) |
| `action_result` | string | Outcome of executing the action (e.g. navigation succeeded, element not found) |
| `screenshot_path` | string | Path under `screenshots/step-NN.png` (FR-003) |

**Validation rules**:
- `action.type` MUST be one of the seven neutral action types (FR-002); any other value is a
  contract violation, not a valid step.
- `screenshot_path` MUST reference a file that exists on disk before the step is considered
  complete (no fabricated steps — Principle V).

## PageSnapshot

The condensed, accessibility-style observation handed to the LLM and stored for
verifiability.

| Field | Type | Notes |
|-------|------|-------|
| `url` | string | Current page URL |
| `title` | string | Current page title |
| `visible_text_excerpt` | string | Condensed visible text (token-budget bounded) |
| `elements` | list of `ElementSnapshot` | Numbered interactive elements (Principle VI) |

## ElementSnapshot

A single interactive element made addressable for the LLM.

| Field | Type | Notes |
|-------|------|-------|
| `agent_id` | integer | Value of the injected `data-agent-id` attribute; stable only for this page state (Principle VI) |
| `tag` | string | e.g. `a`, `button`, `input`, `[role=...]` |
| `label` | string | Best-effort visible text / aria-label used for LLM disambiguation |

**Validation rules**:
- `agent_id` values MUST be unique within a single `PageSnapshot`.
- Hidden/non-visible elements MUST NOT appear in `elements` (matches the offline
  integration-test requirement to ignore hidden elements).

## Action (neutral action / tool call)

The provider-agnostic representation of "what to do next," decoupled from any vendor's
tool-call wire format (Principle IV).

| Field | Type | Notes |
|-------|------|-------|
| `type` | enum: `navigate`, `click`, `type_text`, `scroll`, `read_page`, `go_back`, `finish` | FR-002 |
| `target_agent_id` | integer \| null | Required for `click`/`type_text`; null for the others |
| `value` | string \| null | URL for `navigate`; text to type for `type_text`; null otherwise |
| `finish_summary` | string \| null | Required only when `type = finish`; becomes part of `Run.result_summary` |

## Conversation Turn (LLM abstraction)

The neutral dialogue representation mediating between the agent loop and provider adapters
(Principle IV); not persisted, but part of the contract between `agent.py` and `llm.py`.

| Variant | Carries |
|---------|---------|
| `UserTurn` | Initial goal + first `PageSnapshot` |
| `AssistantTurn` | The model's chosen `Action` (+ its stated `decision` reasoning) |
| `ToolResultsTurn` | The `action_result` + next `PageSnapshot` fed back to the model |

**Validation rules**:
- Adapters MUST losslessly round-trip these three variants to/from each provider's native
  format; a conversion that drops the reasoning/decision text is a contract violation
  (needed for `Step.decision`).

## ArtifactSet

The deliverable bundle for one run, always co-located under `app/runs/<run_id>/` (FR-003,
FR-016).

| File | Derived from | Notes |
|------|--------------|-------|
| `run.json` | `Run` (incl. all `Step` summaries) | Canonical state file polled by the web UI |
| `log.jsonl` | One line per `Step` (decision → action → observation) | Append-only event log |
| `screenshots/step-NN.png` | `Step.screenshot_path` | One per step |
| `report.md` | `Run` + `Step` list | Human-readable narrative |
| `data.json` | Extracted structured data referenced by `finish_summary` / steps | Machine-readable |

**Validation rules**:
- All five files MUST exist for any `Run` whose `status` is `completed`, `failed`, or
  `incomplete` (SC-003) — even failure/incomplete runs get a full, honest artifact set.
- None of the five files MUST ever contain the configured `anthropic_api_key` / `openai_api_key`
  value or any other secret (SC-007) — `RunLogger` MUST NOT write raw exception text or
  request/response payloads that could carry a credential; this is verified by an automated
  test that scans generated artifacts for the configured secret value.

## PresetTask

A predefined (goal, start_url) pairing for one-click/CLI triggering (FR-007).

| Field | Type | Notes |
|-------|------|-------|
| `key` | string | Stable identifier (e.g. `quotes_humor`) used by both dashboard button and CLI `--preset` flag |
| `label` | string | Human-readable name shown on the dashboard button |
| `goal` | string | Natural-language goal pre-filled |
| `start_url` | string | Must be a public, no-login, reliably stable page (research.md §4/§6) |

## RunManager (runtime state, not persisted per-run)

Enforces Principle VII.

| Field | Type | Notes |
|-------|------|-------|
| `active_run_id` | string \| null | Non-null while a run is `in_progress`; enforces single concurrency |
| `runs_started_today` | integer | Reset at day boundary; compared against `daily_run_limit` |
| `daily_run_limit` | integer | From configuration (env var), not hard-coded |
| `provider_ready` | boolean | `false` when `Configuration`'s API key for the selected `llm_provider` is missing (FR-017) |

**Validation rules**:
- A new run request MUST be rejected (not queued) whenever `active_run_id` is non-null,
  `runs_started_today >= daily_run_limit`, or `provider_ready` is `false`, per the spec's
  edge cases — the `provider_ready` check MUST run before any browser or LLM call is
  attempted, so a missing key fails fast with a configuration error rather than mid-run.

## Configuration (Principle II)

| Field | Source | Notes |
|-------|--------|-------|
| `llm_provider` | env `LLM_PROVIDER` | `anthropic` \| `openai` (Principle IV) |
| `anthropic_api_key` / `openai_api_key` | env, only the one matching `llm_provider` is required | Never logged, never committed (Principle II) |
| `daily_run_limit` | env `DAILY_RUN_LIMIT` | Feeds `RunManager.daily_run_limit` |
| `max_steps_per_run` | env (implementation default documented in plan, not user-facing) | Enforces FR-008's step-limit-without-success outcome |

## Entity Relationships

```text
PresetTask ──(fills)──▶ Run ──1:N──▶ Step ──1:1──▶ PageSnapshot ──1:N──▶ ElementSnapshot
                         │              └─1:1──▶ Action
                         └─1:1──▶ ArtifactSet

RunManager ──governs concurrency/quota for──▶ Run (creation only)
```
