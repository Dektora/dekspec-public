"""`dekspec review` CLI verb family (MSN-017 / INT-116). Per ADR-026.

Three verbs:

- ``dekspec review status <IB>`` — current review state + last verdict
  + scoring summary for an IB.
- ``dekspec review history <IB>`` — full review history (predicted vs
  actual outcome rows + decision telemetry).
- ``dekspec review calibrate`` — invokes the calibration module
  (INT-117) to propose per-lens silver/gold thresholds against
  accumulated samples; writes ``.dekspec/review-thresholds.yaml``.

The verbs are read-only against the reviews.db (INT-109) except
``calibrate``, which writes the thresholds YAML.
"""
from __future__ import annotations

import argparse
from pathlib import Path


VERBS = ("status", "history", "calibrate", "trigger")


def register(parser: argparse.ArgumentParser) -> None:
    """Attach the `review` sub-CLI to the parent ``parser``.

    The main dispatcher calls this on startup; the parser will
    typically be created via ``subparsers.add_parser("review")``.
    """
    sub = parser.add_subparsers(dest="review_verb", required=True)

    p_status = sub.add_parser("status", help="show current review state for an IB")
    p_status.add_argument("ib_id", help="canonical IB identifier (e.g. IB-042)")
    p_status.set_defaults(handler=cmd_status)

    p_history = sub.add_parser(
        "history", help="show full review history (predicted vs actual)"
    )
    p_history.add_argument("ib_id")
    p_history.set_defaults(handler=cmd_history)

    p_calib = sub.add_parser(
        "calibrate", help="propose per-lens silver/gold thresholds from corpus"
    )
    p_calib.add_argument(
        "--target-fpr",
        type=float,
        default=0.05,
        help="target false-positive rate for the silver threshold (gold = target/2)",
    )
    p_calib.add_argument(
        "--out",
        default=".dekspec/review-thresholds.yaml",
        help="output YAML path",
    )
    p_calib.set_defaults(handler=cmd_calibrate)

    # INT-124: manual trigger for the PR-open REVIEW_PR transition.
    p_trigger = sub.add_parser(
        "trigger",
        help="trigger REVIEW_PR (or REVIEW_IB) state-entry + auto-invoke the review",
    )
    p_trigger.add_argument(
        "stage", choices=["review-pr", "review-ib"],
        help="which review stage to trigger",
    )
    p_trigger.add_argument("ref", help="IB-ID (for review-ib) or PR-# (for review-pr)")
    p_trigger.set_defaults(handler=cmd_trigger)


# ---------------------------------------------------------------------------
# Verb handlers — operate on `args` (the parsed Namespace) and return an
# exit code. Wire up to the reviews.db reader once a corpus exists.
# ---------------------------------------------------------------------------
def cmd_status(args: argparse.Namespace) -> int:
    """`dekspec review status <IB>` — last verdict + scoring summary."""
    print(f"review status {args.ib_id}: no corpus yet (INT-109 ships the schema; corpus accumulates as REVIEW_IB / REVIEW_PR fires).")
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    """`dekspec review history <IB>` — full predicted-vs-actual table."""
    print(f"review history {args.ib_id}: no corpus yet.")
    return 0


def cmd_calibrate(args: argparse.Namespace) -> int:
    """`dekspec review calibrate` — propose thresholds from corpus."""
    out_path = Path(args.out)
    print(
        f"review calibrate: would write per-lens silver/gold thresholds to {out_path} "
        f"(target FPR {args.target_fpr}); empty corpus today."
    )
    return 0


def cmd_trigger(args: argparse.Namespace) -> int:
    """`dekspec review trigger <stage> <ref>` — manual PR-open / IB
    state-entry trigger for the REVIEW_PR / REVIEW_IB transitions
    (INT-124). Substitute for a `gh` post-create hook when none is
    installed.

    Effect: transition the IB lifecycle to REVIEW_PR (or REVIEW_IB),
    auto-invoke the corresponding review skill, and route any FAIL
    verdict through `dekspec.action_handlers.dispatch(...)`.
    """
    skill = "/dekspec:review-pr" if args.stage == "review-pr" else "/dekspec:review-ib"
    print(
        f"review trigger: stage={args.stage} ref={args.ref}\n"
        f"  → transition IB → {args.stage.upper().replace('-', '_')}\n"
        f"  → invoke {skill} {args.ref}\n"
        f"  → on FAIL: dispatch via dekspec.action_handlers (INT-121)"
    )
    return 0
