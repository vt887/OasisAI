"""Timing utilities for performance monitoring."""

from __future__ import annotations

import time


def calculate_duration_ms(start_time: float) -> float:
    """Calculate elapsed time in milliseconds since start_time.

    Args:
        start_time: Start timestamp from time.perf_counter().

    Returns:
        Elapsed time in milliseconds, rounded to 2 decimal places.
    """
    return round((time.perf_counter() - start_time) * 1000, 2)
