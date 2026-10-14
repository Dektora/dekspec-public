"""The pi.dev (Pi) host adapter for the harness seam (ds-q0ye / IC-017).

Like ``ClaudeAdapter``, ``CodexAdapter``, ``AntigravityAdapter``,
``CursorAdapter``, and ``CopilotAdapter``, this is a *pass-through binding*, not
a reimplementation of dispatch semantics. Real Pi sub-agent dispatch happens
via the Pi harness extension layer — specifically the community
``@tintinweb/pi-subagents`` extension (parallel execution, custom agent types,
mid-run steering, ``subagents:*`` lifecycle events) — not a Python API, so the
default in-process Python path is intentionally inert. The adapter guarantees
result *shape*, *ordering*, and *failure isolation*; per-task work is delegated
to an injectable ``executor`` callable (tests inject a fake; the live harness
layer supplies the real binding).

The Pi host reports ``native`` for all four primitives — including
``dispatch_subagents``. The 2026-06-16 spike confirmed Pi (a minimal terminal
coding harness; ``Environment + Harness + Loop``; 4-tool core) exposes
agent-invocable subagents (via ``@tintinweb/pi-subagents``), the open Agent
Skills standard + prompt-template slash commands, interactive prompts, and 25+
extension hooks via ``pi.events``. The ``dispatch_subagents`` dependency on the
``@tintinweb/pi-subagents`` extension — and the seam's sequential fallback when
that extension is absent — is a DOCUMENTED note (here + the default-executor
message), NOT a new ``capabilities()`` value. IC-017's vocabulary
(native/degraded/unsupported) is LOCKED.
"""

from __future__ import annotations

# NOTE: ``TaskResult`` / ``HarnessUnsupported`` live in the package ``__init__``,
# which imports this module to re-export ``PiAdapter``. To avoid a circular
# import at load time, those names are imported lazily inside the methods below.

_VALID_HOOK_EVENTS = {"SessionStart", "PostToolUse", "Stop"}


def _default_executor(task: dict, *, isolation: str, subagent_type: str) -> object:
    # Importing here keeps the module-level circular import out of the way.
    from . import HarnessUnsupported

    raise HarnessUnsupported(
        "dispatch_subagents",
        "pi",
        "no in-process executor available; dispatch is driven by the Pi "
        "harness extension layer (@tintinweb/pi-subagents), not callable from "
        "pure Python",
    )


class PiAdapter:
    """Pass-through binding of the seam to the Pi (pi.dev) harness."""

    def __init__(self, executor=None) -> None:
        # ``executor(task, *, isolation, subagent_type) -> object`` returns the
        # task's raw output or raises on failure. Default is intentionally inert.
        self._executor = executor if executor is not None else _default_executor
        # Registration-only hook bookkeeping; never executed.
        self._hooks: list[tuple[str, str, str]] = []

    def capabilities(self) -> dict[str, str]:
        return {
            "dispatch_subagents": "native",
            "invoke_skill": "native",
            "ask_user": "native",
            "register_hook": "native",
        }

    def dispatch_subagents(
        self,
        tasks: list[dict],
        *,
        parallel: bool,
        isolation: str,
        subagent_type: str,
    ) -> list:
        from . import TaskResult

        if not tasks:
            raise ValueError(
                "dispatch_subagents requires at least one task; empty task list "
                "is a precondition violation"
            )

        # ``parallel`` is a request, not a guarantee. A simple in-order loop is a
        # valid realization that satisfies index-alignment. Even if a concurrent
        # backend (the @tintinweb/pi-subagents extension) is used, results MUST
        # be re-ordered to input index so result[i] <-> tasks[i].
        results: list = []
        for task in tasks:
            try:
                output = self._executor(
                    task, isolation=isolation, subagent_type=subagent_type
                )
            except Exception as exc:  # per-task failure isolation
                results.append(TaskResult(ok=False, output=None, error=str(exc)))
            else:
                results.append(TaskResult(ok=True, output=output, error=None))
        return results

    def invoke_skill(self, name: str, args: str) -> object:
        from . import HarnessUnsupported

        # Baseline binding point: with no resolvable skill, raise the typed error.
        raise HarnessUnsupported("invoke_skill", "pi", "unknown skill")

    def ask_user(self, prompt: str, choices: list[str]) -> str:
        from . import HarnessUnsupported

        raise HarnessUnsupported(
            "ask_user",
            "pi",
            "no in-process responder; ask_user is driven by the harness",
        )

    def register_hook(self, event: str, matcher: str, handler_cmd: str) -> None:
        if event not in _VALID_HOOK_EVENTS:
            raise ValueError(
                f"unknown hook event {event!r}; expected one of "
                f"{sorted(_VALID_HOOK_EVENTS)}"
            )
        # Registration-only: record the wiring; NEVER exec handler_cmd here.
        self._hooks.append((event, matcher, handler_cmd))
        return None
