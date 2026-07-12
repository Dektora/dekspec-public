> Shared `_lib` prose helper called by `analyze-module-depth`. This is
> not a triggerable skill — it carries no SKILL.md frontmatter and is never
> enumerated by the harness. The parent skill invokes this routine to restructure
> a deep Python module behaviour-preservingly into a package with a small public
> `__init__.py` interface plus private `_*.py` files.

# Folderize Deep Module

Restructure a deep Python module into a package only when the package lets
callers think about less. Do not folderize just to signal importance.

Use this self-contained vocabulary:

- **Module** - anything with an interface and implementation: function, class,
  package, workflow slice, or tier-spanning slice.
- **Interface** - everything callers must know: names, types, invariants,
  ordering, errors, configuration, performance, and lifecycle expectations.
- **Implementation** - code inside the module.
- **Depth** - leverage at the interface. A module is **deep** when a small
  interface hides substantial behavior or policy.
- **Shallow** - interface is nearly as complex as implementation.
- **Seam** - a place where behavior can vary without editing that place.
- **Adapter** - concrete implementation satisfying an interface at a seam.
- **Leverage** - capability callers get per unit of interface they learn.
- **Locality** - change, bugs, and verification concentrated in one module.

## Folderization Rule

Folderize when:

- One file has enough internal parts that it is hard to navigate.
- Callers need a stable public interface while helpers, adapters, types, parsing,
  cache, budget, transport, or implementation phases stay private.
- The package-level interface can be smaller than the internal file layout.

Do not folderize when:

- A single `.py` file is coherent and readable.
- The folder would only create more names/imports with no extra hiding.
- Callers would need to know the submodule layout.
- The split would expose internal seams only for tests.

## Target Shape

Prefer this shape:

```text
module_name/
  __init__.py        # public interface only
  _types.py          # public dataclasses/protocols if large enough
  _implementation.py # default implementation
  _adapters.py       # only when real adapters exist
  _errors.py         # public errors when the interface owns error modes
```

Adapt names to the module's domain. For example, `moment_stack/` may have
`_planning.py`, `_framing.py`, `_materialization.py`, and `_budget.py`.

## Workflow

1. Read the target module, its direct callers, and its direct tests.
2. Identify the current public interface:
   - imported names used by production callers
   - imported names used by tests
   - documented entry points
   - exception classes and dataclasses callers construct
3. Decide whether folderization is justified under the rule above. If not,
   report that and stop unless the user explicitly insists.
4. Design the package:
   - `__init__.py` exports only the public interface with `__all__`
   - private implementation files use leading `_`
   - callers keep the same import path when possible
   - tests import through the public package path
5. Move code in small, behavior-preserving slices:
   - create package directory
   - move public types/errors first
   - move private implementation helpers next
   - leave compatibility imports only when needed
   - update internal imports
6. Verify:
   - `python -m py_compile` for moved files
   - focused tests for the module's public interface
   - smallest broader regression that covers callers
   - `rg` for forbidden private imports from outside the package

## Public Interface Discipline

- `__init__.py` is the package interface.
- Define `__all__` explicitly.
- External callers should import from `package`, not `package._internal`.
- Internal modules may import each other freely.
- Tests should use the public interface unless asserting an internal invariant
  that is intentionally private.
- If a compatibility shim is needed, mark it temporary and keep it thin.

## Import Compatibility

For `foo.py` becoming `foo/`, Python callers can usually keep:

```python
from services.foo import Foo, run_foo
```

because the package path replaces the module path. Before deleting the original
file, ensure no file/package name conflict remains.

If callers import private names from `foo`, either:

- promote the name into the real public interface if it is genuinely public, or
- update callers/tests to use the public behavior seam.

## Anti-Patterns

- Creating `types.py`, `utils.py`, and `helpers.py` by default.
- Splitting by line count only.
- Exposing every internal file in `__init__.py`.
- Making callers orchestrate `_planning`, `_framing`, and `_budget` manually.
- Keeping old tests that lock down shallow helper behavior after interface tests
  cover the deep module behavior.

## Output

When done, report:

- old module path and new package path
- public names exported by `__all__`
- private implementation files created
- callers updated
- tests run
- any compatibility imports left behind
