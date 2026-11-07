"""Job sources. Each source returns a list of Job and never raises on network errors."""
from __future__ import annotations

import html
import logging
import re
from datetime import datetime, timezone

import requests

log = logging.getLogger("jobfinder")

USER_AGENT = "job-finder/0.1 (personal job search tool)"
TIMEOUT = 30


def get_json(url: str, **kwargs):
    headers = {"User-Agent": USER_AGENT, **kwargs.pop("headers", {})}
    resp = requests.get(url, headers=headers, timeout=TIMEOUT, **kwargs)
    resp.raise_for_status()
    return resp.json()


_TAG = re.compile(r"<[^>]+>")


def strip_html(text: str | None) -> str:
    if not text:
        return ""
    # Greenhouse double-escapes its HTML content
    text = html.unescape(html.unescape(text))
    return re.sub(r"\s+", " ", _TAG.sub(" ", text)).strip()


def parse_date(value) -> datetime | None:
    """Accepts ISO strings, unix seconds, or unix milliseconds."""
    if value in (None, ""):
        return None
    try:
        if isinstance(value, (int, float)):
            if value > 1e11:  # milliseconds
                value = value / 1000
            return datetime.fromtimestamp(value, tz=timezone.utc)
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (ValueError, OverflowError, OSError):
        return None
