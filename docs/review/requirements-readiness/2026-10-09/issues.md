# Review findings and dispositions

1. Pass 1: existing Checks filters lacked accessible labels (axe select-name).
   Fixed with useId and htmlFor; retained failure in task-5-browser-1.log.
2. Pass 2: the gate summary could overflow at 200% English text size. The summary
   now wraps, filter layout wraps, and requirement/scope columns collapse at 1024.
   Hardcoded gate status labels now use EN/SI messages. Failure retained in
   task-5-browser-2.log; current production assets used for pass 3.
3. Pass 3: all fourteen mechanical screen probes passed. A getByLabel locator in
   the behavior harness timed out despite the correct named combobox in saved ARIA.
   The role-based tail fixed only the harness and its result writer. No additional
   product design changes or visual iteration occurred.
4. The original-inspection endpoint intentionally returned one 503 for the retry
   probe: POST /api/v1/matters/mat-synthetic/checklist-items/item-synthetic/original-inspection.
   browser.json separates this known response diagnostic in expectedRecoveryConsole
   from healthy errors (empty). The identical keyed retry succeeded and its saved
   state was asserted. No unexpected errors were suppressed.
5. Human approval is pending. Existing legal catalogue labels still include English
   inside Sinhala screens; this task did not rewrite human-owned legal wording.
   Real evidence-read latency is assigned to Task 8, not validated by fixture speed.

Artifacts use synthetic IDs and values only. The 4310 port was occupied by an existing
process, so this packet used an independently started production server on 4312;
no pre-existing server or shared PostgreSQL instance was stopped.
