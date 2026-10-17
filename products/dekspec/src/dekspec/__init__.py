"""DekSpec — shared library for Dektora projects.

Provides:
- constraint_compiler: transforms LOCKED DekSpec artifacts into enforcement representations.
- fidelity_audit: verifies the artifact graph is consistent.
- cli: entry point for the `dekspec` command.

See docs/architecture.md in the repo root for the full architectural picture.
"""

__version__ = "0.130.0"


# The retained tooling/dekspec import surface links individual files here.
# Resolve the package directory once so newly added modules are available
# through that surface too, without maintaining a second module inventory.
from pathlib import Path as _Path

__path__ = [str(_Path(__file__).resolve().parent)]
