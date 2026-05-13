"""Shohoz bus search-trips API client."""

from __future__ import annotations

import logging
from typing import Any

import requests

from .config_loader import RouteConfig
from .constants import DEFAULT_SHOHOZ_HEADERS, SHOHOZ_SEARCH_TRIPS_URL
from .http_client import default_timeout

_LOG = logging.getLogger(__name__)


class ShohozApiError(RuntimeError):
    """Raised when the Shohoz API returns an unexpected payload or a transport error."""


def fetch_trip_count(
    session: requests.Session,
    route: RouteConfig,
    *,
    journey_date: str,
) -> int:
    """
    Call Shohoz ``search-trips`` and return the number of trips in the response.

    Args:
        session: A configured ``requests.Session`` (typically with retries).
        route: Cities to query.
        journey_date: Shohoz-formatted date string ``DD-MMM-YYYY``.

    Returns:
        Non-negative trip count.

    Raises:
        ShohozApiError: on HTTP failures or malformed JSON payloads.
    """

    params = {
        "from_city": route.from_city,
        "to_city": route.to_city,
        "date_of_journey": journey_date,
        "dor": "",
    }

    try:
        response = session.get(
            SHOHOZ_SEARCH_TRIPS_URL,
            headers=DEFAULT_SHOHOZ_HEADERS,
            params=params,
            timeout=default_timeout(),
        )
    except requests.RequestException as exc:
        raise ShohozApiError(f"HTTP request failed for {route.from_city}->{route.to_city}: {exc}") from exc

    if response.status_code != 200:
        snippet = response.text[:500]
        raise ShohozApiError(
            f"Unexpected HTTP {response.status_code} for {route.from_city}->{route.to_city}. "
            f"Body snippet: {snippet!r}"
        )

    try:
        payload = response.json()
    except ValueError as exc:
        snippet = response.text[:500]
        raise ShohozApiError(f"Response was not JSON. Snippet: {snippet!r}") from exc

    count = _extract_trip_list_len(payload)
    _LOG.info(
        "Shohoz trips fetched: %s -> %s on %s | count=%s",
        route.from_city,
        route.to_city,
        journey_date,
        count,
    )
    return count


def _extract_trip_list_len(payload: Any) -> int:
    """
    Safely extract ``len(data.trips.list)`` from the Shohoz payload.

    The live API shape (2026) is typically::
        {"data": {"trips": {"list": [ ... ]}}}
    """

    if not isinstance(payload, dict):
        raise ShohozApiError("Top-level JSON must be an object.")

    data = payload.get("data")
    if not isinstance(data, dict):
        raise ShohozApiError("Missing object path: data")

    trips = data.get("trips")
    if not isinstance(trips, dict):
        # Some error responses may omit trips; treat as zero trips rather than crashing the monitor.
        _LOG.warning("Missing object path: data.trips — treating trip count as 0.")
        return 0

    trip_list = trips.get("list")
    if trip_list is None:
        _LOG.warning("Missing key data.trips.list — treating trip count as 0.")
        return 0
    if not isinstance(trip_list, list):
        raise ShohozApiError("Invalid type for data.trips.list (expected array).")

    return len(trip_list)
