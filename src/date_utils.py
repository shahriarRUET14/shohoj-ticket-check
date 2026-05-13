"""Journey date helpers: Shohoz expects ``DD-MMM-YYYY`` (e.g. ``30-May-2026``)."""

from __future__ import annotations

import logging
import os
import re
from datetime import date, datetime
from typing import Final

from .constants import ENV_OVERRIDE_DATE

_LOG = logging.getLogger(__name__)

# Example: 30-May-2026
_SHOHOZ_DATE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^(?P<day>\d{2})-(?P<mon>[A-Za-z]{3})-(?P<year>\d{4})$"
)


def format_shohoz_date(value: date) -> str:
    """Format a ``datetime.date`` into Shohoz's ``DD-MMM-YYYY`` string."""

    # %d is zero-padded day; %b is locale-dependent abbreviated month name (English on GitHub runners).
    return value.strftime("%d-%b-%Y")


def parse_shohoz_date(value: str) -> date:
    """
    Parse and validate a Shohoz-style date string.

    Raises:
        ValueError: if the string is not exactly ``DD-MMM-YYYY`` or not a real calendar date.
    """

    cleaned = value.strip()
    match = _SHOHOZ_DATE_PATTERN.match(cleaned)
    if not match:
        raise ValueError(
            "Invalid OVERRIDE_DATE format. Expected DD-MMM-YYYY (example: 30-May-2026)."
        )

    # Validate via datetime parsing (also catches impossible dates like 31-Feb-2026).
    try:
        parsed = datetime.strptime(cleaned, "%d-%b-%Y").date()
    except ValueError as exc:
        raise ValueError(f"Invalid calendar date in OVERRIDE_DATE: {cleaned!r}") from exc

    return parsed


def journey_date_from_env_or_today() -> tuple[date, str]:
    """
    Resolve the journey date.

    Returns:
        A tuple of ``(date_object, shohoz_formatted_string)``.
    """

    raw = os.getenv(ENV_OVERRIDE_DATE)
    if raw is None or not raw.strip():
        today = date.today()
        formatted = format_shohoz_date(today)
        _LOG.info("Using today's date for journey: %s", formatted)
        return today, formatted

    parsed = parse_shohoz_date(raw)
    formatted = format_shohoz_date(parsed)
    if os.getenv("GITHUB_ACTIONS", "").lower() == "true":
        _LOG.info(
            "Using OVERRIDE_DATE for journey (exact date omitted from Actions logs; "
            "use a non-secret Actions Variable for OVERRIDE_DATE if you need it visible in logs)."
        )
    else:
        _LOG.info("Using OVERRIDE_DATE for journey: %s", formatted)
    return parsed, formatted
