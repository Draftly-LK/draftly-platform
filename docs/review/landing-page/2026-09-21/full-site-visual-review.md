# Draftly landing-page full-site visual review

**Review date:** 2026-09-21
**Status:** Launch blocked
**Evidence:** 380 PNG captures in
`C:\Users\asus\draftly-review\landing-page-2026-09-21`

The capture set covers desktop, tablet, and mobile versions of the home page,
interactive home-page states, research, careers, legal pages, and inherited
artwork routes. The screenshots remain outside the repository in accordance
with the project's reference-image policy.

## Decision summary

The site is not ready to publish as Draftly. The home page has useful Draftly
copy and a workable information structure, but the shipped surface is still a
patched SAMMY Labs mirror. Several secondary pages present SAMMY's identity,
services, contracts, vendors, infrastructure, locations, and legal scope as if
they belonged to Draftly.

Work must proceed in this order:

1. Remove all SAMMY-owned content, assets, routes, metadata, and claims from the
   public build.
2. Restrict marketing scope to Sri Lanka. Remove the global coverage map and
   worldwide positioning.
3. Replace the black background behind the introductory Draftly paragraph and
   rebalance the site's excessive dark sections.
4. Fix encoding, responsive, navigation, and rendering defects.
5. Capture and review the complete site again before deployment.

This is not a search-and-replace exercise. SAMMY legal pages and operational
claims must be removed or replaced with facts verified for Draftly. Renaming
SAMMY to Draftly would create false statements and potentially publish another
company's legal wording.

## Launch-blocking findings

### P0-01: SAMMY identity remains across public pages

The following visible pages still identify the product or company as SAMMY:

| Page | Evidence from screenshots | Required action |
| --- | --- | --- |
| Careers | `CAREERS · SAMMY LABS`, “One API for every law, globally,” SAMMY job descriptions, London/San Francisco roles, and `careers@sammylabs.com` | Remove the route and all links. Recreate only when Draftly has approved roles and contact details. |
| Regulators | `REGULATORS · SAMMY LABS`, US regulatory examples, agency use cases, and `regulators@sammylabs.com` | Remove the route. It is unrelated to Draftly's current Sri Lankan conveyancing scope. |
| Security | “Security at SAMMY Labs,” SAMMY infrastructure and AI-processing claims, and SAMMY email addresses | Remove from public navigation until Draftly-specific security statements are verified and approved. |
| Service description | “SAMMY Service Description,” SAMMY platform behavior, support email, and SAMMY URLs | Remove. Draftly needs its own reviewed service description. |
| Terms | “SAMMY Labs, Terms of Service,” SAMMY legal entities, England/Wales and Delaware terms, and SAMMY contacts | Remove. Do not edit or relabel this contract. |
| DPA | “SAMMY Labs, Data Processing Agreement,” SAMMY entities, GDPR/UK language, notification periods, and SAMMY processing details | Remove. Do not edit or relabel this agreement. |
| Subprocessors | SAMMY wording and an inherited vendor list | Remove until the real Draftly vendor list and processing purposes are confirmed. |
| Privacy policy | Inherited company, jurisdiction, transfer, retention, and privacy wording | Remove until owner and legal review produce a Draftly policy. |

The current footer links make these pages look official. Until approved Draftly
documents exist, remove the links instead of publishing placeholder contracts.

### P0-02: False operational and compliance claims

The screenshots claim or imply facts about:

- ISO/IEC 27001 certification;
- AWS, Supabase, and Vercel hosting;
- Anthropic model processing;
- PostHog, Slack, and Google Workspace;
- US, UK, and EU hosting regions;
- SSO, multi-factor authentication, backups, and incident response;
- breach-notification and deletion deadlines;
- SAMMY Labs Ltd. and SAMMY Labs, Inc.;
- London and San Francisco teams and vacancies.

These are not Draftly facts established by the repository. Remove the pages
that contain them. New trust and legal content must be based on the deployed
architecture, signed agreements, and approved company details.

### P0-03: SAMMY material remains in metadata and non-visible content

The mirrored HTML contains SAMMY page titles, descriptions, canonical URLs,
Open Graph data, Twitter data, organization schema, worldwide service areas,
founding locations, product descriptions, and SAMMY asset references. This can
surface in search results and link previews even when the visible page says
Draftly.

Before launch, the shipping output must contain none of the following unless a
non-shipping archive is explicitly excluded from the build:

- `SAMMY`, `SAMMY Labs`, or `sammylabs.com`;
- SAMMY company entities or email addresses;
- SAMMY Open Graph, Twitter, icon, and logo assets;
- `Worldwide`, US, UK, or EU service-area claims;
- SAMMY structured data or canonical URLs.

### P0-04: Inherited artwork/demo routes are publicly reachable

The capture set includes these standalone routes:

- `ascii-letter`;
- `ascii-magnifying-glass`;
- `ascii-phone`;
- `ascii-policies`;
- `ascii-radar`;
- `lady-justice-v5`;
- `lady-justice-v6`.

They are raw design/demo artifacts, not product pages. Remove them from the
public route set and deployment artifact. If an original Draftly illustration
is retained on the home page, it should be stored as a normal site asset rather
than exposed as a separate page.

### P0-05: Visible character-encoding corruption

The trust section renders corrupted punctuation such as `â€”` before card
headings. The source copy also contains sequences such as `Ã`, `Â`, and `â€`.
This affects professionalism, accessibility, search text, and future content
patches.

Normalize the copy and generated output to UTF-8, then add a browser assertion
that rejects known mojibake sequences in rendered text.

## Sri Lanka-only positioning

### P1-01: Remove the global coverage map

The home page shows a world map under “Focused coverage. Built to expand
carefully.” The visual communicates worldwide availability even though the
copy says the current scope is Sri Lankan conveyancing. This is the “global
country” problem visible in the screenshots.

Remove the world map.

If a map is important, use only an original Sri Lanka outline and do not imply
island-wide completeness. The existing corpus qualifier must remain beside the
research figures.

### P1-02: Remove global and foreign-market language

Delete inherited phrases such as “globally,” “every law,” “multiple
jurisdictions,” worldwide service areas, foreign regulator use cases, and
London/San Francisco role locations. Do not replace every use of the legal term
“jurisdiction” mechanically; update only the marketing scope and use verified
Sri Lankan wording.

### P1-03: Keep research metrics tied to their scope

The figures for enactments, sections, amendments, cases, Recall@20, and MRR can
remain only with their existing research qualifiers. They must not be paired
with a world map or presented as product-availability statistics.

## Visual and responsive findings

### P1-04: Remove the black background behind the introductory paragraph

The requested paragraph begins:

> Draftly helps lawyers process conveyancing matters without losing sight of
> the evidence.

It currently sits inside the black hero. Move the introductory copy onto a
light or warm off-white background with dark text. The hero can retain orange
accents, but the paragraph should no longer be presented on a full black field.

The current desktop hero also devotes too much space to the ASCII figure, while
the mobile figure competes with the headline and actions. Reduce or remove the
figure when the section is rebuilt. The product proposition and primary action
must dominate the first viewport.

### P1-05: Too much of the site uses the inherited dark visual system

The careers, research, regulators, security, service description, privacy,
terms, DPA, and subprocessors pages are almost entirely black. This makes the
site feel like the source brand and creates long, low-contrast reading
surfaces.

Recommended direction:

- use the light document/workspace canvas as the default Draftly surface;
- reserve dark sections for one or two deliberate moments, not entire policy
  documents;
- render future legal documents on a readable light article layout;
- keep orange as an accent rather than the only hierarchy cue.

### P1-06: Research page begins with excessive empty space

The desktop research capture has a very large empty dark region before the
first meaningful content. Reduce the top spacer/hero height and bring the page
title and research summary into the first viewport.

### P1-07: Tablet matter preview appears blank

The tablet home capture shows a large empty bordered panel where the matter
interface preview should appear. Confirm whether this is a failed asset,
animation state, or breakpoint issue. The preview must either render meaningful
content or be removed at that breakpoint.

### P1-08: Anchor navigation lands beneath the sticky header

The captured home-page navigation states show preceding or clipped content at
the top edge while the sticky navigation overlaps the destination. Add an
appropriate `scroll-margin-top` to every anchor target and verify all Product,
Workflow, Research, Trust, and About jumps at desktop, tablet, and mobile sizes.

### P1-09: Residual SAMMY ticker text appears behind navigation states

One trust-state capture contains faint inherited SAMMY corpus language behind
the sticky navigation. Audit every animated ticker/state, not only the default
home-page frame. The ticker should contain only the approved Draftly document
and research terms.

### P2-01: Mobile density and readability

The mobile layouts generally avoid horizontal overflow, but secondary pages
are extremely long and use small gray body text on black. The footer also
becomes a dense list of links. For the rebuilt pages:

- use at least a comfortable mobile body size and line height;
- shorten line lengths and increase contrast;
- group or collapse footer navigation;
- keep tap targets at least 44 by 44 CSS pixels;
- avoid carrying desktop legal-document density directly onto mobile.

### P2-02: Brand treatment is inconsistent

The top navigation uses a compact Draftly text badge, while the footer uses a
different large serif wordmark treatment. Define one approved wordmark and one
type treatment. Remove remaining source-brand icons, share images, and favicons.

## Page disposition

| Route/page family | Decision before launch |
| --- | --- |
| Home | Keep the information architecture; rebuild with original assets, Sri Lanka-only scope, a light introductory section, and responsive fixes. |
| Research (`lab`) | Keep Draftly research content; remove inherited shell artifacts, reduce empty space, and verify all claims/links. |
| Careers | Remove until Draftly has real approved vacancies. |
| Regulators | Remove; it is a SAMMY/US product page outside current scope. |
| Privacy, Terms, DPA | Remove from the public build until approved Draftly documents exist. Do not rename inherited text. |
| Security | Replace only after the deployed controls and provider facts are verified. |
| Service description | Replace with an approved Draftly scope document; do not adapt SAMMY wording. |
| Subprocessors | Replace from the real Draftly data-flow/vendor inventory. |
| ASCII and Lady Justice routes | Remove from routing and deployment. Retain only approved original artwork as internal assets. |

## Recommended implementation sequence

### Phase 1: Quarantine inherited material

1. Prevent every SAMMY-derived secondary page and artwork route from shipping.
2. Remove footer and navigation links to unavailable legal/company pages.
3. Replace SAMMY metadata, structured data, icons, social images, canonical
   URLs, and contact addresses.
4. Add a shipping-output scan for inherited names, domains, and locations.

### Phase 2: Correct the home page

1. Move the introductory paragraph to a light background.
2. Remove the world map and replace it with Sri Lanka scope cards or a Sri
   Lanka-only visual.
3. Remove remaining global language and hidden SAMMY ticker strings.
4. Repair mojibake, tablet preview rendering, anchor offsets, and mobile
   density.
5. Standardize the Draftly wordmark, favicon, and social preview.

### Phase 3: Rebuild supporting pages

1. Keep and refine the Draftly research page.
2. Author original company and trust pages from verified Draftly facts.
3. Obtain owner/legal approval before publishing privacy, terms, DPA,
   subprocessors, security, or service-description wording.
4. Add careers only when real roles and a real contact channel exist.

### Phase 4: Re-review

Capture the full route set at 375 × 812, 768 × 1024, and 1440 × 900. Review:

- every full page;
- open navigation and menu states;
- every anchor destination;
- form idle, validation, submitting, success, and failure states;
- titles, descriptions, canonical URLs, Open Graph, Twitter, icons, and JSON-LD;
- console errors, failed requests, overflow, clipping, contrast, and keyboard
  focus.

## Acceptance criteria

The landing site may move toward deployment only when all of the following are
true:

- [ ] No shipping page, asset, metadata field, structured-data block, email, or
  URL contains SAMMY/SAMMY Labs branding.
- [ ] No SAMMY legal text or operational claim is represented as Draftly's.
- [ ] Careers, regulators, and raw artwork routes are absent from the public
  build.
- [ ] Unapproved legal/security pages are absent or clearly unavailable, not
  silently rewritten.
- [ ] Marketing scope says Sri Lanka; no world map or worldwide-coverage claim
  remains.
- [ ] The introductory Draftly paragraph is on a light background.
- [ ] Research metrics retain their scope and accuracy qualifiers.
- [ ] Rendered text contains no known mojibake sequences.
- [ ] The tablet matter preview renders correctly or is intentionally removed.
- [ ] Sticky navigation does not cover anchor destinations.
- [ ] Desktop, tablet, and mobile captures show no clipping, overflow, or
  unreadable text.
- [ ] Draftly owns or has approval for every shipped visual asset.
- [ ] Legal/company owners approve all published contact, provider, security,
  and contract information.

## Live browser verification

The local production build at `http://127.0.0.1:4173/` was reviewed in the
browser on 21 September 2026 at desktop, tablet, and mobile widths. The live
DOM and rendered captures confirm the following:

- the introductory paragraph inherits `rgb(20, 19, 20)` from its container;
- visible page text still contains SAMMY code/corpus content;
- the coverage section still claims global coverage across 81 countries and
  uses a world map;
- trust copy contains mojibake including `Draftlyâ€™s` and `â€”`;
- the document does not report horizontal page overflow at 1440, 768, or 375
  CSS pixels, but the fixed mobile header is visibly clipped in deep-scroll
  captures over the global map and footer;
- the browser console reports a missing `/favicon.ico` and repeated warnings
  for an unused preloaded webpack chunk.

Live evidence:

- [Desktop full page](live-browser/landing-desktop-full-1440.png)
- [Desktop hero at 1440 × 900](live-browser/landing-desktop-top-1440x900.png)
- [Tablet hero at 768 × 1024](live-browser/landing-tablet-top-768x1024.png)
- [Tablet coverage section](live-browser/landing-tablet-coverage-768x1024.png)
- [Tablet trust section](live-browser/landing-tablet-trust-768x1024.png)
- [Tablet footer](live-browser/landing-tablet-footer-768x1024.png)
- [Mobile hero at 375 × 812](live-browser/landing-mobile-top-375x812.png)
- [Mobile scope metrics](live-browser/landing-mobile-coverage-375x812.png)
- [Mobile global map](live-browser/landing-mobile-global-map-375x812.png)
- [Mobile trust cards](live-browser/landing-mobile-trust-cards-375x812.png)
- [Mobile footer](live-browser/landing-mobile-footer-375x812.png)
- [Browser console log](live-browser/browser-console.log)

## Overall assessment

The Draftly home-page story is strong enough to preserve: evidence remains
visible, lawyers retain judgment, and the scope is Sri Lankan conveyancing. The
current implementation is still structurally tied to another company's site,
however. The correct next step is to remove the inherited public surface first,
then rebuild the Draftly presentation around its own identity and verified
facts. Visual polish should not precede that cleanup.
