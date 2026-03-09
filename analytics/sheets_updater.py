"""Google Sheets API client and Analytics tab bootstrapper.

Provides helpers to build the Sheets service, locate or create the
Analytics tab, and exposes the shared constants (color palette,
column headers, spreadsheet ID) used by all subsequent tasks.
"""

from googleapiclient.discovery import build

from analytics.auth import get_credentials

# ---------------------------------------------------------------------------
# Spreadsheet identity
# ---------------------------------------------------------------------------

SPREADSHEET_ID = "1jQtCV0r29Ny2FF0KvA6HNPg3ZN62nBBHKECtdDNtLZo"
SHEET_NAME = "Analytics"

# Template for section header rows inserted before each period's data.
# Callers substitute {period} with a human-readable label, e.g. "Last 28 Days".
SECTION_MARKER = "── {period} Performance"

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
