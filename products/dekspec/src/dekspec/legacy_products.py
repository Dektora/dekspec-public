"""Retired product paths keep usage validation and truthful migration messages."""
import sys

def tools_migration(args):
    print("error: command moved to DekTools; use dektools handoff or dektools deepen-record", file=sys.stderr)
    return 1

def builder_migration(args):
    print("error: construction moved to Deck Builder; use dekbuilder implement", file=sys.stderr)
    return 1

def register_helpers(sub):
    handoff = sub.add_parser("handoff", help="Write/read continuity evidence.")
    handoff.add_argument("action", nargs="?", choices=("read", "write"), default="read")
    handoff.add_argument("--at", default=".")
    handoff.add_argument("--input", help="JSON record; required for write.")
    handoff.add_argument("--run-id")
    handoff.set_defaults(func=tools_migration)
    deepen = sub.add_parser(
        "deepen-record", help="Persist multi-pass evidence bound to core; no agent execution.",
        description=(
            "Actions: start (a run; --new-run archives it and carries its latest integration forward), begin "
            "(a pass, pending), append (its outcome), abandon (a pending pass without a run), status. begin "
            "reads the pass's input revision from the base branch itself and refuses a base that lacks the "
            "latest integrated revision. "
            "Pass JSON: pass_id (stable unique ID for retries), candidate (stable ID), targets (at most one "
            "IB or Intent; none for a dry reassessment), completed (count), evidence (list), rejected "
            "[{id,reason}], unresolved/resolved (ID lists), remaining (count), dry (bool), "
            "implementation_status (complete/not-needed/blocked/not-ready), blocker, cost; abandon takes "
            "pass_id and reason. A completion is recorded only when core reports the target complete with "
            "one integration recorded after begin; the pass then holds core's outcome, run id, delivery, "
            "integrated revision and tree, and per-IB completion references. blocked/not-ready need core to "
            "report it; abandon is refused while core shows an unintegrated run. A caller revision must "
            "equal core's; revision and verified are never stored. Outcomes: continue, interrupted (a pass is pending), convergence, stalled, "
            "budget, blocker. Refusals are JSON {error} and leave the record unchanged; status adds "
            "core_error when core cannot be read."),
    )
    deepen.add_argument("action", nargs="?", choices=("status", "start", "append", "begin", "abandon"),
                        default="status")
    deepen.add_argument("--at", default=".")
    deepen.add_argument("--scope", default="whole-repo")
    deepen.add_argument("--input")
    deepen.add_argument("--new-run", action="store_true", help="Archive an ended run and begin new authorized work.")
    deepen.add_argument("--max-passes", type=int, default=12, help="Host safety budget, not a single-pass limit.")
    deepen.set_defaults(func=tools_migration)



def register_implement(sub: object) -> None:
    p = sub.add_parser(
        "implement",
        help="Implement ready work autonomously: resolve, check readiness, drive to integrated completion.",
        description="The core of `/implement` (ADR-059). `next` takes every mechanical step and prints the one "
                    "action an agent harness must take; `ack` records that a dispatched worker returned.",
    )
    verbs = p.add_subparsers(dest="implement_command", metavar="<implement-command>", required=True)
    for name, fn, hlp in (
        ("resolve", builder_migration, "targets a request names — explicit ids, lowercase ids or a description"),
        ("ready", builder_migration, "the READY predicate, with the specific missing preparation when not ready"),
        ("next", builder_migration, "take every mechanical step; print the next action (dispatch, wait, done, blocked)"),
        ("status", builder_migration, "read-only state of each target and delivery"),
    ):
        q = verbs.add_parser(name, help=hlp)
        q.add_argument("request", nargs="+", help="e.g. INT-041, 'int-041 and int-042', 'the auth feature'")
        _common(q)
        q.set_defaults(func=fn)
    q = verbs.add_parser("ack", help="record that dispatched worker <dispatch> returned; checkpoint its work")
    q.add_argument("request", nargs="+", help="the same request passed to `next`")
    q.add_argument("--dispatch", required=True, help="dispatch id from `next` (D-n)")
    q.add_argument("--summary", help="the worker's report")
    _common(q)
    q.set_defaults(func=builder_migration)


def _common(p: object) -> None:
    p.add_argument("--at", help="repository root (default: git top level of the cwd)")
    p.add_argument("--dekspec-root", default="dekspec", help="spec tree relative to the repo (default: dekspec)")
    p.add_argument("--actor", help="identity recorded as the requester (default: $DEKSPEC_ACTOR, then git user.name)")
    p.add_argument("--json", action="store_true", help="machine-readable output")
