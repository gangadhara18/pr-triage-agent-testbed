import os
from pathlib import Path
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db import get_db
from app import models
from app.github_client import GitHubClient
from app.orchestrator import run_triage, format_comment

app = FastAPI(title="PR Triage Agent")

REPO = os.environ.get("GITHUB_REPO")
STATIC_DIR = Path(__file__).parent / "static"


@app.get("/", response_class=HTMLResponse)
def dashboard():
    return (STATIC_DIR / "dashboard.html").read_text(encoding="utf-8")


@app.post("/api/triage/{pr_number}")
def trigger_triage(pr_number: int, db: Session = Depends(get_db)):
    """
    Runs the agent on a real PR and saves the result to the database as
    'pending review'. Does NOT post anything to GitHub — that only
    happens later, if a human accepts or modifies it via /api/decisions.
    """
    github = GitHubClient()
    result = run_triage(github, REPO, pr_number)
    pr_data = result["pr"]
    risk = result["risk"]
    reviewer = result["reviewer"]

    # Reuse the PR row if we've already triaged this PR before, instead
    # of creating a duplicate every time.
    pr_row = (
        db.query(models.PullRequest)
        .filter(models.PullRequest.repo == REPO, models.PullRequest.pr_number == pr_number)
        .first()
    )
    if not pr_row:
        pr_row = models.PullRequest(
            repo=REPO,
            pr_number=pr_number,
            title=pr_data["title"],
            author=pr_data["user"]["login"],
            url=pr_data["html_url"],
        )
        db.add(pr_row)
        db.flush()  # assigns pr_row.id without needing a full commit yet

    suggestion_row = models.Suggestion(
        pr_id=pr_row.id,
        summary_text=result["summary"],
        breaking_change=risk["breaking_change"],
        security_sensitive=risk["security_sensitive"],
        test_coverage_gap=risk["test_coverage_gap"],
        reasoning=risk["reasoning"],
        suggested_fix=risk.get("suggested_fix"),
        suggested_reviewer=reviewer.get("suggested_reviewer"),
        confidence=reviewer.get("confidence"),
    )
    db.add(suggestion_row)
    db.commit()
    db.refresh(suggestion_row)

    return {
        "suggestion_id": suggestion_row.id,
        "pr_title": pr_row.title,
        "comment_preview": result["comment"],
    }


@app.get("/api/suggestions/pending")
def list_pending(db: Session = Depends(get_db)):
    """
    Returns every suggestion that doesn't have a decision on it yet —
    this is what the dashboard's review queue is built from.
    """
    pending = (
        db.query(models.Suggestion)
        .outerjoin(models.Decision)
        .filter(models.Decision.id.is_(None))
        .all()
    )

    result = []
    for s in pending:
        risk = {
            "breaking_change": s.breaking_change,
            "security_sensitive": s.security_sensitive,
            "test_coverage_gap": s.test_coverage_gap,
            "reasoning": s.reasoning,
            "suggested_fix": s.suggested_fix,
        }
        reviewer = {
            "suggested_reviewer": s.suggested_reviewer,
            "confidence": s.confidence,
        }
        result.append({
            "suggestion_id": s.id,
            "pr_number": s.pull_request.pr_number,
            "pr_title": s.pull_request.title,
            "pr_url": s.pull_request.url,
            "summary": s.summary_text,
            "breaking_change": s.breaking_change,
            "security_sensitive": s.security_sensitive,
            "test_coverage_gap": s.test_coverage_gap,
            "reasoning": s.reasoning,
            "suggested_fix": s.suggested_fix,
            "suggested_reviewer": s.suggested_reviewer,
            "comment_preview": format_comment(s.summary_text, risk, reviewer),
        })
    return result


class DecisionInput(BaseModel):
    suggestion_id: int
    decision: str  # "accepted", "modified", or "rejected"
    note: str | None = None
    edited_text: str | None = None  # only used when decision == "modified"


@app.post("/api/decisions")
def submit_decision(payload: DecisionInput, db: Session = Depends(get_db)):
    """
    Records a human's decision on a suggestion. Only "accepted" or
    "modified" actually post a comment to GitHub — "rejected" just
    gets logged with no public action taken.
    """
    suggestion = db.query(models.Suggestion).filter(models.Suggestion.id == payload.suggestion_id).first()
    if not suggestion:
        raise HTTPException(status_code=404, detail="Suggestion not found")

    posted_url = None

    if payload.decision in ("accepted", "modified"):
        if payload.decision == "modified" and payload.edited_text:
            comment_text = payload.edited_text
        else:
            risk = {
                "breaking_change": suggestion.breaking_change,
                "security_sensitive": suggestion.security_sensitive,
                "test_coverage_gap": suggestion.test_coverage_gap,
                "reasoning": suggestion.reasoning,
                "suggested_fix": suggestion.suggested_fix,
            }
            reviewer = {
                "suggested_reviewer": suggestion.suggested_reviewer,
                "confidence": suggestion.confidence,
            }
            comment_text = format_comment(suggestion.summary_text, risk, reviewer)

        github = GitHubClient()
        posted = github.post_pr_comment(REPO, suggestion.pull_request.pr_number, comment_text)
        posted_url = posted["html_url"]

    decision_row = models.Decision(
        suggestion_id=suggestion.id,
        decision=payload.decision,
        note=payload.note,
    )
    db.add(decision_row)
    db.commit()

    return {"status": "recorded", "posted_url": posted_url}
