# Contract: Command-Line Interface

`python -m app.cli`, satisfying the CLI half of FR-007 (User Story 3).

## Invocation forms

| Form | Behavior |
|------|----------|
| `python -m app.cli --preset <key>` | Runs the `PresetTask` identified by `key` (data-model.md) end-to-end, synchronously, printing progress to stdout | 
| `python -m app.cli --goal "<text>" --start-url "<url>"` | Runs a custom goal end-to-end, same execution path as the web dashboard's `POST /run` (no duplicate agent-loop implementation) |
| `python -m app.cli --list-presets` | Prints available preset keys + labels, no run triggered |

## Contract rules

- A CLI-triggered run MUST produce the exact same `ArtifactSet` (FR-003, FR-016) as a
  dashboard-triggered run — the CLI is an alternate trigger, not a parallel implementation.
- The CLI MUST respect the same single-concurrency and daily-quota rules as the web API
  (Principle VII) when running against a shared `app/runs/` state; it MUST refuse to start if
  another run is already active.
- Exit code `0` only on a `completed` run; non-zero for `failed`/`incomplete`/rejected, so the
  CLI is scriptable for verification (constitution's "verifiable" emphasis, SC-002/SC-003).
- The CLI MUST refuse to start (non-zero exit, clear message) if the configured provider's
  API key is missing, matching the web API's rejection behavior (FR-017) — checked before
  any browser or LLM call is attempted.
- All output MUST reflect real execution — no fabricated progress lines (Principle V).
