# Contract: Agent Action / Tool Interface

The neutral tool/action interface the agent loop (`app/agent/agent.py`) dispatches through
`app/agent/tools.py` to `app/agent/browser.py`, independent of which LLM provider produced
the decision (Principle IV). Both the Anthropic and OpenAI adapters MUST expose these same
seven actions to their respective tool-use / function-calling mechanisms, differing only in
wire-format translation.

## Actions (FR-002)

| Action | Required fields (see `Action` in data-model.md) | Effect | Failure handling |
|--------|--------------------------------------------------|--------|-------------------|
| `navigate` | `value` = target URL | Loads the URL in the current page | If unreachable/timeout → `action_result` records the failure; does not crash the run (edge case) |
| `click` | `target_agent_id` | Clicks the element with that `data-agent-id` in the current `PageSnapshot` | If `target_agent_id` no longer exists (stale snapshot) → `action_result` reports "element not found," agent MUST re-observe rather than retry blindly |
| `type_text` | `target_agent_id`, `value` = text | Types `value` into the target element | Same stale-element handling as `click` |
| `scroll` | none | Scrolls the viewport (direction/amount is an implementation default, not user-facing) | Always succeeds unless the page itself errors |
| `read_page` | none | Forces a fresh `PageSnapshot` without taking any other action | Used when the agent needs more page content before deciding |
| `go_back` | none | Browser back navigation | If no history entry exists, `action_result` reports that, agent MUST adapt |
| `finish` | `finish_summary` | Ends the run as `completed`; summary feeds `Run.result_summary` and `report.md`/`data.json` generation | MUST NOT be honored unless at least one prior step produced real observations (a zero-step `finish` is not a valid completed run — Principle V) |

## Every action, regardless of type, MUST:

1. Be preceded by a `PageSnapshot` observation (Principle VI) — the agent never acts blind.
2. Produce an `action_result` string, even on failure — silence is not a valid outcome.
3. Result in exactly one new `Step` record with a screenshot taken after the action executes
   (FR-003), except when the action itself prevented reaching a stable page state (e.g. a
   fatal navigation error) — in that case the run transitions to `failed` with the last
   available screenshot, not a missing one.

## Step-limit contract (FR-008)

If the number of `Step`s reaches the configured `max_steps_per_run` (data-model.md
Configuration) without a `finish` action having been dispatched, the run MUST transition to
`incomplete` — never silently to `completed`.

## No-login boundary (Principle II, FR-009)

The agent MUST NOT attempt any action that would submit credentials or navigate through an
authentication flow. If a `navigate` or the initial `start_url` lands on a page the agent
detects as requiring login (e.g. a password field appears in the next `PageSnapshot`), the
agent MUST treat this as a terminal condition for the run (`failed`), not attempt to proceed.
