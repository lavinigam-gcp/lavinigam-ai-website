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
import sys

from rich.console import Console

from analytics.config import PERIODS, resolve_date_range
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
        "--all",
        action="store_true",
        default=True,
        dest="all_posts",
        help="Include all posts (default behavior)",
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

    # Output
    if args.output_format == "json":
        print_json(ga4_data, gsc_data, args.period)
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
        saved = save_all_csv(ga4_data, gsc_data, args.period)
        if saved:
            console.print(f"\n[green]Saved {len(saved)} CSV files:[/green]")
            for path in saved:
                console.print(f"  {path}")

    if not ga4_data and not gsc_data:
        console.print("[yellow]No data returned. Check your auth and property access.[/yellow]")
        sys.exit(1)


if __name__ == "__main__":
    main()
