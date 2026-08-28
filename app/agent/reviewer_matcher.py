from collections import Counter


class ReviewerMatcher:
    """
    Suggests a reviewer based on who's actually worked on the changed files
    before. No AI here on purpose — this is a solved problem with a simple,
    explainable answer: count who touched these files most, exclude the PR's
    own author, and suggest the top match.
    """

    def __init__(self, github_client):
        self.github = github_client

    def suggest_reviewer(self, repo: str, files: list[dict], pr_author: str) -> dict:
        author_counts = Counter()
        total_commits_considered = 0

        for f in files:
            commits = self.github.get_file_commits(repo, f["filename"])
            for commit in commits:
                author = commit.get("author")
                login = author["login"] if author else None
                if login and login != pr_author:
                    author_counts[login] += 1
                    total_commits_considered += 1

        if not author_counts:
            return {
                "suggested_reviewer": None,
                "confidence": 0,
                "reasoning": "No commit history found for these files from anyone other than the PR author — likely new files or a new repo. Assign manually.",
            }

        top_reviewer, top_count = author_counts.most_common(1)[0]
        confidence = round(top_count / total_commits_considered, 2)

        return {
            "suggested_reviewer": top_reviewer,
            "confidence": confidence,
            "reasoning": f"{top_reviewer} authored {top_count} of {total_commits_considered} relevant prior commits to these files.",
        }
