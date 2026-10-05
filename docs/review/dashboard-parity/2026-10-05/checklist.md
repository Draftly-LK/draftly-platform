# Dashboard empty-account parity

The local preview uses the offline demo matter feed. Production uses the
signed-in account's API feed. The previous empty-account branch removed the
metrics and replaced the dashboard with a first-run workflow panel.

Empty and populated accounts now keep the same dashboard sections and header
actions. Empty accounts show zero counts and the existing empty matter message.
Greeting names, actual matter rows, and deadlines remain specific to each account.
No synthetic matter is inserted into production and authentication is unchanged.

- All 575 tests passed, including empty API feed and failure-state regressions.
- Frontend lint passed.
- Screenshots cover populated and empty states at 1440, 768, 390, and 360px.
- Human visual review is available through the screenshots beside this file.
