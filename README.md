# BeanFeature Lab

BeanFeature Lab is a local research workbench for measuring how the number of original Dry Bean morphological features affects multiclass classification. The scientific engine runs outside HTTP requests; the Instrument Workstation UI reads real saved results through typed API contracts.

## Architecture

`apps/web` is the Next.js frontend; `apps/api` exposes typed FastAPI contracts; `apps/worker` processes one queued scientific run at a time. `tools/cli` and the worker use the same `packages/application` use cases. `packages/research` owns leakage-safe scikit-learn pipelines and nested CV, while `packages/infrastructure` owns official UCI acquisition, SQLite and hash-verified artifact storage. See [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) and [EXPERIMENT_PROTOCOL.md](docs/research/EXPERIMENT_PROTOCOL.md).

## Local setup

- macOS Apple Silicon, Node.js 24 LTS, Python 3.11. LightGBM on macOS requires Homebrew `libomp`.
- `make setup` creates project-local `.venv`, installs Python/frontend dependencies and applies migrations. It does not install into the global Python environment.
- `make migrate` applies subsequent Alembic migrations. Defaults are SQLite at `storage/sqlite/beanfeature.sqlite`, API at `127.0.0.1:8000`, and web at `127.0.0.1:3000`. Optional overrides are described in `.env.example`; do not commit a real `.env`.
- `make api`, `make worker`, and `make web` run in separate terminals. `make test`, `make lint`, `make format`, `make typecheck`, and `make build` cover the developer workflow.

For a hosted local session, run **`make presentation`** from the repository root. It applies migrations and starts FastAPI, one local worker and production Next.js; the configured macOS Cloudflare Named Tunnel serves [beanfeature.fwor1d.ru](https://beanfeature.fwor1d.ru) and `api.fwor1d.ru`. Browser requests use the public API, while Next.js server-side requests use the local API. The Mac must remain on and connected to the internet. **`make presentation-quick`** is the emergency Quick Tunnel fallback. Only one mode can use ports 3000/8000 at a time. Public mode permits reads and the bounded, side-effect-free classifier prediction POST; experiment creation, enqueue, cancel and other writes return HTTP 403. Local CLI and worker remain unrestricted. Ctrl+C stops only app processes launched by the command. Cloudflare credentials and secrets must never enter the repository or UI logs.

## Reproducible scientific execution

Only the official UCI Machine Learning Repository Dry Bean Dataset (ID 602) is accepted. Download and validate it from the repository root:

```sh
.venv/bin/beanfeature dataset fetch --accept-official-schema
.venv/bin/beanfeature dataset validate --accept-official-schema
```

The acknowledgement records literal names from the official ARFF: `DERMASON`, `AspectRation`, and `roundness`; they differ from some prose in `PRODUCT.md` but are never silently renamed. Validation checks the pinned official ZIP and ARFF SHA-256 values, 13,611 rows, 16 numeric predictors, seven classes, no missing/non-finite values, exact attribute order, and target separation. The raw archive/ARFF and processed manifest live under `data/`; none is committed.

Create a short **integration smoke** run (two outer folds, two inner folds; not a final scientific estimate):

```sh
.venv/bin/beanfeature experiments create "LR MI smoke k=4" --model logistic_regression --selector mutual_information --k-original-features 4 --smoke
.venv/bin/beanfeature runs create EXPERIMENT_ID
.venv/bin/beanfeature runs process-next
.venv/bin/beanfeature runs show RUN_ID
.venv/bin/beanfeature runs result RUN_ID
```

Omit `--smoke` for the approved 5×3 repeated-stratified outer / 4-fold stratified inner protocol. The same seed and dataset yield identical outer split identifiers across comparable conditions. `beanfeature-worker` consumes queued runs sequentially and supports clean shutdown; an interrupted running run becomes `FAILED` and is retried only as a new run. To inspect or idempotently enqueue the 86-condition Core MI matrix:

```sh
.venv/bin/beanfeature core enqueue-mi
.venv/bin/beanfeature core enqueue-mi --confirm-compute
```

The predeclared ANOVA/RFE/tree/L1/PCA matrix is also dry-run by default and can be limited to a repeatable branch:

```sh
.venv/bin/beanfeature core enqueue-comparators
.venv/bin/beanfeature core enqueue-comparators --branch rfe --confirm-compute
```

No expensive matrix is launched without `--confirm-compute`. Completed or active conditions are not duplicated; failed conditions receive a new run ID on an explicit retry.

Each completed run persists fold-level predictions, confusion matrices, selected original features or PCA metadata, timings, and split identifiers in `artifacts/runs/RUN-******/result.json`; SQLite stores status, configuration, summary, hashes, and artifact reference. New, failed and cancelled runs have no scientific metrics. The API provides `/api/v1/runs/{id}/summary`, `/detail`, `/folds`, `/stability`, `/api/v1/datasets/{id}/manifest`, and `/api/v1/feature-budget/series` in addition to foundation endpoints; `/docs` lists all routes. The UI has real Feature Budget points, a runs registry and detail, dataset/provenance, paired comparison, and experiment configuration/queueing. It never fills missing points.

For two completed, matched full-protocol runs, `.venv/bin/beanfeature runs compare COMPACT_RUN_ID BASELINE_RUN_ID` saves a separate hash-identified artifact with the 15 paired fold losses. The baseline must be the same model on all 16 original features without a selector. Formal sufficient-k analysis is predeclared as a one-sided Nadeau–Bengio corrected repeated-CV interval with Bonferroni `0.05/15` and margin `0.01`:

```sh
.venv/bin/beanfeature core sufficiency
.venv/bin/beanfeature core sufficiency --model svm_rbf --persist
```

Verify, reproduce without overwriting, and export a completed run:

```sh
.venv/bin/beanfeature runs verify RUN-000003
.venv/bin/beanfeature runs reproduce RUN-000003
.venv/bin/beanfeature runs export RUN-000003 --kind folds.csv
.venv/bin/beanfeature runs export RUN-000003 --kind selected-features.csv
.venv/bin/beanfeature runs export RUN-000003 --kind summary.md
```

`reproduce` first verifies the immutable artifact, dataset hash, protocol and fold completeness, then creates a new queued run. It never modifies the source run.

## Deployment classifier

The active classifier is a versioned deployment artifact refitted on all validated UCI 602 rows from the verified `RUN-000003` Logistic Regression configuration. This refit is for inference and is not an independent quality estimate; the nested-CV metrics remain attached to the scientific run.

```sh
.venv/bin/beanfeature classifier train
.venv/bin/beanfeature classifier predict-example
.venv/bin/beanfeature classifier benchmark
```

`predict-example` uses one real UCI row and reports its actual class only after prediction; it is a demo object, not a new metric. The API requires all 16 finite canonical fields and returns real `predict_proba` probabilities. Logistic Regression responses additionally contain a signed local logit decomposition, explicitly separated from causal or global importance.

## Scientific integrity boundary

Scaling, selection/PCA, hyperparameter search and fitting occur inside the relevant CV training folds. PCA components are never counted as physically measured original features. L1 is a variable-sparsity path and stores the observed non-zero feature count per fold instead of pretending to be fixed-k. Macro-F1, accuracy, recall, confusion matrices and optional multiclass ROC AUC come from real outer-test predictions only; unavailable metrics remain `null`. Latency covers the full fitted pipeline after warm-up. New worker runs record sampled process-tree RSS with baseline, incremental peak, interval and hardware profile; older artifacts remain `NOT_CALCULATED` and are not rewritten. Corrected sufficient-k decisions are derived only from identical outer folds. No UI curve is interpolated and no maximum across outer-CV curves is called a universally “best model” without a separate selection procedure.

## Product routes

- `/` — project question, validated dataset and real run availability.
- `/feature-budget` — real multi-model MI curves, comparator control points, separate PCA representation, baselines and corrected sufficient-k decisions.
- `/experiments` — compatibility-checked configurations, compute estimate and explicit enqueue confirmation.
- `/runs` and `/runs/{id}` — execution registry and reproducibility report with fold diagnostics and exports.
- `/features` — canonical features, data quality, selection frequency/stability and correlation context.
- `/compare` — formal compact-vs-baseline sufficiency and a separate descriptive A-vs-B view on identical outer folds.
- `/classifier` — active deployment model, UCI examples, probabilities and session-only history.

Runtime datasets, SQLite state, models and scientific artifacts are intentionally ignored by Git. Versioned protocol/configuration files and migrations are committed; reported numbers must remain traceable to verified runtime artifacts.
