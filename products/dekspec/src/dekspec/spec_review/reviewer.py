"""Retired: the IC-016 in-process spec-review dispatcher (ADR-061, IC-019).

``Reviewer.dispatch(context_spec, artifact)`` routed on a Context
Specification's role identity to per-role handlers that were placeholders: the
``code-reviewer`` handler returned one hard-coded "stub" finding and the other
five returned ``[]``. An empty list reads as "reviewed, no findings", which is
exactly the success nobody earned. The dispatcher is therefore retired, not
repaired:

- Independent spec review is a fresh-context agent dispatched with the
  ``spec-reviewer`` Agent Role Specification (``dekspec resource role
  spec-reviewer``) by the authoring skills' ``--review`` modes and ``review-ib``.
- Independent code review is a ``code-reviewer`` dispatch whose verdict is the
  ``dekspec ib review`` event the completion gate reads.
- The deterministic ``SPEC-REVIEW`` audit rule needs no dispatcher.

Every call raises ``ReviewerRetiredError`` with those instructions.
"""

from __future__ import annotations

from typing import NoReturn

RETIRED_MESSAGE = (
    "dekspec.spec_review.Reviewer is retired (ADR-061; IC-016 superseded by IC-019): it never performed a review. "
    "Dispatch an independent agent composed from the Agent Role Specification instead — spec review: "
    "`dekspec resource role spec-reviewer`; code review: `dekspec resource role code-reviewer`, recording the "
    "verdict with `dekspec ib review`. Deterministic checks run through `dekspec audit`."
)


class ReviewerRetiredError(RuntimeError):
    """Raised by every use of the retired dispatcher."""


class UnknownReviewerRoleError(ReviewerRetiredError):
    """Retained name for compatibility; the dispatcher it described is retired."""


class Reviewer:
    """Retired placeholder dispatcher. Every call raises ``ReviewerRetiredError``."""

    def dispatch(self, context_spec: object, artifact: object) -> NoReturn:
        raise ReviewerRetiredError(RETIRED_MESSAGE)


__all__ = ["RETIRED_MESSAGE", "Reviewer", "ReviewerRetiredError", "UnknownReviewerRoleError"]
