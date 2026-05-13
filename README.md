# Shohoz Bus Trip Monitor (Python + GitHub Actions)

This repository contains a small, production-minded Python monitor that:

- Calls the Shohoz bus **search-trips** API for one or more routes (`config.json`)
- Counts trips returned (`data.trips.list`)
- Persists the last observed counts in `storage/state.json`
- Sends a **Discord webhook embed** only when a route’s trip count **changes** compared to the last successful run for the same **journey date**

It is designed to run locally or on **GitHub Actions** using a **free** hosted runner.

## Project structure

```text
.
├── .env.example                 # Documents required/optional environment variables
├── .github/
│   └── workflows/
│       └── shohoz-bus-monitor.yml  # Hourly + manual GitHub Actions workflow
├── .gitignore                   # Ignores secrets, venvs, and runtime state JSON
├── change.md                    # Changelog entries for this repository
├── config.json                  # Monitored routes (from_city / to_city)
├── main.py                      # Thin orchestrator (logging + wiring)
├── README.md                    # Setup + operations guide (this file)
├── requirements.txt             # Python dependencies (pinned loosely)
├── src/                         # Modular library code
│   ├── __init__.py
│   ├── constants.py             # API URL, headers, env var names, default paths
│   ├── config_loader.py         # Loads/validates config.json into typed route objects
│   ├── date_utils.py            # Shohoz date formatting + OVERRIDE_DATE validation
│   ├── discord_notifier.py      # Builds embed payloads and posts to Discord
│   ├── http_client.py           # requests.Session + urllib3 retry policy
│   ├── shohoz_client.py         # Shohoz API call + safe JSON parsing
│   └── storage.py               # JSON persistence helpers for last-known counts
└── storage/
    ├── .gitkeep                 # Ensures the directory exists in git
    └── state.json               # Created at runtime (ignored by git)
```

### What each important file does (brief)

- **`main.py`**: loads `.env` from the repo root, configures logging, loads routes + state, fetches counts, applies the “baseline vs change” rules, sends Discord only after successful delivery for changes, persists JSON state.
- **`src/shohoz_client.py`**: performs the GET request and extracts `len(data.trips.list)` defensively.
- **`src/http_client.py`**: centralizes retry behavior for transient HTTP failures.
- **`src/date_utils.py`**: formats dates as **`DD-MMM-YYYY`** and validates `OVERRIDE_DATE`.
- **`src/storage.py`**: reads/writes `storage/state.json` with a small versioned schema.
- **`src/discord_notifier.py`**: formats **embeds** (route, counts, journey date, timestamp, status icon).
- **`.github/workflows/shohoz-bus-monitor.yml`**: installs dependencies, restores/saves cached state, runs `main.py`, uploads logs on failure.

## Prerequisites

- **Python 3.11+** locally (GitHub Actions pins **3.11**)
- A **Discord webhook** URL (only required when a trip-count change should be posted)

## Install dependencies (local)

From the repository root:

```bash
python3.11 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run locally

1. Copy `.env.example` to `.env` in the **repository root** (same folder as `main.py`) and set `DISCORD_WEBHOOK` there. `main.py` loads `.env` automatically via **python-dotenv** (you can still `export` variables in your shell if you prefer).
2. Ensure `config.json` contains your routes.
3. Install dependencies (includes `python-dotenv`), then run:

```bash
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Optional: override the journey date in `.env` instead of exporting:

```bash
# In .env
OVERRIDE_DATE=30-May-2026
```

Notes:

- On the **first observation** for a `(from_city, to_city, journey_date)` key, the monitor **stores a baseline** and **does not** notify Discord (there is no previous value to compare against).
- If the trip count **does not change**, Discord is **not** notified.
- If the trip count **changes**, Discord receives an **embed** describing the delta (example: “Trips increased from **12** to **18**”).

## Environment variables

| Variable | Required | Purpose |
|---|---:|---|
| `DISCORD_WEBHOOK` | Yes (when changes occur) | Discord incoming webhook URL |
| `OVERRIDE_DATE` | No | Forces journey date for all routes, format **`DD-MMM-YYYY`** (example: `30-May-2026`) |
| `DISCORD_TEST_MESSAGE` | No | Set to `1` / `true` / `yes` to send a **one-shot** test message and exit (then remove it) |
| `NOTIFY_ON_BASELINE` | No | Set to `1` / `true` / `yes` to also notify the **first** time each route+date is stored |

## Shohoz API (reference)

- **GET** `https://webapi.shohoz.com/v1.0/web/booking/bus/search-trips`
- **Query params**: `from_city`, `to_city`, `date_of_journey` (**`DD-MMM-YYYY`**), `dor=` (empty)
- **Headers**: see `src/constants.py` (`Referer`, `X-Requested-With`, `User-Agent`, JSON accept/content types)

## GitHub Actions deployment (free tier)

This workflow runs hourly and supports manual runs.

### 1) Create a Discord webhook

1. Open your Discord server → select a channel.
2. **Edit Channel** → **Integrations** → **Webhooks** → **New Webhook**.
3. Copy the **Webhook URL** (starts with `https://discord.com/api/webhooks/...`).
4. Treat it like a password: anyone with the URL can post to your channel.

### 2) Create a GitHub repository

1. On GitHub: **New repository**.
2. Choose a name (example: `shohoj-check-tickets`), set visibility, **do not** add a conflicting README if you already have one locally.
3. Create the repository.

### 3) Push code using git (first push)

From your machine (replace the URL with your repo):

```bash
git init
git add .
git commit -m "feat: add shohoz trip monitor"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

### 4) Add GitHub secrets

In GitHub: **Settings → Secrets and variables → Actions → New repository secret**

- **Secret**: `DISCORD_WEBHOOK` → paste the Discord webhook URL.
- **Secret (optional)**: `OVERRIDE_DATE` → set to a Shohoz date like `30-May-2026` (same format as production).

The workflow maps them here:

- `DISCORD_WEBHOOK: ${{ secrets.DISCORD_WEBHOOK }}`
- `OVERRIDE_DATE: ${{ secrets.OVERRIDE_DATE }}`

### 5) Enable GitHub Actions

1. Go to the **Actions** tab in your repository.
2. If prompted, enable workflows for the repo.
3. Confirm `.github/workflows/shohoz-bus-monitor.yml` appears and runs (use **Run workflow** to test).

### How the hourly cron works (and caveats)

- The workflow uses `cron: "0 * * * *"` which means **minute 0 of every hour**, in the workflow’s default timezone (**UTC** on GitHub-hosted runners).
- GitHub’s documentation notes scheduled workflows **may be delayed** during periods of high load; do not assume minute-perfect scheduling.

### GitHub free-tier limitations (practical)

- **Private repos**: GitHub Free accounts historically had limits on Actions minutes for private repositories; check GitHub’s current billing/docs for your account type.
- **Cache eviction**: this repo persists `storage/state.json` via `actions/cache`. Caches can be **evicted** after periods of inactivity; if evicted, the next run re-baselines counts (you may not get a “change” alert until a subsequent change after re-baseline).
- **Concurrency**: heavy use across many repos can queue runs.

### Debug workflow failures

1. Open **Actions** → select the failed run.
2. Expand **Run monitor (Shohoz + Discord)** logs.
3. If the job failed, download the uploaded artifact **`shohoz-monitor-run-log`** (when present).
4. Common failures:
   - Missing/invalid `DISCORD_WEBHOOK` secret when a change needs to be posted
   - Shohoz API blocked or temporarily failing (retries help, but not infinite)
   - Invalid `OVERRIDE_DATE` format

### Manually trigger the workflow

**Actions → Shohoz Bus Trip Monitor → Run workflow → Run workflow**

### Troubleshooting common issues

- **No Discord messages but the script “succeeds”**: this is normal in **change-only** mode. You only get Discord when the trip **count changes** vs `storage/state.json` for the same journey date key. The final log line explains which case happened.
- **First run for a route/date**: the monitor stores a **baseline** and (by default) does **not** ping Discord. Use **`NOTIFY_ON_BASELINE=1`** once if you want a first-hit confirmation, or **`DISCORD_TEST_MESSAGE=1`** once to prove the webhook URL reaches a channel.
- **Wrong journey date key**: state is stored per `from|to|DD-MMM-YYYY`. If you change `OVERRIDE_DATE` (or the calendar day rolls over), you get a **new** key and a new baseline cycle.
- **`Missing DISCORD_WEBHOOK`**: set it in `.env` (repo root) or GitHub Actions secrets.
- **“Invalid OVERRIDE_DATE format”**: must be like `09-May-2026` (English month abbreviations, zero-padded day).
- **Wrong timezone for “today”**: `today` is computed on the machine running Python; for an exact calendar day in a specific region, set `OVERRIDE_DATE` explicitly.

## Operational behavior (state + change detection)

State keys look like:

`Natore|Dhaka|14-May-2026`

This prevents comparing **today’s** trip list length against **yesterday’s** and generating false alerts.

## Extending the project (intentionally easy)

- Add routes in `config.json`.
- Adjust retry policy in `src/http_client.py`.
- Add new notification channels by introducing a sibling module to `src/discord_notifier.py` and calling it from `main.py`.

## Reference checklist (topics 1–13)

1. **Project structure**: see the tree in [Project structure](#project-structure) above.
2. **Run locally**: see [Run locally](#run-locally).
3. **Install dependencies**: see [Install dependencies (local)](#install-dependencies-local).
4. **Create a Discord webhook**: see [Create a Discord webhook](#1-create-a-discord-webhook).
5. **Create a GitHub repository**: see [Create a GitHub repository](#2-create-a-github-repository).
6. **Push code using git**: see [Push code using git (first push)](#3-push-code-using-git-first-push).
7. **Add GitHub secrets**: see [Add GitHub secrets](#4-add-github-secrets).
8. **Enable GitHub Actions**: see [Enable GitHub Actions](#5-enable-github-actions).
9. **How Actions cron works**: see [How the hourly cron works (and caveats)](#how-the-hourly-cron-works-and-caveats).
10. **Free-tier limitations**: see [GitHub free-tier limitations (practical)](#github-free-tier-limitations-practical).
11. **Debug workflow failures**: see [Debug workflow failures](#debug-workflow-failures).
12. **Manual workflow trigger**: see [Manually trigger the workflow](#manually-trigger-the-workflow).
13. **Troubleshooting common issues**: see [Troubleshooting common issues](#troubleshooting-common-issues).

## License

Add a license file if you plan to open-source this repository publicly.
