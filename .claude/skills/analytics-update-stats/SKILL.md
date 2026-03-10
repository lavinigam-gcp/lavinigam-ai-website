---
name: analytics-update-stats
description: >
  Use when user says '/analytics-update-stats', 'update the sheet', 'push stats to sheets',
  or 'sync analytics to Google Sheets'. Fetches GA4 data and upserts a period section
  in the Analytics tab of the content tracker spreadsheet.
---

# Analytics → Google Sheets Updater

Push GA4 analytics data into the "sprint1-analytics" tab of the content tracker spreadsheet.

## Usage

Run from the project root (venv must be set up):

    make analytics-sheets [PERIOD=7d]

or directly:

    PYTHONPATH=. .venv/bin/python analytics/update_sheets.py --period {period}

## Input

Parse the period from the user's message. Default: `7d`.
Valid: `1d`, `3d`, `7d`, `14d`, `21d`, `28d`, `30d`, `90d`, `365d`

## Weekly tracking cadence

Each period overwrites only its own section — running different periods builds up a
cumulative view of post performance since tracking started:

| Week | Command | GA4 window |
|------|---------|------------|
| Week 1 | `make analytics-sheets PERIOD=7d` | last 7 days |
| Week 2 | `make analytics-sheets PERIOD=14d` | last 14 days (includes week 1) |
| Week 3 | `make analytics-sheets PERIOD=21d` | last 21 days (includes weeks 1–2) |
| Week 4 | `make analytics-sheets PERIOD=28d` | last 28 days (full month) |

After week 4, reset: run `7d` again for the next cycle. Each section stays in the sheet
until overwritten by the same period key, so at any point you can see all periods run
as separate blocks — each one a cumulative window from when you started tracking.

## What it does

1. Fetches GA4 data for the given period (all posts, filtered)
2. Upserts a section in the "Analytics" tab — clears and rewrites only this period's block
3. Applies formatting: dark title bar, blue section header, alternating rows, traffic-light
   conditional formatting on engagement rate and bounce rate
4. Updates the "updated at" summary in row 2

## After running

- Confirm success message and print the spreadsheet URL (printed by the CLI from `SHEETS_SPREADSHEET_ID` in `analytics/config.py`)
