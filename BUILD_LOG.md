# Build Log

## MCP server — Oct 13, 2026

**Goal:** expose the agent's GitHub lookups as MCP tools, so a client like Claude Desktop or Claude Code can pull PR context on its own.

**What I built**
- `app/mcp_server.py` with three read-only tools: `get_pr_details`, `get_pr_diff`, `get_commit_history`.
- Reused `github_client.py` unchanged. `get_commit_history` calls the same `get_file_commits` lookup the Reviewer Matcher uses.
- No write tools on purpose. Posting still only goes through the dashboard's human review.

**Issues hit along the way**
- **SDK version change.** Most examples online use `from mcp.server.fastmcp import FastMCP`. The current SDK (2.x) renamed it to `MCPServer` (`mcp.server.mcpserver`), and the old import fails with a clear error. Pinned `mcp==2.3.0`.
- **Dependency conflict.** `mcp` 2.x needs `uvicorn>=0.31.1`, and the repo pinned `0.30.6`. Bumped to `0.32.1` and checked the dashboard still starts and serves `/`.
- **Useless error messages.** A wrong PR number came back to the model as just "Error executing tool get_pr_details" — the SDK hides unexpected exceptions. Wrapped GitHub calls so HTTP errors are raised as `ToolError`, which the SDK passes through. Now the model sees "GitHub returned 404 for .../pulls/9999".
- **`.env` not found.** MCP clients start the server from their own working directory, so a plain `load_dotenv()` can miss the repo's `.env`. Loaded it from the repo root path instead.
- **Missing token.** `GitHubClient()` raises if there's no token. Created it lazily inside the tools, so the server still starts and lists its tools, and the call returns the "No GitHub token found" message.
- **Large diffs.** Capped `get_pr_diff` at 50,000 characters and return a `truncated` flag so the model knows it didn't see the whole diff.

**How I tested it**
- Wrote a small MCP client script that starts the server over stdio, lists the tools, and calls each one against this repo: PR #3 details and diff, commit history for two files, and PR #9999 to check the error path.
- Launched it the way Claude Desktop does (different working directory, `PYTHONPATH` set) to confirm the `.env` path and missing-token handling.
- Connected it to Claude Desktop / Claude Code and asked it to review PR #3.
