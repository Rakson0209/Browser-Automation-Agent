# Browser Automation Agent

An LLM-driven browser automation agent: give it a natural-language goal and a starting
URL, and it drives headless Chromium (via Playwright) through an observe → decide → act
loop until the goal is achieved or a safety limit is reached — producing a verifiable
artifact set (Markdown report, structured data, per-step screenshots, and a full event
log) for every run, successful or not.

Full requirements, architecture, and design rationale live under
[`specs/001-browser-automation-agent/`](specs/001-browser-automation-agent/) (spec, plan,
research, data model, contracts, tasks) and the project's governing principles are in
[`.specify/memory/constitution.md`](.specify/memory/constitution.md).

## How it works

1. **Observe**: the current page is scanned and every visible interactive element
   (`a`, `button`, `input`, …) is tagged with a numbered `data-agent-id` attribute, so
   the model can target elements by number instead of a brittle CSS selector — this
   keeps the agent resilient to site redesigns and dynamic class names.
2. **Decide**: the numbered snapshot plus the goal are sent to the configured LLM
   provider (Anthropic or OpenAI — or any OpenAI-compatible endpoint, see below —
   switchable via `LLM_PROVIDER`) via a neutral tool-use abstraction, which returns
   exactly one next action: `navigate`, `click`, `type_text`,
   `scroll`, `read_page`, `go_back`, or `finish`.
3. **Act**: the action is dispatched against the real browser, a screenshot is taken, and
   the step (decision → action → observation) is appended to the run's log.
4. Repeat until `finish` is called or the step limit is reached (→ `incomplete`), or until
   the run fails (unreachable start URL, or a login wall — this agent only automates
   public, no-login pages).

Every run — completed, failed, or incomplete — leaves behind:

| File | Contents |
|------|----------|
| `report.md` | Human-readable narrative of the run |
| `data.json` | Structured, machine-checkable result data |
| `screenshots/step-NN.png` | One screenshot per step |
| `run.json` | Canonical state file (goal, status, all steps, result) |
| `log.jsonl` | Append-only per-step event log |

under `app/runs/<run_id>/`.

## Running it locally

```bash
python -m venv .venv
.venv\Scripts\activate          # Windows PowerShell: .venv\Scripts\Activate.ps1
pip install -r requirements.txt
python -m playwright install chromium

copy .env.example .env          # then set LLM_PROVIDER and the matching API key
```

**Web dashboard:**

```bash
uvicorn app.web.server:app --reload
# open http://localhost:8000
```

The dashboard shows a built-in example run (`app/samples/seed-quotes-humor/`, a genuine
4-step execution against quotes.toscrape.com) immediately, even before you trigger
anything — this guarantees there's always something verifiable to look at, since the
`app/runs/` directory is ephemeral across redeploys on most PaaS platforms.

**Bring your own key**: the trigger form has a "Use server default" / "Use my own key"
toggle. On a public deployment, a visitor who doesn't want to (or shouldn't) spend the
operator's own budget can switch to "custom," pick a provider, and paste in their own API
key. That key is used only for that one run, is remembered in the browser's own
`sessionStorage` for convenience (never sent anywhere except back to this server when
triggering a run), and is never written to disk, a session store, or any log/report on
the server (constitution Principle II).

**Using DeepSeek (or any other OpenAI-compatible API)**: `LLM_PROVIDER=openai` doesn't
have to mean OpenAI itself — set `OPENAI_BASE_URL` to any endpoint that speaks the same
chat-completions wire format (DeepSeek, Together.ai, a local vLLM server, ...):

```bash
LLM_PROVIDER=openai
OPENAI_API_KEY=<your DeepSeek key>
OPENAI_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat
```

No code changes needed — this applies to both the server's own default credential and to
"bring your own key" visitors who pick "openai" (they inherit whatever `OPENAI_BASE_URL`
the operator configured, using their own key against that same endpoint). The web form
itself does not let a visitor specify an arbitrary base URL, to avoid turning the trigger
endpoint into an open-ended request proxy — only the operator's env var controls routing.

**CLI:**

```bash
python -m app.cli --list-presets
python -m app.cli --preset quotes_humor
python -m app.cli --goal "collect all humor-tagged quotes" --start-url "https://quotes.toscrape.com/tag/humor/"
```

## Running the tests

```bash
pytest tests/unit tests/llm tests/integration tests/web -q
```

All tests run offline — the browser-integration suite drives real Chromium against local
HTML fixtures under `tests/integration/fixtures/`, never a live third-party site, so the
suite doesn't depend on any external service being reachable. As of this writing all
tests pass (78 tests: config incl. OpenAI-compatible endpoint overrides, LLM adapters,
browser snapshotting, action dispatch, artifact logging incl. secret redaction, run
throttling incl. bring-your-own-key, the full agent loop incl. an unexpected-error safety
net, the web API, presets, and the CLI).

## Key assumptions

- **Daily run limit and per-run step limit** (`DAILY_RUN_LIMIT`, `MAX_STEPS_PER_RUN`) are
  operational safety knobs for whoever deploys this, not user-facing product decisions —
  reasonable defaults ship in `.env.example`.
- **No user accounts**: the dashboard itself has no login; the only access control is the
  daily quota and single-run concurrency.
- **Public, no-login pages only**: the agent will refuse to proceed if the start page (or
  any page reached mid-run) shows a login form. Sites requiring authentication are out of
  scope.
- **One run at a time**: a single in-process lock enforces this — a second concurrent
  request is rejected outright, never queued, to bound cost/resource usage.
- **Ephemeral storage**: `app/runs/` is not assumed durable across redeploys; the seeded
  sample run is the mitigation, not a workaround for a bug.

## Deployment (Zeabur or an equivalent PaaS)

The `Dockerfile` is based on the official `python:3.11-slim-bookworm` image — a genuinely
multi-arch manifest list (this project's target compute is Arm-based, Ampere A1,
CPU-only, no GPU; see the constitution's Compute Profile constraint) — and installs
Chromium via `playwright install --with-deps`, which runs Playwright's own OS-dependency
installer for whatever architecture the build actually runs on.

> **Do not** base this on `mcr.microsoft.com/playwright/python`: that image is amd64-only
> today. Using it produced a real Zeabur deployment failure (`exec /usr/bin/sh: exec
> format error` — the classic architecture-mismatch symptom) before this was corrected.

Configure these environment variables on the platform (never commit them):

| Variable | Purpose |
|----------|---------|
| `LLM_PROVIDER` | `anthropic` or `openai` |
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | Only the one matching `LLM_PROVIDER` is required |
| `DAILY_RUN_LIMIT` | Max runs per day before new triggers are rejected |
| `MAX_STEPS_PER_RUN` | Step ceiling before a run ends `incomplete` |

The platform injects `$PORT`; the container's `CMD` already honors it.

> **Note on this build**: the Dockerfile was authored without a local Docker daemon
> available in the development sandbox, so it could not be build-tested before the first
> real Zeabur deployment attempt — that attempt failed with an architecture mismatch (see
> above), which is now fixed. If you hit further deploy failures, check the Zeabur build
> logs for the actual error rather than assuming the Dockerfile is correct; it has still
> only been verified via one real deployment attempt, not build-tested locally.

## AI-only development workflow

This project was built end-to-end through Claude Code, following the layered order
mandated by the constitution: skeleton/config → foundational engine (LLM abstraction,
browser wrapper, action dispatch, artifact logging, run throttling) → User Story 1 (core
agent loop + CLI) → User Story 2 (web dashboard) → User Story 3 (presets) → polish
(container, docs, Agent Skill). Each layer's automated tests were written and run before
building the next layer on top of it (constitution Principle III), and git history is
organized into one semantic commit per layer/story rather than one giant commit. A
reusable Claude Code Agent Skill for "run one browser-automation goal end to end" lives
under [`.claude/skills/browser-automation-run/`](.claude/skills/browser-automation-run/).

## Known limitations

- `app/runs/` may be wiped on redeploy on some platforms; the seeded sample mitigates
  this for the dashboard's first-load experience, but user-triggered runs are still not
  guaranteed to survive a redeploy.
- The agent is fed a text/accessibility-style view of each page, not a screenshot, as its
  *decision* input (screenshots are captured for the artifact record, not fed back to the
  model) — a future iteration could add real vision input for purely graphical UIs.
- Only one run executes at a time by design (Principle VII) — a queue and horizontal
  scaling are out of scope for this iteration.
- Only public, no-login pages are supported; authenticated sites need separate handling
  this project does not attempt.
