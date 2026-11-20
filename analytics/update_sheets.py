#!/usr/bin/env python3
"""CLI wrapper for analytics → Google Sheets updater."""
import argparse
from pathlib import Path
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Push GA4 analytics to the content tracker Google Sheet."
    )
    parser.add_argument(
        "--period",
        default="7d",
        help="Time period preset (1d, 3d, 7d, 14d, 21d, 28d, 30d, 90d, 365d) or YYYY-MM-DD:YYYY-MM-DD range (default: 7d)",
    )
    args = parser.parse_args()

    repo_root = str(Path(__file__).resolve().parent.parent)
    if repo_root not in sys.path:
        sys.path.insert(0, repo_root)
    from analytics.sheets_updater import update_analytics_sheet

    update_analytics_sheet(args.period)


if __name__ == "__main__":
    main()
