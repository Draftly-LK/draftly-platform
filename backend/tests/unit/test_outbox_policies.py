"""Retry backoff (jobs-and-workers.md §4): min(2^n x 5 s, 30 min), +/-20% jitter."""

from __future__ import annotations

import pytest

from src.platform.messaging.outbox import (
    JITTER_FRACTION,
    MAX_BACKOFF_SECONDS,
    backoff_seconds,
)


@pytest.mark.parametrize(
    ("attempts", "seconds"),
    [(0, 5), (1, 10), (2, 20), (3, 40), (4, 80), (5, 160), (6, 320), (7, 640), (8, 1280)],
)
def test_backoff_doubles_from_five_seconds(attempts: int, seconds: float) -> None:
    assert backoff_seconds(attempts, jitter=0) == seconds


@pytest.mark.parametrize("attempts", [9, 10, 20, 64])
def test_backoff_caps_at_thirty_minutes(attempts: int) -> None:
    assert backoff_seconds(attempts, jitter=0) == MAX_BACKOFF_SECONDS == 1800


@pytest.mark.parametrize("attempts", [-5, -1])
def test_a_negative_attempt_count_backs_off_like_the_first(attempts: int) -> None:
    assert backoff_seconds(attempts, jitter=0) == 5


@pytest.mark.parametrize(
    ("jitter", "factor"),
    [(-0.2, 0.8), (0.2, 1.2), (-1.0, 0.8), (1.0, 1.2), (0.1, 1.1)],
)
def test_jitter_is_clamped_to_twenty_percent(jitter: float, factor: float) -> None:
    assert backoff_seconds(3, jitter=jitter) == pytest.approx(40 * factor)


def test_random_jitter_stays_inside_the_band() -> None:
    delays = {backoff_seconds(3) for _ in range(200)}

    assert all(40 * (1 - JITTER_FRACTION) <= d <= 40 * (1 + JITTER_FRACTION) for d in delays)
    assert len(delays) > 1
