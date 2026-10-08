# Independent Release 1.0 verification

Audit baseline: `7953dfb`, `build/core-completion`, 2026-10-08. This is a focused
challenge of the completed candidate, not a new research or product phase. Four independent
reviewers initially worked read-only; only the coordinator changed source. Scientific and
security reviews ran first, followed by UX and operations within the available concurrency.
The UX reviewer supplied confirmed findings but reached an execution usage limit before
writing its final report; the coordinator completed the affected browser checks. That
interruption is a coverage limitation, not an independent fourth final approval.

## Findings and disposition

All entries below have **Confirmed** confidence. No Critical finding or current incorrect
scientific metric was demonstrated. File locations refer to the corrected checkout; the
functions named also identify the original reviewed paths.

### Agent A — Scientific integrity and reproducibility

**A-1 · Low · future split execution contract.**
`packages/research/src/beanfeature_research/engine.py:342` (`run_nested_cv`) and
`packages/application/src/beanfeature_application/service.py` (`process_next_run`) regenerate
outer splits rather than consuming one previously stored frozen manifest. The protocol expects
recorded indices to be reused. Inspect those calls: no manifest is supplied to the engine.
The independent artifact scan found all 170 current full-protocol runs have the same actual
outer split set `2d534d4c01ed2a011d75d9c04674a3bf7933b4d8772bba030cdd7979b2b8e462`,
with hashes matching the recorded, disjoint train/test indices. Comparison guards reject
mismatched splits. Current saved-evidence conclusions remain valid; regeneration under a
changed splitter implementation is a future execution risk. Accepted at this release scope;
the minimal future correction is passing validated saved indices to the engine, without
rewriting completed artifacts. No new runs were authorized or needed here.

**A-2 · Low · historical inner-partition evidence.**
`engine.py:359`/`:424` save outer indices and inner seed, but not actual inner train/validation
indices. All 171 completed artifacts were scanned; no separate inner manifest was present.
The expected immutable inner-index record is unavailable. Saved seeds, outer indices and
software versions provide a regeneration recipe in the recorded environment, not independent
proof of the historical inner arrays. Documented limitation; future runs should persist the
partitions actually supplied to GridSearchCV. Historical arrays must not be reconstructed
and presented as recorded measurements.

**A-3 · Low · overview verification semantics.**
`service.py` (`feature_budget_series`, `feature_selection_series`) reads COMPLETED SQLite
summaries without verifying every artifact at query time. With an in-memory rejecting artifact
adapter, the verifier/formal analysis rejected evidence but overview series still returned
160/128 recorded points. No source file was corrupted. Expected behavior is a clear distinction
between recorded summaries and a verified evidence snapshot. Corrected the budget/features
source labels and architecture documentation. The overview queries retain their existing cost;
run verification, formal comparisons, Conference Mode and PDF retain the existing verifier.

Independent A validation: **171/171 completed runs verified**, five **15/15** sufficient-k
families, minima **14/14/14/14/15**, and 22 focused tests passed. Nadeau–Bengio correction,
Bonferroni `0.05/15`, margin `0.01`, deterministic earliest-completed selection, smoke/FAILED
exclusion and PCA/original-budget semantics were not changed. No leakage or inconsistent
current UI/report conclusion was demonstrated.

### Agent B — Security and API robustness

**B-1 · Medium · classifier invalid numeric input.**
`service.py:195` (`predict_classifier`): `Area=10**309` in an otherwise valid, 637-byte JSON
request raised OverflowError in numeric validation, producing plain HTTP 500 without CORS.
Expected is the structured 422 input error. Independently reproduced with the real deployment
model in a read-only TestClient. Guarded float conversion now rejects unrepresentable and
non-finite values; boolean/type rejection is preserved. Impact was a repeatable error-contract
bypass, not scientific corruption. Regression plus actual running API confirmed 422/CORS.

**B-2 · Low · out-of-range database IDs.**
`apps/api/src/beanfeature_api/main.py:57` and DB-backed route signatures: run/experiment ID
`9223372036854775808` reached SQLite and raised OverflowError/500. Expected is validation
before binding. A shared positive signed-64-bit Path annotation now covers dataset, experiment,
run and comparison IDs. Six focused cases and real API/proxy GETs return structured 422.

**B-3 · Medium · stored failure-path disclosure.**
`apps/api/src/beanfeature_api/schemas.py:205` (`RunResponse.from_domain`): raw persisted
exception text reached public list/detail responses. A real temporary FileNotFoundError
through the application failure path exposed its absolute path in a safe isolated fixture.
Current historical FAILED records did not contain that leak. Expected is a safe public message
with detailed diagnostics retained locally. DTO serialization now returns a generic failure or
cancellation message; DB/error artifacts stay unchanged. Regression checks both public reads
and the unchanged original diagnostic. This closes a concrete future failure-path disclosure.

B also checked public write guards, actual/chunked body limits, snapshot leases/coalescing/TTL,
PDF concurrency/cache bounds, binary headers, archive/path rejection and CORS. Its 40 targeted
Python and seven proxy tests passed; no additional actionable security finding was established.
There was no disruptive public load or penetration test.

### Agent C — UX, accessibility and end-to-end behavior

**C-1 · Medium · substituted feature condition.**
`apps/web/src/app/features/page.tsx:26` and `FeatureExplorerControls.tsx`: explicit
`?model=mlp&selector=mutual_information&k=4` silently displayed RF/ANOVA/k=1, and changing
RF/ANOVA to LR retained invalid dependent filters while displaying RF. Both were observed in
the real baseline browser. Expected is exact explicit condition matching or an unavailable
state. `lib/view-selection.ts:6` now honors all supplied filters; changing model/method clears
dependent choices. The unavailable view shows no substituted frequencies or heatmap and offers
reset. Real LR change, browser Back and unavailable/reset workflows passed after correction.

**C-2 · Medium · dark-context focused label contrast.**
`apps/web/src/app/globals.css:29`: focused model label used blue `#2e6bd3` on `#252d35`,
only **2.78:1** for small text. Expected is legible focus text/border. Scoped focused label
and outline now use `#9dc0ff`: actual browser computed contrast **7.58:1**; Escape returns
focus to the combobox. No design system or unrelated layout was changed.

**C-3 · Low · invalid fold substitution.**
`apps/web/src/app/runs/[id]/page.tsx:38`: `?fold=r99-f99` silently showed r01-f01 diagnostics.
Expected is explicit unavailable selection. `lib/view-selection.ts:28` defaults only when no
fold was requested. Real invalid selection now shows an alert without fold diagnostics;
the existing r02-f01 link restores the correct matrix and metrics.

**Coordinator R-1 · Low · numeric aliases in a descriptive pair.**
`apps/web/src/app/compare/page.tsx:57`: string comparison allowed `left=03&right=3` to refer
to one ID and substitute a different right run. Source branches establish the reproduction;
the numeric identity guard and regression now reject aliases. The real browser shows a recovery
message without a substituted descriptive result.

C examined representative workstation, classifier, FAILED and eight-section conference states.
The coordinator completed mobile drawer/Escape focus, keyboard frequency-table disclosure,
invalid filters/folds/pairs and source labeling checks. Representative affected layouts at
390×844, 768×1024, 1280×900 and 1920×1080 had no page-width overflow. Full WCAG or complete
screen-reader/browser certification is not inferred from this bounded review.

### Agent D — Release, reliability and portability

**D-1 · High · permanently lost worker heartbeat after a transient SQLite lock.**
`apps/worker/src/beanfeature_worker/main.py:17` (`_heartbeat_loop`); supporting existing
SQLite heartbeat commit and 20-second supervisor freshness check. An uncaught busy commit
killed the heartbeat thread while the process remained alive; the supervisor subsequently
stopped the stack. It occurred during the real audit startup without injected failure; the
original lock holder is unknown. D and the coordinator separately reproduced it on a real idle
worker with an empty temporary DB and an 11-second read transaction: after release the old
worker stayed alive but never recovered its heartbeat. Expected is stop-aware retry of a
recoverable lock, with sustained failure still becoming stale.

The heartbeat loop now catches only SQLite BUSY/LOCKED OperationalError codes, logs a sanitized
warning and retries at the existing five-second interval using the adapter's fresh transaction.
No fabricated heartbeat, queue change, migration or WAL conversion was introduced. Repeating
the real isolated-worker procedure recovered the timestamp about 15 seconds after the original
heartbeat, within the existing stale deadline. Regression exercises a real SQLite lock and
ensures a non-lock database error is not hidden. Persistent failure remains supervised.

D independently passed 22 isolated lifecycle and 38 runtime/PDF tests. It reverified the
existing P1A archive in the compatible fresh Python environment: 2,754 payload files,
171 completed runs verified, two FAILED retained, deployment references valid. The archive
was not overwritten or regenerated. Local port-denial errors in an initial sandbox attempt
disappeared with approved isolated-port access; they were environmental failures, not defects.

## Consolidated validation

- `make test`: **155 Python tests and 38 frontend tests passed**. New coverage is eight API,
  two heartbeat and six selection/navigation cases. Two existing dependency deprecation warnings
  remain. Reviewer subsets are not additional tests to add to these counts.
- `make lint`, Ruff format check (114 Python files), `make typecheck`, `make build` and
  read-only current-DB `alembic check` passed. No migration was run. Git checks are performed
  after final documentation/staging as well.
- Real invalid classifier integer: 422 with allowed-origin CORS; out-of-range run ID: 422
  through API and Next proxy. Normal canonical example inference returned SEKER/200.
  Scientific create/enqueue/cancel against the local public-mode API returned 403/403/403.
- New PDF: **21 pages**, no empty/duplicate extracted pages, three embedded DejaVu fonts,
  readable extracted Cyrillic; rendered pages 4 and 6 inspected for curves/statistics/table
  layout, with no observed clipping or overlap. This is a targeted follow-up to the original
  all-page inspection; reporting/rendering logic did not change.
- One snapshot's PDF was byte-identical through direct API, local Next proxy, public API and
  public proxy (350,255 bytes; SHA-256 `74e784a619319d8831e4e92f409e2c407092d45cdec5f7f5e102d16e9f10363f`).
  Evidence SHA-256 stayed `29782cc44d7391ec38fd73cf53d2a150013db9d1eedc91804c34d4b8de0eb238`.
  Byte identity here concerns the same cached PDF, not every future generation.
- Corrected real presentation started via `make presentation`: API/Web ready, worker online,
  sleep active, external Named Tunnel and both public probes ready. Repeated start reused the
  same session without duplicates. Normal stop and repeated stop succeeded: every saved owned
  process identity was gone, sleep inactive, worker intentionally stopped. The external tunnel
  remained untouched; public HTTP 502 with the origins intentionally stopped is expected.
- All non-heartbeat scientific SQLite rows and **2,757 source dataset/artifact file hashes**
  matched the inventory taken before this audit exactly. Counts remained **171 COMPLETED / 2
  FAILED**, with no queued/running run. Only legitimate operational heartbeat changed. No model
  training, scientific reconstruction, completed-artifact write or new large backup occurred.
- The coordinator also navigated all eight Conference sections by keyboard, verified heading
  focus/progress, and observed successful PDF download feedback for that same evidence hash.
  Browser navigation/filter recovery and the rendered affected desktop/mobile screens were
  inspected; temporary browser tabs and viewport overrides were cleaned up.

## Accepted limits and release judgment

A-1/A-2 describe the bounded historical/future execution reproducibility limits above;
A-3's live-summary integrity limitation is now explicitly visible. They do not invalidate
the verified frozen cohort or authorize future incompatible comparisons. No reviewer finding
was discarded solely because another reviewer disagreed; severity and disposition follow
actual impact and reproduction. No additional important defect was demonstrated after fixes.

Existing Mac powered/open/online dependency, no HA guarantee, externally managed tunnel,
trusted compatible model/archive dependencies, untagged PDF and incomplete formal accessibility
certification remain accepted limitations. No optional Extended research or external validation
was converted into a software blocker. The owner still needs an independent off-device backup,
actual conference-browser/projector rehearsal and an explicit merge/tag/publication decision.

Disposition: **SHIP WITH DOCUMENTED LIMITATIONS**. No confirmed release-blocking defect remains
within the saved-evidence Release 1.0 scope. Final diff/staged hygiene checks pass; the correction
checkpoint is identified by Git rather than embedding its own hash here. No merge, tag,
publication or new scientific run is part of this verification.
