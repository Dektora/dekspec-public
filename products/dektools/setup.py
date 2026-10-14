"""Bundle only the product's own craft resources in its local wheel."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil

from setuptools import setup
from setuptools.command.build_py import build_py


class CraftBuild(build_py):
    def run(self):
        super().run()
        origin = Path(__file__).parent / "plugins/dektools/skills"
        target = Path(self.build_lib) / "dektools/_resources/skills"
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(origin, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        copies = [
            {"source": str(p.relative_to(Path(__file__).parent)),
             "destination": "dektools/_resources/skills/" + str(p.relative_to(origin)),
             "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in sorted(origin.rglob("*")) if p.is_file() and "__pycache__" not in p.parts
        ]
        (target.parent / "copy-manifest.json").write_text(json.dumps({
            "owner": "dektools", "copies": copies,
        }, indent=2) + "\n")


setup(cmdclass={"build_py": CraftBuild})
