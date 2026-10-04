# Case law screen review

Synthetic records only. The populated review mounts the real catalogue, search
and reader components with real compiled CSS and bundled fonts. A test-only
token provider and intercepted API responses supply deterministic states;
Next navigation is represented by ordinary anchors. This checks the components,
not a live Clerk session. Backend authentication is covered separately.

## Mechanical checks

- PASS: 1440×900 and 1024×768 catalogue/search layouts have no horizontal overflow.
- PASS: seven captured states have zero serious or critical axe violations.
- PASS: 22 keyboard focus steps reach controls and links with visible solid rings.
- PASS: reduced-motion review; no decorative animation in the new surfaces.
- PASS: Sinhala at 200% CSS zoom has no horizontal overflow or clipped controls.
- PASS: zero unexpected console errors, zero warnings and zero failed assets.
  Chrome emits two expected HTTP diagnostics for the deliberately injected
  503 unavailable and 403 denied responses; they are negative-test evidence.
- PASS: pagination and collection filtering retain their expected server requests.
- PASS: a failed search retries the same body and idempotency key, with limit 8.
- PASS: successful, empty, unavailable and plan-denied search states are distinct.
- PASS: catalogue reader and external-source results retain their separate links.
- PASS: full-text fixture preserves paragraph breaks and renders script markup as
  literal text, without executing it. Metadata-only state supplies a source link.

## Tokens and presentation

- PASS: IBM Plex Sans loads for English; Noto Sans Sinhala loads for Sinhala.
- PASS: new input/select/button radii measure 6 px; new surfaces have no shadows.
- PASS: parsed state includes a warning icon and text, not color alone.
- PASS: no gradients or decorative effects in new workspace components.
- N/A: the catalogue uses metadata articles, not table rows.
- BASELINE DEVIATION: canvas is `#F3F5F8`, matching current main. The older plan
  specifies `#F4F6F8`; see [release checks](release-checks.md).

## Spec and visual review

- PASS: name/citation, collection and year controls, signed pagination, coverage,
  reader warnings, source links and independent fact-pattern search are present.
- PASS: a top jump link makes search reachable above a long catalogue page.
- PASS: legal assistant behavior and statutory retrieval contracts are unchanged.
- PASS: visual inspection shows readable hierarchy and aligned controls, with no
  blocker in the new components. Longer catalogue rows favor metadata clarity;
  a denser browse treatment is a possible later refinement.
- HUMAN PENDING: Draftly visual identity and Sinhala terminology review.
- HUMAN PENDING: recorded display approval before real full-text publication.

## Captures

- [Catalogue, 1440×900](catalogue-1440x900.png)
- [Search, 1440×900](search-1440x900.png)
- [Search, 1024×768](search-1024x768.png)
- [Metadata reader, 1024×768](reader-metadata-1024x768.png)
- [Approved synthetic text, 1024×768](reader-full-text-1024x768.png)
- [Sinhala catalogue, 1024×768](catalogue-si-1024x768.png)
- [Sinhala at 200% zoom](catalogue-si-200percent.png)

## Actual Next route and shell check

PASS: the real Next development server starts after the gazette route fix.
`/library` and `/library/cases/commonlii-SYNTHETIC-1` return 200. The Case law
entry updates the URL, the reader return link reopens the Case law view, and
the statutory tab switches back. With the API deliberately unconfigured, both
catalogue and reader show their unavailable states without page exceptions.
See [actual shell capture](actual-shell-unavailable-1440x900.png).

The isolated run used port 4314 because 4310 was occupied by the original
checkout; that server was left untouched. Existing development-server diagnostics
include Clerk's route-matcher deprecation, a webpack cache performance message
and Next's localhost-origin warning. Production build passes without warnings.
