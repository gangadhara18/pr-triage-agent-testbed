"""
test_summarizer.py

Run this locally, after adding ANTHROPIC_API_KEY to your .env file.
Fetches a real PR from GitHub, then sends it to Claude for summarization.

Usage:
    python test_summarizer.py
"""

from dotenv import load_dotenv
import os
from app.github_client import GitHubClient
from app.agent.summarizer import Summarizer

load_dotenv()

REPO = os.environ.get("GITHUB_REPO", "gangadhara18/pr-triage-agent-testbed")
PR_NUMBER = 3  # change this to test a different PR

github = GitHubClient()
summarizer = Summarizer()

print("=== Fetching PR from GitHub ===")
pr = github.get_pull_request(REPO, PR_NUMBER)
diff = github.get_pull_request_diff(REPO, PR_NUMBER)
print(f"Title: {pr['title']}")
print(f"Body: {pr['body']}")

print("\n=== Sending to Claude for summarization ===")
summary = summarizer.summarize(title=pr["title"], body=pr["body"], diff=diff)

print("\n=== Summary ===")
print(summary)
