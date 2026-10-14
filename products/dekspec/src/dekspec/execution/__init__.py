"""Execution & Evidence Engine (AE-011; ADR-055 – ADR-058).

The executable path by which an accepted Implementation Brief is carried out
and proven complete — without code beads, without mandatory parent
artifacts, and without treating task closure or a status update as evidence.

* :mod:`contract`   — the IB as a work contract (binding / acceptance / hypothesis)
* :mod:`references` — obligation references resolved to their one canonical home
* :mod:`context`    — generated execution context with a source manifest
* :mod:`record`     — append-only, hash-chained execution records
* :mod:`state`      — current state folded from the record
* :mod:`plan`       — revisable executor plans and internal tasks
* :mod:`scope`      — scope, protected surfaces and spec-impact checks
* :mod:`acceptance` — baselines, protected assets, evidence per test node
* :mod:`floor`      — the read-only acceptance floor report (ADR-062)
* :mod:`engine`     — the verbs and gates (accept … complete)
* :mod:`delivery`   — integrated verification and the landing gate
* :mod:`legacy`     — migration of legacy code-bead work and retired statuses
"""
