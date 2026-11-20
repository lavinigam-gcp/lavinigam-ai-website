---
name: analytics-update-stats
description: >
  Use when user says '/analytics-update-stats', 'update the sheet', 'push stats to sheets',
  or 'sync analytics to Google Sheets'. Fetches GA4 data and refreshes the sprint1-analytics
  tab of the content tracker spreadsheet with post metrics and outbound doc referrals.
---

# Analytics → Google Sheets Updater

Push GA4 analytics data and outbound ADK doc referral clicks into the `sprint1-analytics` tab of the content tracker spreadsheet.

## Usage

Run from the project root (`.venv` must be set up):

    make analytics-sheets [PERIOD=7d]

or directly:

    PYTHONPATH=. .venv/bin/python -m analytics.update_sheets --period {period}

## Input

Parse the period from the user's message. Default: `7d`.
Valid presets: `1d`, `3d`, `7d`, `14d`, `21d`, `28d`, `30d`, `90d`, `365d`
Custom date range: `YYYY-MM-DD:YYYY-MM-DD` (e.g., `2026-03-02:2026-11-20` used by `make update-data`)

## Sheet Replacement Behavior

Each run clears existing data rows below the title block so only a single, clean snapshot of post metrics + outbound doc referral clicks exists in `sprint1-analytics` at a time:

| Cadence Option | Command | Window |
|---|---|---|
| Cumulative Sprint | `make update-data` or `make analytics-sheets PERIOD=2026-03-02:$(date +%Y-%m-%d)` | Sprint start to today |
| Rolling 7 / 14 / 28 days | `make analytics-sheets PERIOD=7d` (or `14d`, `28d`) | Trailing N days |

## What it does

1. Fetches GA4 post overview + geo/device breakdowns for the given period (filtered to valid post paths)
2. Clears prior data rows below the title block in `sprint1-analytics` while preserving the title header
3. Writes post metrics and formats header, alternating rows, and conditional engagement/bounce indicators
4. Fetches and writes the outbound ADK docs / `build-with-adk` referral clicks table alongside post metrics
5. Updates the "Last updated" summary in row 2

## After running

- Confirm success message and print the spreadsheet URL (printed by the CLI from `SHEETS_SPREADSHEET_ID` in `analytics/config.py`)
