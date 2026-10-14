# AI PR & Code Review Triage Agent — Build Log

This document records everything built for this project, in the order it was built, including reasoning behind each decision, the APIs/tools used, and configuration explained in plain language. Intended so anyone (recruiter, interviewer, future you) can read it and understand the full system without reading the code.

---

## Decisions Made

### Backend Framework: FastAPI (Python)

**Decision:** Build the backend in FastAPI rather than Spring Boot.

**Reasoning:** The developer's primary professional experience is Java/Spring Boot (8+ years). FastAPI was chosen deliberately for this project to demonstrate range across stacks, and because the broader AI agent tooling ecosystem (LangChain, most agent frameworks) is Python-native. This is a conscious portfolio decision, not a skills gap — Spring Boot remains the primary professional stack.

---

## Phase 1 — Observation Mode

*Goal: agent reads PRs, generates a plain-language summary, flags risk, suggests a reviewer, and posts the result as a PR comment. No auto-actions (no merging, approving, or blocking).*

### Step 1: Project Setup
*Status: complete*

Created the base project structure:

```
pr-triage-agent/
├── app/
│   ├── agent/            # (empty for now — filled in Steps 4-6)
│   ├── main.py            # (not yet created — Step 3+)
│   ├── github_client.py
│   └── models.py          # (not yet created)
├── .env.example
├── .gitignore
└── requirements.txt
```

**Why this structure:** each concern is isolated into its own file/folder — GitHub communication, the AI agent logic, and data shapes are all kept separate. This makes each piece independently understandable and testable, and it's a structure any engineer would recognize immediately when reviewing the repo.

**Dependencies installed (requirements.txt):**
| Package | Purpose |
|---|---|
| fastapi | Web framework — defines the API endpoints |
| uvicorn | The server that actually runs the FastAPI app |
| requests | Makes HTTP calls to GitHub's API |
| python-dotenv | Loads secrets from the local `.env` file |

**Secrets handling:** `.env` holds real credentials and is never committed (enforced via `.gitignore`). `.env.example` is a safe, fake-value template that *is* committed, documenting what secrets the project needs without exposing them.

### Step 2: GitHub API Connection
*Status: complete — verified with real authenticated request*

**Target repo:** `gangadhara18/pr-triage-agent-testbed` (public, created fresh for this project)

**Authentication method:** GitHub fine-grained Personal Access Token (PAT), scoped narrowly to:
- This repo only (not full account access)
- `Pull requests: Read and write` (needed to fetch PR data and post comments)
- `Contents: Read-only` (needed to read file/diff contents)
- 90-day expiration (forces periodic rotation rather than a token that lives forever)

**Why a fine-grained token instead of a classic one:** classic PATs grant broad access across your whole account; fine-grained tokens can be scoped to a single repo and specific permissions, so a leak has minimal blast radius.

**Code:** `app/github_client.py` — a `GitHubClient` class that:
- Reads the token from the `GITHUB_TOKEN` environment variable (never hardcoded)
- Builds the authorization headers required by every GitHub API request
- Includes a `verify_connection()` sanity-check method that calls GitHub's `/user` endpoint

**Verified:** ran locally via `test_connection.py`, authenticated successfully as `gangadhara18`.

**Rate limits observed during development:** hit GitHub's unauthenticated limit (60 requests/hour) twice while testing without a token from the sandbox. Authenticated requests raise this to ~5,000/hour — confirmed this is resolved once the token is used.

### Step 3: Fetching PR Data
*Status: complete — verified with real PR #1 on the test repo*

**What was built:** three new methods on `GitHubClient`:

| Method | Purpose | GitHub endpoint used |
|---|---|---|
| `get_pull_request()` | Title, author, state, base/head branches, description | `GET /repos/{repo}/pulls/{pr_number}` |
| `get_pull_request_files()` | List of changed files with add/delete line counts | `GET /repos/{repo}/pulls/{pr_number}/files` |
| `get_pull_request_diff()` | Raw diff text (the actual +/- code changes) | Same PR endpoint, requested with a special `Accept: application/vnd.github.v3.diff` header instead of the default JSON header |

**Why the diff needs a different Accept header:** GitHub's API can return the same PR resource in different formats depending on what you ask for — normally JSON, but a `diff`-specific media type returns the raw patch text instead. This is what the summarizer (Step 4) will actually read.

**Verified output** (real PR #1, "Create CONTRIBUTING.md"):
```
Title: Create CONTRIBUTING.md
Author: gangadhara18
State: open
Base branch: main
Head branch: add-contributing-guide
Changed files: CONTRIBUTING.md — +2/-0 (added)
Diff confirmed readable (raw +/- patch text returned correctly)
```

**Local environment setup used for this verification:**
- Python virtual environment (`venv`)
- Dependencies installed via `pip install -r requirements.txt`
- Real token stored only in a local `.env` file (never committed, never shared in any chat/log)
- Verification script: `test_connection.py` — deliberately designed to print only the *results* of using the token, never the token itself, so its output is safe to share anywhere

### Step 4: Summarizer Agent Step
*Status: complete — verified with real Claude API call against real PR data*

**What was built:** `app/agent/summarizer.py` — a `Summarizer` class with one method, `summarize()`, that takes a PR's title, description, and diff, and returns a plain-language explanation of the change.

**Prompt design:**
- A system prompt explicitly defines Claude's role ("you summarize code changes for a busy reviewer") rather than just pasting the diff with no framing — this consistently produces more useful, focused output than an unguided prompt.
- Title + description + diff are all passed together: the diff shows *what* changed, the title/description often shows *why* — combining both produces a better summary than the diff alone.
- Output is constrained to 2-4 sentences, no line-by-line restating, no bullet points — keeps it genuinely skimmable rather than a restructured diff.

**Model used:** `claude-sonnet-5`, called via the official `anthropic` Python SDK.

**Bug encountered and fixed:** the initial code included a `temperature=0.2` parameter (intended to reduce randomness in the output). This model version rejected the request with `400 - temperature is deprecated for this model`. Removed the parameter; the API call succeeded immediately after. Worth noting in interviews as a real example of adapting to a model API change rather than a design flaw.

**Verified output** (real PR #1, "Create CONTRIBUTING.md", body empty):
```
This PR adds a new CONTRIBUTING.md file to the repository, currently
containing only placeholder/sample text. It appears to be a starting
point for contribution guidelines, likely intended to be fleshed out
with actual content later.
```

**Additional real-world evaluation (2 more test PRs, beyond the initial placeholder PR):**

| PR | Description | Summarizer output quality |
|---|---|---|
| #2 — "Add retry helper utility" | Real Python function (retry wrapper), with a proper PR description | Correctly explained the function's purpose AND independently caught that the pasted code was invalid Python (missing newlines/indentation from a GitHub web-editor paste issue) — flagged as needing fixing before merge, unprompted |
| #3 — "Update admin permission check" | A deliberately "risky" change: an admin check hardcoded to always return `True`, with the real check commented out | Correctly identified the security implication ("would grant admin access to any user if merged as-is") and recommended it not be merged as-is — despite the summarizer having no explicit risk-detection instructions in its prompt |

**Observation:** even without dedicated risk-flagging logic, the summarizer surfaced genuine risk signals on its own by reasoning about the diff content. This is a good early signal for Step 5 (the dedicated Risk Classifier), which will make this kind of flagging structured and consistent rather than incidental.

**New dependency:** `anthropic==0.40.0` (official Python SDK for the Claude API).

**Secret added:** `ANTHROPIC_API_KEY` in local `.env` (fine-grained static API key, 90-day expiration, billed separately from claude.ai chat usage).

### Step 5: Risk Classifier Step
*Status: complete — tested for both true positives and false positives*

**What was built:** `app/agent/risk_classifier.py` — a `RiskClassifier` class returning structured JSON (not free text) with three boolean flags plus a reasoning field:
- `breaking_change`
- `security_sensitive`
- `test_coverage_gap`

**Why structured JSON instead of a text description:** downstream, this needs to power a dashboard (sort/filter by risk, show a badge) — that only works reliably on structured data, not a paragraph.

**Real quirk handled:** even with an explicit "respond with ONLY JSON" instruction, Claude sometimes still wraps the response in a ` ```json ` code fence. The code strips this defensively before parsing rather than assuming the instruction is always followed exactly.

**Test 1 — PR #3 (admin permission bypass, high risk expected):**
```
Breaking change: True
Security sensitive: True
Test coverage gap: True
Reasoning: This introduces a new admin permission check that always returns
True, bypassing the actual role check (a critical security flaw left in
from local testing), and changes access control behavior with no
accompanying tests.
```

**Test 2 — PR #2 (retry helper utility, low risk expected):**
```
Breaking change: False
Security sensitive: False
Test coverage gap: True
Reasoning: This adds a new standalone utility function with no changes to
existing APIs, schemas, or auth/security logic, but no test file was added
to cover the new retry logic.
```

**Refinement iteration — fixing the breaking_change conflation:**

The prompt was tightened to score each risk flag independently, with an explicit rule: a brand-new function with no existing callers cannot be `breaking_change`, regardless of how risky it looks for other reasons (that belongs under `security_sensitive` instead).

Verified before/after on PR #3 (admin permission bypass):

| Flag | Before fix | After fix |
|---|---|---|
| breaking_change | `True` (incorrect) | `False` (correct) |
| security_sensitive | `True` | `True` (unchanged) |
| test_coverage_gap | `True` | `True` (unchanged) |

Confirmed the fix was precise, not a regression — `security_sensitive` and `test_coverage_gap` stayed correctly `True` while only the mis-scored `breaking_change` flag changed. The model's updated reasoning explicitly stated *why*: "it's a new file so nothing depends on it yet (not breaking)" — showing the independent-scoring instruction was followed, not just a lucky output.

**Also fixed during this phase:** both `Summarizer` and `RiskClassifier` were hardened against an edge case where Claude's response occasionally contains no text content block (observed once during development, likely a transient API-side issue). Both now search for the text block explicitly and raise a clear error naming the `stop_reason` if none is found, rather than crashing on a bare `AttributeError`.

**Combined output preview (`test_combined.py`):** confirms what the eventual GitHub PR comment (Step 7) will contain — summary and risk assessment together in one readable report, generated from two independent, separately-testable agent calls.

### Step 6: Reviewer Matcher Step
*Status: complete*

**What was built:** `app/agent/reviewer_matcher.py` — a `ReviewerMatcher` class that suggests a PR reviewer based on who's actually committed to the changed files before. No AI/LLM involved here, deliberately — this is a solved, deterministic problem (count commit authors, exclude the PR's own author, suggest the top match), and using an LLM for it would be unnecessary complexity for no real benefit. Same reasoning as the pipeline's direct-REST decision: use AI (or a protocol layer) where it adds real value, not by default everywhere.

**Logic:** for each changed file, fetch its recent commit history via a new `GitHubClient.get_file_commits()` method. Tally commit authors with a `Counter`, excluding the PR's own author (can't be your own reviewer). Suggest the most frequent contributor, with a confidence score (their share of the relevant commits). If no history exists from anyone but the PR author, return `None` with a clear "assign manually" reasoning rather than guessing or crashing.

**Real limitation of the test repo:** since `pr-triage-agent-testbed` is brand new and solo-authored, there's no real multi-author commit history to test the "found a match" path against. Verified with real data:
```
Suggested: None
Confidence: 0
Reasoning: No commit history found for these files from anyone other
than the PR author — likely new files or a new repo. Assign manually.
```
This is the correct result for this data — not a bug.

**Testing the actual selection logic separately:** since real data can't exercise the "match found" path, wrote `test_reviewer_matcher_logic.py` using a fake/test-double `GitHubClient` with fabricated multi-author commit history, to verify the counting and exclusion logic directly:
```
Suggested: priya
Confidence: 0.75
Reasoning: priya authored 3 of 4 relevant prior commits to these files.
```
Correctly picked the majority contributor and correctly excluded the PR author from being suggested as their own reviewer.

### Step 7: Posting Results Back to GitHub
*Status: complete — real comment posted to a live PR*

**What was built:**
- `GitHubClient.post_pr_comment()` — posts a comment via GitHub's `/issues/{pr_number}/comments` endpoint (GitHub treats PR comments as issue comments under the hood — a quirk of their API, not a design choice on our end).
- `app/orchestrator.py` — `run_triage()` runs all three agent steps (summarizer, risk classifier, reviewer matcher) against a PR and formats one combined Markdown comment. Kept separate from the posting logic itself, so formatting can be tested independently of actually writing to GitHub.
- `test_post_comment.py` — shows the exact comment text and explicitly asks for a typed `yes` confirmation before posting anything. This was a deliberate safety choice, since this is the first step in the project that writes to GitHub instead of only reading.

**Bug encountered and fixed:** the first real run failed with `JSONDecodeError: Unterminated string`. Root cause: `max_tokens=300` on the risk classifier was too low, and the response got cut off mid-JSON before it could close properly. Fixed by raising the limit to 600 and adding a proper error handler that surfaces the raw response text and `stop_reason` on any future parse failure, instead of a bare JSON error with no context.

**Real comment posted to PR #3:** [github.com/gangadhara18/pr-triage-agent-testbed/pull/3#issuecomment-5444261077](https://github.com/gangadhara18/pr-triage-agent-testbed/pull/3#issuecomment-5444261077)

```
🤖 AI PR Triage — Automated Analysis

Summary
This change adds a new auth/permissions.py file with a check_admin_access
function intended to verify whether a user has admin privileges. However,
as written, the function unconditionally returns True and bypasses the
actual role check (user.role == 'admin' is commented out), with a note
indicating this was meant as a temporary testing shortcut. This looks
like debug/testing code that was accidentally left in and should not be
merged as-is, since it would grant admin access to all users regardless
of role.

Risk Assessment
⚪ Breaking change: False
🔴 Security sensitive: True
🟡 Test coverage gap: True

This is a new file so nothing yet depends on it, but it implements admin
access control and contains a hardcoded bypass ('return True') that
disables the actual role check, making it highly security sensitive. No
test files were added or modified to cover this new permission logic.

Suggested Reviewer
No suggestion available — not enough commit history. Assign manually.

⚠️ This is an automated analysis to assist review, not a decision. A
human reviewer should verify all findings before acting on them.
```

**This completes Phase 1 (Observation Mode) end-to-end**, as scoped in the original product doc: the agent reads a real PR, generates a summary, flags risk, suggests a reviewer, and posts its findings — entirely advisory, no auto-actions taken.

### Step 8: End-to-End Test
*Status: complete — two real, contrasting examples posted to live PRs*

| | PR #2 — retry helper (real feature) | PR #3 — admin bypass (security issue) |
|---|---|---|
| Breaking change | False | False |
| Security sensitive | **False** | **True** |
| Test coverage gap | True | True |
| Reviewer | Manual (no history) | Manual (no history) |
| Posted comment | [#issuecomment-5444441240](https://github.com/gangadhara18/pr-triage-agent-testbed/pull/2#issuecomment-5444441240) | [#issuecomment-5444261077](https://github.com/gangadhara18/pr-triage-agent-testbed/pull/3#issuecomment-5444261077) |

### Feature Addition: Suggested Fix
*Status: complete — added after Phase 1 completion, based on real reflection during testing*

**What was added:** a `suggested_fix` field on the risk classifier's output — a specific, actionable fix (not a vague "add validation" type suggestion), shown in the posted comment only when something was actually flagged.

**Design decision — kept text-only, not auto-generated code changes:** the agent suggests what to do in plain language; it does not generate a code diff or patch that could be applied automatically. This preserves the same human-in-the-loop principle used throughout the project — the agent informs, a human decides and acts. Auto-applying suggested fixes would be a real escalation in the agent's authority, and was deliberately left off — noted as a possible Phase 3+ consideration, not something to add casually.

**Labeling:** shown in the comment as "Suggested Fix (verify before applying)" — consistent, deliberate wording to avoid implying the fix should be trusted and applied without review.

**Real result, PR #3 (re-posted with the new field):**
```
Suggested Fix (verify before applying)
Restore the actual role check before merging: return user.role == 'admin',
and add a unit test verifying non-admin users are denied access.
```
Specific and directly actionable — named the exact fix and proactively recommended a regression test, not just a generic "review this more closely."

[Posted comment](https://github.com/gangadhara18/pr-triage-agent-testbed/pull/3#issuecomment-5444595847)

---

### Tech Stack

| Component | Choice | Purpose |
|---|---|---|
| Backend framework | FastAPI (Python) | API server + orchestration |
| LLM | Claude API | Summarization, risk classification |
| Source control integration | GitHub REST API | Fetching PR data, posting comments |
| Database | PostgreSQL + SQLAlchemy | Storing PRs, suggestions, and human decisions (Phase 2) |

---

## Phase 2 — Assisted Decision Mode

*Goal: a dashboard where a human explicitly Accepts, Modifies, or Rejects each suggestion before anything is posted to GitHub, with every decision logged. Redesigned from the original plan: the dashboard is the actual approval gate, not a read-only history log of what Phase 1 already posted.*

### Database Setup
*Status: complete*

Three tables, matching the HITL design directly:
- `pull_requests` — the raw fact of what GitHub gave us
- `suggestions` — what the agent concluded (summary, risk flags, suggested fix, suggested reviewer)
- `decisions` — what a human actually did with that suggestion (accepted / modified / rejected, plus an optional note)

Kept as three separate tables rather than one combined table specifically so the agent's output and the human's decision are never blended — a suggestion with no linked decision is "pending review"; one with a decision is "resolved," and both states remain queryable and auditable independently.

**Bug encountered and fixed:** the first server start failed with `sqlalchemy.exc.ArgumentError: Expected string or URL object, got None`. Root cause: `.env` was only being loaded by scripts that explicitly called `load_dotenv()` (like `create_tables.py`); `main.py` didn't, and neither does `uvicorn` automatically. Fixed by moving `load_dotenv()` into `db.py` itself, so any entry point that imports the database module gets the environment loaded automatically, rather than depending on every future script to remember to do it.

**Also encountered:** `psycopg2-binary==2.9.9` failed to build on Python 3.13 (no pre-built wheel, and building from source needs a C++ compiler that wasn't installed). Fixed by bumping to `2.9.10`, which has a pre-built wheel for Python 3.13 — avoided installing an entire compiler toolchain for a one-line version fix.

### Backend API
*Status: complete — tested end-to-end*

Three endpoints in `app/main.py`:
- `POST /api/triage/{pr_number}` — runs the full Phase 1 pipeline (summarizer, risk classifier, reviewer matcher) and saves the result to the database as pending review. **Does not post to GitHub.**
- `GET /api/suggestions/pending` — returns every suggestion without a linked decision yet — this is what the dashboard's review queue will be built from.
- `POST /api/decisions` — records a human decision. Only `accepted` or `modified` actually post a comment to GitHub (using the edited text if modified); `rejected` is logged with no public action taken.

**Verified with a real test run (PR #2):** triaged via the API, saved to the database, correctly appeared in the pending queue with the full summary, risk flags, and suggested fix intact — and confirmed nothing was posted to GitHub, proving the "gate before posting" behavior works as designed.

### Dashboard UI
*Status: complete — all three decision paths tested with real evidence*

**What was built:** a single HTML/CSS/JS page (`app/static/dashboard.html`), served directly by FastAPI at `/` — deliberately not a separate frontend server, to avoid cross-origin complexity for a project this size. Lists every pending suggestion as a card (PR title/link, summary, risk badges, suggested fix, suggested reviewer) with Accept / Modify / Reject controls.

**Bug encountered and fixed:** emoji and special characters (🤖, —) rendered as garbled text (`ðŸ¤–`, `â€"`) on first load. Root cause: Python's `Path.read_text()` uses the operating system's default text encoding when none is specified — UTF-8 on Mac/Linux, but not reliably on Windows. Fixed by explicitly reading the file as `encoding="utf-8"`. A good example of a bug that only surfaces cross-platform (worked fine in initial testing, broke on the actual Windows dev machine).

**Verified with three real, distinct test cases — one per decision path:**

| Decision | PR tested | Result |
|---|---|---|
| Accept | #2 — retry helper | Posted to GitHub unchanged |
| Modify | #3 — admin permission bypass | Edited the suggested-fix text before posting; confirmed the *edited* text (not the original) appeared in the real posted comment |
| Reject | #1 — CONTRIBUTING.md | Logged with a note, dashboard showed "Rejected — logged, nothing posted to GitHub," and no comment appeared on the real PR |

This completes Phase 2 as scoped: the dashboard is the actual approval gate before anything reaches GitHub, and every decision — including rejections — is permanently recorded in the `decisions` table, giving a real, queryable audit trail rather than just a one-off terminal confirmation.

---

## MCP Server (Read-Only Add-On)

**Considered:** using MCP (Anthropic's open protocol for model-to-tool discovery) instead of a direct GitHub REST API client.

**Decision:** The triage pipeline keeps the direct REST client (`github_client.py`). Separately, a read-only MCP server (`app/mcp_server.py`) was added on top of the same client.

**Reasoning (pipeline):** the pipeline needs the same fixed, predictable GitHub calls every run (fetch PR data, fetch history, post a comment after approval). MCP's value is letting a model choose tools on its own, which the pipeline doesn't need, so a protocol layer there would add complexity for no gain.

**What the MCP server does:** built with the official Python `mcp` SDK over stdio, with three read-only tools: `get_pr_details`, `get_pr_diff` (cut at 50,000 characters and flagged `truncated`) and `get_commit_history`. Claude Desktop or Claude Code can use them to look into a PR themselves. GitHub errors come back as readable messages so the model can correct its next call.

**Safety boundary:** there are no write tools. Posting a comment still happens only through the review dashboard after a human decision.

**Tested:** connected to Claude Code through a `.mcp.json` file (on Windows, `claude mcp add` failed on `--` and `--env`), then asked about PR #3; Claude called the tools and answered from live data.

**Roadmap note:** if the project grew to triage across several systems (GitHub + Jira + GitLab), moving the pipeline itself onto MCP would become a well-justified step.
