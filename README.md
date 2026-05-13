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
- **`.github/workflows/shohoz-bus-monitor.yml`**: Ubuntu + Python 3.11, pip install, optional secret check, `main.py`, cache for `storage/state.json`, log artifact on failure.

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
| `DISCORD_WEBHOOK` | Yes (for Discord) | Incoming webhook URL; required in CI when summaries are enabled |
| `OVERRIDE_DATE` | No | Forces journey date for all routes, format **`DD-MMM-YYYY`** (example: `30-May-2026`) |
| `DISCORD_TEST_MESSAGE` | No | Set to `1` / `true` / `yes` to send a **one-shot** test message and exit (then remove it) |
| `NOTIFY_ON_BASELINE` | No | Set to `1` / `true` / `yes` to also notify the **first** time each route+date is stored (usually leave **off** if you use per-run summaries) |
| `DISCORD_NOTIFY_EVERY_CHECK` | No | **`true`** / **`1`** (default when unset): Discord **summary on every successful run** with current trip counts. **`false`** / **`0`**: Discord **only when a trip count changes** (and optional baseline if enabled). |
| `DISCORD_REPORT_EVERY_RUN` | No | **Legacy alias** for `DISCORD_NOTIFY_EVERY_CHECK`; used only if `DISCORD_NOTIFY_EVERY_CHECK` is unset or empty. |

## Shohoz API (reference)

- **GET** `https://webapi.shohoz.com/v1.0/web/booking/bus/search-trips`
- **Query params**: `from_city`, `to_city`, `date_of_journey` (**`DD-MMM-YYYY`**), `dor=` (empty)
- **Headers**: see `src/constants.py` (`Referer`, `X-Requested-With`, `User-Agent`, JSON accept/content types)

## Deploy with GitHub Actions (beginner checklist)

The workflow file is [`.github/workflows/shohoz-bus-monitor.yml`](.github/workflows/shohoz-bus-monitor.yml). It uses **Ubuntu latest**, **Python 3.11**, installs from **`requirements.txt`**, and runs **`main.py`**. Secrets are injected only as environment variables for that job step (they are **not** printed in logs by our scripts).

### Prerequisite: Discord webhook

1. In Discord: open your server → pick a channel → **Edit Channel** → **Integrations** → **Webhooks** → **New Webhook**.
2. Copy the **Webhook URL** (`https://discord.com/api/webhooks/...`). Anyone with the URL can post to that channel—store it only in **GitHub Secrets** (or local `.env`, never commit it).

### 1) Create a GitHub repository

1. On [GitHub](https://github.com), click **+** → **New repository**.
2. Choose a name (for example `shohoj-check-tickets`), visibility, and create it.
3. If you already have this project on your computer, **do not** add a license/README on GitHub that would conflict with your first push (or pull their README first and merge).

### 2) Push your project with git

From your project folder (replace the remote URL with yours):

```bash
git init
git add .
git commit -m "feat: add shohoz trip monitor"
git branch -M main
git remote add origin https://github.com/<your-username>/<your-repo>.git
git push -u origin main
```

If the remote already exists, use `git remote set-url origin ...` instead of `git remote add`.

### 3) Enable GitHub Actions

1. Open the repo on GitHub → **Actions**.
2. If GitHub asks to enable workflows for this repository, approve it.
3. You should see the workflow **“Shohoz Bus Trip Monitor”** listed under “All workflows”.

### 4) Add repository secrets (secure)

1. Repo **Settings** → **Secrets and variables** → **Actions**.
2. **New repository secret** → name **`DISCORD_WEBHOOK`** → paste the full webhook URL → **Add secret**.
3. Optional: **New repository secret** → **`OVERRIDE_DATE`** → value like `30-May-2026` (Shohoz `DD-MMM-YYYY` format).

Secrets are **write-only** in the UI; you cannot read them back later. To rotate: edit by adding a new secret value (replace workflow reference if you rename keys).

Optional **variable** (not secret): **Settings → Secrets and variables → Actions → Variables** → **`NOTIFY_ON_BASELINE`** = `1` if you want a Discord message the first time each route+date is stored on a fresh cache (see [Environment variables](#environment-variables)).

### 5) Confirm the workflow and schedule

- **Cron** is `*/2 * * * *`: roughly **every 2 minutes** in **UTC** (minutes `0, 2, 4, …` of each hour). GitHub **does not guarantee** exact timing; jobs can start **late** when the platform is busy.
- This frequency uses **more Actions minutes** than an hourly job. For private repos or tight quotas, consider changing the cron in [`.github/workflows/shohoz-bus-monitor.yml`](.github/workflows/shohoz-bus-monitor.yml) (for example back to hourly `0 * * * *`).
- Each successful run posts a **Discord summary** when **`DISCORD_NOTIFY_EVERY_CHECK`** is true (default in CI). Set repository **Variable** `DISCORD_NOTIFY_EVERY_CHECK` to **`false`** or **`0`** for **change-only** Discord. Legacy variable **`DISCORD_REPORT_EVERY_RUN`** is still read if the primary is unset.
- If `OVERRIDE_DATE` is a **secret**, GitHub may redact that same text in logs (shown as `***`). Prefer an Actions **Variable** for dates if you need the value visible in logs.

### 6) Trigger a manual test run

1. **Actions** → **Shohoz Bus Trip Monitor**.
2. **Run workflow** → branch **main** → **Run workflow**.
3. Wait for the green checkmark or open the run if it fails.

### 7) View logs for a run

1. **Actions** → click the workflow run row.
2. Open the **monitor** job.
3. Expand each step; **`Run monitor (main.py)`** shows everything `main.py` printed (Shohoz counts, Discord summary lines).

### 8) Debug a failed run

1. Read the red **failed** step in the job log (often **Install dependencies** or **Run monitor**).
2. If the failure happened during **`Run monitor`**, download the artifact **`shohoz-monitor-log-<run id>`** (uploaded only on failure) for the full `tee` log file.
3. Typical issues: missing **`DISCORD_WEBHOOK`** when a trip-count **change** must be posted; invalid **`OVERRIDE_DATE`**; Shohoz API errors (see log lines from `src.shohoz_client`).
4. Locally reproduce with the same env: copy secrets into a local `.env` (never commit) and run `python main.py`, or use **`DISCORD_TEST_MESSAGE=1`** once in `.env` to validate the webhook (see [Environment variables](#environment-variables)).

### 9) Verify scheduled (cron) execution

1. After the first scheduled hour, open **Actions** and filter by **“Scheduled”** (or inspect each run’s title / event badge).
2. If you see no scheduled runs: default branch must be the branch in `on:` (usually **main**), Actions must be enabled, and the workflow file must be on that branch. Very new repos sometimes see the first schedule after a short delay.

### GitHub Actions free tier (practical limits)

- **Public repositories**: Actions minutes for standard hosted jobs are typically generous for a small hourly job; still read [GitHub’s billing docs](https://docs.github.com/en/billing) for your account.
- **Private repositories**: free/private minute allowances have changed over time—confirm your plan.
- **Concurrency / queueing**: many workflows in one org can queue; your job has a **15 minute** timeout.
- **Cache**: `storage/state.json` is stored in **Actions cache**, which can be **evicted** after inactivity; the next run then **re-baselines** counts (fewer “change” alerts until the API count moves again).

### Workflow reference (quick map)

| Item | Value |
|------|--------|
| Runner | `ubuntu-latest` |
| Python | `3.11` (pinned in workflow) |
| Schedule | `cron: "*/2 * * * *"` (UTC, about every 2 minutes) |
| Per-run Discord | `DISCORD_NOTIFY_EVERY_CHECK` (default **true** via workflow bash when vars unset) |
| Manual run | `workflow_dispatch` |
| Secrets → env | `DISCORD_WEBHOOK`, optional `OVERRIDE_DATE` |
| Optional variables | `NOTIFY_ON_BASELINE`, `DISCORD_NOTIFY_EVERY_CHECK` (or legacy `DISCORD_REPORT_EVERY_RUN`) |
| Artifacts | Full `monitor_run.log` uploaded **only if** the job fails |

### Troubleshooting common issues

- **No Discord messages but the script “succeeds”**: with **`DISCORD_NOTIFY_EVERY_CHECK=false`**, Discord only fires on trip-count **changes** (plus optional baseline). With **every-check** mode (default), confirm **`DISCORD_WEBHOOK`** is set and the Discord step did not fail. Check the log line **“Discord mode: …”** at startup.
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

1. **Project structure**: [Project structure](#project-structure)
2. **Run locally**: [Run locally](#run-locally)
3. **Install dependencies**: [Install dependencies (local)](#install-dependencies-local)
4. **Discord webhook**: [Prerequisite: Discord webhook](#prerequisite-discord-webhook)
5. **Create GitHub repo**: [1) Create a GitHub repository](#1-create-a-github-repository)
6. **Push with git**: [2) Push your project with git](#2-push-your-project-with-git)
7. **Enable Actions**: [3) Enable GitHub Actions](#3-enable-github-actions)
8. **Add secrets**: [4) Add repository secrets (secure)](#4-add-repository-secrets-secure)
9. **Cron / schedule**: [5) Confirm the workflow and schedule](#5-confirm-the-workflow-and-schedule)
10. **Free tier**: [GitHub Actions free tier (practical limits)](#github-actions-free-tier-practical-limits)
11. **Debug failures**: [8) Debug a failed run](#8-debug-a-failed-run)
12. **Manual run**: [6) Trigger a manual test run](#6-trigger-a-manual-test-run)
13. **Troubleshooting**: [Troubleshooting common issues](#troubleshooting-common-issues)

## License

Add a license file if you plan to open-source this repository publicly.
