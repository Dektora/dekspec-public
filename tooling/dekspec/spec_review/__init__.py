"""spec_review — retired placeholder review dispatcher (IC-016, superseded by IC-019 / ADR-061).

Kept importable so existing callers get an actionable error instead of an
ImportError. It never returns findings: an in-process stub result must not be
mistaken for an independent review.
"""

from .reviewer import Reviewer, ReviewerRetiredError, UnknownReviewerRoleError

__all__ = ["Reviewer", "ReviewerRetiredError", "UnknownReviewerRoleError"]
