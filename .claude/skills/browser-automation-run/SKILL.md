---
name: "browser-automation-run"
description: "Run one browser-automation goal end to end via the Browser Automation Agent CLI and report back the resulting verifiable artifacts (report, data, screenshots, log)."
argument-hint: "A preset key (e.g. 'quotes_humor'), or a natural-language goal and a start URL"
compatibility: "Requires this repository's app/ package, its Python dependencies installed, and a configured LLM_PROVIDER + matching API key in the environment/.env"
user-invocable: true
disable-model-invocation: false
---

## User Input

```text
$ARGUMENTS
```

You **MUST** consider the user input before proceeding. It is either:

- A preset key from `app/tasks.py` (e.g. `quotes_humor`, `hacker_news_top`), or
- A natural-language goal together with a starting URL (e.g. `goal: <text> start_url: <url>`), or
- Empty — in that case, list the available presets and ask which one to run, or ask for a
  goal + start URL.

## What this skill does

This skill is the repeatable, callable wrapper around "execute one browser-automation
goal end to end," satisfying the project constitution's requirement (Principle I) that
this capability exist as a Claude Code Agent Skill, not just inline application code. It
does not reimplement the agent — it drives the project's own CLI
(`python -m app.cli`), which shares the exact same `RunManager` → agent-loop → `RunLogger`
path as the web dashboard, so results are identical and equally verifiable
(constitution Principle V — no fabrication).

## Steps

1. **Resolve the working directory**: confirm you are at the repository root (the
   directory containing `app/`, `requirements.txt`, and `.env`/`.env.example`). If unsure,
   check for `app/cli.py`.

2. **Confirm prerequisites** (do not attempt to silently work around a missing one):
   - Python dependencies installed (`pip show playwright` should succeed; if not, tell the
     user to run `pip install -r requirements.txt && python -m playwright install
     chromium`).
   - A `.env` file (or equivalent environment variables) with `LLM_PROVIDER` set and the
     matching `ANTHROPIC_API_KEY` or `OPENAI_API_KEY` populated. If missing, tell the user
     exactly which variable is absent — do not guess or fabricate a key.

3. **Run the CLI** with the resolved input:
   - Preset: `python -m app.cli --preset <key>`
   - Custom goal: `python -m app.cli --goal "<goal>" --start-url "<start_url>"`
   - To see available presets first: `python -m app.cli --list-presets`

4. **Read back the real result** — never summarize a run from memory or assumption:
   - Note the printed `Run <id>: <status>` line and exit code (0 only means `completed`).
   - Read `app/runs/<run_id>/report.md` and `app/runs/<run_id>/data.json` and report their
     actual contents to the user.
   - Mention the screenshot count under `app/runs/<run_id>/screenshots/` so the user knows
     visual evidence exists, and point them at `app/runs/<run_id>/log.jsonl` for the full
     step-by-step trace.

5. **If the CLI rejects the run** (`Run rejected: ...`, non-zero exit before any run
   started), relay the exact rejection reason to the user (busy / daily quota reached /
   missing API key) rather than retrying silently — these rejections are intentional
   safety behavior (FR-012, FR-013, FR-017), not bugs to route around.

## Non-negotiable constraints (do not violate)

- Never invent, embellish, or "fill in" what a run supposedly found — only report what is
  actually present in that run's `report.md` / `data.json` / `log.jsonl` (constitution
  Principle V).
- Never target a page that requires login, and never attempt to supply credentials on the
  agent's behalf — this mirrors the agent's own no-login boundary (constitution
  Principle II).
- Never print or log the value of `ANTHROPIC_API_KEY` / `OPENAI_API_KEY`.
