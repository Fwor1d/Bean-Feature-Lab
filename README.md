# BeanFeature Lab

BeanFeature Lab is a local research workbench for studying how the number of original Dry Bean morphological features affects multiclass classification. Stage 4A provides a working application foundation, **not scientific results**. The sole planned scientific source for the next stage is UCI Dry Bean Dataset, ID 602; it has not been downloaded here.

## Architecture

`apps/web` is the Next.js App Router interface. `apps/api` is a thin FastAPI adapter. `apps/worker` is one local worker that maintains a heartbeat and sees queued jobs, but deliberately does not execute ML. `tools/cli` uses the same application service as API and worker. `packages/research` owns independent scientific contracts; `packages/application` owns use cases and repository ports; `packages/infrastructure` implements SQLite, safe artifact paths and environment metadata. See [ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) and [EXPERIMENT_PROTOCOL.md](docs/research/EXPERIMENT_PROTOCOL.md).

## Prerequisites and setup

- macOS Apple Silicon, Node.js 24 LTS with npm, Python 3.11.
- From the repository root: `make setup` creates `.venv`, installs only foundation Python packages and frontend packages, then applies the Alembic migration. No global Python installation is used.
- Defaults work without a `.env` file: API on `127.0.0.1:8000`, web on `127.0.0.1:3000`, SQLite at `storage/sqlite/beanfeature.sqlite`. Root `.env.example` and `apps/web/.env.example` document optional environment variables. Export them in the shell when overriding defaults. Never commit a real `.env`.

Use separate terminals:

```sh
make api
make worker
make web
```

Open `http://127.0.0.1:3000/feature-budget`. The frontend reads the real FastAPI metadata and collections. It shows an explicit unavailable state if the API cannot be reached.

Other developer commands: `make test`, `make lint`, `make format`, `make typecheck`, `make build`, `make migrate`. Run `.venv/bin/beanfeature system info`, `.venv/bin/beanfeature experiments list`, `.venv/bin/beanfeature runs list`, or `--help` for CLI operations. To inspect API routes, open `http://127.0.0.1:8000/docs`.

## Current behavior

- Routes: `/`, `/feature-budget`, `/experiments`, `/runs`, `/features`, `/compare`, `/classifier`, `/settings`. The Feature Budget figure is a real empty Plotly figure; no curve or scientific metric is fabricated. The experiments screen can save a configuration, while dataset validation and ML execution are absent.
- API: `GET /health`, `/api/v1/system/info`, `/api/v1/projects`, `/api/v1/datasets`, `/api/v1/experiments`, `/api/v1/runs`; experiment/run detail, experiment creation, run queueing and cancellation are also available. Errors use `{ "error": { "code", "message" } }`.
- SQLite migration creates `experiments`, `runs`, and `worker_heartbeat`. An internal autoincrement key yields atomic display IDs such as `RUN-000001`; no `MAX(id)+1` sequence. New runs remain `QUEUED` and have `metrics: null`, `result_state: NOT_CALCULATED`. The worker never marks them complete.
- `data/raw`, `data/processed`, `storage/sqlite`, `artifacts/runs`, `artifacts/models` are separate runtime locations. Runtime files are ignored by Git.

## Scientific integrity boundary

The current code does **not** download or preprocess the UCI dataset, train models, select features, run nested CV, calculate Macro-F1, report latency, or register classifier models. `k_original_features` and `n_components` are distinct contracts. PCA components cannot be reported as the number of physical measurements. Run execution state is distinct from scientific result state. The scientific protocol and approved Instrument Workstation UI are defined in [PRODUCT.md](PRODUCT.md) and [DESIGN.md](DESIGN.md); they must not be inferred from empty UI fields.
