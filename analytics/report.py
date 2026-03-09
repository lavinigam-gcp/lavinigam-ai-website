#!/usr/bin/env python3
"""Analytics CLI — fetch GA4 and Search Console metrics for blog posts.

Usage:
    python analytics/report.py                              # all posts, both sources, 30d
    python analytics/report.py --post /posts/my-post/ --period 7d
    python analytics/report.py --source ga4 --period 90d
    python analytics/report.py --format json
    python analytics/report.py --csv
"""

import argparse
import re
import sys
from collections import defaultdict

from rich.console import Console

from analytics.config import EXCLUDED_SLUGS, PERIODS, POSTS_PATH_PREFIX, resolve_date_range
from analytics.ga4 import fetch_ga4_reports
from analytics.gsc import fetch_gsc_reports
from analytics.output import (
    console,
    print_ga4_geo_device,
    print_ga4_overview,
    print_ga4_traffic_sources,
    print_ga4_trend,
    print_gsc_device_country,
    print_gsc_performance,
    print_gsc_queries,
    print_gsc_trend,
    print_json,
    save_all_csv,
)


_POST_PATH_RE = re.compile(r"^/posts/[^/]+$")


def _fmt_num(value: float) -> str:
    """Format a number as string, dropping .0 for whole numbers."""
    return str(int(value)) if value == int(value) else str(value)


def _normalize_path(path: str) -> str:
    """Ensure /posts/{slug} has a trailing slash."""
    if _POST_PATH_RE.match(path):
        return path + "/"
    return path


def _is_blog_post(path: str) -> bool:
    """Return True if path is a real, non-excluded blog post."""
    if not path.startswith(POSTS_PATH_PREFIX) or path == POSTS_PATH_PREFIX:
        return False
    slug = path.removeprefix(POSTS_PATH_PREFIX).strip("/")
    return slug not in EXCLUDED_SLUGS


# Metrics that should be summed when merging rows.
_SUM_METRICS = {
    "screenPageViews", "sessions", "totalUsers", "newUsers",
    "engagedSessions", "eventCount", "clicks", "impressions",
}
# Metrics that need weighted averaging by sessions.
_WEIGHTED_METRICS = {
    "engagementRate", "bounceRate", "averageSessionDuration",
}
# Metrics that are recalculated after merging.
_DERIVED_METRICS = {
    "screenPageViewsPerSession",  # = screenPageViews / sessions
    "ctr",                         # = clicks / impressions
    "position",                    # weighted by impressions
}


def _merge_rows(rows: list[dict], group_keys: list[str]) -> list[dict]:
    """Merge rows that share the same group_keys, summing/averaging metrics."""
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for row in rows:
        key = tuple(row.get(k, "") for k in group_keys)
        groups[key].append(row)

    merged = []
    for key_vals, group in groups.items():
        if len(group) == 1:
            merged.append(group[0])
            continue

        result = dict(zip(group_keys, key_vals))
        all_keys = {k for row in group for k in row}
        metric_keys = all_keys - set(group_keys)

        # Sum metrics.
        for mk in metric_keys & _SUM_METRICS:
            result[mk] = _fmt_num(sum(float(r.get(mk, 0)) for r in group))

        # Weighted average metrics (weight by sessions).
        total_sessions = sum(float(r.get("sessions", 0)) for r in group)
        for mk in metric_keys & _WEIGHTED_METRICS:
            if total_sessions > 0:
                weighted = sum(
                    float(r.get(mk, 0)) * float(r.get("sessions", 0))
                    for r in group
                )
                result[mk] = str(weighted / total_sessions)
            else:
                result[mk] = "0"

        # Derived metrics.
        if "screenPageViewsPerSession" in metric_keys:
            views = float(result.get("screenPageViews", 0))
            sess = float(result.get("sessions", 0))
            result["screenPageViewsPerSession"] = str(views / sess) if sess else "0"

        if "ctr" in metric_keys:
            clicks = float(result.get("clicks", 0))
            impr = float(result.get("impressions", 0))
            result["ctr"] = str(clicks / impr) if impr else "0"

        if "position" in metric_keys:
            total_impr = sum(float(r.get("impressions", 0)) for r in group)
            if total_impr > 0:
                weighted_pos = sum(
                    float(r.get("position", 0)) * float(r.get("impressions", 0))
                    for r in group
                )
                result["position"] = str(weighted_pos / total_impr)
            else:
                result["position"] = "0"

        # Carry over any remaining dimension-like fields.
        for mk in metric_keys - _SUM_METRICS - _WEIGHTED_METRICS - _DERIVED_METRICS:
            result[mk] = group[0].get(mk, "")

        merged.append(result)
    return merged


def _normalize_ga4_data(data: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Normalize pagePath and merge duplicate rows across all GA4 reports."""
    result = {}
    for report_name, rows in data.items():
        if report_name == "trend":
            # Trend has no pagePath dimension, skip normalization.
            result[report_name] = rows
            continue

        # Normalize pagePath.
        for row in rows:
            if "pagePath" in row:
                row["pagePath"] = _normalize_path(row["pagePath"])

        # Filter to actual blog posts only.
        rows = [r for r in rows if _is_blog_post(r.get("pagePath", ""))]

        # Determine group keys (all dimensions).
        if report_name == "overview":
            group_keys = ["pagePath"]
        elif report_name == "traffic_sources":
            group_keys = ["pagePath", "defaultChannelGroup", "sessionSource"]
        elif report_name == "geo_device":
            group_keys = ["pagePath", "country", "deviceCategory"]
        else:
            group_keys = ["pagePath"]

        result[report_name] = _merge_rows(rows, group_keys)
    return result


def _normalize_gsc_data(data: dict[str, list[dict]]) -> dict[str, list[dict]]:
    """Filter GSC data to blog posts only (GSC uses full URLs in page dim)."""
    result = {}
    for report_name, rows in data.items():
        if report_name == "trend":
            result[report_name] = rows
            continue

        # GSC page dimension contains full URLs; filter and normalize.
        for row in rows:
            if "page" in row:
                # Extract path from full URL.
                url = row["page"]
                if "lavinigam.com" in url:
                    path = url.split("lavinigam.com", 1)[1]
                    path = _normalize_path(path)
                    row["page"] = path

        rows = [r for r in rows if _is_blog_post(r.get("page", r.get("pagePath", "")))]

        if report_name == "search_performance":
            group_keys = ["page"]
        elif report_name == "top_queries":
            group_keys = ["page", "query"]
        elif report_name == "device_country":
            group_keys = ["page", "device", "country"]
        else:
            group_keys = ["page"]

        result[report_name] = _merge_rows(rows, group_keys)
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Fetch analytics for lavinigam.com blog posts."
    )
    parser.add_argument(
        "--source",
        choices=["ga4", "gsc", "both"],
        default="both",
        help="Data source (default: both)",
    )
    parser.add_argument(
        "--period",
        default="30d",
        help=f"Time period: {', '.join(PERIODS)} or YYYY-MM-DD:YYYY-MM-DD (default: 30d)",
    )
    parser.add_argument(
        "--post",
        default=None,
        help="Filter to a single post path, e.g. /posts/my-post/",
    )
    parser.add_argument(
        "--all-paths",
        action="store_true",
        default=False,
        help="Show all paths including listing pages and non-normalized duplicates",
    )
    parser.add_argument(
        "--format",
        choices=["table", "json"],
        default="table",
        dest="output_format",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--csv",
        action="store_true",
        help="Also save CSV files to analytics/reports/",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        help="Max rows per table (default: 25)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        start_date, end_date = resolve_date_range(args.period)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        sys.exit(1)

    console.print(
        f"\n[bold]Analytics Report[/bold] — {start_date} to {end_date} ({args.period})\n"
    )

    ga4_data = None
    gsc_data = None

    # Fetch GA4
    if args.source in ("ga4", "both"):
        console.print("[dim]Fetching GA4 data...[/dim]")
        try:
            ga4_data = fetch_ga4_reports(
                start_date, end_date, args.post, args.limit
            )
        except Exception as e:
            console.print(f"[red]GA4 error:[/red] {e}")

    # Fetch GSC
    if args.source in ("gsc", "both"):
        console.print("[dim]Fetching Search Console data...[/dim]")
        try:
            gsc_data = fetch_gsc_reports(
                start_date, end_date, args.post, args.limit
            )
        except Exception as e:
            console.print(f"[red]GSC error:[/red] {e}")

    # Normalize paths (merge trailing-slash duplicates, filter listing pages).
    if not args.all_paths:
        if ga4_data:
            ga4_data = _normalize_ga4_data(ga4_data)
        if gsc_data:
            gsc_data = _normalize_gsc_data(gsc_data)

    # Output
    if args.output_format == "json":
        print_json(ga4_data, gsc_data, args.period, start_date, end_date)
    else:
        if ga4_data:
            if ga4_data.get("overview"):
                print_ga4_overview(ga4_data["overview"], args.period)
            if ga4_data.get("traffic_sources"):
                print_ga4_traffic_sources(ga4_data["traffic_sources"], args.period)
            if ga4_data.get("geo_device"):
                print_ga4_geo_device(ga4_data["geo_device"], args.period)
            if ga4_data.get("trend"):
                print_ga4_trend(ga4_data["trend"], args.period)

        if gsc_data:
            if gsc_data.get("search_performance"):
                print_gsc_performance(gsc_data["search_performance"], args.period)
            if gsc_data.get("top_queries"):
                print_gsc_queries(gsc_data["top_queries"], args.period)
            if gsc_data.get("trend"):
                print_gsc_trend(gsc_data["trend"], args.period)
            if gsc_data.get("device_country"):
                print_gsc_device_country(gsc_data["device_country"], args.period)

    # CSV
    if args.csv:
        saved = save_all_csv(ga4_data, gsc_data, args.period, start_date, end_date)
        if saved:
            console.print(f"\n[green]Saved {len(saved)} CSV files:[/green]")
            for path in saved:
                console.print(f"  {path}")

    if not ga4_data and not gsc_data:
        console.print("[yellow]No data returned. Check your auth and property access.[/yellow]")
        sys.exit(1)


if __name__ == "__main__":
    main()
