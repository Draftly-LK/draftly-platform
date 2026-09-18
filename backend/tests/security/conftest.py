"""Makes the shared HTTP ``harness`` fixture available to the security suites."""

from tests.security.harness import harness

__all__ = ["harness"]
