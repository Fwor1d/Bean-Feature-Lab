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
