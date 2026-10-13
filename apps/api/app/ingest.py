"""Automatic intake of public media (RSS and GDELT). Fetching is the only part that touches the
network; everything that follows (dedupe, caps, analysis) is plain data handling.

Only public news sources are read. Source URLs are configured by staff, so every request is
checked against private address ranges (SSRF) before and after each redirect."""

import html
import ipaddress
import json
import re
import socket
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from email.utils import parsedate_to_datetime
from urllib.parse import quote, urlparse

import httpx
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.analysis import content_hash
from app.config import Settings
from app.enums import SignalStatus, SourceType
from app.models import RawItem, Signal, Source

MAX_BYTES = 5 * 1024 * 1024
MAX_REDIRECTS = 3
DNS_ATTEMPTS = 3
USER_AGENT = "Mozilla/5.0 (compatible; NarrativeCommandRoom/1.0; public-media-monitor)"
ACCEPT = (
    "application/rss+xml, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, */*;q=0.5"
)


class UnsafeUrl(ValueError):
    pass


@dataclass
class Entry:
    title: str
    summary: str
    link: str | None
    published: datetime | None


def check_public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise UnsafeUrl("only http(s) URLs are allowed")
    for attempt in range(DNS_ATTEMPTS):
        try:
            infos = socket.getaddrinfo(parsed.hostname, parsed.port or 443, type=socket.SOCK_STREAM)
            break
        except socket.gaierror as e:
            if attempt == DNS_ATTEMPTS - 1:
                raise UnsafeUrl("host does not resolve") from e
            time.sleep(1)  # Docker's resolver is briefly unavailable right after a restart
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if not ip.is_global:
            raise UnsafeUrl("address is not public")


def fetch_bytes(url: str, *, timeout: float = 20.0) -> bytes:
    with httpx.Client(
        timeout=timeout, follow_redirects=False, headers={"User-Agent": USER_AGENT}
    ) as c:
        for _ in range(MAX_REDIRECTS + 1):
            check_public_url(url)
            with c.stream("GET", url) as r:
                if r.is_redirect:
                    url = str(r.url.join(r.headers["location"]))
                    continue
                r.raise_for_status()
                body = bytearray()
                for chunk in r.iter_bytes():
                    body += chunk
                    if len(body) > MAX_BYTES:
                        raise ValueError("response too large")
                return bytes(body)
    raise UnsafeUrl("too many redirects")


def _clean(text: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", text or ""))).strip()


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _child_text(node: ET.Element, *names: str) -> str:
    for child in node:
        if _local(child.tag) in names and (child.text or "").strip():
            return child.text.strip()
    return ""


def _parse_date(raw: str) -> datetime | None:
    if not raw:
        return None
    try:
        d = parsedate_to_datetime(raw)  # RSS: RFC 822
    except (TypeError, ValueError):
        try:
            d = datetime.fromisoformat(raw.replace("Z", "+00:00"))  # Atom: ISO 8601
        except ValueError:
            return None
    return d if d.tzinfo else d.replace(tzinfo=UTC)


def parse_rss(content: bytes) -> list[Entry]:
    """RSS 2.0 `item` and Atom `entry` elements."""
    root = ET.fromstring(content)
    out = []
    for node in root.iter():
        if _local(node.tag) not in {"item", "entry"}:
            continue
        title = _clean(_child_text(node, "title"))
        if not title:
            continue
        link = _child_text(node, "link") or next(
            (c.get("href") for c in node if _local(c.tag) == "link" and c.get("href")), None
        )
        out.append(
            Entry(
                title,
                _clean(_child_text(node, "description", "summary")),
                link or None,
                _parse_date(_child_text(node, "pubDate", "published", "updated")),
            )
        )
    return out


def gdelt_url(query: str, max_records: int = 50) -> str:
    return (
        "https://api.gdeltproject.org/api/v2/doc/doc?mode=artlist&format=json&sort=datedesc"
        f"&timespan=1d&maxrecords={max_records}&query={quote(query)}"
    )


def parse_gdelt(content: bytes) -> list[Entry]:
    try:
        articles = json.loads(content).get("articles", [])
    except ValueError:  # GDELT answers with plain text when a query is rejected
        raise ValueError(content[:200].decode("utf-8", "replace")) from None
    out = []
    for a in articles:
        title = _clean(a.get("title", ""))
        if not title:
            continue
        try:
            published = datetime.strptime(a["seendate"], "%Y%m%dT%H%M%SZ").replace(tzinfo=UTC)
        except (KeyError, ValueError):
            published = None
        out.append(Entry(title, f"({a.get('domain', '')})", a.get("url"), published))
    return out


X_API = "https://api.x.com/2"
X_TIMELINE_ITEMS = 20


def fetch_json(url: str, token: str, *, params: dict | None = None) -> dict:
    r = httpx.get(
        url,
        params=params,
        timeout=20.0,
        headers={"Authorization": f"Bearer {token}", "User-Agent": USER_AGENT},
    )
    r.raise_for_status()
    return r.json()


def x_entries(source: Source, settings: Settings) -> list[Entry]:
    """Recent original posts of one public account (no replies, no reposts)."""
    if not settings.x_bearer_token:
        raise ValueError("X_BEARER_TOKEN is not configured")
    username = source.query or ""
    if not source.external_id:  # looked up once; the id never changes
        found = fetch_json(f"{X_API}/users/by/username/{username}", settings.x_bearer_token)
        source.external_id = (found.get("data") or {}).get("id")
        if not source.external_id:
            raise ValueError(f"X account @{username} was not found")
    timeline = fetch_json(
        f"{X_API}/users/{source.external_id}/tweets",
        settings.x_bearer_token,
        params={
            "max_results": X_TIMELINE_ITEMS,
            "tweet.fields": "created_at",
            "exclude": "retweets,replies",
        },
    )
    out = []
    for t in timeline.get("data") or []:
        text = _clean(t.get("text", ""))
        if text:
            out.append(
                Entry(
                    text,
                    "",
                    f"https://x.com/{username}/status/{t['id']}",
                    _parse_date(t.get("created_at", "")),
                )
            )
    return out


def entries_for(source: Source, settings: Settings) -> list[Entry]:
    if source.type == SourceType.X.value:
        return x_entries(source, settings)
    if source.type == SourceType.GDELT.value:
        return parse_gdelt(fetch_bytes(gdelt_url(source.query or "")))
    return parse_rss(fetch_bytes(source.url or ""))


def _signals_today(db: Session) -> int:
    start = datetime.now(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.scalar(
            select(func.count())
            .select_from(Signal)
            .join(RawItem, RawItem.id == Signal.raw_item_id)
            .where(RawItem.source_id.is_not(None), Signal.created_at >= start)
        )
        or 0
    )


def ingest_source(db: Session, source: Source, settings: Settings, budget: int) -> list[str]:
    """Store new entries of one source as signals awaiting analysis; returns their ids.

    `budget` is how many more new signals this run may create; a failing source records its error
    and never raises, so one dead feed cannot stop the others.
    """
    try:
        entries = entries_for(source, settings)
    except Exception as e:  # noqa: BLE001 - network, parsing, unsafe URL: all end up on the source
        source.last_error = f"{e.__class__.__name__}: {str(e)[:300]}"
        source.last_fetched_at = datetime.now(UTC)
        db.commit()
        return []

    cutoff = datetime.now(UTC) - timedelta(hours=settings.ingest_max_age_hours)
    created: list[str] = []
    undated = 0
    for entry in entries:
        if len(created) >= budget:
            break
        if entry.published and entry.published < cutoff:
            continue
        if not entry.published:
            undated += 1
            if undated > settings.ingest_undated_per_run:
                continue
        text = entry.title if not entry.summary else f"{entry.title}\n{entry.summary}"
        digest = content_hash(entry.title)  # same headline from two outlets is one signal
        if db.scalar(select(RawItem.id).where(RawItem.content_hash == digest)):
            continue
        if entry.link and db.scalar(select(RawItem.id).where(RawItem.url == entry.link)):
            continue
        item = RawItem(
            source_id=source.id,
            text=text[:4000],
            url=entry.link,
            published_at=entry.published,
            content_hash=digest,
        )
        db.add(item)
        db.flush()
        signal = Signal(raw_item_id=item.id, status=SignalStatus.ANALYZING.value)
        db.add(signal)
        db.flush()
        created.append(signal.id)
    source.last_error = None
    source.last_fetched_at = datetime.now(UTC)
    db.commit()
    return created


def ingest_all(db: Session, settings: Settings) -> list[str]:
    """One pass over every active source. The run budget is shared fairly so that sources sorted
    late in the alphabet are not starved by the early ones."""
    budget = min(
        settings.ingest_max_new_per_run, settings.ingest_max_new_per_day - _signals_today(db)
    )
    sources = list(db.scalars(select(Source).where(Source.active.is_(True)).order_by(Source.name)))
    if budget <= 0 or not sources:
        return []
    share = max(2, budget // len(sources))
    created: list[str] = []
    last_gdelt = 0.0
    for source in sources:
        if budget - len(created) <= 0:
            break
        if source.type == SourceType.GDELT.value:
            wait = settings.gdelt_min_interval_seconds - (time.monotonic() - last_gdelt)
            if last_gdelt and wait > 0:
                time.sleep(wait)
            last_gdelt = time.monotonic()
        created += ingest_source(db, source, settings, min(share, budget - len(created)))
    return created
