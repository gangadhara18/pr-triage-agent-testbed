from app.agent.reviewer_matcher import ReviewerMatcher


class FakeGitHubClient:
    """
    Stands in for the real GitHubClient. Returns made-up commit history
    instead of calling the real API — lets us test the matcher's selection
    logic directly, since our real test repo doesn't have enough commit
    history to show a real match.
    """

    def get_file_commits(self, repo, filepath):
        fake_history = {
            "auth/permissions.py": [
                {"author": {"login": "priya"}},
                {"author": {"login": "priya"}},
                {"author": {"login": "priya"}},
                {"author": {"login": "jordan"}},
                {"author": {"login": "gangadhara18"}},  # PR author, should be excluded
            ],
        }
        return fake_history.get(filepath, [])


matcher = ReviewerMatcher(FakeGitHubClient())

result = matcher.suggest_reviewer(
    repo="fake/repo",
    files=[{"filename": "auth/permissions.py"}],
    pr_author="gangadhara18",
)

print("Suggested:", result["suggested_reviewer"])
print("Confidence:", result["confidence"])
print("Reasoning:", result["reasoning"])

assert result["suggested_reviewer"] == "priya", "Expected priya to be the top match"
assert result["confidence"] == 0.75, "Expected 3 of 4 non-author commits = 0.75"
print("\n✅ Logic test passed.")
