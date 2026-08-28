from dotenv import load_dotenv
import os
from app.github_client import GitHubClient
from app.orchestrator import run_triage

load_dotenv()

REPO = os.environ.get("GITHUB_REPO", "gangadhara18/pr-triage-agent-testbed")
PR_NUMBER = 3

github = GitHubClient()

print(f"=== Running full triage on PR #{PR_NUMBER} ===")
result = run_triage(github, REPO, PR_NUMBER)

print("\n=== This is the comment that will be posted ===\n")
print(result["comment"])

confirm = input(f"\nPost this comment to PR #{PR_NUMBER} on GitHub? (yes/no): ")

if confirm.strip().lower() == "yes":
    posted = github.post_pr_comment(REPO, PR_NUMBER, result["comment"])
    print(f"\n✅ Posted. View it here: {posted['html_url']}")
else:
    print("\nNot posted. Nothing was changed on GitHub.")
