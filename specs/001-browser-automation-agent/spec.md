# Feature Specification: Browser Automation Agent

**Feature Branch**: `001-browser-automation-agent`

**Created**: 2026-07-06

**Status**: Draft

**Input**: User description: "參考 Task3 - Browser Automation Agent.pdf 以及憲章" (Reference the Task3 - Browser Automation Agent.pdf and the project constitution)

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Run a Goal-Driven Browsing Task and Get a Verifiable Report (Priority: P1)

A user provides a natural-language goal (e.g. "collect all humor-tagged quotes") and a
starting web page URL through the dashboard. The system autonomously plans and executes a
sequence of browsing actions (open page, click, type, scroll, read, go back) until the goal
is achieved or a safety limit is reached, then hands back a report the user can trust and
inspect.

**Why this priority**: This is the entire value proposition of the product — without it,
there is no agent, just a form. Every other capability exists to support or expose this
core loop.

**Independent Test**: Submit a goal + start URL against a known, stable public page (e.g. a
quote-scraping practice site) and verify that a completed run produces a written report, a
structured data file, and a screenshot for every step, all consistent with each other.

**Acceptance Scenarios**:

1. **Given** the dashboard is open and idle, **When** the user submits a natural-language
   goal and a valid public start URL, **Then** the system begins a new run and shows it as
   in-progress within seconds.
2. **Given** a run is in progress, **When** the agent completes the goal, **Then** the run is
   marked finished and a Markdown report, a structured data file, per-step screenshots, and a
   full step log are all available for that run.
3. **Given** a completed run's report, **When** the user cross-checks a claim in the report
   against the corresponding step's screenshot, **Then** the screenshot supports the claim
   (no fabricated or unsupported statements).
4. **Given** a run that cannot achieve the goal within the allowed number of steps, **When**
   the step limit is reached, **Then** the run ends in a clearly labeled incomplete/failed
   state rather than being reported as successful.

---

### User Story 2 - Browse Run History and Live Progress (Priority: P2)

A user opens the web dashboard to see past runs (including a built-in example that is always
present) and, for an active run, watches its progress update step-by-step with screenshots as
it happens.

**Why this priority**: Demonstrable, inspectable history is what makes the tool trustworthy
and useful beyond a single one-off execution; it's also required for anyone evaluating the
tool without triggering their own run first.

**Independent Test**: Load the dashboard with no prior interaction and confirm at least one
historical run with its full artifacts is visible; separately, trigger a run and confirm its
detail page updates to reflect new steps without a manual page reload being required.

**Acceptance Scenarios**:

1. **Given** a fresh deployment with no user-triggered runs yet, **When** the user opens the
   dashboard, **Then** at least one historical run with a viewable report, data, and
   screenshots is already present.
2. **Given** a run in progress, **When** the user views that run's detail page, **Then** the
   page reflects newly completed steps and their screenshots without requiring a manual
   refresh.
3. **Given** a list of historical runs, **When** the user selects any past run, **Then** its
   full report, data, screenshots, and log are viewable and downloadable.

---

### User Story 3 - Trigger a Demo Task via One Click or Command Line (Priority: P3)

A user (e.g. an evaluator) wants to see the agent work without composing a goal from
scratch, either by clicking a ready-made preset task in the dashboard or by invoking a
command-line entry point with a preset name.

**Why this priority**: Lowers the friction to demonstrate and verify the system works,
independent of the user's ability to craft a good natural-language goal; important for
grading/demo scenarios but not required for the core capability to exist.

**Independent Test**: Click a preset task button in the dashboard and confirm it starts a run
with the expected goal and start URL pre-filled; separately, invoke the CLI with a preset
name and confirm it runs the same task end-to-end and produces the same artifact set.

**Acceptance Scenarios**:

1. **Given** the dashboard is open, **When** the user clicks a preset task button, **Then** a
   new run starts using that preset's predefined goal and start URL without further manual
   input.
2. **Given** a terminal with the CLI available, **When** the user invokes it with a preset
   task name, **Then** the same run type executes and produces the full artifact set (report,
   data, screenshots, log).

---

### Edge Cases

- What happens when the start URL is unreachable, times out, or returns an error page? The
  run MUST end in a clearly labeled failed state with a diagnostic message, not a silent
  success.
- What happens when the target page requires login? The system MUST refuse or stop rather
  than attempting to authenticate, per the no-login-page boundary.
- What happens when the agent cannot determine a next action (e.g. ambiguous page state)? The
  run MUST either make a best-effort decision and record its reasoning, or end in an
  incomplete state — it MUST NOT stall indefinitely.
- What happens when a second run is requested while one is already in progress? The request
  MUST be rejected or queued, never run concurrently, per the single-concurrency constraint.
- What happens when the daily run quota is exhausted? New run requests MUST be rejected with
  a clear message stating the quota has been reached, rather than silently failing.
- What happens when the site's structure changes mid-run (e.g. a button's class name
  changes)? The agent's element targeting MUST continue to function based on the current
  page snapshot rather than a hard-coded selector.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST accept a natural-language goal and a starting URL as input for a
  new run.
- **FR-002**: System MUST autonomously plan and execute a sequence of browser actions to
  pursue the stated goal, choosing from at least: open/navigate to a URL, click an element,
  type text into an element, scroll, read the current page content, go back to the previous
  page, and declare the goal finished.
- **FR-003**: System MUST produce, for every run regardless of outcome, a human-readable
  report, a structured machine-readable data file, a screenshot for each step taken, and a
  complete step-by-step execution log.
- **FR-004**: System MUST NOT fabricate or embellish reported results — every statement in
  the report and every data value MUST correspond to an action actually executed and page
  state actually observed during that run.
- **FR-005**: System MUST provide a web dashboard where a user can submit a new run, view a
  specific run's live step-by-step progress and screenshots, and browse the list of
  historical runs with their full artifacts.
- **FR-006**: System MUST provide at least one built-in example run (with its full artifact
  set) that is visible on the dashboard immediately, even on a freshly started deployment
  with no user-triggered runs yet.
- **FR-007**: System MUST provide both a one-click preset-task entry point (via the
  dashboard) and a command-line entry point for starting a run, and both MUST produce the
  same kind of full artifact set as a manually specified run.
- **FR-008**: System MUST end a run in a clearly labeled incomplete/failed state (not a
  false success) when the goal cannot be achieved within an allowed number of steps, or when
  the starting page is unreachable.
- **FR-009**: System MUST restrict automation to publicly accessible pages that do not
  require login, and MUST refuse to proceed if a target page requires authentication.
- **FR-010**: System MUST target on-page interactive elements in a way that remains
  functional when the page's markup changes (e.g. dynamic class names), rather than relying
  on brittle, hand-authored selectors.
- **FR-011**: System MUST keep all provider credentials and other secrets out of version
  control, sourcing them only from runtime configuration/environment.
- **FR-012**: System MUST limit execution to at most one run in progress at a time, rejecting
  or queuing additional run requests while a run is active.
- **FR-013**: System MUST enforce a configurable daily limit on the number of runs that can
  be started, and MUST reject new run requests once that limit is reached with a clear
  message.
- **FR-014**: System MUST allow the underlying AI decision-making provider to be switched via
  configuration, without requiring changes to how a run is requested or how its results are
  presented.
- **FR-015**: System MUST expose a public health-check indicator confirming the deployed
  service is reachable and operating.
- **FR-016**: System MUST maintain an automated test suite covering, at minimum:
  configuration handling, run/artifact lifecycle, preset task definitions, action dispatch
  logic (including the "finish" action), offline page element-targeting behavior (using
  local fixtures rather than live third-party sites), the AI-provider abstraction's
  correctness across providers, and web-service startup/routing/error handling. This suite
  MUST pass in full before any deployment.

### Key Entities

- **Run**: A single execution of the agent against one goal + start URL. Attributes include
  the goal, start URL, current status (in progress / completed / failed / incomplete), start
  and end time, and a reference to its full step sequence and final result summary.
- **Step**: One iteration of the agent's observe-decide-act loop within a run. Attributes
  include a sequence index, the decision/action taken, the resulting observation, and an
  associated screenshot.
- **Artifact Set**: The collection of deliverables produced per run — a human-readable
  report, a structured data export, the set of per-step screenshots, and the full event log
  — all traceable back to the same run.
- **Preset Task**: A predefined (goal, start URL) pairing offered for one-click or CLI
  triggering, used for demonstration and verification without requiring the user to compose
  a custom goal.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A user can go from opening the dashboard to viewing a triggered run's first
  in-progress step within 10 seconds of submission.
- **SC-002**: For a representative, well-scoped goal against a stable public page, the agent
  completes the stated goal without human intervention in at least 95% of attempts.
- **SC-003**: 100% of runs — completed, failed, or incomplete — produce a full, internally
  consistent artifact set (report, structured data, screenshots, log) that a human can verify
  independently against the screenshots.
- **SC-004**: On first load of a freshly deployed instance, a user can view at least one
  historical run's full results with zero prior setup or triggered runs.
- **SC-005**: A user can go from opening the dashboard to viewing a completed preset task's
  report in under 2 minutes.
- **SC-006**: Zero instances of a run being reported as successful when the stated goal was
  not actually achieved, across all verification testing.
- **SC-007**: Zero secrets (API keys or credentials) ever appear in version-controlled files
  or in any publicly viewable log or report.
- **SC-008**: 100% of the automated test suite (covering the areas listed in FR-016) passes
  with zero failures prior to every deployment.

## Assumptions

- The daily run limit and per-run step limit are operational safety parameters configurable
  by whoever operates the deployment; their exact numeric values are an implementation
  decision, not a user-facing product requirement.
- Preset/demo tasks target stable, publicly accessible pages chosen for reliability (rather
  than potentially volatile third-party sites), so that demonstrations are reproducible.
- The dashboard itself does not require user accounts or login; access control is limited to
  the daily run-quota and single-concurrency throttling described above. Broader multi-tenant
  access control is out of scope for this feature.
- Run artifacts may not persist indefinitely across redeployments of the hosting
  environment; the built-in example run (FR-006) exists specifically to guarantee visible
  content regardless of persistence behavior.
- Target sites that require login (e.g. authenticated SaaS tools) are explicitly out of
  scope; only publicly accessible, no-login pages are supported.
