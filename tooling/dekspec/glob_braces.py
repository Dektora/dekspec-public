"""Shell-style brace-glob expansion, shared across audit gates.

`glob.glob` and `fnmatch` do not understand brace expansion, so a pattern
like ``src/pkg/{cli,doctor}/**/*.py`` would match nothing. Two independent
gates need this expansion and MUST agree, or a ``Components affected:``
brace fold that passes ``/write-intent --analyze`` + the L7b
component-resolve audit will TESTFAIL every file at the ``--testpass``
diff-confinement gate (ds-059n). Factoring the one expander into this leaf
module makes divergence impossible: both gates import the same function.

Consumers:
  * ``dekspec.fidelity_audit.linkage`` — LINK-INT-COMPONENTS-RESOLVE.
  * ``dekspec.diff_confinement`` — the ``--testpass`` confinement gate.
"""

from __future__ import annotations

import re

__all__ = ["expand_braces"]

_BRACE = re.compile(r"\{([^{}]*)\}")


def expand_braces(pattern: str) -> list[str]:
    """Expand shell-style brace groups ``{a,b,c}`` into literal alternatives.

    Turns one pattern into the cartesian product of its brace branches;
    multiple brace groups in one pattern are all expanded. A pattern with
    no braces returns ``[pattern]`` unchanged. Nested braces are not
    supported — the leftmost brace-free group is expanded each pass until
    none remain.
    """
    results = [pattern]
    while any(_BRACE.search(candidate) for candidate in results):
        expanded: list[str] = []
        for candidate in results:
            m = _BRACE.search(candidate)
            if m is None:
                expanded.append(candidate)
                continue
            for alt in m.group(1).split(","):
                expanded.append(candidate[: m.start()] + alt + candidate[m.end() :])
        results = expanded
    return results
