# Matter overview review issues

## Iteration 1

- Found: filtered arrays returned directly from Zustand selectors caused React
  maximum-update-depth error 185.
- Fix: selected stable store arrays and derived matter-specific collections
  after selection.
- Result: console is clean and both target viewports pass.
