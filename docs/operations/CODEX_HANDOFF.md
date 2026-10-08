# Codex handoff

Start by reading root `AGENTS.md`. The repository is the source of truth; prior
chat history is unnecessary. BeanFeature Lab studies the effect of **original
Dry Bean morphological feature count** on multiclass classification.

## Authoritative sources

- `PRODUCT.md`: intended product and Core/Extended boundaries.
- `DESIGN.md`: Instrument Workstation, Russian UI, MUI/Plotly/Tabler stack.
- `docs/research/EXPERIMENT_PROTOCOL.md`: frozen scientific method.
- `docs/architecture/ARCHITECTURE.md`: dependency and persistence boundaries.
- `docs/operations/NEW_DEVICE_SETUP.md`: private RC download, installation,
  checksum, isolated restore and local validation.
- `docs/operations/LOCAL_WORKFLOW.md`: CLI, recovery, reports and Mac presentation.
- Release and independent review records in `docs/operations/`; treat historical
  counts/checkpoint results as context and verify the actual checkout/runtime.

## Implementation map

`packages/research` contains scientific pipelines, nested CV and corrected paired
statistics. `packages/application` contains shared use cases, reporting snapshots
and ports. `packages/infrastructure` implements SQLite, official dataset storage,
immutable artifacts, deployment models, runtime packages and PDF rendering.
`apps/api` is thin FastAPI; `apps/web` is Next.js/TypeScript; `apps/worker` executes
the scientific queue; `tools/cli` uses the same application layer.

SQLite metadata lives in `storage/sqlite/beanfeature.sqlite`; datasets in `data/`;
scientific results in `artifacts/runs/`; deployment registry/models in
`artifacts/models/`. These are **not in Git**. A source clone without the private
runtime asset cannot recreate saved evidence. There is no global runtime-root
environment variable. Run services from the recovered checkout root.

## Scientific rules

Official UCI 602 ARFF names remain literal. Core uses outer repeated stratified
5×3 CV and inner shuffled stratified 4-fold CV. All learned preprocessing belongs
inside training folds. Future full-protocol execution consumes the verified
recorded outer manifest from the earliest compatible completed run; missing,
corrupt or incompatible evidence fails before training. It must not regenerate
splits or fall back to another source after a selected-source verification failure.

Sufficient-k is same-model 16-original-feature baseline, fixed absolute Macro-F1
loss margin 0.01, one-sided Nadeau–Bengio correction and Bonferroni 0.05/15.
Formal decisions require complete paired families and identical frozen splits.
PCA dimensions do not reduce physical measurements. Classifier deployment refit
is for inference, not a new quality estimate. Conference and PDF share one verified
snapshot; expiration requires explicit renewal, never silent evidence substitution.

Never edit completed artifacts, replace null evidence with zero, reconstruct missing
historical inner indices/memory/rank distributions, change the frozen margin, or
run experiments to recover already-recorded results. Failed and smoke runs retain
their honest status. New research requires an explicitly scoped protocol/task.

## Receiving-device workflow

Follow `NEW_DEVICE_SETUP.md` exactly: authenticate GitHub outside chat, clone the
RC installer, `make install-python`, download/checksum/verify the private asset,
restore into a nonexistent root, fetch the same tag into that root and `make install`.
Do not run migrations before restore or merge runtime directories manually.

Run `scripts/verify_scientific_runtime.py` with `.venv/bin/python`, read-only Alembic
check, classifier `predict-example`, local API/Web, Conference and PDF smoke checks.
Use Ctrl-C in each owned local service terminal. Worker is optional for browsing
saved results and writes only operational heartbeat while the queue is empty.
Do not enqueue, reproduce, train or benchmark during installation validation.

Quality gates: `make test`, `make lint`, `.venv/bin/ruff format --check .`,
`make typecheck`, `make build`, read-only Alembic, `git diff --check`.
Read Git status/branch before edits; create a development branch from the detached
RC when asked to continue. Do not rewrite scientific history.

## Completed scope and boundaries

Core, runtime backup/restore, local Mac presentation lifecycle, classifier,
scientific exploration/provenance/exports, eight-section Conference and scientific
PDF are implemented. External validation, Extended selectors, calibration/Pareto
research and historical unavailable measurements remain explicit limitations.
Mac public hosting depends on power/network and local Cloudflare credentials.
Linux/native Windows are not certified by the same-Mac distribution test.

Owner approval is required for merges, stable release/tag publication, changing
visibility/DNS/hosting, destructive runtime operations, credential handling beyond
normal secure tools, or newly scoped scientific computation. Local read-only checks
and routine reversible fixes within an authorized task can proceed. Project-local
Impeccable skills are for meaningful UI work; do not invoke them for installation
or backend-only work. Never paste tokens into prompts or commit credentials.
