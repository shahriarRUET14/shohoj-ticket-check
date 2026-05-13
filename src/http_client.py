"""HTTP session factory with retries for transient failures."""

from __future__ import annotations

import logging
from typing import Final

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

_LOG = logging.getLogger(__name__)

_DEFAULT_TIMEOUT_S: Final[tuple[float, float]] = (10.0, 30.0)  # (connect, read)


def create_requests_session(
    *,
    total_retries: int = 5,
    backoff_factor: float = 1.0,
    status_forcelist: tuple[int, ...] = (429, 500, 502, 503, 504),
) -> requests.Session:
    """
    Build a ``requests.Session`` configured with urllib3 retries.

    Notes:
        - Retries are applied for idempotent methods like GET by default.
        - ``429`` is included because Shohoz may rate-limit; urllib3 will honor ``Retry-After`` when present.
    """

    retry = Retry(
        total=total_retries,
        connect=total_retries,
        read=total_retries,
        backoff_factor=backoff_factor,
        status_forcelist=list(status_forcelist),
        allowed_methods=frozenset(["GET"]),
        raise_on_status=False,
    )

    adapter = HTTPAdapter(max_retries=retry)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    _LOG.debug(
        "Created HTTP session: total_retries=%s backoff_factor=%s status_forcelist=%s",
        total_retries,
        backoff_factor,
        status_forcelist,
    )
    return session


def default_timeout() -> tuple[float, float]:
    """Default (connect, read) timeouts for outbound HTTP calls."""

    return _DEFAULT_TIMEOUT_S
