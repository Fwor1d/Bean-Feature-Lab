# Core completion UI audit — 2026-10-08

Scope: the existing Instrument Workstation identity, real API-backed scientific screens and deployment classifier. This was one bounded Impeccable audit with two independent reviewers (design and technical detector), followed by a correction batch and confirmation. No replacement design system or fake scientific content was introduced.

## Evidence and corrections

- `/compare` had a production Server/Client boundary error. The existing client-marked Link adapter now crosses the MUI component prop boundary correctly. Formal and descriptive comparison views render in the production browser.
- Sufficient-k open circles inherited transparent stroke and were invisible. Explicit green marker color makes the calculated markers visible. Model markers also differ by shape; chart/table values remain sourced from API artifacts.
- Baseline and sufficient markers no longer add ten redundant legend entries. A shared caption explains them; the five model entries and x-axis remain readable on the narrow viewport.
- Semantic tables now scroll within their own surface rather than widening the entire Feature Budget/Features page. LR local-contribution tables use MUI TableContainer for the same reason.
- Dataset hashes/schema and quality diagnostics are collapsible on Features, keeping verified dataset status visible and analytical controls closer to the first viewport.
- L1 results have a dedicated sparse-path table with actual per-fold nonzero counts. They are not mislabeled as an absent fixed-k curve.
- Historical run detail explains that its null sufficient-k field is immutable and links to separately calculated Core paired decisions.
- The final integration check found that the web proxy rejected dotted export filenames despite a healthy FastAPI export. Only the five known run export names are now allowed, with traversal rejection tests and forwarded Content-Disposition. Production CSV smoke returned 200 and exactly 15 fold rows plus the header.

The technical reviewer ran `impeccable detect --json apps/web/src`: exit 0, zero findings, no suppressions or false-positive dismissals. That detector result is not an exhaustive accessibility certification.

## Functional confirmation

Production routes checked against the real API: `/`, `/feature-budget`, `/experiments`, `/runs`, `/runs/3`, `/features`, `/compare`, descriptive comparison, L1 sparse path, PCA representation, and `/classifier`.

Desktop viewport: 1280×720. Narrow viewport: 390×844. The MI chart has visible green sufficient markers, separate model shapes and a readable five-item legend. Budget and Features tables stay within page width. Navigation/context move to drawers at narrow width. Loading, unavailable/empty and partial scientific states remain explicit.

A real UCI example was loaded through the public API and predicted by the active deployment model: SEKER, probability 0.7732868856; actual class SEKER. This is a single inference smoke, not a new evaluation metric. Clean-browser route/prediction checks recorded no warning/error logs.

## Limitations

No exhaustive screen-reader, WCAG or cross-browser audit was claimed. Some scientific labels retain English terminology. Historical artifacts contain selection frequencies and fold sets, not complete selector rank distributions; the UI does not invent missing ranks.
