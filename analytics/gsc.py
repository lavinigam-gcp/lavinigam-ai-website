"""Google Search Console API client — fetches search performance data."""

import google.auth
from googleapiclient.discovery import build

from analytics.config import GSC_SITE_URL, POSTS_PATH_PREFIX


def _get_service():
    """Create Search Console service using Application Default Credentials."""
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/webmasters.readonly"]
    )
    return build("searchconsole", "v1", credentials=credentials)


def _query(
    service,
    start_date: str,
    end_date: str,
    dimensions: list[str],
    post_path: str | None = None,
    row_limit: int = 100,
) -> list[dict]:
    """Run a Search Console query and return parsed rows."""
    body: dict = {
        "startDate": start_date,
        "endDate": end_date,
        "dimensions": dimensions,
        "rowLimit": row_limit,
    }

    # Filter to posts or a specific post
    page_filter_value = (
        f"{GSC_SITE_URL.rstrip('/')}{post_path}"
        if post_path
        else f"{GSC_SITE_URL.rstrip('/')}{POSTS_PATH_PREFIX}"
    )
    page_filter_operator = "equals" if post_path else "contains"

    body["dimensionFilterGroups"] = [
        {
            "filters": [
                {
                    "dimension": "page",
                    "operator": page_filter_operator,
                    "expression": page_filter_value,
                }
            ]
        }
    ]

    response = (
        service.searchanalytics()
        .query(siteUrl=GSC_SITE_URL, body=body)
        .execute()
    )

    rows = []
    for row in response.get("rows", []):
        entry = dict(zip(dimensions, row["keys"]))
        entry["clicks"] = row["clicks"]
        entry["impressions"] = row["impressions"]
        entry["ctr"] = row["ctr"]
        entry["position"] = row["position"]
        rows.append(entry)
    return rows


def fetch_gsc_reports(
    start_date: str,
    end_date: str,
    post_path: str | None = None,
    limit: int = 25,
) -> dict[str, list[dict]]:
    """Fetch all GSC reports. Returns dict keyed by report name."""
    service = _get_service()

    results = {}

    # Report 1: Per-post search performance
    results["search_performance"] = _query(
        service, start_date, end_date, ["page"], post_path, row_limit=limit
    )

    # Report 2: Top queries
    results["top_queries"] = _query(
        service, start_date, end_date, ["page", "query"], post_path, row_limit=100
    )

    # Report 3: Daily trend (single-post mode only)
    if post_path:
        results["trend"] = _query(
            service, start_date, end_date, ["date"], post_path, row_limit=1000
        )

    # Report 4: Device + country
    results["device_country"] = _query(
        service, start_date, end_date, ["page", "device", "country"], post_path, row_limit=limit
    )

    return results
