# HARMLESS DEMO of a malicious Python package. Do not publish.
#
# Real attacks (typosquats, hijacked maintainer accounts) put code like this in
# setup.py, because pip runs it the moment the package is built from source,
# before you've imported or used anything. This version only records the NAMES
# of secret-looking environment variables, never their values, writes them to
# a local file, and makes no network calls. A real one would send the values
# somewhere.
import getpass
import os
from pathlib import Path

import setuptools

LOOKS_SECRET = ("TOKEN", "SECRET", "PASSWORD", "API_KEY", "ACCESS_KEY")
names = sorted(k for k in os.environ if any(word in k.upper() for word in LOOKS_SECRET))
loot = Path(os.environ.get("DEMO_LOOT_FILE", "demo-loot.txt"))
loot.write_text(
    f"Install-time code ran as {getpass.getuser()}.\n"
    f"It could read these environment variables: {', '.join(names) or 'none'}\n"
)

setuptools.setup(name="harmless-typosquat-demo", version="1.0.0", py_modules=[])
