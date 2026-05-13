#!/usr/bin/env python3
"""
Shohoz bus trip monitor entrypoint.

This script is intentionally small: it wires configuration, HTTP, storage, and Discord
notifications together while keeping protocol details in ``src/``.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Allow `python main.py` from the repository root without requiring an editable install.
_ROOT_DIR = Path(__file__).resolve().parent
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

# Load `.env` from the repo root so local runs pick up DISCORD_WEBHOOK without manual `export`.
# On GitHub Actions there is typically no `.env` file; injected env vars still win by default.
from dotenv import load_dotenv  # noqa: E402

load_dotenv(_ROOT_DIR / ".env", override=False)

from src.config_loader import load_routes_config  # noqa: E402
from src.constants import (  # noqa: E402
    DEFAULT_STATE_PATH,
    ENV_DISCORD_TEST_MESSAGE,
    ENV_NOTIFY_ON_BASELINE,
)
from src.date_utils import journey_date_from_env_or_today  # noqa: E402
from src.discord_notifier import (  # noqa: E402
    BaselineObservation,
    TripCountChange,
    send_baseline_notifications,
    send_test_webhook,
    send_trip_change_notifications,
)
from src.env_utils import truthy  # noqa: E402
from src.http_client import create_requests_session  # noqa: E402
from src.shohoz_client import ShohozApiError, fetch_trip_count  # noqa: E402
from src.storage import (  # noqa: E402
    load_state,
    read_route_state,
    save_state,
    state_key,
    upsert_route_state,
)

_LOG = logging.getLogger("shohoz_monitor")


def _configure_logging() -> None:
    """Configure stdout logging in a structured, grep-friendly format."""

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def _resolve_paths() -> tuple[Path, Path]:
    """Resolve config and state paths relative to the repository root."""

    config_path = _ROOT_DIR / "config.json"
    state_path = _ROOT_DIR / DEFAULT_STATE_PATH
    return config_path, state_path


def run() -> int:
    """
    Execute one monitoring cycle.

    Returns:
        ``0`` on success, ``1`` if any route failed after retries or Discord sending failed.
    """

    _configure_logging()

    if truthy(ENV_DISCORD_TEST_MESSAGE):
        try:
            send_test_webhook()
        except RuntimeError as exc:
            _LOG.error("%s", exc)
            return 1
        _LOG.info("DISCORD_TEST_MESSAGE succeeded; remove it from `.env` when you are done testing.")
        return 0

    config_path, state_path = _resolve_paths()

    try:
        _, journey_date = journey_date_from_env_or_today()
    except ValueError as exc:
        _LOG.error("Invalid journey date configuration: %s", exc)
        return 1

    try:
        routes = load_routes_config(config_path)
    except (OSError, ValueError) as exc:
        _LOG.error("Failed loading routes config: %s", exc)
        return 1

    state = load_state(state_path)
    session = create_requests_session()

    change_events: list[TripCountChange] = []
    pending_baselines: list[BaselineObservation] = []
    state_dirty = False
    failures = 0

    for route in routes:
        key = state_key(
            from_city=route.from_city,
            to_city=route.to_city,
            journey_date=journey_date,
        )

        try:
            current = fetch_trip_count(session, route, journey_date=journey_date)
        except ShohozApiError as exc:
            failures += 1
            _LOG.error("Shohoz API error for %s: %s", key, exc)
            continue

        previous = read_route_state(state, key)
        if previous is None:
            _LOG.info(
                "New route/date key (no saved baseline yet): %s | current trips=%s",
                key,
                current,
            )
            pending_baselines.append(
                BaselineObservation(
                    from_city=route.from_city,
                    to_city=route.to_city,
                    journey_date=journey_date,
                    trip_count=current,
                )
            )
            continue

        if previous == current:
            _LOG.info("No trip-count change for %s (trips=%s). Skipping Discord.", key, current)
            continue

        _LOG.warning("Trip-count change detected for %s: %s -> %s", key, previous, current)
        change_events.append(
            TripCountChange(
                from_city=route.from_city,
                to_city=route.to_city,
                journey_date=journey_date,
                previous_count=previous,
                current_count=current,
            )
        )

    if change_events:
        try:
            send_trip_change_notifications(change_events)
        except RuntimeError as exc:
            _LOG.error("Discord notification failed: %s", exc)
            return 1

        for change in change_events:
            upsert_route_state(
                state,
                key=state_key(
                    from_city=change.from_city,
                    to_city=change.to_city,
                    journey_date=change.journey_date,
                ),
                from_city=change.from_city,
                to_city=change.to_city,
                journey_date=change.journey_date,
                trip_count=change.current_count,
            )
        state_dirty = True

    if pending_baselines:
        if truthy(ENV_NOTIFY_ON_BASELINE):
            try:
                send_baseline_notifications(pending_baselines)
            except RuntimeError as exc:
                _LOG.error("Discord baseline notification failed: %s", exc)
        else:
            _LOG.info(
                "Recorded %s baseline(s) locally without Discord "
                "(set NOTIFY_ON_BASELINE=1 for a first-run message, or DISCORD_TEST_MESSAGE=1 to test the webhook).",
                len(pending_baselines),
            )

        for obs in pending_baselines:
            baseline_key = state_key(
                from_city=obs.from_city,
                to_city=obs.to_city,
                journey_date=obs.journey_date,
            )
            upsert_route_state(
                state,
                key=baseline_key,
                from_city=obs.from_city,
                to_city=obs.to_city,
                journey_date=obs.journey_date,
                trip_count=obs.trip_count,
            )
        state_dirty = True

    if state_dirty:
        try:
            save_state(state_path, state)
        except OSError as exc:
            _LOG.error("Failed persisting state file: %s", exc)
            return 1

    if failures:
        _LOG.error("Completed with %s route failure(s).", failures)
        return 1

    if change_events:
        _LOG.info("Summary: Discord trip-change message(s) sent for %s route(s).", len(change_events))
    elif pending_baselines:
        if truthy(ENV_NOTIFY_ON_BASELINE):
            _LOG.info("Summary: Discord baseline message sent for %s route(s).", len(pending_baselines))
        else:
            _LOG.info(
                "Summary: %s baseline(s) saved; Discord skipped (alerts are change-only by default).",
                len(pending_baselines),
            )
    else:
        _LOG.info(
            "Summary: no baseline or trip-count changes — Discord not used this run. "
            "Counts matched `storage/state.json` for every route on %s.",
            journey_date,
        )

    _LOG.info("Completed successfully.")
    return 0


def main() -> int:
    """``main`` wrapper kept tiny for testability."""

    return run()


if __name__ == "__main__":
    raise SystemExit(main())
