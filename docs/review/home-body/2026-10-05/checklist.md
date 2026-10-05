# Homepage body review: 2026-10-05

Scope: body content only. Header markup, header helpers, sidebar files,
shared buttons, global CSS, authentication, matter feed and business rules
were checked against HEAD and remain unchanged.

## Validation

- PASS: populated and empty dashboards at 1440, 1200, 1024, 768, 600, 390 and 360 px.
- PASS: mobile body order is recent matters, obligations, live workflows, then planned workflows.
- PASS: desktop queue/agenda use an 8/4 split, including the narrower desktop surface.
- PASS: no horizontal overflow, console errors or page exceptions in the browser matrix.
- PASS: no serious or critical axe findings in any matrix entry.
- PASS: each matter row has one link; clicking its title opens the same matter route.
- PASS: View all opens /matters; live workflows open /new as before.
- PASS: planned workflows have no destination or keyboard tab stop.
- PASS: row and workflow focus indicators are visible and 2 px wide.
- PASS: hover feedback respects reduced motion.
- PASS: all 575 frontend tests with minWorkers=1 and maxWorkers=2.
- PASS: typecheck, source lint (generated files excluded), isolated production build and Markdown lint.

The default parallel test run hit an existing tooltip timing failure; the
complete suite passed with fewer workers. No tooltip code was changed.

## Visual review

The queue exposes matter names, reference, instrument, status, activity and
next action without a table header. The amber cue is contextual to review rows.
The agenda uses connected urgency icons and dates. Workflow tiles use compact
document marks, serif titles, Gazette metadata and explicit Start actions;
planned workflows form a smaller neutral strip. Shadows are local and subtle.

Before/after evidence: `before-<width>.png`, `populated-<width>.png` and
`empty-<width>.png`. Raw layout/a11y probes are retained locally in `probes.json`.
Full-page captures can change viewport-anchored backdrop scaling when the
page height changes; the frozen backdrop implementation is unchanged.

Human visual identity approval remains a user review; no production deployment.
Live deadlines still have no backend feed, and workflow selection still goes
through the existing intake screen. No unsupported route or fake data was added.
