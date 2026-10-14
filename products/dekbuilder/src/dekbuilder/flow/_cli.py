"""Command presentation for the fixed wave interface."""

from dekbuilder.implement.cli import _action_text, _actor, _guard, _print, _root


@_guard
def _command(args):
    from ._state import _status
    from ._wave import _next_round

    root = _root(args)
    if args.wave_command == "next":
        result = _next_round(root, args.request, actor=_actor(args))
        lines = [f"Building: {result['building']}/{result['limit']}",
                 f"Started: {', '.join(result['started']) or '0 briefs'}"]
        for action in result["actions"]:
            lines.extend([f"Acknowledge request: {action['ack_request']}", _action_text(action)])
    else:
        result = _status(root, args.request)
        lines = [f"{len(result['briefs'])} briefs"]
        for row in result["briefs"]:
            lines.append(f"{row['brief']} ({row['policy']})")
            lines.extend(f"  {stage}: {value or '—'}" for stage, value in row["stages"].items())
            lines.append(f"  lead time: {row['lead_time_seconds']} seconds; "
                         f"base merges: {row['base_merges']}; CI runs: {row['ci_runs']}")
            lines.extend(f"  repair: {r['kind']} at {r['at']}" for r in row["repairs"])
            if row["stop"]:
                stop = row["stop"]
                lines.append(f"  stop: {stop['cause']} ({stop['kind']}) — {stop['detail']}")
    lines.append(f"Queue: {', '.join(result['queue']) or '0 briefs'}")
    _print(args, result, "\n".join(lines))
    return 0


def _register(subparsers):
    parser = subparsers.add_parser("wave", help="Advance or observe a request's briefs.")
    commands = parser.add_subparsers(dest="wave_command", required=True)
    for verb, help_text in (
        ("next", "Advance in-flight briefs, then start ready briefs up to the limit."),
        ("status", "Read stage times, repairs and stop causes without writes or fetching."),
    ):
        command = commands.add_parser(verb, help=help_text, description=help_text)
        command.add_argument("request", help="Intent, brief ids, or an implement-style description")
        command.add_argument("--at", default=None, help="repository root (default: current git root)")
        command.add_argument("--json", action="store_true", help="machine-readable result")
        command.set_defaults(func=_command)
