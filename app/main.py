"""A deliberately small service. The interesting part of this repo is how the
image is built, described, signed and checked, not the app itself."""
import os

from fastapi import FastAPI

app = FastAPI(title="supply-chain-lab")


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/version")
def version() -> dict[str, str]:
    # Baked in at build time, so a running container can say which commit it
    # came from; the signed provenance attestation proves it.
    return {"commit": os.environ.get("GIT_SHA", "unknown"), "build": os.environ.get("BUILD_URL", "unknown")}
