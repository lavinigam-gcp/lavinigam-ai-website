"""Output formatting — rich tables, JSON, CSV."""

import csv
import json
import os
from datetime import date

from rich.console import Console
from rich.table import Table

from analytics.config import REPORTS_DIR

console = Console()


def _fmt_duration(seconds_str: str) -> str:
    """Format seconds string as 'Xm Ys'."""
    try:
        total = float(seconds_str)
    except (ValueError, TypeError):
        return seconds_str
    minutes = int(total // 60)
    seconds = int(total % 60)
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _fmt_pct(value_str: str) -> str:
    """Format a decimal ratio as percentage."""
    try:
        return f"{float(value_str) * 100:.1f}%"
    except (ValueError, TypeError):
        return value_str


def _fmt_position(value_str: str) -> str:
    """Format position to 1 decimal."""
    try:
        return f"{float(value_str):.1f}"
    except (ValueError, TypeError):
        return value_str


# -- Rich table printers --


def print_ga4_overview(rows: list[dict], period: str) -> None:
    """Print GA4 per-post overview table."""
    table = Table(title=f"GA4 Post Overview ({period})")
    table.add_column("Page", style="cyan", max_width=50)
    table.add_column("Views", justify="right")
    table.add_column("Sessions", justify="right")
    table.add_column("Users", justify="right")
    table.add_column("New Users", justify="right")
    table.add_column("Engagement", justify="right", style="green")
    table.add_column("Bounce", justify="right", style="red")
    table.add_column("Avg Duration", justify="right")
    table.add_column("Pages/Session", justify="right")
    table.add_column("Events", justify="right")

    for row in rows:
        table.add_row(
            row.get("pagePath", ""),
            row.get("screenPageViews", "0"),
            row.get("sessions", "0"),
            row.get("totalUsers", "0"),
            row.get("newUsers", "0"),
            _fmt_pct(row.get("engagementRate", "0")),
            _fmt_pct(row.get("bounceRate", "0")),
            _fmt_duration(row.get("averageSessionDuration", "0")),
            row.get("screenPageViewsPerSession", "0"),
            row.get("eventCount", "0"),
        )
    console.print(table)


def print_ga4_traffic_sources(rows: list[dict], period: str) -> None:
    """Print traffic source breakdown table."""
    table = Table(title=f"GA4 Traffic Sources ({period})")
    table.add_column("Page", style="cyan", max_width=40)
    table.add_column("Channel", style="yellow")
    table.add_column("Source")
    table.add_column("Sessions", justify="right")
    table.add_column("Users", justify="right")

    for row in rows:
        table.add_row(
            row.get("pagePath", ""),
            row.get("defaultChannelGroup", ""),
            row.get("sessionSource", ""),
            row.get("sessions", "0"),
            row.get("totalUsers", "0"),
        )
    console.print(table)


def print_ga4_geo_device(rows: list[dict], period: str) -> None:
    """Print geo + device breakdown table."""
    table = Table(title=f"GA4 Geo & Device ({period})")
    table.add_column("Page", style="cyan", max_width=40)
    table.add_column("Country")
    table.add_column("Device")
    table.add_column("Sessions", justify="right")
    table.add_column("Users", justify="right")

    for row in rows:
        table.add_row(
            row.get("pagePath", ""),
            row.get("country", ""),
            row.get("deviceCategory", ""),
            row.get("sessions", "0"),
            row.get("totalUsers", "0"),
        )
    console.print(table)


def print_ga4_trend(rows: list[dict], period: str) -> None:
    """Print daily GA4 trend table."""
    table = Table(title=f"GA4 Daily Trend ({period})")
    table.add_column("Date", style="cyan")
    table.add_column("Views", justify="right")
    table.add_column("Sessions", justify="right")
    table.add_column("Users", justify="right")

    for row in rows:
        table.add_row(
            row.get("date", ""),
            row.get("screenPageViews", "0"),
            row.get("sessions", "0"),
            row.get("totalUsers", "0"),
        )
    console.print(table)


def print_gsc_performance(rows: list[dict], period: str) -> None:
    """Print GSC per-page search performance table."""
    table = Table(title=f"Search Console Performance ({period})")
    table.add_column("Page", style="cyan", max_width=50)
    table.add_column("Clicks", justify="right", style="green")
    table.add_column("Impressions", justify="right")
    table.add_column("CTR", justify="right")
    table.add_column("Position", justify="right")

    for row in rows:
        table.add_row(
            row.get("page", ""),
            str(row.get("clicks", 0)),
            str(row.get("impressions", 0)),
            _fmt_pct(str(row.get("ctr", 0))),
            _fmt_position(str(row.get("position", 0))),
        )
    console.print(table)


def print_gsc_queries(rows: list[dict], period: str) -> None:
    """Print top search queries table."""
    table = Table(title=f"Search Console Top Queries ({period})")
    table.add_column("Page", style="cyan", max_width=40)
    table.add_column("Query", style="yellow", max_width=40)
    table.add_column("Clicks", justify="right", style="green")
    table.add_column("Impressions", justify="right")
    table.add_column("CTR", justify="right")
    table.add_column("Position", justify="right")

    for row in rows:
        table.add_row(
            row.get("page", ""),
            row.get("query", ""),
            str(row.get("clicks", 0)),
            str(row.get("impressions", 0)),
            _fmt_pct(str(row.get("ctr", 0))),
            _fmt_position(str(row.get("position", 0))),
        )
    console.print(table)


def print_gsc_trend(rows: list[dict], period: str) -> None:
    """Print daily GSC trend table."""
    table = Table(title=f"Search Console Daily Trend ({period})")
    table.add_column("Date", style="cyan")
    table.add_column("Clicks", justify="right", style="green")
    table.add_column("Impressions", justify="right")
    table.add_column("CTR", justify="right")
    table.add_column("Position", justify="right")

    for row in rows:
        table.add_row(
            row.get("date", ""),
            str(row.get("clicks", 0)),
            str(row.get("impressions", 0)),
            _fmt_pct(str(row.get("ctr", 0))),
            _fmt_position(str(row.get("position", 0))),
        )
    console.print(table)


def print_gsc_device_country(rows: list[dict], period: str) -> None:
    """Print GSC device + country breakdown table."""
    table = Table(title=f"Search Console Device & Country ({period})")
    table.add_column("Page", style="cyan", max_width=40)
    table.add_column("Device")
    table.add_column("Country")
    table.add_column("Clicks", justify="right", style="green")
    table.add_column("Impressions", justify="right")

    for row in rows:
        table.add_row(
            row.get("page", ""),
            row.get("device", ""),
            row.get("country", ""),
            str(row.get("clicks", 0)),
            str(row.get("impressions", 0)),
        )
    console.print(table)


# -- JSON output --


def print_json(ga4_data: dict | None, gsc_data: dict | None, period: str) -> None:
    """Print combined results as JSON to stdout."""
    output = {"period": period}
    if ga4_data is not None:
        output["ga4"] = ga4_data
    if gsc_data is not None:
        output["gsc"] = gsc_data
    console.print_json(json.dumps(output, default=str))


# -- CSV saving --


def _save_csv(rows: list[dict], filename: str) -> str:
    """Save rows to CSV. Returns the file path."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    filepath = os.path.join(REPORTS_DIR, filename)
    if not rows:
        return filepath
    with open(filepath, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)
    return filepath


def save_all_csv(
    ga4_data: dict | None, gsc_data: dict | None, period: str
) -> list[str]:
    """Save all report sections as CSVs. Returns list of saved file paths."""
    today = date.today().isoformat()
    saved = []

    if ga4_data:
        for name, rows in ga4_data.items():
            if rows:
                path = _save_csv(rows, f"{today}-ga4-{name}-{period}.csv")
                saved.append(path)

    if gsc_data:
        for name, rows in gsc_data.items():
            if rows:
                path = _save_csv(rows, f"{today}-gsc-{name}-{period}.csv")
                saved.append(path)

    return saved
