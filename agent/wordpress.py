"""Read published WordPress articles independently of RSS excerpt settings."""
from __future__ import annotations

import datetime as dt
from html.parser import HTMLParser
import re
from urllib.parse import urlparse

import requests


class _Text(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        if tag in {"p", "br", "li", "div", "h1", "h2", "h3", "h4"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1
        self.parts.append(" ")

    def handle_data(self, value):
        if not self.hidden:
            self.parts.append(value)


def plain_text(value):
    parser = _Text()
    parser.feed(value or "")
    return re.sub(r"\s+", " ", "".join(parser.parts)).strip()


def canonical_url(url):
    parsed = urlparse(url)
    return ((parsed.hostname or "").removeprefix("www."), parsed.path.rstrip("/"))


def fetch_articles(site, *, start=None, end=None, slugs=None):
    if urlparse(site).scheme != "https":
        raise ValueError("The blog source must use HTTPS")
    params = {"status": "publish", "per_page": 100, "page": 1,
              "orderby": "date", "order": "asc",
              "_fields": "id,status,date_gmt,link,title,excerpt,content"}
    if start:
        params["after"] = (start - dt.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S")
    if end:
        params["before"] = (end - dt.timedelta(seconds=1)).strftime("%Y-%m-%dT%H:%M:%S")
    if slugs:
        params["slug"] = ",".join(sorted(set(slugs)))
    articles = {}
    while True:
        response = requests.get(site.rstrip("/") + "/wp-json/wp/v2/posts", params=params,
                                timeout=45, headers={"User-Agent": "byrachitmishra-agent"})
        response.raise_for_status()
        rows = response.json()
        if not isinstance(rows, list) or "X-WP-TotalPages" not in response.headers:
            raise ValueError("Cannot verify complete WordPress pagination")
        for row in rows:
            content = row.get("content") or {}
            if row.get("status") != "publish" or content.get("protected"):
                continue
            link = row.get("link", "")
            if urlparse(link).scheme not in {"https", "http"} or canonical_url(link)[0] != canonical_url(site)[0]:
                raise ValueError("Unexpected article source URL")
            stamp = row.get("date_gmt")
            if not stamp:
                raise ValueError("Published article has no publication date")
            published = dt.datetime.fromisoformat(stamp.replace("Z", "+00:00"))
            if published.tzinfo is None:
                published = published.replace(tzinfo=dt.timezone.utc)
            if start and not start <= published < end:
                continue
            body = plain_text(content.get("rendered", ""))
            articles[row["id"]] = {"id": row["id"], "title": plain_text(row["title"]["rendered"]),
                                   "link": link, "published": published.isoformat(),
                                   "excerpt": plain_text((row.get("excerpt") or {}).get("rendered", "")),
                                   "body": body, "words": len(body.split())}
        if params["page"] >= int(response.headers["X-WP-TotalPages"]):
            break
        params["page"] += 1
    return sorted(articles.values(), key=lambda article: (article["published"], article["id"]))
