"""The malicious-dependency demo, as tests: the attack works when nothing stops
it, and each defence used in this repo stops it.

The "malicious" packages in demo/ are harmless: they record only the names of
secret-looking environment variables to a local file, never values, and make
no network calls.
"""
import hashlib
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PY_PACKAGE = ROOT / "demo" / "python-package"
NPM_PACKAGE = ROOT / "demo" / "npm-package"
SECRET_NAME = "FAKE_DEMO_API_TOKEN"
SECRET_VALUE = "do-not-steal-this-value"


@pytest.fixture
def env(tmp_path):
    """An environment with a fake secret in it, and where the loot would go."""
    e = os.environ.copy()
    e[SECRET_NAME] = SECRET_VALUE
    e["DEMO_LOOT_FILE"] = str(tmp_path / "loot.txt")
    e["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return e


def pip(env, tmp_path, *args):
    return subprocess.run(
        [sys.executable, "-m", "pip", "install", "--no-deps", "--no-build-isolation",
         "--target", str(tmp_path / "site"), *args],
        env=env, capture_output=True, text=True, cwd=tmp_path,
    )


def loot(env) -> str | None:
    path = Path(env["DEMO_LOOT_FILE"])
    return path.read_text() if path.exists() else None


def sdist(tmp_path) -> Path:
    """The package as a source archive, the way it would arrive from an index."""
    archive = tmp_path / "harmless_typosquat_demo-1.0.0.tar.gz"
    with tarfile.open(archive, "w:gz") as tar:
        tar.add(PY_PACKAGE / "setup.py", arcname="harmless_typosquat_demo-1.0.0/setup.py")
    return archive


# ---- Python ----

def test_installing_from_source_runs_its_code(env, tmp_path):
    result = pip(env, tmp_path, str(sdist(tmp_path)))
    assert result.returncode == 0, result.stderr
    stolen = loot(env)
    assert stolen is not None, "install-time code should have run"
    assert SECRET_NAME in stolen
    assert SECRET_VALUE not in stolen, "the demo must never record values"


def test_wheels_only_blocks_packages_from_an_index(env, tmp_path):
    # --only-binary=:all: (used in the Dockerfile) refuses anything that would
    # have to be built, and building is when setup.py runs.
    index = tmp_path / "index"
    index.mkdir()
    sdist(tmp_path).rename(index / "harmless_typosquat_demo-1.0.0.tar.gz")
    result = pip(env, tmp_path, "--only-binary=:all:", "--no-index", "--find-links", str(index),
                 "harmless-typosquat-demo")
    assert result.returncode != 0
    assert "No matching distribution" in result.stderr
    assert loot(env) is None


def test_wheels_only_does_not_cover_a_direct_path(env, tmp_path):
    # Found while building this repo: pip applies --only-binary to packages it
    # looks up in an index, but an archive given as a path or URL is built
    # anyway, and its code runs. One reason this repo also pins hashes.
    result = pip(env, tmp_path, "--only-binary=:all:", str(sdist(tmp_path)))
    assert result.returncode == 0, result.stderr
    assert loot(env) is not None


def test_a_hash_pinned_lockfile_rejects_a_swapped_package(env, tmp_path):
    # The lockfile pinned a different file (say, the real package); the
    # archive that arrived doesn't match, so pip stops before building it.
    archive = sdist(tmp_path)
    expected = hashlib.sha256(b"the file the lockfile was made from").hexdigest()
    lock = tmp_path / "requirements.txt"
    lock.write_text(f"harmless-typosquat-demo @ {archive.as_uri()} --hash=sha256:{expected}\n")
    result = pip(env, tmp_path, "--require-hashes", "-r", str(lock))
    assert result.returncode != 0
    assert "DO NOT MATCH THE HASHES" in result.stderr
    assert loot(env) is None


def test_hash_mode_rejects_anything_not_in_the_lockfile(env, tmp_path):
    # In --require-hashes mode, a package with no pinned hash can't sneak in.
    result = pip(env, tmp_path, "--require-hashes", str(sdist(tmp_path)))
    assert result.returncode != 0
    assert loot(env) is None


def test_the_real_lockfile_pins_every_package():
    lines = (ROOT / "requirements.txt").read_text()
    packages = [line for line in lines.splitlines() if line and not line[0].isspace() and not line.startswith("#")]
    assert packages
    for entry in packages:
        assert "==" in entry, f"not pinned to a version: {entry}"
    assert lines.count("--hash=sha256:") >= len(packages)


# ---- npm ----

npm = shutil.which("npm")


@pytest.fixture
def npm_project(tmp_path):
    project = tmp_path / "project"
    project.mkdir()
    (project / "package.json").write_text('{"name": "victim", "version": "1.0.0", "private": true}')
    shutil.copytree(NPM_PACKAGE, tmp_path / "evil")
    return project


@pytest.mark.skipif(npm is None, reason="npm not installed")
def test_npm_runs_postinstall_scripts_by_default(env, npm_project):
    result = subprocess.run([npm, "install", "--no-audit", "--no-fund", "../evil"],
                            cwd=npm_project, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    stolen = loot(env)
    assert stolen is not None and SECRET_NAME in stolen
    assert SECRET_VALUE not in stolen


@pytest.mark.skipif(npm is None, reason="npm not installed")
def test_npm_ignore_scripts_stops_it(env, npm_project):
    result = subprocess.run([npm, "install", "--no-audit", "--no-fund", "--ignore-scripts", "../evil"],
                            cwd=npm_project, env=env, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert loot(env) is None
