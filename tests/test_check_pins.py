import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
import check_pins  # noqa: E402

SHA = "3d3c42e5aac5ba805825da76410c181273ba90b1"
DIGEST = "sha256:" + "ab" * 32


def write(tmp_path, name, text):
    path = tmp_path / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return path


def test_actions_must_use_commit_shas(tmp_path):
    wf = write(tmp_path, "ci.yml", f"""
jobs:
  a:
    steps:
      - uses: actions/checkout@{SHA} # v7.0.1
      - uses: actions/setup-python@v7
      - uses: "docker/login-action@main"
      - uses: ./local-action
      - uses: docker://alpine:3.20
      - uses: docker://alpine@{DIGEST}
""")
    problems = check_pins.check_workflow(wf)
    assert len(problems) == 3
    assert any("setup-python@v7" in p for p in problems)
    assert any("login-action@main" in p for p in problems)
    assert any("docker://alpine:3.20" in p for p in problems)


def test_short_or_fake_shas_are_not_enough(tmp_path):
    wf = write(tmp_path, "ci.yml", f"    - uses: actions/checkout@{SHA[:7]}\n    - uses: a/b@{'g' * 40}\n")
    assert len(check_pins.check_workflow(wf)) == 2


def test_base_images_must_use_digests(tmp_path):
    df = write(tmp_path, "Dockerfile", f"""
ARG PY=python:3.12-slim@{DIGEST}
ARG BAD=python:3.12-slim
FROM ${{PY}} AS build
FROM build
FROM ${{BAD}}
FROM node:22
FROM scratch
""")
    problems = check_pins.check_dockerfile(df)
    assert [p.split(": ", 1)[1] for p in problems] == [
        "base image not pinned by digest: python:3.12-slim",
        "base image not pinned by digest: node:22",
    ]


def test_requirements_need_versions_and_hashes(tmp_path):
    req = write(tmp_path, "requirements.txt", """# comment
-c other.txt
good==1.0 \\
    --hash=sha256:aaa
nohash==2.0
    # via something
loose>=3 \\
    --hash=sha256:bbb
""")
    problems = check_pins.check_requirements(req)
    assert any("nohash==2.0 has no hash" in p for p in problems)
    assert any("loose>=3 is not pinned" in p for p in problems)
    assert len(problems) == 2


def test_this_repo_is_fully_pinned():
    root = Path(__file__).resolve().parent.parent
    assert check_pins.check(root) == []
