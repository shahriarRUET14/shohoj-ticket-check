"""Small helpers for reading boolean-like environment variables."""

from __future__ import annotations

import os

from .constants import ENV_DISCORD_NOTIFY_EVERY_CHECK, ENV_DISCORD_REPORT_EVERY_RUN


def truthy(env_name: str) -> bool:
    """
    Return True when ``env_name`` is set to a common affirmative string.

    Treats as false: unset, empty, ``0``, ``false``, ``no``, ``off`` (case-insensitive).
    """

    raw = os.getenv(env_name)
    if raw is None:
        return False
    return raw.strip().lower() in {"1", "true", "yes", "on", "y"}


def _parse_bool_env(raw: str | None) -> bool | None:
    """Return True/False for explicit boolean strings, or None if unset/blank/unknown."""

    if raw is None or not raw.strip():
        return None
    lowered = raw.strip().lower()
    if lowered in {"0", "false", "no", "off", "n"}:
        return False
    if lowered in {"1", "true", "yes", "on", "y"}:
        return True
    return None


def discord_notify_every_check() -> bool:
    """
    Discord notification mode (configurable boolean).

    - **True** (“every check”): post a summary embed on every successful run with current trip counts.
    - **False** (“only on change”): post Discord only when a route’s trip count changes vs
      ``storage/state.json`` (plus optional baseline / change embeds as before).

    Primary env: ``DISCORD_NOTIFY_EVERY_CHECK`` (``true`` / ``false`` / ``1`` / ``0``, etc.).

    If that is **unset or empty**, falls back to legacy ``DISCORD_REPORT_EVERY_RUN``.

    If both are unset/empty, defaults to **True** (every check), matching the bundled GitHub Actions workflow.
    """

    primary = _parse_bool_env(os.getenv(ENV_DISCORD_NOTIFY_EVERY_CHECK))
    if primary is not None:
        return primary

    legacy = _parse_bool_env(os.getenv(ENV_DISCORD_REPORT_EVERY_RUN))
    if legacy is not None:
        return legacy

    return True


# Backward-compatible name used in earlier commits.
def discord_report_every_run() -> bool:
    """Deprecated: use ``discord_notify_every_check()``."""

    return discord_notify_every_check()
