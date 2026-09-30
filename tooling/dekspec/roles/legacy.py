"""Retired Context Specifications: recognizing what a project still holds (ADR-061).

One classification, used by the markdown migration and by the
`LINK-LEGACY-CONTEXT-SPEC` audit rule, so the disposition a project sees does not
depend on which library span a migration run happens to cover.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from . import LEGACY_IDS

__all__ = ["KNOWN_LIBRARY_COPIES", "LegacyFile", "classify_legacy", "content_digest"]

#: sha256 (of LF-normalized content) of every version of the library's former
#: `dekspec/context-specs/role-*.md` files, from its git history.
KNOWN_LIBRARY_COPIES: dict[str, str] = {
    "5b3a157a38b94749f67d070c2033cc1adfff9f3d4d55ee54f98d0c1c9530e769": "role-specifier.md @ 630d8978 (CS-001)",
    "af24ed8d01690767453ed732f3a4f94ec3437a677d7e33d9ac2352d2a3e8647b": "role-spec-reviewer.md @ 630d8978 (CS-002)",
    "3e3f805c9326e7a8bc18a7124826e1773cf89f7f560f3b45c0f161605b052f61": "role-implementer.md @ 630d8978 (CS-003)",
    "14e657979bdca6420f62f321dbdf17ff099fb77a7a34aaffa6695ccde899e209": "role-implementer.md @ 6ad7ee76 (CS-003)",
    "9d1f50cf5581043465edc34d2d13100f76298fc16cb3c67ed5bf9e88afe1f2bd": "role-code-reviewer.md @ 630d8978 (CS-004)",
    "7362bfabfd961f0d777a386f0cedbb2c2c88f8bb7323205a196fa887e9c35427": "role-verifier.md @ 630d8978 (CS-005)",
    "a454cdc4de08f4bd7cd0a804ed81e9da76b7afc0b43c5a466113f570d257a643": "role-auditor.md @ 630d8978 (CS-006)",
}

_CS_ID = re.compile(r"\bCS-\d{3,}\b")


def content_digest(data: bytes) -> str:
    """sha256 of the content with a UTF-8 BOM dropped and CRLF line ends made LF,
    so a checkout's line-ending conversion never makes a pristine copy look edited."""
    return hashlib.sha256(data.removeprefix(b"\xef\xbb\xbf").replace(b"\r\n", b"\n")).hexdigest()


@dataclass(frozen=True)
class LegacyFile:
    kind: str  # "unmodified" | "custom" | "other"
    legacy_id: str | None  # the CS id the file carries, if any
    successor: str | None  # the role that continues it, if known
    library_copy: str | None  # which library file an unmodified copy came from

    @property
    def successor_text(self) -> str:
        if self.successor:
            return f"`{self.successor}`" + (f" (was {self.legacy_id})" if self.legacy_id else "")
        return "the library's Agent Role Specifications"


def classify_legacy(path: Path, data: bytes) -> LegacyFile:
    """Classify one file found under a project's retired `context-specs/` directory."""
    origin = KNOWN_LIBRARY_COPIES.get(content_digest(data))
    text = data.decode("utf-8", errors="replace")
    match = _CS_ID.search(text)  # the first id in the file, by position
    legacy_id = match.group(0) if match else None
    stem = path.stem.removeprefix("role-")
    successor = LEGACY_IDS.get(legacy_id or "") or (stem if stem in LEGACY_IDS.values() else None)
    if origin:
        kind = "unmodified"
    elif path.name.startswith("role-") or "## Role Identity" in text:
        kind = "custom"  # a Context Specification: role-keyed file or its section layout
    else:
        kind = "other"  # anything else in the directory, even one that mentions a CS id
    return LegacyFile(kind, legacy_id, successor, origin)
