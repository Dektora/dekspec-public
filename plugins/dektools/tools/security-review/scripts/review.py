#!/usr/bin/env python3
"""Run a small supported detector set and report explicitly scoped coverage."""
from __future__ import annotations

import argparse
import fnmatch
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "scripts"))
from evidence_common import emit, git, identity, state_dir  # noqa: E402

CATEGORIES = {"bandit": "source", "pip-audit": "dependencies", "gitleaks": "secrets"}


def normalize(detector, data, sensitive=()):
    findings = []
    def add(rule, path, line, severity, confidence, evidence):
        path = str(Path(path))
        findings.append({"detector": detector, "rule": rule, "path": path, "line": line,
                         "severity": severity, "confidence": confidence,
                         "spec_priority": "elevated" if any(fnmatch.fnmatch(path, g) for g in sensitive) else None,
                         "evidence": evidence})
    if detector == "bandit":
        for item in data["results"]:
            add(item["test_id"], item["filename"], item["line_number"], item["issue_severity"],
                item["issue_confidence"], item["issue_text"])
    elif detector == "pip-audit":
        for dep in data["dependencies"]:
            for vuln in dep.get("vulns", []):
                add(vuln["id"], "requirements.txt", None, vuln.get("severity"), None,
                    {"package": dep["name"], "version": dep["version"], "fix_versions": vuln.get("fix_versions", [])})
    elif detector == "gitleaks":
        if not isinstance(data, list):
            raise ValueError("Expected Gitleaks list")
        for item in data:
            add(item["RuleID"], item["File"], item["StartLine"], item.get("Severity"), None,
                item["Description"])
    else:
        raise ValueError(f"Unsupported detector: {detector}")
    return findings


def validate_evidence(evidence, current):
    if evidence.get("identity") != current:
        raise ValueError("Stale evidence: repository/revision/tree identity differs")
    if not all(k in evidence for k in ("coverage", "findings", "raw_directory")):
        raise ValueError("Evidence is missing coverage, findings or raw reference")
    coverage = evidence["coverage"]
    if not isinstance(coverage, list) or not isinstance(evidence["findings"], list):
        raise ValueError("Invalid evidence shape")
    evidence = dict(evidence)
    complete = (bool(coverage) and all(c.get("status") == "run" for c in coverage)
                and {c.get("category") for c in coverage} >= set(CATEGORIES.values())
                and not evidence.get("tree_changed_during_scan"))
    evidence["verdict"] = "findings" if evidence["findings"] else "scoped-clean" if complete else "incomplete"
    return evidence


def scan(repo, detectors=None, sensitive=(), runner=subprocess.run, which=shutil.which):
    current = identity(repo)
    repo = Path(current["repo"])
    files = git(repo, "ls-files", "--cached", "--others", "--exclude-standard", "-z").stdout.decode().split("\0")
    python = any(f.endswith(".py") for f in files)
    applicable = {"bandit": python, "pip-audit": (repo / "requirements.txt").is_file(), "gitleaks": True}
    selected = set(detectors) if detectors is not None else {d for d, yes in applicable.items() if yes}
    out = state_dir(repo, "security") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    out.mkdir(mode=0o700)
    coverage, findings = [], []
    for detector, category in CATEGORIES.items():
        row = {"detector": detector, "category": category, "status": "unassessed"}
        coverage.append(row)
        if detector not in selected:
            row["status"] = "unassessed" if applicable[detector] else "unsupported"
            continue
        if not applicable[detector]:
            row["status"] = "unsupported"
            continue
        exe = which(detector)
        if not exe:
            row["status"] = "unavailable"
            continue
        raw_path = out / f"{detector}.json"
        commands = {
            "bandit": [exe, "-r", ".", "-f", "json", "-o", str(raw_path)],
            # No --fix or implicit scan of the harness environment.
            "pip-audit": [exe, "-r", "requirements.txt", "--format", "json", "--output", str(raw_path)],
            "gitleaks": [exe, "dir", ".", "--redact", "--report-format", "json", "--report-path", str(raw_path), "--exit-code", "10"],
        }
        try:
            version = runner([exe, "version"] if detector == "gitleaks" else [exe, "--version"],
                             cwd=repo, capture_output=True, text=True, timeout=15, check=False)
            row["version"] = version.stdout.strip()[:200]
            proc = runner(commands[detector], cwd=repo, capture_output=True, text=True, timeout=300, check=False)
            row.update(exit_code=proc.returncode, raw=str(raw_path))
            accepted = (0, 10) if detector == "gitleaks" else (0, 1)
            if proc.returncode not in accepted:
                raise ValueError(f"scanner exited {proc.returncode}")
            data = json.loads(raw_path.read_text())
            parsed = normalize(detector, data, sensitive)
            if proc.returncode and not parsed:
                raise ValueError("nonzero result without findings")
            findings.extend(parsed)
            partial = (detector == "bandit" and data.get("errors")) or (
                detector == "pip-audit" and any(d.get("skip_reason") for d in data["dependencies"]))
            row["status"] = "failed" if partial else "run"
            if partial:
                row["error"] = "Detector skipped inputs; see raw evidence"
        except (OSError, ValueError, KeyError, TypeError, subprocess.TimeoutExpired) as exc:
            row.update(status="failed", error=str(exc))
    # These adapters cannot assess arbitrary source languages or lockfile types.
    foreign = any(Path(f).suffix in {".js", ".ts", ".go", ".rs", ".java", ".rb"} for f in files)
    if foreign:
        coverage.append({"detector": None, "category": "source", "status": "unsupported",
                         "detail": "Non-Python source needs a configured adapter"})
    other_locks = any(Path(f).name in {"poetry.lock", "uv.lock", "package-lock.json", "Cargo.lock", "go.sum"} for f in files)
    if other_locks:
        coverage.append({"detector": None, "category": "dependencies", "status": "unsupported",
                         "detail": "Lockfile coverage is not supplied by requirements.txt scanning"})
    changed = identity(repo) != current
    complete = all(c["status"] == "run" for c in coverage) and not changed
    verdict = "findings" if findings else "scoped-clean" if complete else "incomplete"
    result = {"identity": current, "tree_changed_during_scan": changed, "verdict": verdict,
              "coverage": coverage, "findings": findings, "scope": "supported configured detectors only",
              "agent_analysis": [], "raw_directory": str(out)}
    (out / "review.json").write_text(json.dumps(result, indent=2) + "\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--at", default=".")
    parser.add_argument("--detector", action="append", choices=CATEGORIES, help="Configured detector (repeatable); default all applicable.")
    parser.add_argument("--sensitive", action="append", default=[], help="Spec-sensitive path glob; affects priority only.")
    parser.add_argument("--evidence", help="Reuse a review JSON only for exactly matching target identity.")
    parser.add_argument("--full", action="store_true", help="Full JSON evidence; default compact summary.")
    args = parser.parse_args()
    try:
        result = (validate_evidence(json.loads(Path(args.evidence).read_text()), identity(Path(args.at)))
                  if args.evidence else scan(Path(args.at), args.detector, args.sensitive))
        if args.full:
            emit(result, True)
        else:
            emit({"verdict": result["verdict"], "findings": len(result["findings"]),
                  "coverage": result["coverage"], "evidence": result["raw_directory"],
                  "help": "Use --full for findings. Verdict covers configured detectors only."})
        return 1 if result["verdict"] == "incomplete" or any(c["status"] == "failed" for c in result["coverage"]) else 0
    except (OSError, ValueError) as exc:
        print(f"error: {json.dumps(str(exc))}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
