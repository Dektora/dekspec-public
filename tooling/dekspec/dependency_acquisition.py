"""Cross-platform, user-scoped acquisition of DekSpec's external binary
dependencies (currently `br` / beads-rust). Realizes ADR-044 / INT-178.

Policy (ADR-044): for the detected OS + CPU architecture, resolve a
DekSpec-pinned upstream release, download the official release artifact over
HTTPS, verify it against a source-controlled pinned SHA-256 *before* the
artifact is extracted or executed, and install the binary atomically into a
user-scoped executable directory — no Rust/Cargo, WSL, Bash, administrator
privileges, or machine-wide PATH mutation. Idempotent; supports upgrade,
repair, and uninstall. DekSpec downloads the genuine upstream artifact; it
does not fork, vendor, or redistribute beads-rust.

Supply-chain invariants:
  * HTTPS-only, allowlisted origin (the pinned upstream repo).
  * checksum verified before extraction/execution; mismatch/missing/malformed
    is rejected and leaves no partial binary.
  * atomic replacement on upgrade; never clobbers an *unrelated* `br`.
  * every install records repo, tag, asset, checksum, path, and timestamp.

All network I/O funnels through the module-level `_fetch` hook so tests run
fully offline by injecting bytes.
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import platform
import shutil
import stat
import subprocess
import tarfile
import tempfile
import zipfile
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen

# --------------------------------------------------------------------------
# Pinned upstream metadata (reviewed, source-controlled). Bump deliberately;
# refresh the checksums from the release's SHA256SUMS when the version moves.
# --------------------------------------------------------------------------

BR_UPSTREAM_REPO = "Dicklesworthstone/beads_rust"
BR_ALLOWLISTED_HOST = "github.com"
BR_PINNED_VERSION = "0.2.16"

# Compatible range: DekSpec accepts exactly the pinned version as "recognized".
# A different beads-rust on PATH still works (identity-checked), but doctor
# flags it as an unrecognized/incompatible version with a repair command.
BR_COMPATIBLE_VERSIONS = (BR_PINNED_VERSION,)

_RELEASE_DOWNLOAD_BASE = (
    f"https://{BR_ALLOWLISTED_HOST}/{BR_UPSTREAM_REPO}/releases/download"
)


@dataclass(frozen=True)
class BrAsset:
    """A resolved, pinned release artifact for one (os, arch) host."""

    os_name: str          # "windows" | "linux" | "darwin"
    arch: str             # "x86_64" | "aarch64"
    asset_name: str       # upstream asset filename
    sha256: str           # pinned lowercase hex digest
    version: str

    @property
    def url(self) -> str:
        return f"{_RELEASE_DOWNLOAD_BASE}/v{self.version}/{self.asset_name}"

    @property
    def is_zip(self) -> bool:
        return self.asset_name.endswith(".zip")

    @property
    def binary_name(self) -> str:
        return "br.exe" if self.os_name == "windows" else "br"


# Canonical per-(os, arch) asset. Upstream publishes each binary under two
# arch spellings (amd64/x86_64, arm64/aarch64) with identical bytes; we pin
# one canonical name per host so selection is deterministic. Checksums are the
# real v0.2.16 SHA256SUMS values.
_BR_ASSETS: dict[tuple[str, str], BrAsset] = {
    ("windows", "x86_64"): BrAsset(
        "windows", "x86_64", f"br-{BR_PINNED_VERSION}-windows_amd64.zip",
        "9bf5f367ed2fa183a5e3882e8d1aec029174972a15ed53732aa3d251ed769767",
        BR_PINNED_VERSION,
    ),
    ("linux", "x86_64"): BrAsset(
        "linux", "x86_64", f"br-{BR_PINNED_VERSION}-linux_amd64.tar.gz",
        "461efbc44cec9166e7c7334d6c9f9793bea4ab8cb998aa47fd5f50b632ceb1a6",
        BR_PINNED_VERSION,
    ),
    ("linux", "aarch64"): BrAsset(
        "linux", "aarch64", f"br-{BR_PINNED_VERSION}-linux_arm64.tar.gz",
        "d0bf93bb4dc5dbaa44a4e0d4b58ad5ba0ea221ab7402854203b4ba763c99a7f1",
        BR_PINNED_VERSION,
    ),
    ("darwin", "x86_64"): BrAsset(
        "darwin", "x86_64", f"br-{BR_PINNED_VERSION}-darwin_amd64.tar.gz",
        "9375ee03eeff3d0971419424ba9b781e4d6c04f3b75798825cd0184fbd3be1d7",
        BR_PINNED_VERSION,
    ),
    ("darwin", "aarch64"): BrAsset(
        "darwin", "aarch64", f"br-{BR_PINNED_VERSION}-darwin_arm64.tar.gz",
        "67396a0cee144f72df34596590c694dd037a7647965d30f15550420d29134dce",
        BR_PINNED_VERSION,
    ),
}


# --------------------------------------------------------------------------
# Errors
# --------------------------------------------------------------------------

class DependencyError(Exception):
    """Base class for acquisition failures."""


class UnsupportedPlatform(DependencyError):
    """No pinned asset for the detected (os, arch)."""


class ChecksumMismatch(DependencyError):
    """Downloaded artifact did not match the pinned SHA-256."""


class RefusingToClobber(DependencyError):
    """An unrelated executable named `br` already occupies the target."""


class InsecureSource(DependencyError):
    """A non-HTTPS or non-allowlisted download URL was requested."""


# --------------------------------------------------------------------------
# Platform detection + asset resolution
# --------------------------------------------------------------------------

def detect_platform() -> tuple[str, str]:
    """Return canonical (os_name, arch) for the current host.

    os_name ∈ {windows, linux, darwin}; arch ∈ {x86_64, aarch64}. Normalizes
    upstream's duplicate spellings (amd64→x86_64, arm64→aarch64).
    """
    system = platform.system().lower()
    os_name = {"windows": "windows", "linux": "linux", "darwin": "darwin"}.get(
        system, system
    )
    machine = platform.machine().lower()
    arch = {
        "amd64": "x86_64", "x86_64": "x86_64", "x64": "x86_64",
        "arm64": "aarch64", "aarch64": "aarch64",
    }.get(machine, machine)
    return os_name, arch


def resolve_asset(os_name: str, arch: str) -> BrAsset:
    """Resolve the pinned asset for a (os, arch), or raise UnsupportedPlatform."""
    try:
        return _BR_ASSETS[(os_name, arch)]
    except KeyError:
        supported = ", ".join(f"{o}/{a}" for o, a in sorted(_BR_ASSETS))
        raise UnsupportedPlatform(
            f"no pinned br asset for {os_name}/{arch}. "
            f"Supported: {supported}."
        ) from None


def user_bin_dir() -> Path:
    """The user-scoped executable directory DekSpec installs into.

    `%USERPROFILE%\\.local\\bin` on Windows, `~/.local/bin` elsewhere — a
    user-writable location requiring no administrator rights and no
    machine-wide PATH change.
    """
    return Path.home() / ".local" / "bin"


# --------------------------------------------------------------------------
# Download + verify (network funnels through _fetch for offline testing)
# --------------------------------------------------------------------------

def _fetch(url: str) -> bytes:  # pragma: no cover - exercised via injection
    """Fetch bytes over HTTPS. Tests inject a replacement to run offline."""
    with urlopen(url, timeout=60) as resp:  # noqa: S310 - scheme asserted below
        return resp.read()


def _assert_secure_source(url: str) -> None:
    if not url.startswith("https://"):
        raise InsecureSource(f"refusing non-HTTPS download source: {url}")
    host = url.split("/", 3)[2] if url.count("/") >= 2 else ""
    if host != BR_ALLOWLISTED_HOST:
        raise InsecureSource(
            f"refusing download from non-allowlisted host {host!r} "
            f"(allowlisted: {BR_ALLOWLISTED_HOST})"
        )


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def download_and_verify(asset: BrAsset, *, fetch=None) -> bytes:
    """Download the asset over HTTPS and verify its pinned SHA-256.

    Returns the raw archive bytes only if the digest matches; raises
    ChecksumMismatch (before any extraction/execution) otherwise. Never
    touches the filesystem, so a rejected artifact leaves nothing behind.
    """
    fetch = fetch or _fetch
    _assert_secure_source(asset.url)
    data = fetch(asset.url)
    if not data:
        raise ChecksumMismatch(f"empty/missing artifact for {asset.asset_name}")
    actual = _sha256(data)
    if actual != asset.sha256:
        raise ChecksumMismatch(
            f"checksum mismatch for {asset.asset_name}: "
            f"expected {asset.sha256}, got {actual}"
        )
    return data


def _extract_binary(archive_bytes: bytes, asset: BrAsset, dest_dir: Path) -> Path:
    """Extract the `br`/`br.exe` binary from the verified archive into
    dest_dir under a temp name. Returns the extracted temp path."""
    want = asset.binary_name
    if asset.is_zip:
        with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
            member = _match_member(zf.namelist(), want)
            payload = zf.read(member)
    else:
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:gz") as tf:
            member = _match_member(tf.getnames(), want)
            extracted = tf.extractfile(member)
            payload = extracted.read() if extracted else b""
    if not payload:
        raise DependencyError(f"archive {asset.asset_name} contained no {want}")
    tmp = dest_dir / f".{want}.extract.tmp"
    tmp.write_bytes(payload)
    return tmp


def _match_member(names: list[str], want: str) -> str:
    """Pick the archive member that is the br binary (exact basename match)."""
    for n in names:
        if Path(n).name == want:
            return n
    # Some archives ship `br` without extension even on windows; fall back.
    base = "br.exe" if want == "br.exe" else "br"
    for n in names:
        if Path(n).name in (base, "br", "br.exe"):
            return n
    raise DependencyError(f"no {want} member found in archive ({names})")


# --------------------------------------------------------------------------
# Install record (provenance)
# --------------------------------------------------------------------------

def _record_path(dest_dir: Path) -> Path:
    return dest_dir / ".dekspec-dependencies.json"


def _load_record(dest_dir: Path) -> dict:
    p = _record_path(dest_dir)
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {}


def _write_record(dest_dir: Path, asset: BrAsset, dest: Path, *, now=None) -> None:
    rec = _load_record(dest_dir)
    ts = (now or datetime.now(timezone.utc)).isoformat()
    rec["br"] = {
        "repo": BR_UPSTREAM_REPO,
        "release_tag": f"v{asset.version}",
        "asset": asset.asset_name,
        "sha256": asset.sha256,
        "version": asset.version,
        "path": str(dest),
        "installed_at": ts,
    }
    _record_path(dest_dir).write_text(
        json.dumps(rec, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


# --------------------------------------------------------------------------
# Identity + installed-state introspection
# --------------------------------------------------------------------------

def is_beads_rust(br_path: str | os.PathLike) -> bool:
    """Does the binary at br_path look like beads-rust (not brotli's `br`)?

    Runs `br --help` and checks for the `beads` substring. False on any
    subprocess error or timeout.
    """
    try:
        proc = subprocess.run(
            [str(br_path), "--help"],
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return False
    return "beads" in ((proc.stdout or "") + (proc.stderr or "")).lower()


def _br_version(br_path: str | os.PathLike) -> str | None:
    try:
        proc = subprocess.run(
            [str(br_path), "--version"],
            capture_output=True, text=True, timeout=2, check=False,
        )
    except (subprocess.TimeoutExpired, OSError):
        return None
    out = ((proc.stdout or "") + (proc.stderr or "")).strip()
    # Expect e.g. "br 0.2.16"; return the first token that looks like a version.
    for tok in out.replace("v", " ").split():
        if tok[:1].isdigit() and "." in tok:
            return tok
    return out or None


@dataclass
class BrStatus:
    installed: bool
    path: str | None
    version: str | None
    is_beads_rust: bool
    hash_recognized: bool
    compatible: bool
    managed_by_dekspec: bool
    pinned_version: str = BR_PINNED_VERSION
    compatible_versions: tuple[str, ...] = BR_COMPATIBLE_VERSIONS


def br_status(dest_dir: Path | None = None) -> BrStatus:
    """Report the current `br` install state for doctor.

    Resolution order: a DekSpec-managed install in dest_dir (default
    user_bin_dir), else the first `br` on PATH.
    """
    dest_dir = dest_dir or user_bin_dir()
    managed = _load_record(dest_dir).get("br")
    managed_path = dest_dir / ("br.exe" if os.name == "nt" else "br")

    if managed and managed_path.exists():
        version = managed.get("version")
        return BrStatus(
            installed=True, path=str(managed_path), version=version,
            is_beads_rust=True,
            hash_recognized=managed.get("sha256")
            in {a.sha256 for a in _BR_ASSETS.values()},
            compatible=version in BR_COMPATIBLE_VERSIONS,
            managed_by_dekspec=True,
        )

    found = shutil.which("br")
    if found:
        version = _br_version(found)
        return BrStatus(
            installed=True, path=found, version=version,
            is_beads_rust=is_beads_rust(found),
            hash_recognized=False,  # unmanaged: not verified against a pin
            compatible=version in BR_COMPATIBLE_VERSIONS,
            managed_by_dekspec=False,
        )

    return BrStatus(
        installed=False, path=None, version=None, is_beads_rust=False,
        hash_recognized=False, compatible=False, managed_by_dekspec=False,
    )


# --------------------------------------------------------------------------
# Atomic install / upgrade / repair / uninstall
# --------------------------------------------------------------------------

def _atomic_install(src_tmp: Path, dest: Path) -> None:
    """Move src_tmp to dest atomically (os.replace within the same dir) and
    make it executable. Overwrites an existing dest in one syscall."""
    if os.name != "nt":
        src_tmp.chmod(src_tmp.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    os.replace(src_tmp, dest)


@dataclass
class InstallResult:
    action: str           # "installed" | "upgraded" | "noop" | "repaired"
    path: str
    version: str
    asset: str
    sha256: str


def install_br(
    dest_dir: Path | None = None,
    *,
    os_name: str | None = None,
    arch: str | None = None,
    fetch=None,
    force: bool = False,
    now=None,
) -> InstallResult:
    """Idempotently acquire `br` into a user-scoped bin dir.

    - No-op if a DekSpec-managed compatible `br` is already present (unless
      force).
    - Upgrades a managed but out-of-date `br` in place (atomic replace).
    - Refuses to clobber an *unrelated* `br` (fails the beads-rust identity
      check and was not installed by DekSpec) unless force.
    - Downloads → verifies SHA-256 → extracts → atomically installs, using a
      temp dir cleaned on success or failure. On any failure no partial binary
      is left at the destination.
    """
    if os_name is None or arch is None:
        det_os, det_arch = detect_platform()
        os_name = os_name or det_os
        arch = arch or det_arch
    asset = resolve_asset(os_name, arch)

    dest_dir = dest_dir or user_bin_dir()
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / asset.binary_name

    record = _load_record(dest_dir).get("br")
    managed_here = bool(record) and Path(record.get("path", "")) == dest

    # Idempotency: managed + compatible + present → no-op.
    if not force and dest.exists() and managed_here:
        if record.get("version") in BR_COMPATIBLE_VERSIONS:
            return InstallResult(
                "noop", str(dest), record["version"], asset.asset_name,
                record.get("sha256", ""),
            )

    # Clobber guard: a pre-existing binary we did NOT install and that is not
    # beads-rust is off-limits (e.g. brotli's `br`).
    if dest.exists() and not managed_here and not force:
        if not is_beads_rust(dest):
            raise RefusingToClobber(
                f"{dest} exists and is not beads-rust (an unrelated `br`, e.g. "
                f"brotli). Refusing to overwrite. Move it aside or re-run with "
                f"force to replace."
            )

    upgrading = dest.exists()

    # Download + verify happen in memory; nothing hits dest until verified.
    data = download_and_verify(asset, fetch=fetch)

    tmp_root = Path(tempfile.mkdtemp(prefix="dekspec-br-"))
    try:
        extracted = _extract_binary(data, asset, tmp_root)
        # Move the verified binary into the destination dir under a temp name,
        # then atomically swap — so an interrupted copy never yields a partial
        # binary at `dest`.
        staged = dest_dir / f".{asset.binary_name}.staged.tmp"
        shutil.copy2(extracted, staged)
        try:
            _atomic_install(staged, dest)
        finally:
            if staged.exists():
                staged.unlink()
    finally:
        shutil.rmtree(tmp_root, ignore_errors=True)

    _write_record(dest_dir, asset, dest, now=now)
    if force:
        action = "repaired"
    elif upgrading:
        action = "upgraded"
    else:
        action = "installed"
    return InstallResult(
        action, str(dest), asset.version, asset.asset_name, asset.sha256
    )


def repair_br(dest_dir: Path | None = None, *, fetch=None, **kw) -> InstallResult:
    """Force a clean reinstall of the pinned `br` (atomic replace)."""
    return install_br(dest_dir, fetch=fetch, force=True, **kw)


def uninstall_br(dest_dir: Path | None = None) -> bool:
    """Remove the DekSpec-managed `br` and its record. Returns True if a
    managed binary was removed. Never removes an unmanaged `br`."""
    dest_dir = dest_dir or user_bin_dir()
    record = _load_record(dest_dir)
    managed = record.get("br")
    if not managed:
        return False
    p = Path(managed.get("path", ""))
    removed = False
    if p.exists() and p.parent == dest_dir:
        p.unlink()
        removed = True
    record.pop("br", None)
    rp = _record_path(dest_dir)
    if record:
        rp.write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    elif rp.exists():
        rp.unlink()
    return removed


def repair_command() -> str:
    """The precise operator command to install/repair `br`."""
    return "dekspec dependencies install br"
