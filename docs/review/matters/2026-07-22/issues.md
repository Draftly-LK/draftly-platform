# Matters review issues

## Iterations 1-2

- Found: the review harness used `networkidle`, which was unreliable for the
  App Router stream; the first production server also inherited mixed dev/build
  assets after an invalid build sequence.
- Fix: changed navigation readiness to `domcontentloaded`, stopped the listener,
  rebuilt from a clean process state, and restarted the production server.
- Result: both viewports pass all mechanical assertions.

