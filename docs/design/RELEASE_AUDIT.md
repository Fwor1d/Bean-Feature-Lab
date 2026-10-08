# Release 1.0 interface review — 2026-10-08

Scope: refine the existing Instrument Workstation and Conference Mode; no replacement visual identity or scientific examples. The independent Impeccable critique used two reviewers: visual/UX and technical detector. Initial visual score was 28/40; it is a baseline, not a claimed final score. The detector ran exactly once: exit 0, zero findings, no suppressions. Browser/DOM checks and manual review supplemented it; none establishes exhaustive WCAG conformance.

## Important defects addressed

- An original-feature selector offered PCA while the page could still render MI. PCA now belongs to the separate representation, including legacy `?selector=pca` URLs; the UI states that all 16 raw measurements remain required.
- Conference Plotly legend collided with the x-axis at shorter desktop heights. The legend now sits above the plot with reserved margins. Model shapes and line styles supplement color; numerical results remain available.
- Editing classifier inputs left a previous prediction on screen. Editing clears the prediction and example identity; session history stays separate. Invalid input focuses and names the first offending field; busy input is disabled.
- Run downloads lacked explicit failure/success feedback. Verified exports now use bounded requests, MIME checks, safe generated filenames and accessible status/error messages. PDF feedback reports handoff to the browser, not an unverifiable claim that the file was saved.
- Comparison filters replaced browser history; invalid requested pairs could silently select another pair. Filters now create history entries, unavailable pairs fail explicitly, and supported selectors remain usable after an API comparison error.
- Heatmap missing values became zero. Missing/nonfinite frequencies now stay null; a keyboard-scrollable numeric table distinguishes unmeasured values from measured zero.

## Accessibility and responsive confirmation

Skip links, a focusable main landmark, current-page navigation, visible focus, heading structure, accessible control names, MUI drawer Escape/focus return, reduced motion and coarse-pointer targets were checked or improved. Pagination controls are localized. Short desktop presentation spacing and a sticky footer keep navigation discoverable. Fullscreen state tracks the browser event and the ordinary layout remains usable when fullscreen does not activate.

Production browser coverage: home, Feature Budget (MI and PCA), Features, Experiments, Runs, run detail/fold diagnostics/export, formal and descriptive Compare, Classifier, Conference and Settings. Representative sizes: 1920×1080 projector, 1280×900 desktop, 768×1024 tablet and 390×844 mobile; independent reviewers also checked 1280×720. Charts, long Russian condition labels, table scrolling, drawers and Conference step controls were exercised. No page-width overflow was observed in the checked states.

Real journeys confirmed: UCI example inference with seven model probabilities; editing clears the old result; invalid fields receive focus; fold selection and CSV feedback; all eight Conference sections by keyboard; mobile section chooser; explicit API-unavailable feedback; expired snapshot disables PDF and explicit renewal preserves the current step. Numerical heatmap disclosure opens on tablet. No application console warnings/errors appeared in the normal checked journeys.

## Honest coverage limits

Native fullscreen activation was not confirmed by the in-app browser; ordinary-window operation remained functional. This is not a full cross-browser, assistive-technology or WCAG 2.2 certification. PDF is readable with selectable Russian text but is not a tagged accessible PDF. Some established scientific terminology remains English. Extended research and absent historical rank/memory measurements remain outside this interface pass.
