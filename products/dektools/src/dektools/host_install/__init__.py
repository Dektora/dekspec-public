"""`dektools install`: DekTools' own host install (IB-279).

Surface skeleton only (ADR-062): the contracted command and its options exist so the
acceptance tests reach their assertions; no install, check or uninstall behavior is
implemented yet. The implementation replaces this module within IB-279's Scope.
"""

from __future__ import annotations


def register_install(sub):
    """Register `install --platform … [--target] [--source] [--check | --uninstall]`."""
    install = sub.add_parser("install", help="Install DekTools' skills for a host.")
    install.add_argument("--platform")
    install.add_argument("--target", default=".")
    install.add_argument("--source")
    install.add_argument("--check", action="store_true")
    install.add_argument("--uninstall", action="store_true")
    install.set_defaults(func=install_command)


def install_command(args):
    """Behavior-free: writes nothing, prints nothing, exits 0."""
    return 0
