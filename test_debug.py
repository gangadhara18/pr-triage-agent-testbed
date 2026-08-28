from dotenv import load_dotenv
import os
from app.github_client import GitHubClient
from app.agent.risk_classifier import MODEL, SYSTEM_PROMPT
from anthropic import Anthropic

load_dotenv()

REPO = os.environ.get("GITHUB_REPO", "gangadhara18/pr-triage-agent-testbed")
PR_NUMBER = 3

github = GitHubClient()
client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

pr = github.get_pull_request(REPO, PR_NUMBER)
files = github.get_pull_request_files(REPO, PR_NUMBER)
diff = github.get_pull_request_diff(REPO, PR_NUMBER)

file_list = "\n".join(f"- {f['filename']} ({f['status']})" for f in files)
user_message = f"PR Title: {pr['title']}\n\nChanged files:\n{file_list}\n\nDiff:\n{diff}"

response = client.messages.create(
    model=MODEL,
    max_tokens=300,
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": user_message}],
)

print("Stop reason:", response.stop_reason)
print("Number of content blocks:", len(response.content))
for i, block in enumerate(response.content):
    print(f"\nBlock {i}: type={block.type}")
    print(block)
