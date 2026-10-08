# BeanFeature Lab Agent Instructions

## Project goal

BeanFeature Lab is a scientific ML workbench for studying how the number of original Dry Bean morphological features affects multiclass classification quality.

Primary scientific dataset:
- UCI Dry Bean Dataset
- Dataset ID: 602
- 13,611 samples
- 16 numerical original features
- 7 classes

The project must prioritize scientific correctness, reproducibility, and honest reporting over filling the UI with results.

## Canonical data schema

Use the official UCI ARFF schema as canonical.

Do not silently rename canonical raw fields.

Important official spellings include:
- `AspectRation`
- `roundness`
- class `DERMASON`

Human-readable UI aliases are allowed, but canonical dataset, API, experiment, and artifact metadata must preserve official names.

## Scientific integrity

Never:
- invent metrics;
- generate placeholder scientific curves;
- hardcode a best model;
- hardcode an optimal feature count;
- fabricate confusion matrices;
- convert missing scientific values to zero;
- treat incomplete experiments as completed;
- modify existing scientific artifacts to make results look better.

Missing results must remain explicitly:
- not calculated;
- not run;
- partial;
- unavailable.

Do not infer or reconstruct historical measurements that were never recorded unless an explicitly validated reconstruction method is part of the task.

## Cross-validation and leakage

Core scientific evaluation uses:

- outer CV: `RepeatedStratifiedKFold(n_splits=5, n_repeats=3)`
- inner CV: `StratifiedKFold(n_splits=4, shuffle=True)`

All data-dependent preprocessing must be trained only within the appropriate training fold.

This includes:
- scaling;
- feature selection;
- PCA;
- imputation if introduced;
- hyperparameter tuning;
- calibration.

Never fit a selector, scaler, PCA, or other distribution-dependent transform on the full dataset before CV.

Comparable Core conditions must use the same frozen outer split manifest.

## Metrics

Primary metric:
- Macro-F1

Required:
- Accuracy
- per-class recall
- confusion matrix

Diagnostic where applicable:
- multiclass ROC AUC OvR

Resource measurements must be reported separately and honestly.

## Feature budget semantics

Original feature budget and PCA dimensionality are different concepts.

`k_original_features`
means the number of original measurable input features.

`n_components`
means PCA components.

Never present PCA components as a reduction in the number of physical measurements required.

## Sufficient-k

The fixed non-inferiority-style margin is:

`delta = 0.01` absolute Macro-F1 loss relative to the same-model 16-original-feature baseline.

Do not change this margin after seeing results.

Comparisons must be paired on identical outer folds.

Do not use naive `std / sqrt(n)` as if repeated-CV fold scores were independent.

Use the statistical method frozen in `docs/research/EXPERIMENT_PROTOCOL.md`.

If the required statistical method or baseline is unavailable, report sufficient-k as not calculated.

## Core models

Core model families:
- Logistic Regression
- SVM RBF
- Random Forest
- XGBoost
- LightGBM

MLP is a Core 16-feature baseline and may be Extended for full feature-budget curves.

## Core selectors

Core research methods:
- Mutual Information
- ANOVA
- RFE
- L1 Logistic Regression
- tree-based importance
- PCA as a separate dimensionality branch

Extended methods include:
- correlation pruning
- Sequential Feature Selection
- additional exploratory combinations

Do not expand into Extended scope unless the task explicitly requests it.

## Architecture

Keep the scientific core independent of FastAPI and the frontend.

High-level structure:

- `apps/web` - Next.js / TypeScript frontend
- `apps/api` - thin FastAPI adapter
- `apps/worker` - local experiment worker
- `packages/research` - scientific logic
- `packages/application` - application use cases and ports
- `packages/infrastructure` - SQLite, files, artifacts, external adapters
- `tools/cli` - CLI using the same application layer

Do not calculate scientific metrics in the frontend.

Do not execute heavy nested-CV training inside an HTTP request.

CLI, worker, and API should reuse the same application layer.

## Persistence

SQLite stores experiment/run metadata and references.

Scientific datasets and model/result artifacts remain file-based unless architecture documentation is deliberately changed.

Preserve:
- dataset hashes;
- config fingerprints;
- split identities;
- fold records;
- artifact hashes;
- run provenance;
- Git provenance.

Do not rewrite historical completed run artifacts.

Reproduction or reruns must create new run records and artifacts.

Never overwrite an existing completed run during reproduce, verify, export, recovery, or migration workflows.

## Deployment classifier

The classifier deployment model is separate from scientific evaluation.

A deployment model may be trained on all validated data for inference.

Do not describe full-dataset deployment training as an independent quality estimate.

Classifier probabilities must come from the actual model, not synthetic confidence values.

## Public demo security

Public web mode is read-only for scientific state-changing operations.

Public users may:
- read results;
- inspect runs;
- use allowed inference endpoints.

Public users must not be able to:
- create experiments;
- enqueue runs;
- cancel runs;
- modify scientific state.

Local trusted CLI workflows may retain write access.

Never expose:
- Cloudflare tokens;
- secrets;
- arbitrary filesystem paths.

## Frontend design

Follow `DESIGN.md`.

Primary direction:
- Instrument Workstation
- dense scientific workspace
- clear provenance and experiment state
- no generic SaaS dashboard aesthetic

Use:
- MUI Core
- MUI X Data Grid Community
- Plotly
- Tabler Icons

Do not use Lucide.

Avoid:
- glassmorphism;
- decorative agriculture clichés;
- fake KPI cards;
- decorative charts with no analytical value.

Handle explicitly:
- loading;
- empty state;
- partial results;
- failed runs;
- running runs;
- API unavailable;
- not calculated values.

## Design workflow

For substantial frontend or visual work, use the available project-local design / Impeccable skills and follow `DESIGN.md`.

Use the appropriate design audit, critique, and polish workflow after significant UI changes.

Do not invoke design workflows for backend-only, infrastructure-only, or purely scientific tasks unless visual work is actually involved.

## Language

User-facing UI text is Russian.

Common established ML terms may remain in English where clearer.

Code, identifiers, commit messages, technical documentation, and agent task prompts should generally use English unless an existing file clearly uses Russian.

Final user-facing work reports should be concise and in Russian.

## Git

Before significant work:
- inspect `git status`;
- inspect the current branch;
- avoid destructive operations.

Do not:
- amend or rewrite historical scientific commits without explicit instruction;
- commit secrets;
- commit runtime SQLite;
- commit downloaded UCI binaries;
- commit generated scientific artifacts if they are intentionally runtime-only.

Use small checkpoint commits after coherent completed phases.

Do not merge into `main` unless explicitly requested.

## Quality

For normal non-emergency work, run the relevant quality gates before declaring completion.

Python:
- pytest
- ruff check
- ruff format --check

Frontend:
- tests
- typecheck
- lint
- production build

Also:
- `git diff --check`

Prefer repository-defined Makefile/package scripts over manually reconstructing equivalent commands.

Do not skip critical tests merely to report a green result.

## Documentation hierarchy

Before changing scientific behavior, consult:
- `PRODUCT.md`
- `docs/research/EXPERIMENT_PROTOCOL.md`
- `docs/architecture/ARCHITECTURE.md`

Before significant UI work, consult:
- `DESIGN.md`

These documents are authoritative for their respective domains.

Do not duplicate large sections of these documents into task prompts.

## Working style

For large tasks:
1. inspect the existing implementation;
2. preserve already-working behavior;
3. make the smallest coherent architectural change;
4. verify it;
5. commit a checkpoint when the phase is complete.

Do not refactor unrelated working code during a focused task.

Do not stop for minor clarification if the repository and documentation provide enough information to make a safe decision.

Do not repeatedly re-audit already documented stable areas of the repository unless the current task depends on them or evidence suggests that documentation is stale.

At the end of a major task, report concisely in Russian:
- what was completed;
- real runs/results created;
- tests/checks;
- commit SHA;
- remaining blockers;
- recommended next step.
