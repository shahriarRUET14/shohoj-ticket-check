# Changelog

All changes to this project will be documented in this file.

## [Unreleased]

- Add Shohoz bus trip monitor with hourly GitHub Actions, Discord embed alerts on count changes, and JSON state storage (by shahriarmahmud, 2026-05-14)
- Load `.env` automatically in `main.py` using python-dotenv so local runs pick up `DISCORD_WEBHOOK` without manual exports (by shahriarmahmud, 2026-05-14)
- Clarify Discord change-only behavior, add optional baseline + test webhook env flags, and improve webhook logging (by shahriarmahmud, 2026-05-14)
