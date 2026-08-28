from dotenv import load_dotenv
import os
from app.github_client import GitHubClient
from app.agent.risk_classifier import RiskClassifier

load_dotenv()

REPO = os.environ.get("GITHUB_REPO", "gangadhara18/pr-triage-agent-testbed")
PR_NUMBER = 2  # the "risky" auth PR is a good first test for this one

github = GitHubClient()
classifier = RiskClassifier()

print("=== Fetching PR from GitHub ===")
pr = github.get_pull_request(REPO, PR_NUMBER)
files = github.get_pull_request_files(REPO, PR_NUMBER)
diff = github.get_pull_request_diff(REPO, PR_NUMBER)
print(f"Title: {pr['title']}")

print("\n=== Sending to Claude for risk classification ===")
result = classifier.classify(title=pr["title"], files=files, diff=diff)

print("\n=== Risk Assessment ===")
print(f"Breaking change: {result['breaking_change']}")
print(f"Security sensitive: {result['security_sensitive']}")
print(f"Test coverage gap: {result['test_coverage_gap']}")
print(f"Reasoning: {result['reasoning']}")
