"""
MCP server for the PR Triage Agent.

Exposes the same GitHub lookups the agent uses (PR details, diff, file
commit history) as read-only tools, so any MCP client — Claude Desktop,
Claude Code — can pull PR context on its own instead of being handed it.

Nothing here writes to GitHub. Posting comments stays behind the
dashboard's human review step.

Run directly (stdio):
    python -m app.mcp_server
"""

import os
from pathlib import Path

import requests
from dotenv import load_dotenv
from mcp.server.mcpserver import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from mcp.types import ToolAnnotations

from app.github_client import GitHubClient

# MCP clients launch this from their own working directory, so load .env
# from the repo root explicitly rather than relying on cwd.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

DEFAULT_REPO = os.environ.get("GITHUB_REPO")
MAX_DIFF_CHARS = 50_000

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)

mcp = MCPServer(
    name="pr-triage",
    instructions=(
        "Read-only access to GitHub pull requests: details, diffs, and "
        "commit history for files. Use these to triage or review a PR."
    ),
)

_github = None


def _client() -> GitHubClient:
    # Created on first use so the server still starts (and lists its tools)
    # even if the token is missing; the tool call reports the error instead.
    global _github
    if _github is None:
        try:
            _github = GitHubClient()
        except ValueError as e:
            raise ToolError(str(e)) from e
    return _github


def _repo(repo: str | None) -> str:
    repo = repo or DEFAULT_REPO
    if not repo:
        raise ToolError("No repo given and GITHUB_REPO isn't set. Pass repo as 'owner/name'.")
    return repo


def _call(fn, *args, **kwargs):
    # ToolError messages go back to the model, so it can tell a bad PR
    # number (404) from a bad token (401) and fix its next call.
    # Any other exception just shows up as a generic failure.
    try:
        return fn(*args, **kwargs)
    except requests.HTTPError as e:
        raise ToolError(f"GitHub returned {e.response.status_code} for {e.response.url}") from e


@mcp.tool(annotations=READ_ONLY)
def get_pr_details(pr_number: int, repo: str | None = None) -> dict:
    """Get a pull request's title, author, state, branches, description, and changed files.

    Args:
        pr_number: The PR number.
        repo: 'owner/name'. Defaults to GITHUB_REPO from .env.
    """
    repo = _repo(repo)
    github = _client()
    pr = _call(github.get_pull_request, repo, pr_number)
    files = _call(github.get_pull_request_files, repo, pr_number)

    return {
        "repo": repo,
        "number": pr["number"],
        "title": pr["title"],
        "author": pr["user"]["login"],
        "state": pr["state"],
        "merged": pr.get("merged", False),
        "base_branch": pr["base"]["ref"],
        "head_branch": pr["head"]["ref"],
        "url": pr["html_url"],
        "created_at": pr["created_at"],
        "body": pr.get("body") or "",
        "files": [
            {
                "filename": f["filename"],
                "status": f["status"],
                "additions": f["additions"],
                "deletions": f["deletions"],
            }
            for f in files
        ],
    }


@mcp.tool(annotations=READ_ONLY)
def get_pr_diff(pr_number: int, repo: str | None = None) -> dict:
    """Get the unified diff for a pull request. Very large diffs are cut off.

    Args:
        pr_number: The PR number.
        repo: 'owner/name'. Defaults to GITHUB_REPO from .env.
    """
    repo = _repo(repo)
    diff = _call(_client().get_pull_request_diff, repo, pr_number)

    # Don't flood the model's context with a huge diff. Tell the caller
    # it was cut so it doesn't assume it saw everything.
    truncated = len(diff) > MAX_DIFF_CHARS
    return {
        "repo": repo,
        "number": pr_number,
        "truncated": truncated,
        "total_chars": len(diff),
        "diff": diff[:MAX_DIFF_CHARS],
    }


@mcp.tool(annotations=READ_ONLY)
def get_commit_history(filepaths: list[str], repo: str | None = None, max_results: int = 10) -> dict:
    """Get recent commits for each file — who changed it, when, and why.

    This is the same lookup the Reviewer Matcher uses to suggest a reviewer.

    Args:
        filepaths: Paths in the repo, e.g. ["app/github_client.py"].
        repo: 'owner/name'. Defaults to GITHUB_REPO from .env.
        max_results: Commits per file (1-30).
    """
    repo = _repo(repo)
    max_results = max(1, min(max_results, 30))
    github = _client()

    history = {}
    for path in filepaths:
        commits = _call(github.get_file_commits, repo, path, max_results=max_results)
        history[path] = [
            {
                "sha": c["sha"][:7],
                # author is None when the commit email isn't linked to a GitHub account
                "author": c["author"]["login"] if c.get("author") else None,
                "author_name": c["commit"]["author"]["name"],
                "date": c["commit"]["author"]["date"],
                "message": c["commit"]["message"].splitlines()[0],
            }
            for c in commits
        ]

    return {"repo": repo, "history": history}


if __name__ == "__main__":
    mcp.run()  # stdio — don't print() anywhere in this process, it'd corrupt the protocol
