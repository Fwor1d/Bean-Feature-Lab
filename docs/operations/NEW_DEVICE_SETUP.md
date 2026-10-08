# Installation on another computer

BeanFeature Lab combines a scientific research workbench, a deployment classifier,
Conference Mode and offline PDF reporting. **Both the private source and private
runtime asset are required** to restore recorded results without the original Mac.
This guide uses RC `v1.0.0-rc.1`, not the final stable release or the production tunnel.
The RC's `distribution.json` identifies its exact source commit, backup identity
and verification context. Check release notes before choosing another version.

## Platforms and prerequisites

| Component | Requirement / verified installation |
|---|---|
| macOS | Apple Silicon is acceptance-tested using an isolated fresh installation on the same Mac; this is not a second-device test. Homebrew `libomp` is required for LightGBM. |
| Linux | Scientific/API/Web architecture permits local Linux use; dependency pins include Linux-only packages, but a Linux installation has not been acceptance-tested. Prefer x86_64 with Python wheels and OpenMP (`libgomp1` on Debian/Ubuntu). |
| Windows | Native Windows is not supported by these POSIX Make/shell workflows. WSL2 Linux is a possible, unverified path; do not claim native compatibility. |
| Python | CPython **3.11** only; tested **3.11.9**. `.python-version` selects the minor version. `PYTHON=/path/to/python3.11 make install` overrides the executable. |
| Node/npm | Node **24.x**, tested **24.21.0**; npm **11.x**, pinned package-manager reference **11.19.0**. `engine-strict` rejects incompatible versions. |
| Python packages | Exact versions in `requirements/python311.lock`, build tooling in `requirements/bootstrap.lock`. ML versions match the trusted deployment model environment. |
| SQLite | Supplied by Python; tested **3.45.1**. Schema/head consistency is checked read-only. No separate SQLite server. |
| PDF/fonts | Pinned ReportLab and Matplotlib; DejaVu Cyrillic fonts ship inside Matplotlib and are embedded. No system-font installation. Optional Poppler is for visual verification only. |
| Tools | Git, Make, GitHub CLI (`gh`), internet access to GitHub/PyPI/npm and sufficient disk space (allow several GB for two environments, frontend modules, builds and restored runtime). |

On macOS, install prerequisites using your usual trusted installers/package manager;
for Homebrew dependencies: `brew install libomp gh` (optionally `poppler`). Confirm
`python3.11 --version`, `node --version`, `npm --version`, `git --version`, `make --version`.
Do not silently upgrade scientific dependencies to resolve an installation error.

## Private GitHub authentication and source

The repository and release assets require an account granted access to
`Fwor1d/Bean-Feature-Lab`. Authenticate interactively and use the credential manager:

```sh
gh auth login --hostname github.com --web
gh auth setup-git
gh auth status
gh repo view Fwor1d/Bean-Feature-Lab --json isPrivate,visibility
gh release view v1.0.0-rc.1 --repo Fwor1d/Bean-Feature-Lab
gh repo clone Fwor1d/Bean-Feature-Lab BeanFeatureLab-installer
cd BeanFeatureLab-installer
git fetch origin tag v1.0.0-rc.1
git checkout --detach v1.0.0-rc.1
make install-python
```

Never paste personal access tokens into Codex prompts, shell command arguments,
source files or `.env`. Configure access through `gh`/SSH and secure OS credentials.
This bootstrap clone provides the existing P1A CLI; it does not create a scientific DB.

## Download, checksum and safe restore

Run from the installer root. Choose your own **nonexistent** target; its parent must
already exist. The following sibling layout is an example, not a machine-specific path:

```sh
mkdir -p storage/backups/rc-download
gh release download v1.0.0-rc.1 --repo Fwor1d/Bean-Feature-Lab \
  --dir storage/backups/rc-download \
  --pattern 'BeanFeatureLab-v1.0.0-rc.1-runtime-v1.tar.gz*' \
  --pattern distribution.json --pattern DATASET_ATTRIBUTION.md
cd storage/backups/rc-download
shasum -a 256 -c BeanFeatureLab-v1.0.0-rc.1-runtime-v1.tar.gz.sha256
# Linux alternative: sha256sum -c BeanFeatureLab-v1.0.0-rc.1-runtime-v1.tar.gz.sha256
cd ../../..
.venv/bin/beanfeature runtime inspect storage/backups/rc-download/BeanFeatureLab-v1.0.0-rc.1-runtime-v1.tar.gz > storage/backups/rc-inspection.json
.venv/bin/beanfeature runtime verify storage/backups/rc-download/BeanFeatureLab-v1.0.0-rc.1-runtime-v1.tar.gz > storage/backups/rc-verification.json
.venv/bin/beanfeature runtime restore storage/backups/rc-download/BeanFeatureLab-v1.0.0-rc.1-runtime-v1.tar.gz \
  --target-root ../BeanFeatureLab-restored > storage/backups/rc-restoration.json
```

Inspect alone is not payload/scientific verification. Verify/restore reuse the P1A
checks: manifest, payload SHA-256/size, SQLite integrity/schema/foreign keys,
dataset identity, DB/file references, completed artifacts/fold companions and model
checksums. Restore refuses existing targets, including empty directories/symlinks;
there is no force/merge mode. A `.restore-in-progress` marker is not a valid runtime.
Keep the downloaded archive and checksum as independent recovery files.

The archive contains SQLite, official ZIP/ARFF/validation metadata, completed runs,
preserved FAILED partial files, saved analyses, deployment registry/models and
benchmarks. Source/dependencies/secrets/tunnel configuration/caches/logs are excluded.
Historical unavailable measurements/inner indices stay unavailable. The reused
backup's exporter Git provenance can predate the RC: schema/protocol compatibility
and immutable payload identities determine validity, not exporter commit equality.
Last restored heartbeat is historical; it does not imply a live worker.

Dataset attribution: [Dry Bean, UCI 602, CC BY 4.0](../research/DATASET_ATTRIBUTION.md).
Preserve the supplied attribution asset with redistributed backups. Checksums establish
transfer identity; trust the private release/owner before deserializing deployment models.

## Populate the restored root with the same source

Runtime restore creates a runtime-only directory, because Git intentionally excludes
scientific state. Populate it using the **same remote tag**; no local original checkout
or copied virtual environment is used:

```sh
cd ../BeanFeatureLab-restored
git init
git remote add origin https://github.com/Fwor1d/Bean-Feature-Lab.git
git fetch --depth 1 origin tag v1.0.0-rc.1
git checkout --detach v1.0.0-rc.1
git status --short
unset BEANFEATURE_DATABASE_URL
make install
.venv/bin/python -m pip check
.venv/bin/python -c 'import sqlite3; print(sqlite3.sqlite_version)'
.venv/bin/python scripts/verify_scientific_runtime.py
BEANFEATURE_DATABASE_URL='sqlite:///file:storage/sqlite/beanfeature.sqlite?mode=ro&uri=true' .venv/bin/alembic check
.venv/bin/beanfeature classifier predict-example
```

Compare `git rev-parse HEAD` with downloaded `distribution.json`'s `source_commit`.
The validation script checks every completed run plus recorded full-protocol outer
indices and their frozen source using a read-only SQLite URL. For this RC expect
171 completed (170 full-protocol, one smoke), two FAILED historical runs, validated
13,611-row/16-feature UCI data and an active deployment model. These are RC evidence
counts, not constants in scientific logic. `predict-example` performs inference only,
without training, benchmarking or writing model artifacts.

`make setup` creates/migrates a fresh runtime and is intended for development without
restored results. For the downloaded runtime use **`make install` + read-only check**;
do not migrate merely to hide incompatibility. All service commands run from this
recovered root. A DB URL override alone does not relocate dataset/model adapters.

## Local services without Cloudflare

Terminal A, from the restored root (safe read-only scientific API):

```sh
BEANFEATURE_DEMO_READ_ONLY=1 \
BEANFEATURE_DATABASE_URL='sqlite:///file:storage/sqlite/beanfeature.sqlite?mode=ro&uri=true' \
.venv/bin/uvicorn beanfeature_api.main:app --host 127.0.0.1 --port 8000
```

Terminal B, from the same root:

```sh
export BEANFEATURE_INTERNAL_API_BASE_URL=http://127.0.0.1:8000
export NEXT_PUBLIC_API_BASE_URL=/api/backend
make build
cd apps/web
npm run start -- --port 3000
```

Open `http://127.0.0.1:3000`, `/feature-budget`, `/runs`, `/classifier` and `/conference`.
For occupied ports choose an unused API/Web pair, change both frontend variables and
pass the selected ports; do not kill unrelated processes. API CORS defaults cover local
3000; use the same-origin proxy or explicitly set `BEANFEATURE_CORS_ORIGINS` for other
browser origins. `.env.example` documents optional values, but Python commands do not
automatically source it: pass/export variables explicitly. Real `.env` files remain local.

Saved-result browsing, Conference and reporting do not require a worker. If requested,
check the queue is empty, then Terminal C from the restored root: `make worker` with
`BEANFEATURE_DATABASE_URL` unset (worker heartbeat needs a writable restored DB).
Stop each service with Ctrl-C; worker leaves completed evidence unchanged. Do not
run enqueue/reproduce/process-next/classifier train/benchmark during this validation.

Readiness probes: `curl --fail http://127.0.0.1:8000/ready` and
`curl --fail http://127.0.0.1:3000/api/ready`. Scientific state writes return 403 in
the read-only API; bounded real classifier prediction is allowed. Public hostname,
Cloudflare Named Tunnel configuration/credentials and macOS `caffeinate` are not
required for local use. Do not run `make presentation` on the new device until its
own hosting configuration has been deliberately approved.

## Conference and PDF checks

In `/conference`, create a verified snapshot of the available full-protocol cohort,
navigate all eight sections and download PDF on the last step. The default two-hour
snapshot expires explicitly; renew it deliberately. An expired/API-restarted snapshot
cannot silently become another report. Verify that Russian text, tables and figures
are readable in a local PDF viewer without internet.

For direct/API-proxy binary verification, with the local services running:

```sh
.venv/bin/python - <<'PY'
import hashlib, json, urllib.request
from pathlib import Path
api = 'http://127.0.0.1:8000'
web = 'http://127.0.0.1:3000/api/backend'
def read(url):
    return urllib.request.urlopen(url, timeout=180).read()
cohorts = json.loads(read(api + '/api/v1/reports/core/cohorts'))
assert len(cohorts) == 1, 'Select an explicit compatible cohort if several exist'
snapshot = json.loads(read(api + '/api/v1/reports/core/snapshot?cohort_id=' + cohorts[0]['cohort_id']))
path = '/api/v1/reports/core/' + snapshot['snapshot_id'] + '/pdf'
direct, proxied = read(api + path), read(web + path)
assert direct.startswith(b'%PDF-') and direct == proxied
Path('storage/backups/installation-report.pdf').write_bytes(direct)
print(snapshot['evidence_sha256'], len(direct), hashlib.sha256(direct).hexdigest())
PY
```

This compares one snapshot's cached response through both paths; it does **not**
claim byte-identical PDF generation across devices/timestamps. Optional PDF inspection:
`pdftoppm -f 1 -singlefile -png storage/backups/installation-report.pdf /tmp/bfl-report`.

## Quality gates and development

```sh
make test
make lint
.venv/bin/ruff format --check .
make typecheck
make build
git diff --check
```

Tests use bounded isolated fixtures; they do not rerun the scientific cohort. Create
an owner-requested development branch from the detached tag before continuing work.
Read [CODEX_HANDOFF.md](CODEX_HANDOFF.md), root `AGENTS.md` and authoritative documents.
Keep Git free of runtime/archives/generated reports; keep independent backup copies.

## Troubleshooting and limits

- GitHub 404/auth errors: private access is missing; check `gh auth status` and owner
  permissions. Authenticate outside chat, never paste tokens into source.
- Unsupported Python/Node: install the required major/minor; do not bypass engine
  checks. Missing `python3.11`: supply `PYTHON=/path/to/python3.11`.
- LightGBM OpenMP load error: install the platform OpenMP runtime (`libomp` macOS,
  `libgomp1` Debian/Ubuntu); do not retrain to work around a missing library.
- No compatible wheel/locked version: stop and report platform/dependency details;
  do not silently relax pins or claim Linux/Windows verification.
- Restore target exists: use another nonexistent sibling. Hash/format/schema failure:
  re-download the matching trusted RC assets or report corruption/incompatibility.
- API empty/model unavailable: confirm current directory and DB override; source
  alone is not restored runtime. Never fabricate results or regenerate the model.
- PDF fonts unavailable: repair the pinned Matplotlib wheel. Fonts come from that
  package, not incidental macOS fonts. Snapshot expiry requires explicit renewal.
- A fresh dataset/seed without a trusted frozen outer manifest cannot start a
  full-protocol experiment. Historical missing inner indices/rank distributions and
  memory measurements remain unavailable; external validation remains out of scope.
- PyPI/npm access remains necessary to install dependencies; the RC is an independent
  scientific-state distribution, not an offline OS/package mirror. Future compatible
  device checks can require platform wheels/system libraries.
- Local availability depends on the new machine staying on. This installation neither
  migrates public hosting nor reuses the original Mac's hostname, credentials or DNS.
- RC pins Next.js/eslint-config-next 16.3.8, sharp 0.35.5 and source-map-js 1.2.2
  after npm advisory checks; `npm audit --omit=dev` reported zero advisories at
  distribution validation. Full audit retains five high entries in the dev-only
  ESLint → fast-glob → micromatch → braces chain (GHSA-vfj7-8cjw-p6xm).
  Braces has no compatible patched release at this checkpoint. Do not feed untrusted
  patterns to development tooling or run `npm audit fix --force` (its proposed
  Next/ESLint downgrade is incompatible). Recheck advisories before future hosting.
