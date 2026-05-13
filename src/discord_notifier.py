"""Discord webhook notifications using embeds."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import requests

from .constants import ENV_DISCORD_WEBHOOK
from .http_client import create_requests_session, default_timeout

_LOG = logging.getLogger(__name__)


def _execute_webhook_url(webhook_url: str) -> str:
    """Append ``wait=true`` so Discord returns a message object (helps logging and debugging)."""

    base = webhook_url.strip()
    sep = "&" if "?" in base else "?"
    return f"{base}{sep}wait=true"

# Discord allows up to 10 embeds per webhook execute payload.
_MAX_EMBEDS_PER_MESSAGE = 10


@dataclass(frozen=True, slots=True)
class TripCountChange:
    """A detected change worth notifying."""

    from_city: str
    to_city: str
    journey_date: str
    previous_count: int
    current_count: int


@dataclass(frozen=True, slots=True)
class RouteRunSnapshot:
    """One route’s trip count after a Shohoz fetch (used for per-run Discord summaries)."""

    from_city: str
    to_city: str
    journey_date: str
    current_count: int
    previous_count: int | None


def send_run_summary_notification(snapshots: list[RouteRunSnapshot]) -> None:
    """
    Post a single Discord embed listing **current** trip counts for every route in this run.

    Raises:
        RuntimeError: if ``DISCORD_WEBHOOK`` is missing or Discord rejects the payload.
    """

    if not snapshots:
        return

    webhook_url = require_discord_webhook_url()
    session = create_requests_session(total_retries=3, backoff_factor=0.75)

    checked_at = datetime.now(timezone.utc)
    checked_at_str = checked_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    embed_timestamp = checked_at.isoformat(timespec="seconds").replace("+00:00", "Z")

    any_changed = any(
        s.previous_count is not None and s.previous_count != s.current_count for s in snapshots
    )
    any_new = any(s.previous_count is None for s in snapshots)

    title = "🚌 Shohoz trip check"
    if any_changed:
        title += " · count changed"
    elif any_new:
        title += " · new baseline"

    color = 0xF39C12 if any_changed else (0x3498DB if any_new else 0x2ECC71)

    fields: list[dict[str, Any]] = []
    for s in snapshots:
        if s.previous_count is None:
            detail = f"**{s.current_count}** trips available\n_First observation for this journey date (baseline)._"
        elif s.previous_count != s.current_count:
            delta = s.current_count - s.previous_count
            detail = (
                f"**{s.current_count}** trips available\n"
                f"Was **{s.previous_count}** last run → **Δ {delta:+d}**"
            )
        else:
            detail = f"**{s.current_count}** trips available\nUnchanged vs last run (**{s.previous_count}**)."

        fields.append(
            {
                "name": f"{s.from_city} → {s.to_city}",
                "value": detail,
                "inline": False,
            }
        )

    journey = snapshots[0].journey_date
    embed: dict[str, Any] = {
        "title": title,
        "description": f"Journey date **{journey}** · checked **{checked_at_str}**",
        "color": color,
        "timestamp": embed_timestamp,
        "fields": fields[:25],
        "footer": {"text": "Shohoz bus monitor · periodic summary"},
    }

    payload = {"embeds": [embed]}
    _post_json(session, webhook_url, payload)


def require_discord_webhook_url() -> str:
    """Read ``DISCORD_WEBHOOK`` from the environment or raise a clear error."""

    url = os.getenv(ENV_DISCORD_WEBHOOK)
    if not url or not url.strip():
        raise RuntimeError(
            "Missing DISCORD_WEBHOOK environment variable. "
            "Set it to your Discord incoming webhook URL."
        )
    return url.strip()


def send_test_webhook() -> None:
    """
    Post a short plain-text message to prove the webhook URL works.

    Enable with ``DISCORD_TEST_MESSAGE=1`` in ``.env`` (or CI env).
    """

    webhook_url = require_discord_webhook_url()
    session = create_requests_session(total_retries=3, backoff_factor=0.75)
    payload: dict[str, Any] = {
        "content": "✅ **Shohoz bus monitor** — Discord webhook test OK (you can remove `DISCORD_TEST_MESSAGE` now).",
    }
    _post_json(session, webhook_url, payload)


@dataclass(frozen=True, slots=True)
class BaselineObservation:
    """First observation for a route + journey date key (no prior stored count)."""

    from_city: str
    to_city: str
    journey_date: str
    trip_count: int


def send_baseline_notifications(observations: list[BaselineObservation]) -> None:
    """Post a Discord embed summarizing first-time baselines for the current run."""

    if not observations:
        return

    webhook_url = require_discord_webhook_url()
    session = create_requests_session(total_retries=3, backoff_factor=0.75)

    fields: list[dict[str, Any]] = []
    for obs in observations:
        fields.append(
            {
                "name": f"{obs.from_city} → {obs.to_city}",
                "value": f"Journey **{obs.journey_date}** — recorded **{obs.trip_count}** trips.",
                "inline": False,
            }
        )

    embed: dict[str, Any] = {
        "title": "📌 Baseline recorded",
        "description": (
            "These routes were seen for the **first time** for this journey date in `storage/state.json`. "
            "By default you will only get alerts when the trip **count changes**."
        ),
        "color": 0x3498DB,
        "fields": fields[:25],
        "footer": {"text": "Shohoz bus monitor"},
    }

    payload = {"embeds": [embed]}
    _post_json(session, webhook_url, payload)


def send_trip_change_notifications(changes: list[TripCountChange]) -> None:
    """
    Post Discord embed(s) describing trip count changes.

    Raises:
        RuntimeError: if ``DISCORD_WEBHOOK`` is missing.
        requests.HTTPError: if Discord rejects the payload.
    """

    if not changes:
        return

    webhook_url = require_discord_webhook_url()
    session = create_requests_session(total_retries=3, backoff_factor=0.75)

    # Chunk to respect Discord limits.
    for offset in range(0, len(changes), _MAX_EMBEDS_PER_MESSAGE):
        chunk = changes[offset : offset + _MAX_EMBEDS_PER_MESSAGE]
        payload = {"embeds": [_build_embed(change) for change in chunk]}
        _post_json(session, webhook_url, payload)


def _post_json(session: requests.Session, webhook_url: str, payload: dict[str, Any]) -> None:
    url = _execute_webhook_url(webhook_url)
    try:
        response = session.post(
            url,
            json=payload,
            timeout=default_timeout(),
        )
    except requests.RequestException as exc:
        raise RuntimeError(f"Discord webhook request failed: {exc}") from exc

    if response.status_code not in (200, 204):
        snippet = response.text[:500]
        raise RuntimeError(
            f"Discord webhook rejected the payload: HTTP {response.status_code}. Snippet: {snippet!r}"
        )

    embeds = payload.get("embeds")
    if isinstance(embeds, list):
        _LOG.info("Discord webhook OK (HTTP %s, embeds=%s).", response.status_code, len(embeds))
    else:
        _LOG.info("Discord webhook OK (HTTP %s).", response.status_code)

    if response.status_code == 200 and response.content:
        try:
            body = response.json()
            msg_id = body.get("id")
            channel_id = body.get("channel_id")
            if msg_id:
                _LOG.info("Discord message id=%s channel_id=%s", msg_id, channel_id)
        except ValueError:
            _LOG.debug("Discord returned 200 but body was not JSON; skipping message id log.")


def _build_embed(change: TripCountChange) -> dict[str, Any]:
    delta = change.current_count - change.previous_count
    if delta > 0:
        status_icon = "📈"
        movement = f"Trips increased from **{change.previous_count}** to **{change.current_count}**"
        color = 0x2ECC71
    elif delta < 0:
        status_icon = "📉"
        movement = f"Trips decreased from **{change.previous_count}** to **{change.current_count}**"
        color = 0xE74C3C
    else:
        # Should not happen (we only enqueue on change), but keep the embed sane.
        status_icon = "➖"
        movement = f"Trip count unchanged at **{change.current_count}**"
        color = 0x95A5A6

    route_label = f"{change.from_city} → {change.to_city}"
    checked_at = datetime.now(timezone.utc)
    checked_at_str = checked_at.strftime("%Y-%m-%d %H:%M:%S UTC")
    embed_timestamp = checked_at.isoformat(timespec="seconds").replace("+00:00", "Z")

    return {
        "title": f"{status_icon} Shohoz trip count update",
        "description": f"{movement} for **{route_label}**.",
        "color": color,
        "timestamp": embed_timestamp,
        "fields": [
            {"name": "Route", "value": f"`{change.from_city}` → `{change.to_city}`", "inline": True},
            {"name": "Trip count", "value": str(change.current_count), "inline": True},
            {"name": "Previous count", "value": str(change.previous_count), "inline": True},
            {"name": "Journey date", "value": change.journey_date, "inline": True},
            {"name": "Checked at", "value": checked_at_str, "inline": False},
            {"name": "Status", "value": f"{status_icon} {'+' if delta > 0 else ''}{delta} vs last run", "inline": True},
        ],
        "footer": {"text": "Shohoz bus monitor"},
    }
