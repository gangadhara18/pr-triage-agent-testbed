from app.agent.summarizer import Summarizer
from app.agent.risk_classifier import RiskClassifier
from app.agent.reviewer_matcher import ReviewerMatcher


def run_triage(github_client, repo: str, pr_number: int) -> dict:
    """
    Runs all three agent steps against a PR and returns everything gathered,
    plus the formatted comment text ready to post. Doesn't post anything
    itself — posting is a separate, explicit step.
    """
    pr = github_client.get_pull_request(repo, pr_number)
    files = github_client.get_pull_request_files(repo, pr_number)
    diff = github_client.get_pull_request_diff(repo, pr_number)

    summarizer = Summarizer()
    classifier = RiskClassifier()
    matcher = ReviewerMatcher(github_client)

    summary = summarizer.summarize(title=pr["title"], body=pr["body"], diff=diff)
    risk = classifier.classify(title=pr["title"], files=files, diff=diff)
    reviewer = matcher.suggest_reviewer(repo, files, pr_author=pr["user"]["login"])

    comment = format_comment(summary, risk, reviewer)

    return {
        "pr": pr,
        "summary": summary,
        "risk": risk,
        "reviewer": reviewer,
        "comment": comment,
    }


def format_comment(summary: str, risk: dict, reviewer: dict) -> str:
    breaking_icon = "🔴" if risk["breaking_change"] else "⚪"
    security_icon = "🔴" if risk["security_sensitive"] else "⚪"
    tests_icon = "🟡" if risk["test_coverage_gap"] else "⚪"

    if reviewer["suggested_reviewer"]:
        reviewer_line = f"**{reviewer['suggested_reviewer']}** (confidence: {reviewer['confidence']})"
    else:
        reviewer_line = "No suggestion available — not enough commit history. Assign manually."

    fix_section = ""
    if risk.get("suggested_fix"):
        fix_section = f"\n**Suggested Fix** (verify before applying)\n{risk['suggested_fix']}\n"

    return f"""🤖 **AI PR Triage — Automated Analysis**

**Summary**
{summary}

**Risk Assessment**
{breaking_icon} Breaking change: {risk['breaking_change']}
{security_icon} Security sensitive: {risk['security_sensitive']}
{tests_icon} Test coverage gap: {risk['test_coverage_gap']}

*{risk['reasoning']}*
{fix_section}
**Suggested Reviewer**
{reviewer_line}

---
> ⚠️ **This is an automated analysis to assist review, not a decision.** A human reviewer should verify all findings before acting on them.
"""
