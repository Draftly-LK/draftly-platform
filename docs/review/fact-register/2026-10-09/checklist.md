# Task 3 synthetic fact-register review packet

These captures use synthetic matter, document, actor and fact values. No real
case was opened. This packet records mechanical checks and AI screenshot
critique; it is not a human-approved visual or terminology baseline.

## Scope and method

The browser harness mounts the actual `FactsScreen`, `FactRegister`,
`DocumentProcessingReviewScreen`, `AppShell` and API client against synthetic
HTTP responses. Token, Clerk, Next navigation and image adapters exist only in
the ignored test harness. Production authentication remains unchanged. Actual
Next request rendering separately checks the locale cookie and HTML language;
unconfigured authentication correctly redirects protected routes.

Review captures cover English and Sinhala at 1440 × 900 and 1024 × 768. Both
locales have a 1024 capture with every rendered font and line height doubled
to exercise 200% text expansion. Manual governed enum entry and document review
are captured in both locales at 1024. Source refusal, mutation refusal, API
unavailability and the collapsed Sinhala navigation rail have separate captures.

`synthetic-measurements.json` records layout, focus, cookie/reload, axe, fonts, reduced
motion, keyboard targets, API paths and console/request observations.
Opaque retry keys and request digests are replaced with presence/privacy flags;
the raw harness output stays ignored under the repository's `raw-*` convention.
`remaining-sinhala-option-keys.json` names the existing option labels whose
Sinhala catalogue still contains English; those legacy taxonomy labels are
not claimed as localized by this task.

## Mechanical outcomes

| Check | Result and limit |
| --- | --- |
| Locale default, SI cookie, invalid cookie and reload | Actual Next HTML language is EN, SI, EN respectively and survives reload; actual component switch renders Sinhala and persists the cookie |
| Review, manual and document screens in both locales | Actual components render synthetic values and sources; no root horizontal overflow in the 14 captured states |
| Axe | Zero serious or critical violations in all 14 captured states |
| Keyboard and focus | Review receives focus; next keyboard control has a visible 2px navy outline; command palette opens/closes by keyboard; manual entry submits a refused request with 33 recorded tab targets; scope/conflict commands are component-tested rather than fully keyboard-submitted here |
| 200% text | Both locale review captures wrap stage labels, fact titles, controls and evidence without root overflow; review becomes one column at 1024 |
| Sources and permissions | Corrected page loads through authenticated blob client; original 403 and mutation 403 remain visible and do not promote the fact; API 503 does not masquerade as an empty register |
| Adjacent navigation | Existing matter tabs, stage indicator, expanded shell and SI rail are included; sidebar and stepper focused unit tests also pass |
| Tokens and fonts | Computed canvas is existing `#f3f5f8`; loaded font faces and matching weight/glyph checks prove Plex/Source Serif 4 in EN and all four configured fonts in SI; statuses retain icon and text |
| Console and assets | Final production-asset probes record four expected 403/503 console errors, zero warnings/page errors/failed assets; earlier development navigation aborted two protected-route chunks. This is not a global zero-error authenticated route gate |
| Reduced motion | Actual reduced-motion preference is true; primary-control transition is `1e-05s`; new loading animation has a reduced-motion alternative |
| Lighthouse | Synthetic rendered review DOM: accessibility 100, best practices 100, desktop 1440 × 900; performance and authenticated runtime are outside this static snapshot measurement |

Lighthouse ran with CLI 13.5.0 against the script-free rendered DOM, using
same-origin proxies for existing fonts/styles/images. The CLI emitted a Node
engine advisory (repository Node 22.16; CLI requests 22.19). Execution and report
completed. Its unscored label/name advisory identifies the existing shell
search shortcut label; default axe serious/critical gates remain clear.

Font loading is subset/weight-sensitive. Final EN-only metrics retain the false
default-weight Latin-glyph Sinhala/serif checks for transparency; per-locale
probes additionally record loaded font faces and checks using actual Sinhala
glyphs and display weight 600. Those checks pass for all four configured fonts
in the Sinhala rendered screen. No shared font substitution was made.

## Screen iterations and critique

| Screen | Design iterations | Issues found and disposition |
| --- | --- | --- |
| Canonical review | 3 | First: missing governed fact labels rendered generic text; added complete existing fact-key UI labels. Second: doubled text exposed cramped card title/review columns and overlapping stage labels; allowed wrapping and one-column review at 1024. Third: final EN/SI captures show readable titles, controls and evidence; human review remains pending |
| Manual entry | 1 | Governed negative search option is readable and distinct from no evidence; no automatic subject or transaction choice; native selects can truncate long identity context while ordinal and full reviewed context remain available in the register |
| Document review | 1 | Corrected source page remains visible beside the canonical register; optional OCR failure has a truthful message without removing the page; no fact-specific bounding box is invented |
| Shell/rail and refusal states | 1 | Locale control retains an accessible full name in the rail; refusal messages stay visible with status icons and text |

Additional harness runs verified changed fixtures, keyboard probes and final
labels; they are not further visual design iterations. The three-iteration cap
does not turn unresolved human review into self-approval.

## Remaining owner and Task 8 gates

- Human screenshot/layout and Sinhala terminology approval is pending for this
  concrete synthetic packet, including new generic fact and enum UI labels.
- A real authenticated API journey must prove database persistence, source
  retention, lost-response manual replay and refresh/re-entry across the full
  workflow. Synthetic HTTP and component tests do not prove that journey.
- Protected application routes, link destinations and console/asset zero-error
  gates still require configured authentication and real synthetic backend
  fixtures in Task 8. Actual locale server rendering was checked separately.
- Existing `rta.subtype`, `rta.process`, `rta.service`, `newMatter.scope` and
  `newMatter.parcelKind` English option keys are enumerated in the companion
  JSON. Existing document review/classification, authentication and matter
  state labels still have legacy English text; later owning tasks must review
  those screen namespaces. New fact labels, status/control labels and shell
  common navigation labels are translated.
- Existing document OCR word overlay uses its prior blue RGBA styling; this
  task does not claim that legacy overlay as a fact locator or new token.
  Older plan/spec typography and canvas examples differ from current shared
  navy-refresh tokens; this task preserves current repository tokens.
- Lighthouse's existing shell search label/name advisory remains for its
  owning accessibility review; the static 100/100 scores are not an
  authenticated runtime or human visual approval.
