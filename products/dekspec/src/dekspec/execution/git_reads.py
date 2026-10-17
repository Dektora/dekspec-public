"""Run Git through one process-local, thread-safe, bounded remembering layer.
Public run(root, *args, **options) returns subprocess.CompletedProcess; capture_output defaults true.
Public popen opens a live stream, which cannot be a remembered answer.
Callers retain subprocess options, decoding and errors; identity, eligibility and HEAD races are hidden.
Uncertain reads, eviction and oversized output run normally; Git and launch errors are never merged.
Retain at most 4,096 answers and 1 MiB combined output per answer; callers never manage memory.
Alternatives: semantic reader objects or a general process wrapper; one Git call preserves caller policy.
"""

import io as _io
import os as _os
import re as _re
import subprocess as _subprocess
import threading as _threading
from collections import OrderedDict as _OrderedDict
from pathlib import Path as _Path

__all__ = ["run", "popen"]

_answers = _OrderedDict()
_pending = set()
_condition = _threading.Condition()
_oid = r"(?:[0-9a-fA-F]{40}|[0-9a-fA-F]{64})"
_part = _re.compile(rf"({_oid}|HEAD)(\^\{{(?:commit|tree)\}}|\^\d+|~\d+|:.+)?", _re.DOTALL)
# Unknown options take the ordinary subprocess path. In particular, options
# which add implicit refs, use reflogs/index state, write files, or invoke
# external diff/textconv programs cannot become fixed questions by accident.
_flags = {
    "rev-parse": {"--verify", "-q", "--quiet", "--end-of-options"},
    "cat-file": {"-e", "-t"},
    "show": set(),
    "ls-tree": {"-r", "-t", "-d", "-z", "-l", "--name-only", "--name-status",
                "--full-name", "--full-tree", "--object-only"},
    "merge-base": {"--is-ancestor", "--all", "-a", "--octopus", "--independent"},
    "rev-list": {"--not", "--reverse", "--topo-order", "--parents", "--children",
                 "--count", "--first-parent", "--boundary", "--objects", "--no-object-names"},
    "diff": {"--name-only", "--name-status", "--stat", "--numstat", "--shortstat",
             "--raw", "--patch", "-p", "-r", "-z", "-M", "-C", "--no-renames",
             "--no-ext-diff", "--no-textconv", "--binary", "--full-index"},
    "diff-tree": {"--name-only", "--name-status", "--no-commit-id", "--root",
                  "--raw", "--patch", "-p", "-r", "-z", "-M", "-C", "-m",
                  "--no-renames", "--no-ext-diff", "--no-textconv"},
    "log": {"--reverse", "--topo-order", "--follow", "--name-only", "--full-history",
            "--raw", "-m", "--first-parent", "--no-decorate"},
}


def _question(args):
    """Recognize only fixed revision expressions and options we understand."""
    start = 0
    while args[start:start + 1] == ("-c",):
        if start + 1 >= len(args):
            return None
        config = args[start + 1].split("=", 1)[0].lower()
        # Repository/ref redirection and external drivers defeat file guards.
        if config.startswith(("core.", "extensions.", "include", "diff.", "filter.")) and config != "core.quotepath":
            return None
        start += 2
    if start >= len(args) or args[start] not in _flags:
        return None
    command, tail = args[start], args[start + 1:]
    tail = tail[:tail.index("--")] if "--" in tail else tail
    revisions, formats = [], []
    index = 0
    while index < len(tail):
        value = tail[index]
        if value in _flags[command] or (command == "cat-file" and value == "blob"):
            pass
        elif command in {"rev-list", "log"} and value in {"-n", "--max-count", "--format"}:
            index += 1
            if index >= len(tail):
                return None
            if value == "--format":
                formats.append(tail[index])
            elif not tail[index].isdigit():
                return None
        elif command in {"rev-list", "log"} and value.startswith("--max-count=") and value[12:].isdigit():
            pass
        elif command == "ls-tree" and value.startswith("--format="):
            pass
        elif command == "log" and value.startswith("--format="):
            formats.append(value[9:])
        elif value.startswith("-"):
            return None
        else:
            revisions.append(value)
        index += 1
    if not revisions:
        return None
    parts = []
    for revision in revisions:
        # A colon begins a literal path, whose dots aren't range syntax.
        split = revision.split("..") if ":" not in revision else [revision]
        if len(split) > 2 or not all(_part.fullmatch(part) for part in split):
            return None
        parts.extend(split)
    if command == "rev-parse" and ("--verify" not in tail or len(parts) != 1):
        return None
    if command == "cat-file" and (len(parts) != 1 or not any(v in tail for v in ("-e", "-t", "blob"))):
        return None
    if command == "show" and (len(parts) != 1 or ":" not in parts[0]):
        return None
    if command == "ls-tree" and len(parts) != 1:
        return None
    if command == "diff" and len(parts) < 2:
        return None
    if command == "log":
        # Besides decorations, some formats read live notes/mailmaps, describe
        # refs, use relative dates, or abbreviate ids against the current object
        # database. Uncertain output takes the uncached path too.
        if (not formats or not any(".." in r.split(":", 1)[0] for r in revisions)
                or any("%d" in f or "%D" in f or "%(" in f
                       or _re.search(r"%(?:[ac][rhdDNEL]|[gGNShtp])", f) for f in formats)):
            return None
    return command, parts, any(p.startswith("HEAD") for p in parts), args[:start]


def _read(path):
    """Read optional repository metadata; unreadable files disable remembering."""
    try:
        return path.read_text()
    except FileNotFoundError:
        return ""


def _repository(root, relative_head, relations):
    """Snapshot ordinary loose/packed-ref repositories, including linked worktrees.

    Repeat this filesystem inspection at every lookup and after each miss; never
    retain an answer while replacements, grafts or shallow ancestry apply.
    Unfamiliar storage and redirected repositories are ordinary uncached calls.
    """
    try:
        folder = _Path(root).resolve(strict=True)
        for parent in (folder, *folder.parents):
            marker = parent / ".git"
            if marker.is_dir():
                gitdir = marker
                break
            if marker.is_file():
                link = marker.read_text().strip()
                if not link.startswith("gitdir: "):
                    return None
                gitdir = (parent / link[8:]).resolve(strict=True)
                break
            if (parent / "HEAD").is_file() and (parent / "objects").is_dir():
                gitdir = parent
                break
        else:
            return None
        common_link = _read(gitdir / "commondir").strip()
        common = (gitdir / common_link).resolve(strict=True) if common_link else gitdir
        if (common / "reftable").exists() or _re.search(r"refstorage\s*=\s*(?!files\b)", _read(common / "config"), _re.I):
            return None
        packed = _read(common / "packed-refs")
        if " refs/replace/" in packed:
            return None
        for directory in {gitdir, common}:
            if any(p.is_file() for p in (directory / "refs/replace").rglob("*")):
                return None
            if _read(directory / "info/grafts"):
                return None
            if relations and (directory / "shallow").exists():
                return None
        head = None
        if relative_head:
            head = _read(gitdir / "HEAD").strip()
            if head.startswith("ref: "):
                ref = head[5:]
                if not ref.startswith("refs/") or ".." in ref or "\\" in ref:
                    return None
                head = _read(gitdir / ref).strip() or _read(common / ref).strip()
                if not head:
                    head = next((line.split()[0] for line in packed.splitlines()
                                 if line.endswith(" " + ref)), "")
            if not _re.fullmatch(_oid, head):
                return None
        # Recreating a repository at the same path must not revive old answers.
        identity = tuple((str(p), p.stat().st_dev, p.stat().st_ino) for p in (gitdir, common))
        return str(folder), identity, head
    except (OSError, ValueError, UnicodeError):
        return None


def _present(command, answer, options):
    """Recreate subprocess's per-caller decoding, newline and check semantics."""
    code, stdout, stderr = answer
    if options.get("text") or options.get("universal_newlines") or options.get("encoding") or options.get("errors"):
        def decode(value):
            if not isinstance(value, bytes):
                return value
            with _io.TextIOWrapper(_io.BytesIO(value), encoding=options.get("encoding"),
                                   errors=options.get("errors")) as stream:
                return stream.read()
        stdout, stderr = decode(stdout), decode(stderr)
    result = _subprocess.CompletedProcess(command, code, stdout, stderr)
    if options.get("check"):
        result.check_returncode()
    return result


def _absent_path(root, args, question):
    """Prove an absent tree entry, not an unavailable commit/tree/blob object."""
    command, parts, _, prefix = question
    if command not in {"show", "cat-file"} or len(parts) != 1 or ":" not in parts[0]:
        return False
    if command == "cat-file" and "blob" not in args:
        return False
    commit, path = parts[0].split(":", 1)
    if not path or path.startswith(("/", ":")) or any(p in {".", "..", ""} for p in path.split("/")):
        return False
    exists = run(root, *prefix, "cat-file", "-e", f"{commit}^{{commit}}")
    if exists.returncode:
        return False
    tree = run(root, *prefix, "ls-tree", "-z", commit, "--", f":(literal){path}")
    return tree.returncode == 0 and tree.stdout == b""


def _path_presence(root, parts):
    """Git's missing-path diagnostic depends on whether the path exists on disk."""
    return tuple(_os.path.lexists(_Path(root) / p.split(":", 1)[1])
                 for p in parts if ":" in p)


def popen(root, *args, **options) -> _subprocess.Popen:
    """Open Git in root with unchanged subprocess.Popen options; never remember."""
    return _subprocess.Popen(["git", *args], cwd=root, **options)


def run(root, *args, **options):
    """Run Git in root with subprocess.run options and unchanged result/error semantics."""
    options.setdefault("capture_output", True)
    command = ["git", *args]
    question = _question(args)
    git_env = tuple(sorted((k, v) for k, v in _os.environ.items() if k.startswith("GIT_")))
    # Explicit environments (including archive isolation), supplied stdin and
    # noncapturing/advanced Popen policies always retain the original call.
    allowed = {"capture_output", "check", "text", "universal_newlines", "encoding", "errors", "timeout", "env"}
    redirected = {"GIT_DIR", "GIT_COMMON_DIR", "GIT_WORK_TREE", "GIT_OBJECT_DIRECTORY",
                  "GIT_ALTERNATE_OBJECT_DIRECTORIES", "GIT_SHALLOW_FILE", "GIT_NAMESPACE", "GIT_INDEX_FILE",
                  "GIT_CONFIG_PARAMETERS", "GIT_CONFIG_COUNT", "GIT_REPLACE_REF_BASE"}
    if (question is None or not options.get("capture_output") or options.get("env") is not None
            or set(options) - allowed or any(k in redirected or k.startswith("GIT_TRACE") for k, _ in git_env)
            or ("text" in options and "universal_newlines" in options
                and bool(options["text"]) != bool(options["universal_newlines"]))):
        return _subprocess.run(command, cwd=root, **options)
    kind, parts, relative_head, _ = question
    relations = kind in {"merge-base", "rev-list", "diff", "diff-tree", "log"} or any(
        "^" in p or "~" in p for p in parts)
    while True:
        snapshot = _repository(root, relative_head, relations)
        if snapshot is None:
            return _subprocess.run(command, cwd=root, **options)
        path_state = _path_presence(root, parts)
        key = (snapshot, args, git_env)
        with _condition:
            remembered = _answers.get(key)
            if remembered is not None:
                answer, diagnostic_state = remembered
                if diagnostic_state is None or diagnostic_state == path_state:
                    _answers.move_to_end(key)
                    break
                del _answers[key]
            if key in _pending:
                _condition.wait()
                continue
            _pending.add(key)
            answer = None
            break
    if answer is not None:
        return _present(command, answer, options)
    try:
        raw_options = {k: v for k, v in options.items()
                       if k not in {"check", "text", "universal_newlines", "encoding", "errors"}}
        result = _subprocess.run(command, cwd=root, **raw_options)
        answer = result.returncode, result.stdout, result.stderr
        fixed = result.returncode == 0 or (
            kind == "merge-base" and "--is-ancestor" in args and result.returncode == 1)
        # ls-tree can succeed while printing BAD for an unavailable object's
        # size. A later fetch can supply it, so that is not a fixed answer.
        if (kind == "ls-tree" and ("-l" in args or any("%(objectsize" in a for a in args))
                and isinstance(result.stdout, bytes) and b"BAD" in result.stdout):
            fixed = False
        if not fixed and result.returncode == 128:
            try:
                fixed = _absent_path(root, args, question)
            except OSError:
                # A failed proof (for example a removed cwd) must not replace
                # the result the caller's own Git invocation already returned.
                fixed = False
        size = sum(len(v) for v in (result.stdout, result.stderr) if isinstance(v, bytes))
        if (fixed and size <= 1024 * 1024 and all(isinstance(v, bytes) for v in answer[1:])
                and _repository(root, relative_head, relations) == snapshot
                and (result.returncode != 128 or _path_presence(root, parts) == path_state)
                and git_env == tuple(sorted((k, v) for k, v in _os.environ.items() if k.startswith("GIT_")))):
            with _condition:
                _answers[key] = (answer, path_state if result.returncode == 128 else None)
                _answers.move_to_end(key)
                while len(_answers) > 4096:
                    _answers.popitem(last=False)
        return _present(command, answer, options)
    finally:
        with _condition:
            _pending.remove(key)
            _condition.notify_all()
