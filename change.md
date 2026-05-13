# Changelog

All changes to this project will be documented in this file.

## [Unreleased]

- Add Shohoz bus trip monitor with hourly GitHub Actions, Discord embed alerts on count changes, and JSON state storage (by shahriarmahmud, 2026-05-14)
- Load `.env` automatically in `main.py` using python-dotenv so local runs pick up `DISCORD_WEBHOOK` without manual exports (by shahriarmahmud, 2026-05-14)
- Fix GitHub Actions workflow YAML (broken `run` block) and harden deployment: Python version echo, secret presence check, `actions: write` for cache, clearer README deploy guide (by shahriarmahmud, 2026-05-14)
- Add configurable boolean `DISCORD_NOTIFY_EVERY_CHECK` (every check vs change-only) with legacy `DISCORD_REPORT_EVERY_RUN` alias (by shahriarmahmud, 2026-05-14)
