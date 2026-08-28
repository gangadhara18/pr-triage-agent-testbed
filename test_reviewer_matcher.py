from dotenv import load_dotenv
import os
from app.github_client import GitHubClient
from app.agent.reviewer_matcher import ReviewerMatcher

load_dotenv()

REPO = os.environ.get("GITHUB_REPO", "gangadhara18/pr-triage-agent-testbed")
PR_NUMBER = 3

github = GitHubClient()
matcher = ReviewerMatcher(github)

pr = github.get_pull_request(REPO, PR_NUMBER)
files = github.get_pull_request_files(REPO, PR_NUMBER)

print(f"PR #{PR_NUMBER}: {pr['title']}")
print(f"Author: {pr['user']['login']}")
print(f"Changed files: {[f['filename'] for f in files]}")

result = matcher.suggest_reviewer(REPO, files, pr_author=pr["user"]["login"])

print("\nReviewer Suggestion:")
print(f"  Suggested: {result['suggested_reviewer']}")
print(f"  Confidence: {result['confidence']}")
print(f"  Reasoning: {result['reasoning']}")
