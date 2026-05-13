"""Load and validate ``config.json`` route definitions."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

_LOG = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class RouteConfig:
    """A single monitored city pair."""

    from_city: str
    to_city: str


def load_routes_config(path: str | Path) -> list[RouteConfig]:
    """
    Load routes from JSON.

    Expected JSON shape (array of objects):
        [{"from_city": "...", "to_city": "..."}, ...]
    """

    cfg_path = Path(path)
    if not cfg_path.is_file():
        raise FileNotFoundError(f"config.json not found at: {cfg_path.resolve()}")

    raw_text = cfg_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError as exc:
        raise ValueError(f"config.json is not valid JSON: {cfg_path}") from exc

    if not isinstance(data, list):
        raise ValueError("config.json must be a JSON array of route objects.")

    routes: list[RouteConfig] = []
    for idx, item in enumerate(data):
        route = _parse_route_object(item, index=idx)
        routes.append(route)

    if not routes:
        raise ValueError("config.json contains no routes.")

    _LOG.info("Loaded %s route(s) from %s", len(routes), cfg_path)
    return routes


def _parse_route_object(item: Any, *, index: int) -> RouteConfig:
    if not isinstance(item, dict):
        raise ValueError(f"Route #{index + 1} must be a JSON object.")

    from_city = item.get("from_city")
    to_city = item.get("to_city")

    if not isinstance(from_city, str) or not from_city.strip():
        raise ValueError(f"Route #{index + 1} is missing a non-empty string 'from_city'.")
    if not isinstance(to_city, str) or not to_city.strip():
        raise ValueError(f"Route #{index + 1} is missing a non-empty string 'to_city'.")

    return RouteConfig(from_city=from_city.strip(), to_city=to_city.strip())
