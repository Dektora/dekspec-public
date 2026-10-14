"""Spec-owned archaeology scan CLI adapter."""
import json
from pathlib import Path

def _error(exc, code=1):
    print(f"error: {json.dumps(str(exc))}")
    return code

def scan_command(args):
    from .archeology.scan import scan
    try:
        root = Path(args.at).resolve()
        for parent in (root, *root.parents):
            if (parent / ".git").exists() or (parent / ".dekspec/config.yaml").is_file():
                root = parent
                break
        target = Path(args.target)
        if not target.is_absolute():
            target = root / target
        print(json.dumps([item.to_dict() for item in scan(target, repo_root=root)], indent=2))
        return 0
    except (OSError, ValueError) as exc:
        return _error(exc)
