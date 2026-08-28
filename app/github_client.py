import os
import requests

GITHUB_API_BASE = "https://api.github.com"


class GitHubClient:
    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("GITHUB_TOKEN")

        if not self.token:
            raise ValueError(
                "No GitHub token found. Set the GITHUB_TOKEN environment "
                "variable (in your local .env file) before running this."
            )

        self.headers = {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    def verify_connection(self) -> dict:
        response = requests.get(f"{GITHUB_API_BASE}/user", headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_pull_request(self, repo: str, pr_number: int) -> dict:
        url = f"{GITHUB_API_BASE}/repos/{repo}/pulls/{pr_number}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_pull_request_files(self, repo: str, pr_number: int) -> list[dict]:
        url = f"{GITHUB_API_BASE}/repos/{repo}/pulls/{pr_number}/files"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()
        return response.json()

    def get_pull_request_diff(self, repo: str, pr_number: int) -> str:
        url = f"{GITHUB_API_BASE}/repos/{repo}/pulls/{pr_number}"
        diff_headers = {**self.headers, "Accept": "application/vnd.github.v3.diff"}
        response = requests.get(url, headers=diff_headers)
        response.raise_for_status()
        return response.text

    def get_file_commits(self, repo: str, filepath: str, max_results: int = 30) -> list[dict]:
        """
        Fetches recent commit history for a single file. Used by the
        Reviewer Matcher to see who's worked on this file before.

        Returns a list of commits, each with an author login (or None if
        the commit author isn't linked to a GitHub account).
        """
        url = f"{GITHUB_API_BASE}/repos/{repo}/commits"
        params = {"path": filepath, "per_page": max_results}
        response = requests.get(url, headers=self.headers, params=params)
        response.raise_for_status()
        return response.json()

    def post_pr_comment(self, repo: str, pr_number: int, body: str) -> dict:
        """
        Posts a comment on a PR. GitHub treats PR comments the same as
        issue comments, which is why this uses the /issues/ endpoint
        rather than /pulls/ — a quirk of GitHub's API, not a mistake.
        """
        url = f"{GITHUB_API_BASE}/repos/{repo}/issues/{pr_number}/comments"
        response = requests.post(url, headers=self.headers, json={"body": body})
        response.raise_for_status()
        return response.json()
