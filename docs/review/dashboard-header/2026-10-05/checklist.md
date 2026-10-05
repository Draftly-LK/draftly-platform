# Dashboard header review

Reviewed on 2026-10-05 at 360, 390, 600, 768, 1024 and 1440 px in both locales.

- PASS: greeting, one-line summary, counts and actions stay in order on compact headers.
- PASS: three equal count columns, thin dividers, 12 px labels and 22 px numbers.
- PASS: In drafting stays on one line.
- PASS: actions have equal widths and are 36 px tall on compact headers.
- PASS: icons hide before stacking; creation remains the first action.
- PASS: English at 390 px fits without icons; at 360 px its labels require stacking.
- PASS: Sinhala at 360 and 390 px requires stacking; at 600 and 768 px icons fit.
- PASS: dashboard drawer opener is transparent, white, 40 px, with a gold focus ring.
- PASS: drawer opens and closes with Escape; no serious or critical axe findings.
- PASS: no horizontal page overflow at any checked width.
- PASS: visual review of mobile and desktop screenshots.
- PASS: build, typecheck, source lint (generated files excluded) and all 572 unit tests; contrast checks include the amber tint on navy and light surfaces.

Evidence: `<locale>-<width>.png` and `probes.json` in this directory.
The app currently serves English only. Sinhala was reviewed using a temporary
locale-cookie override and the existing Sinhala catalogue. The override was
removed after verification; several catalogue labels still use English.
The screenshot focus ring is intentional: keyboard focus was checked before capture.
