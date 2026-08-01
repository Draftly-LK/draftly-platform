# Home review issues

## Iteration 1

- Found: the first review command inherited a stale Next child process that
  held port 4310 but did not respond.
- Fix: terminated the workspace-owned listener and restarted the development
  server cleanly on the required port.
- Result: both browser reviews passed; no screen defect remained.
