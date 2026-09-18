"""Fixed identities and times shared by the test suites.

Fixed rather than generated so a hash or ordering assertion does not depend on
the day or the order the suite runs.
"""

from __future__ import annotations

from datetime import UTC, datetime

USER_A = "usr_synthetic"
USER_B = "usr_synthetic_b"
MATTER_A = "mat_synthetic"
MATTER_B = "mat_synthetic_b"

NOW = datetime(2026, 8, 17, 9, 0, tzinfo=UTC)
