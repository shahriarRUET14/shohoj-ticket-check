"""JSON persistence for last known trip counts.

State is keyed by route + journey date so a day change does not look like a false "change"
compared to yesterday's totals.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

_LOG = logging.getLogger(__name__)

STATE_VERSION = 1


def state_key(*, from_city: str, to_city: str, journey_date: str) -> str:
    """Stable dictionary key for a monitored route on a journey date."""

    return f"{from_city.strip()}|{to_city.strip()}|{journey_date.strip()}"


def load_state(path: str | Path) -> dict[str, Any]:
    """Load JSON state from disk; return an empty dict if missing or invalid."""

    state_path = Path(path)
    if not state_path.is_file():
        _LOG.info("No existing state file at %s — starting fresh.", state_path)
        return {}

    try:
        raw = json.loads(state_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        _LOG.error("Failed reading state file %s: %s — starting fresh.", state_path, exc)
        return {}

    if not isinstance(raw, dict):
        _LOG.error("State file must contain a JSON object — starting fresh.")
        return {}

    version = raw.get("version")
    if version != STATE_VERSION:
        _LOG.warning(
            "State file version mismatch (found=%s expected=%s). Continuing with best-effort merge.",
            version,
            STATE_VERSION,
        )

    routes = raw.get("routes")
    if routes is None:
        return {}
    if not isinstance(routes, dict):
        _LOG.error("Invalid state schema: 'routes' must be an object — starting fresh.")
        return {}

    return {"version": STATE_VERSION, "routes": routes}


def read_route_state(state: dict[str, Any], key: str) -> int | None:
    """Return the last persisted trip count for a key, or None if unknown."""

    routes = state.get("routes")
    if not isinstance(routes, dict):
        return None

    entry = routes.get(key)
    if not isinstance(entry, dict):
        return None

    count = entry.get("trip_count")
    if isinstance(count, bool) or not isinstance(count, int):
        return None

    return count


def upsert_route_state(
    state: dict[str, Any],
    *,
    key: str,
    from_city: str,
    to_city: str,
    journey_date: str,
    trip_count: int,
) -> None:
    """Update in-memory state for a route key."""

    if "routes" not in state or not isinstance(state["routes"], dict):
        state["routes"] = {}

    routes = state["routes"]
    routes[key] = {
        "from_city": from_city,
        "to_city": to_city,
        "journey_date": journey_date,
        "trip_count": trip_count,
    }


def save_state(path: str | Path, state: dict[str, Any]) -> None:
    """Atomically write JSON state to disk (best-effort atomic replace)."""

    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)

    state["version"] = STATE_VERSION

    tmp_path = state_path.with_suffix(state_path.suffix + ".tmp")
    payload = json.dumps(state, indent=2, sort_keys=True) + "\n"
    tmp_path.write_text(payload, encoding="utf-8")
    tmp_path.replace(state_path)
    _LOG.info("Saved state: %s", state_path)
