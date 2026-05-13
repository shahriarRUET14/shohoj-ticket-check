"""Shared constants for Shohoz API integration."""

SHOHOZ_SEARCH_TRIPS_URL = "https://webapi.shohoz.com/v1.0/web/booking/bus/search-trips"

# Headers mirror a typical browser XHR call to reduce accidental blocking.
DEFAULT_SHOHOZ_HEADERS: dict[str, str] = {
    "Referer": "https://www.shohoz.com/",
    "X-Requested-With": "XMLHttpRequest",
    "User-Agent": "Mozilla/5.0",
    "Accept": "application/json",
    "Content-Type": "application/json",
}

# Environment variable names used across the app.
ENV_DISCORD_WEBHOOK = "DISCORD_WEBHOOK"
ENV_OVERRIDE_DATE = "OVERRIDE_DATE"
# Optional: send a one-shot plain message then exit 0 (verifies webhook URL + channel).
ENV_DISCORD_TEST_MESSAGE = "DISCORD_TEST_MESSAGE"
# Optional: send an embed the first time each route/date key is seen (default is change-only).
ENV_NOTIFY_ON_BASELINE = "NOTIFY_ON_BASELINE"

# Default relative path for persisted counts (repo root is cwd in Actions and typical local runs).
DEFAULT_STATE_PATH = "storage/state.json"
