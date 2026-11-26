# supply-chain-lab

[![CI](https://github.com/Kurtis-H/supply-chain-lab/actions/workflows/ci.yml/badge.svg)](https://github.com/Kurtis-H/supply-chain-lab/actions/workflows/ci.yml)
[![Release](https://github.com/Kurtis-H/supply-chain-lab/actions/workflows/release.yml/badge.svg)](https://github.com/Kurtis-H/supply-chain-lab/actions/workflows/release.yml)
[![OpenSSF Scorecard](https://api.scorecard.dev/projects/github.com/Kurtis-H/supply-chain-lab/badge)](https://scorecard.dev/viewer/?uri=github.com/Kurtis-H/supply-chain-lab)

**Software supply-chain security, demonstrated and proven in CI.** A small service is built into a container image that comes with a full list of its contents (SBOM), a vulnerability gate, a keyless signature, and SLSA build provenance. A deploy gate accepts it, and CI proves the gate **rejects** tampered images and signatures from anyone else. A harmless "malicious" package shows what a real attack can do at install time, and which defences stop it.

Everything here is free: GitHub Actions, GitHub Container Registry, Sigstore, Syft, Grype and OpenSSF Scorecard.

## Threats, defences, and the proof

| Threat | Defence here | Proven by |
|---|---|---|
| A dependency runs code the moment it's installed (typosquats, hijacked packages) | Wheels only (`--only-binary`), hash-pinned lockfile, `npm --ignore-scripts` | [`tests/test_malicious_dependency.py`](tests/test_malicious_dependency.py): the attack works unprotected, and each defence blocks it |
| A package is swapped for a different file with the same name and version | `requirements.txt` pins a SHA-256 for every file; installs use `--require-hashes` | Same tests: a mismatched archive is refused before any code runs |
| An action's tag is moved to malicious code (as in the 2025 tj-actions compromise) | Every action pinned to a full commit SHA | [`scripts/check_pins.py`](scripts/check_pins.py) fails CI on any tag-only `uses:` |
| A base image tag is re-pushed with different contents | `FROM` pinned by digest | Same check |
| Shipping known vulnerabilities | SBOM (Syft) scanned by Grype; CI fails on fixable high or critical | The *Image, SBOM and vulnerability gate* job |
| An attacker pushes their own image to the registry | Keyless signing with cosign; the gate trusts only this repo's release workflow | *Deploy gate rejects tampered and foreign images*: an unsigned, tampered image is refused |
| Someone signs with their own valid identity | The gate checks **who** signed, not just that something was signed | Same job: the real signature, checked against a different expected signer, is refused |
| "What exactly is running, and where did it come from?" | SLSA build provenance and a signed SBOM attached to the image; the image reports its own commit | *Deploy gate accepts the signed image*: `gh attestation verify`, `cosign verify-attestation`, and `/version` matching the commit |

## The malicious-dependency demo

[`demo/`](demo/) holds two packages that behave like real malicious ones: a Python package whose `setup.py` runs at install time, and an npm package with a `postinstall` script. They are **harmless**: they record only the **names** of secret-looking environment variables (never values) to a local file, and make no network calls. A real attack would send the values somewhere.

What the tests show:

| Install | Install-time code runs? |
|---|---|
| `pip install` from a source archive | **Yes.** It sees `FAKE_DEMO_API_TOKEN` |
| `pip install --only-binary=:all:` resolving from an index | No: no wheel, so nothing is built |
| `pip install --only-binary=:all:` with a direct path or URL | **Yes.** pip ignores the flag for explicit archives (found while building this) |
| `pip install --require-hashes` against a lockfile that pinned a different file | No: hash mismatch, refused before building |
| `pip install --require-hashes` with a package that isn't in the lockfile | No: refused |
| `npm install` | **Yes**, via `postinstall` |
| `npm install --ignore-scripts` | No |

No single setting covers everything, which is why the image build uses **both** wheels-only and hash pinning.

## How the release works

[`release.yml`](.github/workflows/release.yml):

1. **Build and push** to `ghcr.io/kurtis-h/supply-chain-lab`, tagged by commit (and `latest` on `main`, `pr-<n>` on pull requests).
2. **Sign** the image digest with `cosign sign`. It's keyless: GitHub's OIDC token proves the signer is this repo's release workflow, Sigstore's Fulcio issues a short-lived certificate for that identity, and the signature is recorded in the Rekor transparency log. There is no private key to steal.
3. **Attest** the SBOM (`cosign attest --type spdxjson`) and the build provenance (`actions/attest-build-provenance`, SLSA v1).
4. **Deploy gate, accept:** verify the signature *and* the signer's identity, the SBOM attestation, and the provenance, then run the image and check it reports the commit that built it.
5. **Deploy gate, reject:** build a tampered copy (one extra file) and push it unsigned. The gate must refuse it, and must refuse the genuine image when expecting a different signer.

Steps 4 and 5 run on every pull request too, so the chain is proven before merge.

### Verify an image yourself

```bash
IMAGE=ghcr.io/kurtis-h/supply-chain-lab:latest
cosign verify "$IMAGE" \
  --certificate-identity "https://github.com/Kurtis-H/supply-chain-lab/.github/workflows/release.yml@refs/heads/main" \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
gh attestation verify "oci://$IMAGE" --repo Kurtis-H/supply-chain-lab
```

## Hardening details

* Workflows start from `permissions: contents: read`. Only the publishing job gets `packages: write`, `id-token: write` and `attestations: write`.
* Checkouts use `persist-credentials: false`, so later steps can't reuse the token.
* The image runs as an unprivileged user (CI checks the UID), and nothing in it is built from source.
* Dependabot keeps the pins fresh: it updates SHA-pinned actions with their version comments, regenerates the lockfile hashes, and bumps the base image digest.
* [OpenSSF Scorecard](https://scorecard.dev/viewer/?uri=github.com/Kurtis-H/supply-chain-lab) grades the repo's own practices every week.

## Run the tests

```bash
pip install --require-hashes -r requirements.txt -r requirements-dev.txt
python -m pytest -v          # includes the malicious-dependency demo (needs npm for the npm part)
python scripts/check_pins.py
```
