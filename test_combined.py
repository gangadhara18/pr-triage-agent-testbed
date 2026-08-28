from dotenv import load_dotenv
import os
from app.github_client import GitHubClient
from app.agent.summarizer import Summarizer
from app.agent.risk_classifier import RiskClassifier

load_dotenv()

REPO = os.environ.get("GITHUB_REPO", "gangadhara18/pr-triage-agent-testbed")
PR_NUMBER = 3

github = GitHubClient()
summarizer = Summarizer()
classifier = RiskClassifier()

pr = github.get_pull_request(REPO, PR_NUMBER)
files = github.get_pull_request_files(REPO, PR_NUMBER)
diff = github.get_pull_request_diff(REPO, PR_NUMBER)

summary = summarizer.summarize(title=pr["title"], body=pr["body"], diff=diff)
risk = classifier.classify(title=pr["title"], files=files, diff=diff)

print(f"PR #{PR_NUMBER}: {pr['title']}\n")
print("Summary:")
print(summary)
print("\nRisk Assessment:")
print(f"  Breaking change: {risk['breaking_change']}")
print(f"  Security sensitive: {risk['security_sensitive']}")
print(f"  Test coverage gap: {risk['test_coverage_gap']}")
print(f"  Reasoning: {risk['reasoning']}")
