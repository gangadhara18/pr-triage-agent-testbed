from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship

from app.db import Base


class PullRequest(Base):
    __tablename__ = "pull_requests"

    id = Column(Integer, primary_key=True)
    repo = Column(String, nullable=False)
    pr_number = Column(Integer, nullable=False)
    title = Column(String, nullable=False)
    author = Column(String, nullable=False)
    url = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    suggestions = relationship("Suggestion", back_populates="pull_request")


class Suggestion(Base):
    __tablename__ = "suggestions"

    id = Column(Integer, primary_key=True)
    pr_id = Column(Integer, ForeignKey("pull_requests.id"), nullable=False)

    summary_text = Column(Text)
    breaking_change = Column(Boolean)
    security_sensitive = Column(Boolean)
    test_coverage_gap = Column(Boolean)
    reasoning = Column(Text)
    suggested_fix = Column(Text, nullable=True)
    suggested_reviewer = Column(String, nullable=True)
    confidence = Column(Float, nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow)

    pull_request = relationship("PullRequest", back_populates="suggestions")
    decisions = relationship("Decision", back_populates="suggestion")


class Decision(Base):
    __tablename__ = "decisions"

    id = Column(Integer, primary_key=True)
    suggestion_id = Column(Integer, ForeignKey("suggestions.id"), nullable=False)

    decision = Column(String, nullable=False)  # "accepted", "modified", or "rejected"
    note = Column(Text, nullable=True)
    decided_at = Column(DateTime, default=datetime.utcnow)

    suggestion = relationship("Suggestion", back_populates="decisions")
