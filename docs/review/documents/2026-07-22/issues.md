# Documents review issues

## Iteration 1

- Found: `muted-ink` on `disabled-bg` produced 4.47:1 contrast on the Replaced
  status badge, reported by axe as serious.
- Fix: retained the prescribed disabled background and used `ink` for the
  status label.
- Result: zero serious/critical axe violations at both viewports.
