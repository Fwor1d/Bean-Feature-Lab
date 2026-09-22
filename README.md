# BeanFeature Lab

BeanFeature Lab is a local research workbench for measuring how the number of original Dry Bean morphological features affects multiclass classification. The scientific engine runs outside HTTP requests; the Instrument Workstation UI reads real saved results through typed API contracts.

## Architecture

`apps/web` is the Next.js frontend; `apps/api` exposes typed FastAPI contracts; `apps/worker` processes one queued scientific run at a time. `tools/cli` and the worker use the same `packages/application` use cases. `packages/research` owns leakage-safe scikit-learn pipelines and nested CV, while `packages/infrastructure` owns official UCI acquisition, SQLite and hash-verified artifact storage. See [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) and [EXPERIMENT_PROTOCOL.md](docs/research/EXPERIMENT_PROTOCOL.md).

## Local setup

- macOS Apple Silicon, Node.js 24 LTS, Python 3.11. LightGBM on macOS requires Homebrew `libomp`.
- `make setup` creates project-local `.venv`, installs Python/frontend dependencies and applies migrations. It does not install into the global Python environment.
- `make migrate` applies subsequent Alembic migrations. Defaults are SQLite at `storage/sqlite/beanfeature.sqlite`, API at `127.0.0.1:8000`, and web at `127.0.0.1:3000`. Optional overrides are described in `.env.example`; do not commit a real `.env`.
- `make api`, `make worker`, and `make web` run in separate terminals. `make test`, `make lint`, `make format`, `make typecheck`, and `make build` cover the developer workflow.

For a normal live demonstration, run **`make presentation`** from the repository root. It applies migrations and starts FastAPI, one local worker and production Next.js; the existing macOS Cloudflare Named Tunnel serves [beanfeature.fwor1d.ru](https://beanfeature.fwor1d.ru) and `api.fwor1d.ru`. Browser requests use the public API, while Next.js server-side requests use the local API. The Mac must remain on and connected to the internet. The command reuses a current production build when its inputs and public API URL match. If DNS is not ready, the local application still starts with a warning. For today's emergency fallback, **`make presentation-quick`** keeps the previous two temporary `trycloudflare.com` tunnels and same-origin browser proxy. Only one mode can use ports 3000/8000 at a time. Both public modes are read-only (write requests return HTTP 403); local CLI and worker remain unrestricted. Ctrl+C stops app processes launched by the command, not the system Cloudflare service. Do not put secrets or private datasets into the demo.

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

Omit `--smoke` for the approved 5×3 repeated-stratified outer / 4-fold stratified inner protocol. The same seed and dataset yield identical outer split identifiers across comparable conditions. `beanfeature-worker` consumes queued runs sequentially and supports clean shutdown; an interrupted running run becomes `FAILED` on restart and can be reproduced as a new run. To enqueue the entire 86-condition Core MI matrix, first inspect the compute budget with `.venv/bin/beanfeature core enqueue-mi`; an explicit `--confirm-compute` is required to enqueue it. No expensive matrix is launched automatically.

Each completed run persists fold-level predictions, confusion matrices, selected original features or PCA metadata, timings, and split identifiers in `artifacts/runs/RUN-******/result.json`; SQLite stores status, configuration, summary, hashes, and artifact reference. New, failed and cancelled runs have no scientific metrics. The API provides `/api/v1/runs/{id}/summary`, `/detail`, `/folds`, `/stability`, `/api/v1/datasets/{id}/manifest`, and `/api/v1/feature-budget/series` in addition to foundation endpoints; `/docs` lists all routes. The UI has real Feature Budget points, a runs registry and detail, dataset/provenance, paired comparison, and experiment configuration/queueing. It never fills missing points.

For two completed, matched full-protocol runs, `.venv/bin/beanfeature runs compare COMPACT_RUN_ID BASELINE_RUN_ID` saves a separate hash-identified artifact with the 15 paired fold losses. The baseline must be the same model on all 16 original features without a selector. `GET /api/v1/runs/{id}/paired-comparison/{baseline_id}` computes the same read-only comparison; neither path declares a sufficient `k`.

## Scientific integrity boundary

Scaling, selection/PCA, hyperparameter search and fitting occur inside the relevant CV training folds. PCA components are never counted as physically measured original features. Macro-F1, accuracy, recall, confusion matrices and optional multiclass ROC AUC come from real outer-test predictions only; unavailable metrics remain `null`. Resource timing measures the full pipeline; peak memory is explicitly not calculated. The predeclared sufficient-k margin is 0.01 Macro-F1, but no sufficient-k claim is made until an uncertainty-interval method appropriate for dependent repeated-CV folds is approved. Final classifier artifact, Extended selectors, Pareto analysis and report generation remain later stages.
