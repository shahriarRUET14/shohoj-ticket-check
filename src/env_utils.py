"""Small helpers for reading boolean-like environment variables."""

from __future__ import annotations

import os


def truthy(env_name: str) -> bool:
    """
    Return True when ``env_name`` is set to a common affirmative string.

    Treats as false: unset, empty, ``0``, ``false``, ``no``, ``off`` (case-insensitive).
    """

    raw = os.getenv(env_name)
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}
