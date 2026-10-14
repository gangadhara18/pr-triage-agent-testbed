# AI PR & Code Review Triage Agent

An AI agent that reads a pull request, explains what it does in plain language, flags potential risks, and suggests a reviewer — then posts all of that as a comment directly on the PR. It never approves, blocks, or merges anything. It only informs. A human always makes the actual decision.

## Why this exists

Engineering teams get more pull requests than reviewers can carefully read. A one-line typo fix and a change to authentication logic often sit in the same queue, with no distinction between them. This agent gives a reviewer a fast, honest first read of a PR before they open the diff themselves — including flagging things that are easy to miss, like a security bypass hidden behind a normal-looking commit message.

## What it actually does

For any pull request, the agent:

1. **Summarizes** the change in plain language (what it does, and why, based on the diff and description).
2. **Flags risk**: is this a breaking change? Does it touch anything security-sensitive? Is there a test coverage gap?
3. **Suggests a specific fix** when something is flagged — not just "this looks risky," but a concrete next step a reviewer can evaluate and act on.
4. **Suggests a reviewer**, based on who's actually worked on the changed files before.
5. **Waits for a human decision** in a review dashboard — Accept, Modify, or Reject — before anything gets posted publicly. Every decision is logged permanently, including rejections.
6. **Posts the (possibly edited) result** as a comment on the real PR, clearly labeled as an automated, advisory analysis — not a decision.

## A real example

Here's an actual comment the agent posted on a test PR that introduced a hardcoded security bypass:

> 🤖 **AI PR Triage — Automated Analysis**
>
> **Summary**
> This change adds a new `check_admin_access` function, but as written it always returns `True`, bypassing the actual role check. This looks like debug code left in by mistake and should not be merged as-is.
>
> **Risk Assessment**
> ⚪ Breaking change: False
> 🔴 Security sensitive: True
> 🟡 Test coverage gap: True
>
> **Suggested Fix** (verify before applying)
> Restore the actual role check before merging: `return user.role == 'admin'`, and add a unit test verifying non-admin users are denied access.
>
> **Suggested Reviewer**
> No suggestion available — not enough commit history. Assign manually.
>
> ⚠️ This is an automated analysis to assist review, not a decision. A human reviewer should verify all findings before acting on them.

The agent caught this without being told to look for security issues specifically — it reasoned about the code's actual behavior, not just its syntax.

## The review dashboard (Phase 2)

Rather than posting immediately, the agent's findings go into a review queue first. A small local dashboard shows each pending suggestion — summary, risk flags, suggested fix, suggested reviewer — with three actions:

- **Accept** — posts the comment to GitHub exactly as generated.
- **Modify** — lets you edit the comment text before it posts.
- **Reject** — nothing gets posted; the rejection (with an optional reason) is logged instead.

Every decision, including rejections, is saved permanently to a database — a real audit trail of what the agent suggested versus what a human actually did with it, not just a one-off approval prompt.

## MCP server

The same GitHub lookups the agent uses are also exposed as an MCP server (`app/mcp_server.py`, built on the official Python MCP SDK). That means any MCP client — Claude Desktop, Claude Code — can pull PR context itself, instead of only this agent's fixed pipeline using it.

Three tools, all read-only:

- **`get_pr_details`** — title, author, state, branches, description, and the list of changed files with line counts.
- **`get_pr_diff`** — the unified diff. Very large diffs are cut at 50,000 characters and flagged as `truncated`, so the model knows it didn't see everything.
- **`get_commit_history`** — recent commits for one or more files: who changed them, when, and the commit message. This is the same lookup the Reviewer Matcher uses.

It deliberately has no write tools. Posting a comment still only happens through the review dashboard after a human decision — the MCP server doesn't open a way around that.

It reuses `github_client.py` as-is, reads `GITHUB_TOKEN` and `GITHUB_REPO` from the same `.env`, and runs over stdio. GitHub errors (a wrong PR number, a bad token) are passed back to the model as readable messages rather than a generic failure, so it can correct its next call.

**Claude Code:**

```
claude mcp add --transport stdio --env PYTHONPATH=/path/to/pr-triage-agent-testbed pr-triage -- /path/to/pr-triage-agent-testbed/.venv/bin/python -m app.mcp_server
```
**Claude Code on Windows (PowerShell):** `claude mcp add` can fail on the `--` and `--env` options there. A `.mcp.json` file in the repo root works instead:

```json
{
  "mcpServers": {
    "pr-triage": {
      "command": "C:\\path\\to\\venv\\Scripts\\python.exe",
      "args": ["-m", "app.mcp_server"],
      "env": { "PYTHONPATH": "C:\\path\\to\\pr-triage-agent-testbed" }
    }
  }
}
```

Start Claude Code in that folder, approve the server when it asks, and check it with `/mcp`. The file has local paths, so it is not committed.


**Claude Desktop** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "pr-triage": {
      "command": "/path/to/pr-triage-agent-testbed/.venv/bin/python",
      "args": ["-m", "app.mcp_server"],
      "env": { "PYTHONPATH": "/path/to/pr-triage-agent-testbed" }
    }
  }
}
```

Then ask something like *"Look at PR #3 and tell me if it's safe to merge, and who should review it"* — the model decides which tools to call.

## How it's built

```
GitHub PR → Fetch diff & file history → Three AI/logic steps → Saved to database (pending review)
                                                                        ↓
                                                    Dashboard: Accept / Modify / Reject
                                                                        ↓
                                                    Decision logged  →  Comment posted to GitHub (if approved)
```

- **Summarizer** — sends the diff to Claude, asks for a plain-language explanation.
- **Risk Classifier** — sends the same diff to Claude, asks for structured yes/no risk flags plus reasoning and a suggested fix.
- **Reviewer Matcher** — no AI here on purpose. It's a solved problem: count who's committed to these files before, exclude the PR's own author, suggest the top match. Using an LLM for this would just be unnecessary complexity.
- **Dashboard & database** — a FastAPI backend with three tables (PRs, suggestions, and human decisions) and a small web UI, so nothing reaches GitHub without an explicit human decision, and every decision is recorded.

**Tech stack:** Python, FastAPI, the Claude API (`anthropic` SDK), GitHub's REST API, PostgreSQL + SQLAlchemy, Model Context Protocol (`mcp` SDK).

## Honest limitations (found while building this)

No portfolio project is bug-free, and pretending otherwise isn't useful to anyone. A few real things found and fixed along the way:

- **Early on, the risk classifier conflated "breaking change" with "risky change"** — it flagged a brand-new function as a breaking change just because it also had a security issue. Fixed by explicitly telling the model to score each risk flag independently, and verified the fix with a real before/after comparison.
- **A truncated response once broke JSON parsing** — the response length limit was too low for a longer explanation, cutting the output off mid-sentence. Fixed by raising the limit and adding clearer error handling.
- **Reviewer suggestions need real commit history to work well.** On a brand-new repo (like the test repo used here), there often isn't enough history yet, so the agent correctly says "assign manually" instead of guessing.

## How this compares to existing tools

Tools like GitHub Copilot's PR review, CodeRabbit, and Sonar already do AI-assisted PR review commercially, and this project doesn't claim to outdo them. It was built to demonstrate the underlying skills directly: designing prompts for structured, reliable output; building human-in-the-loop governance instead of full automation; and debugging real failures in an AI pipeline rather than just wiring one up and hoping it works.

## Roadmap (not yet built)

- **Phase 3:** low-risk automation, like auto-labeling trivial PRs (still no auto-merge or auto-approve).
- **Auto-applying suggested fixes:** currently the agent only suggests a fix in plain language for a human to evaluate — it never generates or applies a code change itself. Deliberately left as advisory-only for now; auto-applying fixes would be a meaningful escalation in the agent's authority and deserves its own careful decision later, not something added casually.

## Running it locally

1. Clone this repo and create a Python virtual environment.
2. `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and add your own GitHub token, Anthropic API key, and PostgreSQL connection details.
4. Create the database tables: `python create_tables.py`
5. Run any of the `test_*.py` scripts to see each part of the pipeline individually, or `test_post_comment.py` for the original end-to-end flow (Phase 1 style — posts immediately after a terminal confirmation).
6. To use the review dashboard instead: start the server with `uvicorn app.main:app --reload`, then open `http://127.0.0.1:8000` in a browser. Trigger a triage via `POST /api/triage/{pr_number}` (e.g. with curl or the included `test_api.py`), then review it in the dashboard.
7. To use the MCP server, see the [MCP server](#mcp-server) section above for Claude Code and Claude Desktop setup.
