"""One-call wave control: hides request expansion, per-brief driving, readiness, ordering, capacity, locking and coordinator fast-forward, plus stage/count/repair interpretation.
Public next_round(root, request, *, actor), for a repository Path, implement-style request string and requester identity, takes one round and returns BS-046's actions/started/building/limit/queue; pass each action's ack_request unchanged to implement ack after its fresh worker returns.
Public status(root, request) returns {briefs: [BS-046 brief status], queue: [brief]}; UTC stages, seconds of lead time, counts, repairs and distinct stop causes require no write/fetch precautions.
Public register(subparsers) installs wave next/status (request, --at, --json) in one call; callers never manage brief lists, locks, event formats, forge reads or per-brief request construction.
Invalid or absent capacity defaults to two, already-started work resumes without another start, and an empty landing queue is []; recorded failures retain their distinct BS-046 causes, repairs have null stop.
Alternatives: Wave(root).advance()/snapshot() adds object lifetime; discover()/start()/advance()/collect() leaks ordering and locks; the chosen two request operations plus CLI registration minimize caller knowledge.
"""

# Lazy entry points keep CLI registration available when Spec is absent,
# so the existing provider diagnostic (including receipts) stays reachable.
__all__ = ["next_round", "status", "register"]


def next_round(root, request, *, actor):
    """Advance each in-flight brief once, then fill free building slots."""
    from ._wave import _next_round

    return _next_round(root, request, actor=actor)


def status(root, request):
    """Observe one request without changing files, refs, records or fetching."""
    from ._state import _status

    return _status(root, request)


def register(subparsers):
    """Register the wave command group with an argparse subparser collection."""
    from ._cli import _register

    _register(subparsers)
