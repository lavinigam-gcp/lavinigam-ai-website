"""GA4 Data API client — fetches post-level analytics."""

import google.auth
from google.analytics.data_v1beta import BetaAnalyticsDataClient
from google.analytics.data_v1beta.types import (
    BatchRunReportsRequest,
    DateRange,
    Dimension,
    Filter,
    FilterExpression,
    Metric,
    OrderBy,
    RunReportRequest,
)

from analytics.config import GA4_PROPERTY, POSTS_PATH_PREFIX


def _get_client() -> BetaAnalyticsDataClient:
    """Create GA4 client using Application Default Credentials."""
    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/analytics.readonly"]
    )
    return BetaAnalyticsDataClient(credentials=credentials)


def _posts_filter(post_path: str | None = None) -> FilterExpression:
    """Build a filter for pagePath — exact match or starts-with /posts/."""
    if post_path:
        return FilterExpression(
            filter=Filter(
                field_name="pagePath",
                string_filter=Filter.StringFilter(
                    match_type=Filter.StringFilter.MatchType.EXACT,
                    value=post_path,
                ),
            )
        )
    return FilterExpression(
        filter=Filter(
            field_name="pagePath",
            string_filter=Filter.StringFilter(
                match_type=Filter.StringFilter.MatchType.BEGINS_WITH,
                value=POSTS_PATH_PREFIX,
            ),
        )
    )


def _overview_request(
    start_date: str, end_date: str, post_path: str | None, limit: int
) -> RunReportRequest:
    """Per-post overview: pageviews, sessions, users, engagement."""
    return RunReportRequest(
        property=GA4_PROPERTY,
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="pagePath")],
        metrics=[
            Metric(name="screenPageViews"),
            Metric(name="sessions"),
            Metric(name="totalUsers"),
            Metric(name="newUsers"),
            Metric(name="engagementRate"),
            Metric(name="bounceRate"),
            Metric(name="averageSessionDuration"),
            Metric(name="screenPageViewsPerSession"),
            Metric(name="userEngagementDuration"),
            Metric(name="engagedSessions"),
            Metric(name="eventCount"),
        ],
        dimension_filter=_posts_filter(post_path),
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="screenPageViews"),
                desc=True,
            )
        ],
        limit=limit,
    )


def _traffic_sources_request(
    start_date: str, end_date: str, post_path: str | None, limit: int
) -> RunReportRequest:
    """Traffic source breakdown per post."""
    return RunReportRequest(
        property=GA4_PROPERTY,
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[
            Dimension(name="pagePath"),
            Dimension(name="defaultChannelGroup"),
            Dimension(name="sessionSource"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="totalUsers"),
        ],
        dimension_filter=_posts_filter(post_path),
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="sessions"),
                desc=True,
            )
        ],
        limit=limit,
    )


def _geo_device_request(
    start_date: str, end_date: str, post_path: str | None, limit: int
) -> RunReportRequest:
    """Geographic and device breakdown per post."""
    return RunReportRequest(
        property=GA4_PROPERTY,
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[
            Dimension(name="pagePath"),
            Dimension(name="country"),
            Dimension(name="deviceCategory"),
        ],
        metrics=[
            Metric(name="sessions"),
            Metric(name="totalUsers"),
        ],
        dimension_filter=_posts_filter(post_path),
        order_bys=[
            OrderBy(
                metric=OrderBy.MetricOrderBy(metric_name="sessions"),
                desc=True,
            )
        ],
        limit=limit,
    )


def _trend_request(
    start_date: str, end_date: str, post_path: str
) -> RunReportRequest:
    """Daily time series for a single post."""
    return RunReportRequest(
        property=GA4_PROPERTY,
        date_ranges=[DateRange(start_date=start_date, end_date=end_date)],
        dimensions=[Dimension(name="date")],
        metrics=[
            Metric(name="screenPageViews"),
            Metric(name="sessions"),
            Metric(name="totalUsers"),
        ],
        dimension_filter=_posts_filter(post_path),
        order_bys=[
            OrderBy(dimension=OrderBy.DimensionOrderBy(dimension_name="date"))
        ],
    )


def _parse_report(response) -> list[dict]:
    """Convert a GA4 RunReportResponse to a list of dicts."""
    if not response.rows:
        return []
    headers = [h.name for h in response.dimension_headers] + [
        h.name for h in response.metric_headers
    ]
    rows = []
    for row in response.rows:
        values = [dv.value for dv in row.dimension_values] + [
            mv.value for mv in row.metric_values
        ]
        rows.append(dict(zip(headers, values)))
    return rows


def fetch_ga4_reports(
    start_date: str,
    end_date: str,
    post_path: str | None = None,
    limit: int = 25,
) -> dict[str, list[dict]]:
    """Fetch all GA4 reports. Returns dict keyed by report name."""
    client = _get_client()

    requests = [
        _overview_request(start_date, end_date, post_path, limit),
        _traffic_sources_request(start_date, end_date, post_path, limit),
        _geo_device_request(start_date, end_date, post_path, limit),
    ]
    if post_path:
        requests.append(_trend_request(start_date, end_date, post_path))

    batch_response = client.batch_run_reports(
        BatchRunReportsRequest(property=GA4_PROPERTY, requests=requests)
    )

    report_names = ["overview", "traffic_sources", "geo_device"]
    if post_path:
        report_names.append("trend")

    results = {}
    for name, report in zip(report_names, batch_response.reports):
        results[name] = _parse_report(report)

    return results
