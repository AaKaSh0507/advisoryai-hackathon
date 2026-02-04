"""Datetime utilities with timezone-aware functions.

This module provides timezone-aware datetime functions to replace the deprecated
datetime.utcnow() which was deprecated in Python 3.12.
"""

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Return the current UTC datetime with timezone info.

    This replaces datetime.utcnow() which is deprecated in Python 3.12+.
    Returns a timezone-aware datetime object in UTC.
    """
    return datetime.now(timezone.utc)
