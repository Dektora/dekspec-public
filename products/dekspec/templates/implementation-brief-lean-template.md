# Implementation Brief: [bounded outcome, in a few words]

**Status:** DRAFT
**Authority policy:** lean
**Risk:** normal
**Parent:** none

<!-- A lean brief is one page (ADR-079). Add another section, such as
Rationale, Out of scope or Open Issues, only when this brief needs it.
Accept refuses it unless execution.lean is on and Risk is normal. -->

## Outcome

[What is true when this brief is done. The result, not the task list.]

## Scope

- `path/or/glob/**` — [what may change here]

<!-- Root-anchored globs; a change outside them needs an amendment. -->

## Design intent

[What a new module hides, what callers need from it, and what they must never need to know.]

<!-- No names or signatures: the test author designs the interface. -->

## Acceptance

```yaml
- id: AC-1
  condition: "[observable behavior]"
  verify:
    pytest: ["tests/test_[area].py::test_[behavior]"]
```

<!-- Each condition names the tests that prove it. -->

## Implementation Hypothesis

- Likely files: `path/to/file.py` — [expected change]

<!-- A starting guess the builder may revise within Scope. -->
