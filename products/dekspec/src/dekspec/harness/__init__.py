"""The harness seam (ds-mnxj / IC-017).

A narrow, host-agnostic interface exposing exactly five capabilities behind one
``HarnessAdapter`` Protocol:

    - ``dispatch_subagents`` — fan out a set of tasks to sub-agents
    - ``invoke_skill``       — invoke a named skill
    - ``ask_user``           — ask the operator a question
    - ``register_hook``      — wire a lifecycle hook (registration-only)
    - ``capabilities``       — report the per-primitive capability matrix

Invariants (IC-017, reconciled):
    - In-process only (ADR-024): no out-of-process executor / subprocess dispatch
      backend / lifecycle DB. The injectable executor pattern is in-process by
      construction.
    - Deep module (ADR-036): exactly the five public capabilities — nothing extra.
    - Typed error, never partial: an unsatisfiable + non-degradable request raises
      ``HarnessUnsupported(primitive, host, reason)`` — never a partial result.
    - Result-shape invariance + index alignment hold in both parallel and
      sequential dispatch modes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from .antigravity_adapter import AntigravityAdapter
from .claude_adapter import ClaudeAdapter
from .codex_adapter import CodexAdapter
from .copilot_adapter import CopilotAdapter
from .cursor_adapter import CursorAdapter
from .pi_adapter import PiAdapter

__all__ = [
    "TaskResult",
    "CapabilityMatrix",
    "HarnessUnsupported",
    "HarnessAdapter",
    "ClaudeAdapter",
    "CodexAdapter",
    "AntigravityAdapter",
    "CursorAdapter",
    "CopilotAdapter",
    "PiAdapter",
    "get_adapter",
    "run_fanout",
]


@dataclass
class TaskResult:
    """The result of a single dispatched task.

    Exactly one of ``output`` / ``error`` is meaningful: on success ``ok`` is
    ``True`` and ``output`` carries the task's raw result; on failure ``ok`` is
    ``False`` and ``error`` carries ``str(exc)``.
    """

    ok: bool
    output: object | None
    error: str | None


# A capability matrix maps each of the four primitives to one of
# "native" | "degraded" | "unsupported".
CapabilityMatrix = dict[str, str]


class HarnessUnsupported(Exception):
    """Raised when a primitive is unsatisfiable on a host and cannot degrade.

    Carries the offending ``primitive``, the ``host`` it was requested on, and a
    human-readable ``reason``. ``str()`` includes all three.
    """

    def __init__(self, primitive: str, host: str | None, reason: str) -> None:
        self.primitive = primitive
        self.host = host
        self.reason = reason
        super().__init__(f"{primitive} on host {host!r}: {reason}")


@runtime_checkable
class HarnessAdapter(Protocol):
    """The narrow seam every host adapter satisfies."""

    def capabilities(self) -> CapabilityMatrix:
        ...

    def dispatch_subagents(
        self,
        tasks: list[dict],
        *,
        parallel: bool,
        isolation: str,
        subagent_type: str,
    ) -> list[TaskResult]:
        ...

    def invoke_skill(self, name: str, args: str) -> object:
        ...

    def ask_user(self, prompt: str, choices: list[str]) -> str:
        ...

    def register_hook(self, event: str, matcher: str, handler_cmd: str) -> None:
        ...


def get_adapter(host: str | None = None, *, executor=None) -> HarnessAdapter:
    """Return the adapter for ``host``.

    ``None`` and ``"claude"`` resolve to the baseline Claude adapter; ``"codex"``
    resolves to the Codex adapter; ``"antigravity"`` resolves to the Antigravity
    adapter; ``"cursor"`` resolves to the Cursor adapter; ``"copilot"`` resolves
    to the Copilot adapter; ``"pi"`` resolves to the Pi adapter. Any other host
    raises ``HarnessUnsupported`` — there is no fabricated fallback.

    ``executor`` is forwarded to the chosen adapter's constructor. ``None``
    preserves the baseline behavior: each adapter installs its default inert
    executor (which raises ``HarnessUnsupported`` on dispatch).
    """
    if host in (None, "claude"):
        return ClaudeAdapter(executor=executor)
    if host == "codex":
        return CodexAdapter(executor=executor)
    if host == "antigravity":
        return AntigravityAdapter(executor=executor)
    if host == "cursor":
        return CursorAdapter(executor=executor)
    if host == "copilot":
        return CopilotAdapter(executor=executor)
    if host == "pi":
        return PiAdapter(executor=executor)
    raise HarnessUnsupported("get_adapter", host, "no adapter registered")


def run_fanout(
    tasks: list[dict],
    *,
    host: str | None = None,
    executor=None,
    parallel: bool = True,
    isolation: str = "none",
    subagent_type: str = "general-purpose",
) -> list[TaskResult]:
    """Host-neutral fan-out: drive ``dispatch_subagents`` through the seam.

    This is the single shared entry point the fan-out substrate uses to dispatch
    a set of tasks regardless of host. It composes the seam — ``get_adapter`` to
    resolve the host adapter, then the adapter's ``dispatch_subagents`` — and
    introduces no dispatch logic of its own. Each adapter realizes the dispatch
    on its host (Claude → the Agent tool, Codex → multi-agent, Antigravity →
    dynamic subagents, Cursor → async/nested subagents, Copilot → VS Code
    multi-agent / CLI ``/fleet``); the result-shape and index-alignment
    invariants hold identically across all of them.

    Error propagation flows straight from the seam: an empty ``tasks`` list
    raises ``ValueError`` (from ``dispatch_subagents``); no ``executor`` leaves
    the adapter's default inert executor in place, which raises
    ``HarnessUnsupported`` on dispatch; an unknown ``host`` raises
    ``HarnessUnsupported(primitive="get_adapter")`` from ``get_adapter``.
    """
    adapter = get_adapter(host, executor=executor)
    return adapter.dispatch_subagents(
        tasks,
        parallel=parallel,
        isolation=isolation,
        subagent_type=subagent_type,
    )
