# Landing navbar startup review

## Reproduced issues

1. The saved navbar and the navbar mounted by React both played their entrance
   animation. Holding the client bootstrap until the saved animation finished
   recorded two visible entrances on desktop and mobile. The regression expected
   one and failed before the fix.
2. The readability helper inferred the navbar theme from label colour. Contrast
   repairs could change that colour independently of the section theme, producing
   a white mobile navbar over the dark hero. The background regression failed
   before the fix: the panel was cream instead of dark.

## Changes and results

- Hide the saved navbar during JavaScript startup. Its replacement plays the
  existing entrance once. A `noscript` rule keeps the saved navigation visible
  when JavaScript is disabled, on both the landing and research pages.
- Read the visible navbar's React backdrop state when synchronising the helper
  theme, before repairing text contrast. Scrolling still selects the existing
  light and dark treatments.
- All four navbar regressions pass: slow startup and reload at 1440 and 375 px,
  repaired-label independence, section transitions, mobile menu dismissal, and
  the no-JavaScript fallback.
- The existing tablet navigation and research/footer/beta navigation tests pass
  on rerun. The tablet test timed out during the first broader run; the separate
  rerun passed without changing that test.
- The other ten selected landing browser tests passed in the broader run.
- All seven landing API and cache-policy unit tests pass.
- Frontend and landing lint and typecheck pass. The frontend production build
  passes.

## Visual evidence

Cold loads and genuine cached reloads were checked at 1440 x 900, 1024 x 768,
and 375 x 812. Each load had one visible navbar entrance, a dark hero navbar,
no horizontal overflow, and no page errors. Cache events and computed colours
are recorded in [results.json](results.json).

- [Desktop](1440x900.png)
- [Tablet](1024x768.png)
- [Mobile](375x812.png)

## Review scope

This is a targeted landing navbar repair. Workspace tokens, legal content, and
application contracts are unchanged. A full accessibility or localisation audit
was not run for this change. The draft PR retains the human visual gate: review
the first-load appearance in Chrome or Edge on the deployed preview before merge.
The live production site has not been changed by this branch.
