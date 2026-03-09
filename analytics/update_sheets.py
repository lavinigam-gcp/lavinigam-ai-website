#!/usr/bin/env python3
"""CLI wrapper for analytics → Google Sheets updater."""
import argparse
from analytics.sheets_updater import update_analytics_sheet

def main():
    parser = argparse.ArgumentParser(
        description="Push GA4 analytics to the content tracker Google Sheet."
    )
    parser.add_argument(
        "--period", default="7d",
        help="Time period: 1d, 3d, 7d, 30d, 90d, 365d (default: 7d)"
    )
    args = parser.parse_args()
    update_analytics_sheet(args.period)

if __name__ == "__main__":
    main()
