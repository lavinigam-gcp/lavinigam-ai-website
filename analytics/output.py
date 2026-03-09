"""Output formatting — rich tables, JSON, CSV."""

import csv
import json
import os
from collections import defaultdict
from datetime import date, datetime

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


# -- Number formatting --


def _round2(value: str) -> str:
    """Round a numeric string to 2 decimal places, drop trailing zeros."""
    try:
        v = float(value)
        if v == int(v):
            return str(int(v))
        return f"{v:.2f}"
    except (ValueError, TypeError):
        return value


def _round_row(row: dict) -> dict:
    """Round all numeric values in a row to 2 decimal places."""
    result = {}
    for k, v in row.items():
        if isinstance(v, (int, float)):
            result[k] = _round2(str(v))
        elif isinstance(v, str):
            try:
                float(v)
                result[k] = _round2(v)
            except ValueError:
                result[k] = v
        else:
            result[k] = v
    return result


# -- JSON output --


def print_json(
    ga4_data: dict | None,
    gsc_data: dict | None,
    period: str,
    start_date: str = "",
    end_date: str = "",
) -> None:
    """Print combined results as JSON to stdout."""
    output = {
        "period": period,
        "startDate": start_date,
        "endDate": end_date,
        "fetchedAt": datetime.now().isoformat(timespec="seconds"),
    }
    if ga4_data is not None:
        output["ga4"] = {
            name: [_round_row(r) for r in rows]
            for name, rows in ga4_data.items()
        }
    if gsc_data is not None:
        output["gsc"] = {
            name: [_round_row(r) for r in rows]
            for name, rows in gsc_data.items()
        }
    console.print_json(json.dumps(output, default=str))


# -- Geo summary helpers --


def _summarize_geo(geo_rows: list[dict]) -> dict[str, dict]:
    """Build per-post geo/device summary from geo_device rows.

    Returns {pagePath: {"topCountries": "India (43%), US (21%)", "desktopPct": 82.5, ...}}
    """
    by_post: dict[str, list[dict]] = defaultdict(list)
    for row in geo_rows:
        by_post[row.get("pagePath", "")].append(row)

    summaries = {}
    for path, rows in by_post.items():
        total_sessions = sum(float(r.get("sessions", 0)) for r in rows)

        # Country breakdown.
        country_sessions: dict[str, float] = defaultdict(float)
        device_sessions: dict[str, float] = defaultdict(float)
        for r in rows:
            sess = float(r.get("sessions", 0))
            country = r.get("country", "")
            device = r.get("deviceCategory", "")
            if country:
                country_sessions[country] += sess
            if device:
                device_sessions[device] += sess

        # Top 3 countries.
        top_countries = sorted(country_sessions.items(), key=lambda x: -x[1])[:3]
        if total_sessions > 0:
            country_str = ", ".join(
                f"{c} ({s/total_sessions*100:.0f}%)" for c, s in top_countries
            )
        else:
            country_str = ""

        # Device split.
        desktop_pct = (device_sessions.get("desktop", 0) / total_sessions * 100) if total_sessions else 0
        mobile_pct = (device_sessions.get("mobile", 0) / total_sessions * 100) if total_sessions else 0
        tablet_pct = (device_sessions.get("tablet", 0) / total_sessions * 100) if total_sessions else 0

        summaries[path] = {
            "topCountries": country_str,
            "desktopPct": f"{desktop_pct:.1f}",
            "mobilePct": f"{mobile_pct:.1f}",
            "tabletPct": f"{tablet_pct:.1f}",
        }
    return summaries


# -- CSV saving --


def save_all_csv(
    ga4_data: dict | None,
    gsc_data: dict | None,
    period: str,
    start_date: str = "",
    end_date: str = "",
) -> list[str]:
    """Save a single consolidated CSV per source. Returns list of saved file paths."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    today = date.today().isoformat()
    fetched_at = datetime.now().isoformat(timespec="seconds")
    saved = []

    if ga4_data and ga4_data.get("overview"):
        # Build geo summary lookup.
        geo_summary = _summarize_geo(ga4_data.get("geo_device", []))

        # Consolidated columns.
        fieldnames = [
            "pagePath", "screenPageViews", "sessions", "totalUsers", "newUsers",
            "engagementRate", "bounceRate", "averageSessionDuration",
            "screenPageViewsPerSession", "engagedSessions", "eventCount",
            "topCountries", "desktopPct", "mobilePct", "tabletPct",
            "period", "startDate", "endDate", "fetchedAt",
        ]

        rows = []
        for row in ga4_data["overview"]:
            rounded = _round_row(row)
            path = rounded.get("pagePath", "")
            geo = geo_summary.get(path, {})
            rows.append({
                **{k: rounded.get(k, "") for k in fieldnames[:11]},
                "topCountries": geo.get("topCountries", ""),
                "desktopPct": geo.get("desktopPct", ""),
                "mobilePct": geo.get("mobilePct", ""),
                "tabletPct": geo.get("tabletPct", ""),
                "period": period,
                "startDate": start_date,
                "endDate": end_date,
                "fetchedAt": fetched_at,
            })

        filepath = os.path.join(REPORTS_DIR, f"{today}-ga4-report-{period}.csv")
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        saved.append(filepath)

    if gsc_data and gsc_data.get("search_performance"):
        fieldnames = [
            "page", "clicks", "impressions", "ctr", "position",
            "period", "startDate", "endDate", "fetchedAt",
        ]

        rows = []
        for row in gsc_data["search_performance"]:
            rounded = _round_row(row)
            rows.append({
                **{k: rounded.get(k, "") for k in fieldnames[:5]},
                "period": period,
                "startDate": start_date,
                "endDate": end_date,
                "fetchedAt": fetched_at,
            })

        filepath = os.path.join(REPORTS_DIR, f"{today}-gsc-report-{period}.csv")
        with open(filepath, "w", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
        saved.append(filepath)

    return saved
