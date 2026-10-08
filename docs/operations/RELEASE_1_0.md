# Release 1.0 acceptance — 2026-10-08

Decision: **SHIP for the documented local Mac-hosted research/presentation scope**.
The completed Core, P1A recovery, P1B lifecycle, Conference Mode and PDF are included.
This is a release candidate on `build/core-completion`; no merge or public uptime guarantee
is implied. Git holds software and frozen methodology, not the valuable runtime evidence.

## Focused completion audit and fixes

| Category | Finding | Resolution |
|---|---|---|
| Release blocker | Workstation sufficient-k could publish a minimum from an incomplete family; repository order selected later runs | Require all 15 comparisons; deterministic earliest-completed selection; verification failure never substitutes another run |
| Important scientific defect | Generic paired comparisons lacked complete config/artifact checks | Require completed verified artifacts, matching dataset version/hash, seed/full protocol, summary consistency and existing research split compatibility |
| Important UX defect | PCA selector could label an original-feature MI view incorrectly | Separate representation and legacy-URL handling; preserve 16 raw inputs |
| Important UX defect | Classifier retained a result after editing its inputs | Clear stale result/example; focus invalid field; distinguish probabilities, local logits and session history from evaluation |
| Important accessibility defect | Heatmap treated missing frequencies as zero; lacked full numeric alternative | Preserve null, retain measured zero, add semantic keyboard-scrollable table |
| Important quality defect | Projector legend/axis collision; fragile downloads and comparison recovery | Reserved legend margins, short-screen spacing, sticky controls, typed verified downloads/status/errors, explicit invalid pairs and usable recovery |
| Important API defect | Chunked inference bypassed declared-size check; file errors could expose paths | Bound actual body bytes at API/proxy; safe 413/503 with allowed-browser CORS; validate model probability output |
| Minor polish | Pagination, focus navigation, labels and snapshot/fullscreen feedback | Russian controls, skip links/current-page landmarks, history, reduced motion, honest download feedback |
| Future research | External validation, Extended selectors, calibration, Pareto/ablation, full historical ranks/memory | Explicitly deferred; no experiments or reconstructed measurements added |

No unrelated architecture or process-manager replacement was needed. App/API version metadata
now follows release 1.0.0. The [independent interface review](../design/RELEASE_AUDIT.md)
records its coverage and limits. Documentation corrects the old automatic-migration claim
and describes the implemented module layout, reporting and recovery.

## Acceptance evidence

| Check | Actual outcome |
|---|---|
| Dataset | Official UCI 602; 13,611 rows, 16 canonical numerical features, 7 classes, no missing values; canonical AspectRation/roundness/DERMASON retained |
| Scientific history | 171 COMPLETED (170 full protocol, 1 smoke), 2 FAILED; no queued/running conditions and no new ML runs |
| Artifact verification | All 171 completed runs passed the existing verifier through the real API |
| Formal sufficient-k | Five complete families, 15/15 paired comparisons each; LR/SVM/RF/XGBoost k=14 and LightGBM k=15; frozen Nadeau–Bengio method, margin 0.01 and within-model Bonferroni 0.05/15 unchanged |
| Conference evidence | One verified 170-condition full-protocol cohort; earliest completed selection, stable dataset/split/result/fingerprint identities; four snapshot requests returned the same ID |
| Scientific exploration | Actual dataset/feature/budget/comparison pages; MI model filter and browser Back; PCA representation remains distinct; numeric heatmap disclosure |
| Run provenance | Real run detail, fold change, metrics/confusion diagnostics/hashes, CSV feedback; JSON/config/Markdown/folds/selected-features exports matched API/proxy/public bytes and attachment MIME headers |
| Classifier | Real UCI example predicted SEKER, actual SEKER, model probability about 0.7732868856; seven normalized probabilities and LR logit explanation; this is one inference smoke, not a new scientific measurement |
| Conference navigation | All eight sections by keyboard; mobile chooser, visible controls, explicit expiry/renewal preserving step, public PDF feedback and return to workstation |
| Responsive/accessibility | Representative 1920×1080, 1280×900, 768×1024 and 390×844 checks; independent 1280×720 review; no checked page-width overflow; drawer Escape/focus return, error-field focus, numeric chart alternatives, reduced-motion/coarse-pointer styling |
| Real failure handling | Stopped backend reports API unavailable; restart loses old snapshot, explicitly disables export, and renewal preserves step 8; invalid comparison displays no substituted evidence |
| PDF | Real 21-page A4 output; all pages rendered and inspected, no empty/duplicate pages or observed clipped tables/figures; Russian text extracted and three DejaVu fonts embedded |
| PDF transport | API, Next.js proxy, public API and public proxy returned byte-identical PDF for the same snapshot, with application/pdf, attachment and matching X-Evidence-SHA256 |
| Public API | Scientific create/enqueue/cancel returned 403 through public API/proxy; inference 200, invalid input 422, oversized chunked request 413; expired snapshot 410, invalid cohort/incompatible smoke 422; no exposed local paths in inspected metadata |
| Resource protection | Existing snapshot/PDF coalescing and bounded caches/concurrency retained; new actual-byte bounds and client/upstream deadlines; focused automated coverage exercises concurrent/expired/partial/corrupt cases |
| Healthy lifecycle | Existing make presentation: local/public API/Web ready, worker online, external Named Tunnel, sleep active; repeated start creates no duplicate session |
| Real component failure | Terminated only birth-time-verified owned Web with empty queue; supervisor exited code 2, status reported failed, all owned processes gone and external Named Tunnel intact |
| Shutdown | Normal stop and repeated stop succeed; owned sleep assertions released; external tunnel unchanged |
| Runtime recovery | Reused existing P1A package, restored to new isolated directory; all 171 completed runs verified; scientific DB metadata identical, 2,753 dataset/artifact payload hashes identical (four source README scaffolds excluded) |
| Runtime preservation | All non-heartbeat DB rows and all 2,757 source dataset/artifact file hashes identical before/after; only legitimate operational heartbeat may differ |
| Compatible installation | Fresh isolated Python 3.11 venv installed 1.0.0 with compatible current dependency versions; read-only restored classifier inference and a 21-page PDF worked with fonts supplied by that venv's Matplotlib |

Public networking produced occasional transient HTTP 502 during testing; subsequent probes,
PDF paths and public-policy checks succeeded. Local scientific/lifecycle state was not
corrupted or restarted in response to transient public errors.

## Automated gates

- `make test`: **145 Python tests**, **32 frontend tests** passed. Two existing
  Starlette/httpx/AnyIO deprecation warnings remain; they are not hidden failures.
- `make lint`: Ruff and frontend ESLint passed.
- `.venv/bin/ruff format --check .`: passed.
- `make typecheck` and `make build`: passed, production routes generated.
- Alembic consistency checked with explicit **read-only SQLite** on current and restored DBs:
  no new upgrade operations detected. No migration ran during acceptance.
- `git diff --check`: passed. Runtime data, packages, model files, generated PDFs,
  archives, logs, session metadata and secrets are excluded from the release commits.

The frontend/scientific correction checkpoints are `3927e57` and `05cb6e0`.
The final release/documentation checkpoint is identified by Git; this document does not
embed its own commit hash. Acceptance uses the corrected implementation and real saved
results; a clean working tree is checked after committing the final release files.

## Explicit limitations and owner actions

- External validation, calibration, additional selectors/ablation/Pareto and MLP full budget
  curves remain separate future research. Historical missing ranks/memory stay unavailable.
- The public demo needs this Mac powered, open and online. Caffeinate cannot defeat lid-close,
  forced sleep, shutdown or network loss. The local supervisor detects failure and stops;
  it is not unattended high-availability hosting or a remote-control service.
- Native fullscreen activation was not confirmed in the in-app browser; the ordinary-window
  experience remained usable. Check it in the actual conference browser/projector beforehand.
- No full WCAG 2.2/cross-browser/screen-reader certification is claimed. PDF has selectable
  Cyrillic text but is not a tagged accessible PDF. Some established ML terms remain English.
- Compatibility was checked in a fresh local Python environment, not a clean macOS image or
  every OS/browser. Inference requires trusted model files and compatible ML dependencies.
- Only an on-device verified backup was observed. The owner must keep an independent trusted
  off-device copy and its integrity metadata; Git alone cannot recover scientific runtime.
- Before a talk: follow the [Russian rehearsal checklist and committee Q&A](CONFERENCE_NOTES_RU.md),
  download the current PDF, verify public readiness and keep a local fallback. Publication/tagging
  or merging to main remains an explicit owner decision, not part of this completion.

No known release-blocking defect remains within this scope. Optional research and the owner’s
operational backup/rehearsal actions are distinguished from defects; no stronger generalization
or accessibility/uptime guarantee is inferred from passing tests.
