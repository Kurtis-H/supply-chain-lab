#!/usr/bin/env python3
"""Fail if anything this repo builds from could change without a code change.

* GitHub Actions must be pinned to a full commit SHA. A tag like @v4 can be
  moved by whoever controls the action, which is how the 2025 tj-actions
  compromise spread.
* Docker base images must be pinned by digest. A tag can be re-pushed.
* Python requirements files must pin every package with a hash.

Usage: check_pins.py [repo root]. Prints every problem, exits 1 if any.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

SHA = re.compile(r"^[0-9a-f]{40}$")
USES = re.compile(r"^\s*(?:-\s*)?uses:\s*([^\s#]+)")
DIGEST = re.compile(r"@sha256:[0-9a-f]{64}\b")


def check_workflow(path: Path) -> list[str]:
    problems = []
    for n, line in enumerate(path.read_text().splitlines(), 1):
        m = USES.match(line)
        if not m:
            continue
        ref = m.group(1).strip("'\"")
        if ref.startswith("./"):
            continue  # an action in this repo
        if ref.startswith("docker://"):
            if not DIGEST.search(ref):
                problems.append(f"{path}:{n}: docker action not pinned by digest: {ref}")
            continue
        _, _, version = ref.partition("@")
        if not SHA.match(version):
            problems.append(f"{path}:{n}: action not pinned to a commit SHA: {ref}")
    return problems


def check_dockerfile(path: Path) -> list[str]:
    problems = []
    args: dict[str, str] = {}
    for n, line in enumerate(path.read_text().splitlines(), 1):
        stripped = line.strip()
        arg = re.match(r"ARG\s+(\w+)=(\S+)", stripped)
        if arg:
            args[arg.group(1)] = arg.group(2)
            continue
        frm = re.match(r"FROM\s+(?:--platform=\S+\s+)?(\S+)", stripped, re.I)
        if not frm:
            continue
        image = frm.group(1)
        var = re.fullmatch(r"\$\{?(\w+)\}?", image)
        if var:
            image = args.get(var.group(1), image)
        if image == "scratch" or not re.search(r"[:/@.]", image) and image in _stages(path):
            continue
        if not DIGEST.search(image):
            problems.append(f"{path}:{n}: base image not pinned by digest: {image}")
    return problems


def _stages(path: Path) -> set[str]:
    return set(re.findall(r"^FROM\s+\S+\s+AS\s+(\S+)", path.read_text(), re.I | re.M))


def check_requirements(path: Path) -> list[str]:
    problems = []
    text = path.read_text()
    entries = re.split(r"\n(?=\S)", text)
    for entry in entries:
        first = entry.strip().splitlines()[0] if entry.strip() else ""
        if not first or first.startswith(("#", "-c", "-r", "--")):
            continue
        name = first.split()[0]
        if "==" not in name:
            problems.append(f"{path}: {name} is not pinned to an exact version")
        if "--hash=sha256:" not in entry:
            problems.append(f"{path}: {name} has no hash")
    return problems


def check(root: Path) -> list[str]:
    problems: list[str] = []
    for wf in sorted((root / ".github" / "workflows").glob("*.y*ml")):
        problems += check_workflow(wf)
    for df in sorted(root.glob("**/Dockerfile")):
        if "node_modules" not in df.parts:
            problems += check_dockerfile(df)
    for req in sorted(root.glob("requirements*.txt")):
        problems += check_requirements(req)
    return problems


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent.parent
    problems = check(root)
    for p in problems:
        print(f"::error::{p}")
    print(f"{len(problems)} unpinned dependencies" if problems else "Everything is pinned.")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
