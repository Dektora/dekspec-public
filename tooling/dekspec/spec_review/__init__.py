"""spec_review — role-keyed spec-review dispatcher package (IC-016 / INT-140).

Brand-new top-level sibling under ``tooling/dekspec/`` (ADR-011 Option B);
independent of the LOCKED MSN-017 ``tooling/dekspec/review/`` package. Both
import paths ``from dekspec.spec_review.reviewer import Reviewer`` AND
``from dekspec.spec_review import Reviewer`` resolve via this re-export.
"""

from .reviewer import Reviewer, UnknownReviewerRoleError

__all__ = ["Reviewer", "UnknownReviewerRoleError"]
