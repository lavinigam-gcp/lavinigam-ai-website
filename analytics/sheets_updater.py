"""Google Sheets API client and Analytics tab bootstrapper.

Provides helpers to build the Sheets service, locate or create the
Analytics tab, and exposes the shared constants (color palette,
column headers, spreadsheet ID) used by all subsequent tasks.
"""

import json
import os
import re
import subprocess
import sys
from collections import defaultdict
from datetime import datetime

from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    FilterExpressionList,
    Metric,
    OrderBy,
    RunReportRequest,
)
from googleapiclient.discovery import build

from analytics.auth import get_credentials
from analytics.config import (
    EXCLUDED_SLUGS,
    GA4_PROPERTY,
    POSTS_PATH_PREFIX,
    SHEETS_SPREADSHEET_ID as SPREADSHEET_ID,
)

SHEET_NAME = "sprint1-analytics"

# Template for section header rows inserted before each period's data.
# Callers substitute {period} with a human-readable label, e.g. "Last 28 Days".
SECTION_MARKER = "── {period} Performance"
DOC_CLICKS_MARKER = "── {period} Doc Referrals"
DOC_CLICKS_HEADERS_LEFT = ["Post", "ADK Docs Page", "Clicks"]
DOC_CLICKS_HEADERS_RIGHT = ["Post", "Source Code Repo", "Clicks"]
ADK_LINK_DOMAINS = [
    "google.github.io/adk-docs",               # ADK docs
    "github.com/lavinigam-gcp/build-with-adk", # code samples repo
]
DOC_CLICKS_RIGHT_START = 4  # column E (0-indexed), after gap column D
DOC_CLICKS_TOTAL_COLS = 7   # A-G spans both tables + gap
MIN_METRICS_ROWS = 15  # minimum gap rows reserved below metrics section

# ---------------------------------------------------------------------------
# Color palette (RGB values on 0–1 scale)
# ---------------------------------------------------------------------------

COLOR_TITLE_BG = {"red": 0.118, "green": 0.227, "blue": 0.373}
COLOR_SECTION_BG = {"red": 0.102, "green": 0.451, "blue": 0.910}
COLOR_HEADER_BG = {"red": 0.910, "green": 0.941, "blue": 0.996}
COLOR_ROW_ALT = {"red": 0.973, "green": 0.976, "blue": 0.980}
COLOR_WHITE = {"red": 1.0, "green": 1.0, "blue": 1.0}
COLOR_WHITE_TEXT = COLOR_WHITE
COLOR_DARK_TEXT = {"red": 0.2, "green": 0.2, "blue": 0.2}
COLOR_GREEN = {"red": 0.714, "green": 0.843, "blue": 0.659}
COLOR_YELLOW = {"red": 1.0, "green": 0.949, "blue": 0.8}
COLOR_RED = {"red": 0.957, "green": 0.800, "blue": 0.800}

# ---------------------------------------------------------------------------
# Column layout
# ---------------------------------------------------------------------------

COLUMN_HEADERS = [
    "Post",
    "Views",
    "Sessions",
    "Users",
    "New Users",
    "Engagement %",
    "Bounce %",
    "Avg Duration (s)",
    "Pages/Session",
    "Engaged Sessions",
    "Events",
    "Top Countries",
    "Desktop %",
    "Mobile %",
]

NUM_COLS = len(COLUMN_HEADERS)  # 14


# ---------------------------------------------------------------------------
# Service factory
# ---------------------------------------------------------------------------

def _get_service():
    """Return an authenticated Google Sheets v4 service resource."""
    return build("sheets", "v4", credentials=get_credentials())


# ---------------------------------------------------------------------------
# Sheet-ID lookup
# ---------------------------------------------------------------------------

def _get_sheet_id(service) -> int | None:
    """Return the sheetId of SHEET_NAME, or None if it does not exist."""
    meta = (
        service.spreadsheets()
        .get(spreadsheetId=SPREADSHEET_ID, fields="sheets.properties")
        .execute()
    )
    for sheet in meta.get("sheets", []):
        props = sheet.get("properties", {})
        if props.get("title") == SHEET_NAME:
            return props["sheetId"]
    return None


# ---------------------------------------------------------------------------
# Tab bootstrap
# ---------------------------------------------------------------------------

def ensure_analytics_tab(service) -> int:
    """Ensure the Analytics tab exists; create it if missing.

    Returns the integer sheetId of the Analytics tab (idempotent — safe
    to call multiple times).
    """
    sheet_id = _get_sheet_id(service)
    if sheet_id is not None:
        return sheet_id

    response = (
        service.spreadsheets()
        .batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={
                "requests": [
                    {
                        "addSheet": {
                            "properties": {
                                "title": SHEET_NAME,
                            }
                        }
                    }
                ]
            },
        )
        .execute()
    )

    new_sheet_id: int = response["replies"][0]["addSheet"]["properties"]["sheetId"]
    return new_sheet_id


# ---------------------------------------------------------------------------
# Section layout manager
# ---------------------------------------------------------------------------

def _read_col_a(service) -> list[str]:
    """Read all values in column A of the Analytics tab."""
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A:A"
    ).execute()
    return [row[0] if row else "" for row in result.get("values", [])]


def find_section_start(service, period: str) -> int | None:
    """Return 0-indexed row of the section header for `period`, or None."""
    marker = SECTION_MARKER.format(period=period)
    col_a = _read_col_a(service)
    for i, cell in enumerate(col_a):
        if cell.startswith(marker):
            return i
    return None


def _find_section_end(col_a: list[str], start: int) -> int:
    """Return 0-indexed row just past the last data row of the section."""
    for i in range(start + 1, len(col_a)):
        if col_a[i].startswith("──"):  # next section header
            return i
    return len(col_a)


def clear_section(service, sheet_id: int, period: str) -> int | None:
    """Delete the rows of an existing period section. Returns start row or None if not found."""
    col_a = _read_col_a(service)
    marker = SECTION_MARKER.format(period=period)
    start = None
    for i, cell in enumerate(col_a):
        if cell.startswith(marker):
            start = i
            break
    if start is None:
        return None

    end = _find_section_end(col_a, start)
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{
            "deleteDimension": {
                "range": {
                    "sheetId": sheet_id,
                    "dimension": "ROWS",
                    "startIndex": start,
                    "endIndex": end,
                }
            }
        }]}
    ).execute()
    return start


def _clear_all_data(service, sheet_id: int) -> None:
    """Delete all data rows below the header, keeping title (row 1) and summary (row 2)."""
    col_a = _read_col_a(service)
    if len(col_a) <= 3:
        return
    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": [{"deleteDimension": {"range": {
            "sheetId": sheet_id,
            "dimension": "ROWS",
            "startIndex": 3,
            "endIndex": len(col_a),
        }}}]},
    ).execute()


def next_available_row(service) -> int:
    """Return 0-indexed index of first row to insert a new section."""
    col_a = _read_col_a(service)
    for i in range(len(col_a) - 1, -1, -1):
        if col_a[i].strip():
            return i + 2  # +1 for blank separator, +1 for next row
    return 3  # Default: after title (row 0), summary (row 1), blank (row 2)


# ---------------------------------------------------------------------------
# Section data builder and writer
# ---------------------------------------------------------------------------

def build_section_rows(
    period: str,
    start_date: str,
    end_date: str,
    overview_rows: list[dict],
    geo_summary: dict,
) -> list[list]:
    """Build the list of rows to write for a period section.

    Returns: [section_header_row, column_headers_row, ...data_rows]
    """
    section_header = f"{SECTION_MARKER.format(period=period)} ({start_date} → {end_date})"

    data_rows = []
    for row in overview_rows:
        path = row.get("pagePath", "")
        geo = geo_summary.get(path, {})
        dur = float(row.get("averageSessionDuration", 0))
        data_rows.append([
            path,
            row.get("screenPageViews", ""),
            row.get("sessions", ""),
            row.get("totalUsers", ""),
            row.get("newUsers", ""),
            round(float(row.get("engagementRate", 0)), 2),
            round(float(row.get("bounceRate", 0)), 2),
            round(dur, 1),
            round(float(row.get("screenPageViewsPerSession", 0)), 2),
            row.get("engagedSessions", ""),
            row.get("eventCount", ""),
            geo.get("topCountries", ""),
            geo.get("desktopPct", ""),
            geo.get("mobilePct", ""),
        ])

    return [[section_header]] + [COLUMN_HEADERS] + data_rows


def write_section_data(service, insert_row: int, rows: list[list]) -> None:
    """Write rows starting at insert_row (0-indexed) into the Analytics tab."""
    start_a1 = f"{SHEET_NAME}!A{insert_row + 1}"
    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=start_a1,
        valueInputOption="USER_ENTERED",
        body={"values": rows},
    ).execute()


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _cell_range(sheet_id: int, row_start: int, row_end: int,
                col_start: int = 0, col_end: int | None = None) -> dict:
    """Build a GridRange dict (all indices 0-based, end exclusive)."""
    r = {
        "sheetId": sheet_id,
        "startRowIndex": row_start,
        "endRowIndex": row_end,
        "startColumnIndex": col_start,
    }
    if col_end is not None:
        r["endColumnIndex"] = col_end
    return r


def _repeat_cell(sheet_id: int, row: int, col_start: int, col_end: int,
                 bg: dict, fg: dict, bold: bool = False, font_size: int = 10) -> dict:
    """Build a RepeatCellRequest for a single row range."""
    return {
        "repeatCell": {
            "range": _cell_range(sheet_id, row, row + 1, col_start, col_end),
            "cell": {"userEnteredFormat": {
                "backgroundColor": bg,
                "textFormat": {"foregroundColor": fg, "bold": bold, "fontSize": font_size},
            }},
            "fields": "userEnteredFormat(backgroundColor,textFormat)",
        }
    }


def format_section(service, sheet_id: int, insert_row: int, num_data_rows: int) -> None:
    """Apply all visual formatting for a section starting at insert_row."""
    section_row = insert_row          # section header row
    col_hdr_row = insert_row + 1      # column header row
    data_start  = insert_row + 2      # first data row
    data_end    = data_start + num_data_rows

    requests = [
        # Section header: blue bg, white bold text.
        _repeat_cell(sheet_id, section_row, 0, NUM_COLS,
                     COLOR_SECTION_BG, COLOR_WHITE_TEXT, bold=True),
        # Merge section header across all columns.
        {"mergeCells": {
            "range": _cell_range(sheet_id, section_row, section_row + 1, 0, NUM_COLS),
            "mergeType": "MERGE_ALL",
        }},
        # Column header row: light blue bg, dark bold text.
        _repeat_cell(sheet_id, col_hdr_row, 0, NUM_COLS,
                     COLOR_HEADER_BG, COLOR_DARK_TEXT, bold=True),
    ]

    # Alternating data row colors.
    for i in range(num_data_rows):
        row = data_start + i
        bg = COLOR_WHITE if i % 2 == 0 else COLOR_ROW_ALT
        requests.append(_repeat_cell(sheet_id, row, 0, NUM_COLS, bg, COLOR_DARK_TEXT))

    # Column widths: post column wider, metric columns narrower.
    requests += [
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": 0, "endIndex": 1},
            "properties": {"pixelSize": 280},
            "fields": "pixelSize",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": 1, "endIndex": NUM_COLS},
            "properties": {"pixelSize": 90},
            "fields": "pixelSize",
        }},
    ]

    # Conditional formatting: engagementRate (column F = index 5).
    eng_range = _cell_range(sheet_id, data_start, data_end, 5, 6)
    requests += [
        {"addConditionalFormatRule": {"rule": {
            "ranges": [eng_range],
            "booleanRule": {
                "condition": {"type": "NUMBER_GREATER_THAN_EQ",
                              "values": [{"userEnteredValue": "0.6"}]},
                "format": {"backgroundColor": COLOR_GREEN},
            },
        }, "index": 0}},
        {"addConditionalFormatRule": {"rule": {
            "ranges": [eng_range],
            "booleanRule": {
                "condition": {"type": "NUMBER_BETWEEN",
                              "values": [{"userEnteredValue": "0.4"},
                                         {"userEnteredValue": "0.6"}]},
                "format": {"backgroundColor": COLOR_YELLOW},
            },
        }, "index": 1}},
        {"addConditionalFormatRule": {"rule": {
            "ranges": [eng_range],
            "booleanRule": {
                "condition": {"type": "NUMBER_LESS",
                              "values": [{"userEnteredValue": "0.4"}]},
                "format": {"backgroundColor": COLOR_RED},
            },
        }, "index": 2}},
    ]

    # Conditional formatting: bounceRate (column G = index 6).
    bounce_range = _cell_range(sheet_id, data_start, data_end, 6, 7)
    requests += [
        {"addConditionalFormatRule": {"rule": {
            "ranges": [bounce_range],
            "booleanRule": {
                "condition": {"type": "NUMBER_LESS_THAN_EQ",
                              "values": [{"userEnteredValue": "0.4"}]},
                "format": {"backgroundColor": COLOR_GREEN},
            },
        }, "index": 3}},
        {"addConditionalFormatRule": {"rule": {
            "ranges": [bounce_range],
            "booleanRule": {
                "condition": {"type": "NUMBER_BETWEEN",
                              "values": [{"userEnteredValue": "0.4"},
                                         {"userEnteredValue": "0.6"}]},
                "format": {"backgroundColor": COLOR_YELLOW},
            },
        }, "index": 4}},
        {"addConditionalFormatRule": {"rule": {
            "ranges": [bounce_range],
            "booleanRule": {
                "condition": {"type": "NUMBER_GREATER",
                              "values": [{"userEnteredValue": "0.6"}]},
                "format": {"backgroundColor": COLOR_RED},
            },
        }, "index": 5}},
    ]

    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": requests},
    ).execute()


# ---------------------------------------------------------------------------
# Title block and summary row
# ---------------------------------------------------------------------------

def write_title_block(service, sheet_id: int) -> None:
    """Write the title row and ensure summary row exists (idempotent)."""
    result = service.spreadsheets().values().get(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A1:A3",
    ).execute()
    existing = result.get("values", [])

    title_val = "📊 Analytics Dashboard"
    # Only write if title row is missing or wrong.
    if not existing or not existing[0] or existing[0][0] != title_val:
        service.spreadsheets().values().update(
            spreadsheetId=SPREADSHEET_ID,
            range=f"{SHEET_NAME}!A1",
            valueInputOption="USER_ENTERED",
            body={"values": [[title_val], [""], [""]]},
        ).execute()
        service.spreadsheets().batchUpdate(
            spreadsheetId=SPREADSHEET_ID,
            body={"requests": [
                _repeat_cell(sheet_id, 0, 0, NUM_COLS,
                             COLOR_TITLE_BG, COLOR_WHITE_TEXT, bold=True, font_size=14),
                {"mergeCells": {
                    "range": _cell_range(sheet_id, 0, 1, 0, NUM_COLS),
                    "mergeType": "MERGE_ALL",
                }},
                {"updateSheetProperties": {
                    "properties": {
                        "sheetId": sheet_id,
                        "gridProperties": {"frozenRowCount": 1},
                    },
                    "fields": "gridProperties.frozenRowCount",
                }},
            ]},
        ).execute()


def update_summary_row(service, period: str, start_date: str, end_date: str) -> None:
    """Update row 2 with a simple last-updated date."""
    summary = f"Last updated: {datetime.now().strftime('%b %-d, %Y')}"

    service.spreadsheets().values().update(
        spreadsheetId=SPREADSHEET_ID,
        range=f"{SHEET_NAME}!A2",
        valueInputOption="USER_ENTERED",
        body={"values": [[summary]]},
    ).execute()


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

def _fetch_analytics_json(period: str) -> dict | None:
    """Run analytics.report --format json and return parsed JSON output."""
    result = subprocess.run(
        [sys.executable, "-m", "analytics.report",
         "--source", "ga4", "--format", "json", "--period", period],
        capture_output=True,
        text=True,
        env={**os.environ, "PYTHONPATH": "."},
    )
    if result.returncode != 0:
        print(f"analytics.report failed (exit {result.returncode}):")
        if result.stderr:
            print(result.stderr.strip())
        return None
    # analytics.report (via rich) may prepend a header line and ANSI codes.
    # Strip ANSI codes and find the JSON object.
    clean = re.sub(r"\x1b\[[0-9;]*m", "", result.stdout)
    try:
        start = clean.index("{")
        return json.loads(clean[start:])
    except (ValueError, json.JSONDecodeError):
        return None


_CLEAN_SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9-]*[a-z0-9]$")


def _is_valid_post_path(path: str) -> bool:
    """Return True if path is a clean, non-excluded blog post path."""
    if not path.startswith(POSTS_PATH_PREFIX) or path == POSTS_PATH_PREFIX:
        return False
    slug = path.removeprefix(POSTS_PATH_PREFIX).strip("/")
    return bool(_CLEAN_SLUG_RE.match(slug)) and slug not in EXCLUDED_SLUGS


def _build_geo_summary(geo_rows: list[dict]) -> dict:
    """Build per-post geo/device summary dict keyed by pagePath."""
    by_post: dict[str, list[dict]] = defaultdict(list)
    for row in geo_rows:
        by_post[row.get("pagePath", "")].append(row)

    summary = {}
    for path, rows in by_post.items():
        total = sum(float(r.get("sessions", 0)) for r in rows)
        countries: dict[str, float] = defaultdict(float)
        devices: dict[str, float] = defaultdict(float)
        for r in rows:
            s = float(r.get("sessions", 0))
            c = r.get("country", "")
            d = r.get("deviceCategory", "")
            if c:
                countries[c] += s
            if d:
                devices[d] += s
        top3 = sorted(countries.items(), key=lambda x: -x[1])[:3]
        country_str = (
            ", ".join(f"{c} ({s / total * 100:.0f}%)" for c, s in top3)
            if total > 0 else ""
        )
        summary[path] = {
            "topCountries": country_str,
            "desktopPct": f"{devices.get('desktop', 0) / total * 100:.1f}" if total else "0",
            "mobilePct":  f"{devices.get('mobile',  0) / total * 100:.1f}" if total else "0",
        }
    return summary


def _fetch_doc_clicks(start_date: str, end_date: str) -> list[dict]:
    """Fetch outbound click events to ADK docs from GA4, grouped by post + URL."""
    client = BetaAnalyticsDataClient(credentials=get_credentials())
    req = RunReportRequest(
        property=GA4_PROPERTY,
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="pagePath"), Dimension(name="linkUrl")],
        metrics=[Metric(name="eventCount")],
        dimension_filter=FilterExpression(
            and_group=FilterExpressionList(expressions=[
                FilterExpression(filter=Filter(
                    field_name="eventName",
                    string_filter=Filter.StringFilter(value="click", match_type="EXACT"),
                )),
                FilterExpression(
                    or_group=FilterExpressionList(expressions=[
                        FilterExpression(filter=Filter(
                            field_name="linkUrl",
                            string_filter=Filter.StringFilter(
                                value=domain, match_type="CONTAINS"
                            ),
                        ))
                        for domain in ADK_LINK_DOMAINS
                    ])
                ),
            ])
        ),
        order_bys=[OrderBy(metric=OrderBy.MetricOrderBy(metric_name="eventCount"), desc=True)],
        limit=50,
    )
    resp = client.run_report(req)
    return [
        {
            "pagePath": row.dimension_values[0].value,
            "linkUrl": row.dimension_values[1].value,
            "clicks": int(row.metric_values[0].value),
        }
        for row in resp.rows
        if _is_valid_post_path(row.dimension_values[0].value)
    ]


def _split_clicks_by_domain(click_rows: list[dict]) -> tuple[list[dict], list[dict]]:
    """Split click rows into (adk_docs, source_code) by domain."""
    docs, code = [], []
    for r in click_rows:
        if "google.github.io/adk-docs" in r["linkUrl"]:
            docs.append(r)
        else:
            code.append(r)
    return docs, code


def _clicks_to_rows(click_rows: list[dict]) -> list[list]:
    """Convert click dicts to [post, url, clicks] rows."""
    return [
        [r["pagePath"], r["linkUrl"].replace("https://", ""), r["clicks"]]
        for r in click_rows
    ]


def write_doc_clicks_section(
    service, sheet_id: int,
    metrics_insert_row: int, num_metric_rows: int,
    period: str, start_date: str, end_date: str,
    click_rows: list[dict],
) -> None:
    """Write side-by-side Doc Referrals tables below the metrics section."""
    gap = max(num_metric_rows, MIN_METRICS_ROWS)
    insert_row = metrics_insert_row + 2 + gap + 1

    docs_rows, code_rows = _split_clicks_by_domain(click_rows)
    left_data = _clicks_to_rows(docs_rows)
    right_data = _clicks_to_rows(code_rows)
    max_data = max(len(left_data), len(right_data))

    # Section header (merged across both tables)
    header = f"{DOC_CLICKS_MARKER.format(period=period)} ({start_date} → {end_date})"
    hdr_row = insert_row
    col_hdr_row = insert_row + 1
    data_start = insert_row + 2

    # Build left table rows: header + column headers + data (padded)
    left_rows = [[header]] + [DOC_CLICKS_HEADERS_LEFT]
    for i in range(max_data):
        left_rows.append(left_data[i] if i < len(left_data) else ["", "", ""])

    # Build right table rows: empty (header is merged) + column headers + data
    right_rows = [[""]] + [DOC_CLICKS_HEADERS_RIGHT]
    for i in range(max_data):
        right_rows.append(right_data[i] if i < len(right_data) else ["", "", ""])

    # Write both tables
    left_range = f"{SHEET_NAME}!A{hdr_row + 1}"
    right_range = f"{SHEET_NAME}!E{hdr_row + 1}"
    service.spreadsheets().values().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={
            "valueInputOption": "USER_ENTERED",
            "data": [
                {"range": left_range, "values": left_rows},
                {"range": right_range, "values": right_rows},
            ],
        },
    ).execute()

    # Formatting
    rs = DOC_CLICKS_RIGHT_START  # 4 = column E
    requests = [
        # Section header: blue bg, white bold, merged across A-G
        _repeat_cell(sheet_id, hdr_row, 0, DOC_CLICKS_TOTAL_COLS,
                     COLOR_SECTION_BG, COLOR_WHITE_TEXT, bold=True),
        {"mergeCells": {
            "range": _cell_range(sheet_id, hdr_row, hdr_row + 1, 0, DOC_CLICKS_TOTAL_COLS),
            "mergeType": "MERGE_ALL",
        }},
        # Left column headers (A-C)
        _repeat_cell(sheet_id, col_hdr_row, 0, 3,
                     COLOR_HEADER_BG, COLOR_DARK_TEXT, bold=True),
        # Right column headers (E-G)
        _repeat_cell(sheet_id, col_hdr_row, rs, rs + 3,
                     COLOR_HEADER_BG, COLOR_DARK_TEXT, bold=True),
    ]

    # Alternating row colors for both tables
    for i in range(max_data):
        row = data_start + i
        bg = COLOR_WHITE if i % 2 == 0 else COLOR_ROW_ALT
        requests.append(_repeat_cell(sheet_id, row, 0, 3, bg, COLOR_DARK_TEXT))
        requests.append(_repeat_cell(sheet_id, row, rs, rs + 3, bg, COLOR_DARK_TEXT))

    # Column widths: post cols wider, URL cols wider, clicks narrow
    requests += [
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": 1, "endIndex": 2},
            "properties": {"pixelSize": 300},
            "fields": "pixelSize",
        }},
        {"updateDimensionProperties": {
            "range": {"sheetId": sheet_id, "dimension": "COLUMNS",
                      "startIndex": rs + 1, "endIndex": rs + 2},
            "properties": {"pixelSize": 300},
            "fields": "pixelSize",
        }},
    ]

    service.spreadsheets().batchUpdate(
        spreadsheetId=SPREADSHEET_ID,
        body={"requests": requests},
    ).execute()


def update_analytics_sheet(period: str = "7d") -> None:
    """Main entry point. Fetch GA4 data and upsert the period section in the Analytics tab."""
    print(f"Fetching GA4 data for period: {period}...")
    data = _fetch_analytics_json(period)
    if not data or not data.get("ga4", {}).get("overview"):
        print("No GA4 data returned. Sheet not updated.")
        return

    start_date  = data.get("startDate", "")
    end_date    = data.get("endDate", "")
    overview    = [r for r in data["ga4"]["overview"]
                   if _is_valid_post_path(r.get("pagePath", ""))]
    geo_rows    = data["ga4"].get("geo_device", [])
    geo_summary = _build_geo_summary(geo_rows)

    print("Connecting to Google Sheets...")
    service  = _get_service()
    sheet_id = ensure_analytics_tab(service)

    # Write title block (idempotent — skips if already present).
    write_title_block(service, sheet_id)

    # Clear all existing data sections — only one set of metrics + doc
    # referrals should exist at a time, regardless of period key.
    _clear_all_data(service, sheet_id)
    insert_row = 3  # Start right after title(0), summary(1), blank(2)

    # Write data rows.
    rows = build_section_rows(period, start_date, end_date, overview, geo_summary)
    print(f"Writing {len(rows)} rows at sheet row {insert_row + 1}...")
    write_section_data(service, insert_row, rows)

    # Apply formatting.
    num_data_rows = len(overview)
    print("Applying formatting...")
    format_section(service, sheet_id, insert_row, num_data_rows)

    # Fetch and write doc referrals section (ADK docs + build-with-adk clicks).
    print("Fetching doc referral clicks...")
    click_rows = _fetch_doc_clicks(start_date, end_date)
    if click_rows:
        write_doc_clicks_section(
            service, sheet_id, insert_row, num_data_rows,
            period, start_date, end_date, click_rows,
        )
        print(f"Doc referrals: {len(click_rows)} rows written.")
    else:
        print("No doc referral clicks found for this period.")

    # Update summary row.
    update_summary_row(service, period, start_date, end_date)

    print(f"Done. Analytics tab updated for period: {period}")
    print(f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")
