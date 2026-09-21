# Landing-page navbar typography review

- Mechanical: Playwright suite passed at 375 × 812, 768 × 1024, and
  1440 × 900. Console errors, failed responses, clipping, and horizontal
  overflow were all absent.
- Typography: the `Draftly` navbar wordmark uses `Darker Grotesque`, matching
  the other navbar labels on desktop and mobile. A computed-style assertion
  protects this behavior.
- Visual: inspected all three final viewport screenshots. The wordmark is
  legible, aligned with the navigation nodes, and no longer uses the former
  Georgia-rendered SVG lettering.
- Responsive: the desktop navigation and mobile/tablet menu treatments retain
  their existing spacing, contrast, and focus behavior.
- Result: pass. No second styling adjustment was needed after screenshot
  review.
