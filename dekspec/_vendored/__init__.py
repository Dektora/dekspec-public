"""Wheel-bundled vendored content (templates + cherry-picked docs).

Populated at wheel build time by `setup.py::VendoringBuildPy` from the
project-root `templates/` and `docs/` directories. Empty in a fresh source
checkout — the build hook materializes content here only when invoking
`python -m build` (wheel/sdist) or the equivalent.

`tooling/dekspec/vendoring.py::library_root()` prefers `<source-root>/templates/`
when present (editable installs + source checkouts) and falls back to this
package's `_vendored/templates/` when only the wheel-installed layout is
available (pip / pipx installs). The fallback exists so `verify-vendored`
works correctly from any install method (closes ds-md9).
"""
