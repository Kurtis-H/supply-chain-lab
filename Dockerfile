# syntax=docker/dockerfile:1
# Base images are pinned by digest (scripts/check_pins.py enforces it), so a
# re-pushed tag can't change what gets built. Dependabot bumps the digest.
ARG PYTHON_IMAGE=python:3.12-slim

FROM ${PYTHON_IMAGE} AS build
WORKDIR /build
COPY requirements.txt .
# --require-hashes: every package must match a hash in the lockfile.
# --only-binary: wheels only, so no package runs its own code at install time.
RUN python -m venv /venv \
 && /venv/bin/pip install --no-cache-dir --require-hashes --only-binary=:all: -r requirements.txt

FROM ${PYTHON_IMAGE}
ARG GIT_SHA=unknown
ARG BUILD_URL=unknown
ENV GIT_SHA=${GIT_SHA} BUILD_URL=${BUILD_URL} PATH=/venv/bin:$PATH PYTHONDONTWRITEBYTECODE=1
LABEL org.opencontainers.image.source="https://github.com/Kurtis-H/supply-chain-lab" \
      org.opencontainers.image.description="Signed, attested demo service for supply-chain-lab" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.revision="${GIT_SHA}"
COPY --from=build /venv /venv
COPY app /srv/app
WORKDIR /srv
USER 65534:65534
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=3s CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]
