"""
test_connection.py

Run this locally, AFTER setting up your .env file with a real GITHUB_TOKEN.
This script never prints or logs the token itself — only the results of
using it, so it's safe to share the output with anyone (including in chat).

Usage:
    python test_connection.py
"""

from dotenv import load_dotenv
import os
from app.github_client import GitHubClient

# Loads variables from .env into the environment, so GitHubClient can find them
load_dotenv()

REPO = os.environ.get("GITHUB_REPO", "gangadhara18/pr-triage-agent-testbed")
PR_NUMBER = 1  # change this if you want to test a different PR

client = GitHubClient()  # reads GITHUB_TOKEN from the environment automatically

print("=== Step 2 check: verifying authentication ===")
user = client.verify_connection()
print(f"Authenticated as: {user['login']}")

print("\n=== Step 3 check: fetching PR details ===")
pr = client.get_pull_request(REPO, PR_NUMBER)
print(f"Title: {pr['title']}")
print(f"Author: {pr['user']['login']}")
print(f"State: {pr['state']}")
print(f"Base branch: {pr['base']['ref']}")
print(f"Head branch: {pr['head']['ref']}")
print(f"Body: {pr['body']}")

print("\n=== Fetching changed files ===")
files = client.get_pull_request_files(REPO, PR_NUMBER)
for f in files:
    print(f"  {f['filename']} — +{f['additions']}/-{f['deletions']} ({f['status']})")

print("\n=== Fetching diff (first 500 characters) ===")
diff = client.get_pull_request_diff(REPO, PR_NUMBER)
print(diff[:500])

print("\n✅ All checks passed if no errors were raised above.")
