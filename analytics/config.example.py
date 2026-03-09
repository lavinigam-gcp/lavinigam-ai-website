"""Analytics configuration — property IDs, site URL, period presets.

Copy this file to config.py and fill in your values:
    cp analytics/config.example.py analytics/config.py
"""

from datetime import date, timedelta

GA4_PROPERTY_ID = "YOUR_GA4_PROPERTY_ID"
GA4_PROPERTY = f"properties/{GA4_PROPERTY_ID}"
GSC_SITE_URL = "sc-domain:yourdomain.com"
POSTS_PATH_PREFIX = "/posts/"
REPORTS_DIR = "analytics/reports"

PERIODS = {
    "1d": 1,
    "3d": 3,
    "7d": 7,
    "30d": 30,
    "90d": 90,
    "365d": 365,
}


def resolve_date_range(period_str: str) -> tuple[str, str]:
    """Return (start_date, end_date) as YYYY-MM-DD strings.

    Accepts '7d', '30d', etc. or 'YYYY-MM-DD:YYYY-MM-DD'.
    """
    if ":" in period_str:
        start, end = period_str.split(":", 1)
        return start, end
    days = PERIODS.get(period_str)
    if days is None:
        raise ValueError(
            f"Unknown period '{period_str}'. Use: {', '.join(PERIODS)} or YYYY-MM-DD:YYYY-MM-DD"
        )
    end = date.today()
    start = end - timedelta(days=days)
    return start.isoformat(), end.isoformat()
