"""Safe native YAML loading with the established Python-loader diagnostics."""
from __future__ import annotations

import re
from typing import Any, IO

import yaml


# Known scanner/resolver differences: tabs, non-specific tags, BOM handling,
# and block scalar headers without whitespace before a comment. Conservative
# fallback also covers these characters inside otherwise harmless quoted text.
_PYTHON_SYNTAX = re.compile(r"[\t!\ufeff]|[|>][0-9+-]*#")

def safe_load(source: str | bytes | IO[Any]) -> Any:
    """Use libyaml for ordinary input without widening SafeLoader's grammar.

    Keep syntax where the loaders differ on the original loader. Retry native
    failures there too, preserving exception text, snippets and marks.
    """
    loader = getattr(yaml, "CSafeLoader", yaml.SafeLoader)
    # Applications may extend SafeLoader's constructors or resolvers. Only use
    # the native scanner while both classes share the same interpretation tables.
    tables = ("yaml_constructors", "yaml_multi_constructors",
              "yaml_implicit_resolvers", "yaml_path_resolvers")
    if loader is yaml.SafeLoader or any(
        getattr(loader, name) is not getattr(yaml.SafeLoader, name) for name in tables
    ):
        return yaml.safe_load(source)
    position = None
    if isinstance(source, (str, bytes)):
        content = source
    else:
        position = source.tell()
        content = source.read()
    try:
        text = content.decode("utf-8") if isinstance(content, bytes) else content
    except UnicodeError:
        text = "\ufeff"  # Let SafeLoader handle other byte encodings as before.
    if not _PYTHON_SYNTAX.search(text):
        try:
            return yaml.load(content, Loader=loader)
        except yaml.YAMLError:
            pass
    if position is not None:
        source.seek(position)
    return yaml.safe_load(source)
