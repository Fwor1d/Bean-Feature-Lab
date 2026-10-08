# Local research and hosting workflow

Run all commands from the repository root. Runtime data, SQLite and scientific/model artifacts are intentionally not in Git; retain these directories when moving the project. `make setup` prepares dependencies and migrations, but does not recreate calculated results.

## Research

1. `beanfeature dataset fetch --accept-official-schema` downloads only official UCI 602. Use `.venv/bin/beanfeature` for every CLI command below.
2. `beanfeature dataset validate --accept-official-schema` verifies the pinned source hash and exact canonical ARFF schema. `beanfeature dataset quality` reports diagnostics without cleaning rows or predictors.
3. `beanfeature core enqueue-mi` and `beanfeature core enqueue-comparators` show matrix availability without enqueuing. Add `--confirm-compute` only when the displayed workload is intended. Comparator branches can be limited with `--branch`.
4. `make worker` processes queued conditions sequentially in isolated measured processes. An interrupted run is retained as failed; restart does not manufacture completion. Explicit retry creates a new run, while completed/active conditions are not duplicated.
5. `beanfeature runs verify RUN-000003` verifies hashes, config, dataset, protocol and folds. `beanfeature runs reproduce RUN-000003` verifies the original and creates a new queued run; it never overwrites the source. Reproduction on different software/hardware is recorded with new provenance and is not a promise of bitwise-identical timing.
6. `beanfeature runs export RUN-000003 --kind folds.csv` exports verified fold results. Other kinds are `result.json`, `config.json`, `selected-features.csv` (when applicable), and `summary.md`. These exports make no sufficient-k claim from a historical null field.
7. `beanfeature core sufficiency` reads the predeclared corrected paired analysis; `--persist` writes separate derived analysis artifacts. Original run results remain immutable.

The frozen scientific specification is [EXPERIMENT_PROTOCOL.md](../research/EXPERIMENT_PROTOCOL.md). Comparison decisions apply only to matching data and split hashes. PCA remains a representation of all 16 measured features, and L1 records varying observed sparsity rather than an invented fixed-k curve.

## Runtime preservation and recovery

P1A preserves the existing layout: `storage/sqlite/beanfeature.sqlite`, `data/raw`,
`data/processed`, `artifacts/runs` and `artifacts/models`. No live-state migration,
new environment variable or presentation-script change is required. A backup is runtime
state, not a source checkout or dependency installation.

Stop scientific writers before backup, including the worker, dataset acquisition,
classifier training/benchmark writes and persisted analysis commands. Read-only API/Web
may remain available. The queue must be empty and no run may be active; wait at least
20 seconds after stopping the worker so its last heartbeat is stale. Backup refuses
active runs/fresh heartbeat and checks source DB/file identities again before publication.
It does not stop processes itself and is not a coordinated live-backup system.

```sh
.venv/bin/beanfeature runtime backup --output storage/backups/runtime-state.tar.gz
.venv/bin/beanfeature runtime inspect storage/backups/runtime-state.tar.gz
.venv/bin/beanfeature runtime verify storage/backups/runtime-state.tar.gz
.venv/bin/beanfeature runtime restore storage/backups/runtime-state.tar.gz \
  --target-root /existing-parent/BeanFeatureLab-recovered
```

Choose a new output filename and an explicit **nonexistent** restore directory whose
parent already exists. Even an existing empty directory or symlink is rejected. There
is no force/overwrite/merge mode. Output must be outside scientific runtime directories;
`storage/backups/` is ignored by Git. Store another copy outside the machine for recovery.
Commands return JSON and nonzero exit status on failure; reports can be redirected to
files under `storage/backups/`.

Without `--source-root`, backup uses the current working directory's file layout and
the existing `BEANFEATURE_DATABASE_URL` setting (or its usual default). The DB must be
an existing local file SQLite URL without URI options. `--source-root /path/to/source`
selects that root's conventional SQLite path and ignores the environment DB override.
The packaged DB always uses the conventional relative path. Persisted absolute or
escaping dataset/artifact references are rejected rather than rewritten.

### Contents and integrity format

The gzip-compressed tar package contains only regular files with relative paths:

- Required: a consistent SQLite Backup API snapshot, official UCI ZIP and ARFF,
  dataset validation manifest, completed results/fold companions, and required DB
  artifact references. SQLite preserves definitions, runs, IDs, events, statuses,
  summaries, timestamps, fingerprints and historical provenance, including the last
  recorded heartbeat (it is not proof of a live worker after restore).
- Optional groups, included when present: failed/partial fold records, recognized
  paired/sufficiency analysis, current and legacy LR deployment pipelines/metadata,
  registry and deployment benchmarks. Once included, every file is mandatory for
  this package's integrity, even if its group was optional at export time.
- `manifest.json`: format version, capture time, exporter Git/software provenance,
  schema/protocol versions, dataset/run identities, logical DB hash/counts, required
  paths, optional-group availability, exclusions and per-file sizes/SHA-256.
- `manifest.sha256`: the SHA-256 of the exact `manifest.json` bytes, followed by a
  newline. The manifest does not contain its own hash. The command also reports the
  archive SHA-256; retain it separately if desired.

The v1 allowlist recognizes official UCI dataset files, run result/fold/error JSON,
paired comparison and Core sufficiency JSON, existing LR deployment versions and their
benchmark files. Unrecognized runtime files are excluded and listed, never silently
treated as scientific results. Secrets/environment files, Cloudflare configuration,
Git/source, dependencies, build output, logs, caches, temporary files and README
scaffolding are excluded. SQLite journal/WAL/SHM files are not copied: their committed
state is represented by the consistent snapshot.

`inspect` validates the manifest checksum and archive structure/inventory; its
`payload_verified=false` explicitly means payload hashes/scientific content were not
verified. `verify` extracts to a temporary location, checks every payload hash/size,
SQLite integrity/foreign keys and database/file relationships, then reuses the existing
dataset loader and completed-run verifier. It also checks fold companions and deployment
checksums/references without executing joblib. Failed/partial results remain failed/partial.

Restore performs the same full verification before exclusively creating the target.
It rejects traversal, absolute paths, duplicate entries, links, special files, extended
tar metadata and unlisted content. V1 limits are 8 MiB for the manifest, 100,000 payload
files and 16 GiB of uncompressed payload. Caught failures clean staging and the newly
created target; an abrupt kill/power loss can leave `.restore-in-progress` and a partial
target. Do not start processes there: keep the original package and restore into another
new directory. No existing runtime directory is replaced.

### Compatible checkout and recovery limits

Use a Python 3.11 checkout supporting the package's Alembic schema and saved scientific
protocols. Unsupported format/schema/protocol is rejected; a different Git commit,
platform or software provenance alone does not invalidate intact saved results.
Exporter provenance is separate from immutable historical run provenance. Checksums
establish integrity relative to the manifest, not archive authenticity or repeatable
timing. Use trusted backups; serialized models still require compatible, trusted
dependencies before inference.

The restored directory contains runtime only. To use it with the unchanged default
workflow, populate **that new directory** with a compatible Git checkout, then install
dependencies. For example, using a trusted local checkout and its compatible ref:

```sh
git -C /existing-parent/BeanFeatureLab-recovered init
git -C /existing-parent/BeanFeatureLab-recovered fetch /path/to/compatible-checkout <compatible-ref>
git -C /existing-parent/BeanFeatureLab-recovered checkout --detach FETCH_HEAD
cd /existing-parent/BeanFeatureLab-recovered
make setup
```

Runtime paths are ignored by that checkout; tracked README scaffolding is restored by
Git. Ensure `BEANFEATURE_DATABASE_URL` is unset or selects this recovered SQLite before
setup or starting processes. Match recorded ML dependency versions when using the
deployment pipeline. Optional `create_container(..., runtime_root=...)` is used only by
isolated verification, not a new API/worker/hosting setting. Backup and restore never
enqueue, rerun, recover or rewrite historical scientific results. Missing historical
measurements and dirty-run source snapshots that were never saved remain unavailable.

## Deployment classifier

`beanfeature classifier train` refits the verified Logistic Regression full-16 baseline configuration on the complete validated dataset and registers a versioned deployment artifact. This is inference training, not an independent quality assessment. It does not change the source run's metrics.

The active registry and metadata live under `artifacts/models/`; they contain model/version, source run/config, dataset/schema/classes, timestamps and artifact hash. Model reads verify the serialized artifact before loading it. Never load untrusted joblib files.

`beanfeature classifier predict-example` uses a real UCI row. Its actual class is display-only and is never part of model input. The browser has finite numeric validation, observed ranges without clipping, seven real probabilities, local LR logit contributions and browser-memory-only history. Confidence is a model probability, not guaranteed truth. Contribution decomposition is neither causal importance nor a probability decomposition.

`beanfeature classifier benchmark` measures deployment latency/RSS in a fresh process and stores a separate engineering artifact. RSS sampling may miss short peaks; historical scientific runs without memory measurements stay not calculated.

## Hosting

`make presentation` uses the existing system Cloudflare Named Tunnel and permanent domains. `make presentation-quick` is the emergency Quick Tunnel mode. Use only one mode at a time. Both start the local API, one worker and production web frontend; Ctrl+C stops those application processes without removing scientific state or stopping the system tunnel.

The Mac must remain awake, online and running the application. A public URL is not a remote server: Cloudflare forwards to the Mac's local ports. Local health is `http://127.0.0.1:8000/health`; public health is `https://api.fwor1d.ru/health`. A transient tunnel-readiness warning during startup should be followed by checking both public domains. Local 200 with public 502 indicates a tunnel/origin/network availability issue, not a need to alter dataset or scientific results.

Public mode permits GET reads and side-effect-free classifier prediction POST, while create/enqueue/cancel and other writes stay blocked with 403. Classifier payloads are bounded at 32 KiB and schema-validated. This is a lightweight local-tool boundary, not a full authentication or production traffic-limiting system. Local trusted CLI writes remain available. Do not expose arbitrary artifact paths, secrets, Cloudflare credentials or tokens.

## Quality gate

Python: `.venv/bin/pytest -q`, `.venv/bin/ruff check .`, `.venv/bin/ruff format --check .`, `.venv/bin/alembic check`.

Frontend, from `apps/web`: `npm test`, `npm run typecheck`, `npm run lint`, `npm run build`. Finish with `git diff --check` and inspect tracked files for runtime state or secrets.
