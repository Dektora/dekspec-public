"""Bundle only Builder-owned resources from the standalone product source."""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py

ROOT = Path(__file__).resolve().parent


class ProductBuild(build_py):
    def run(self):
        super().run()
        destination = Path(self.build_lib) / "dekbuilder" / "_payload"
        if destination.exists():
            shutil.rmtree(destination)
        source = ROOT / "plugins" / "dekbuilder"
        shutil.copytree(source, destination / "plugins" / "dekbuilder")
        files = []
        for path in sorted(source.rglob("*")):
            if path.is_file():
                rel = path.relative_to(ROOT).as_posix()
                files.append({"source": rel, "destination": rel,
                              "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
        (destination / "copy-manifest.json").write_text(json.dumps({"owner": "dekbuilder", "files": files}, indent=2) + "\n")


setup(cmdclass={"build_py": ProductBuild})
