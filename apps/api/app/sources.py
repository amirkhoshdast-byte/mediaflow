"""Starting list of public media sources. Reuters and AP publish no public RSS feeds, and UN News
refuses non-browser clients, so they are read through GDELT, which indexes their articles. Adjust the list from the Sources page."""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import AuditLog, Source

# (type, name, url or query, language, domain)
STARTER: list[tuple[str, str, str, str, str]] = [
    ("rss", "BBC World", "http://feeds.bbci.co.uk/news/world/rss.xml", "en", "international"),
    ("rss", "BBC Middle East", "http://feeds.bbci.co.uk/news/world/middle_east/rss.xml", "en", "international"),
    ("rss", "Al Jazeera", "https://www.aljazeera.com/xml/rss/all.xml", "en", "international"),
    ("rss", "The Guardian World", "https://www.theguardian.com/world/rss", "en", "international"),
    ("rss", "New York Times World", "https://rss.nytimes.com/services/xml/rss/nyt/World.xml", "en", "international"),
    ("rss", "Foreign Policy", "https://foreignpolicy.com/feed/", "en", "politics"),
    ("rss", "DW", "https://rss.dw.com/xml/rss-en-all", "en", "international"),
    ("rss", "France 24", "https://www.france24.com/en/rss", "en", "international"),
    ("rss", "Middle East Eye", "https://www.middleeasteye.net/rss", "en", "international"),
    ("rss", "IRNA English", "https://en.irna.ir/rss", "en", "iran"),
    ("rss", "Tehran Times", "https://www.tehrantimes.com/rss", "en", "iran"),
    ("rss", "Press TV", "https://www.presstv.ir/rss.xml", "en", "iran"),
    ("gdelt", "Reuters (via GDELT)", 'domain:reuters.com (Iran OR Tehran OR UNESCO OR diplomacy OR "Middle East")', "en", "international"),
    ("gdelt", "AP (via GDELT)", 'domain:apnews.com (Iran OR Tehran OR UNESCO OR diplomacy OR "Middle East")', "en", "international"),
    ("gdelt", "UN News (via GDELT)", "domain:news.un.org", "en", "international"),
    ("gdelt", "Iran in world media (GDELT)", "Iran sourcelang:english", "en", "iran"),
]  # fmt: skip


def seed_sources(db: Session) -> None:
    """Only on a pristine system: once staff changed the list, never put sources back."""
    touched = db.scalar(select(func.count()).select_from(Source)) or db.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action.like("source.%"))
    )
    if touched:
        return
    for kind, name, target, lang, domain in STARTER:
        db.add(
            Source(
                type=kind,
                name=name,
                url=target if kind == "rss" else None,
                query=target if kind == "gdelt" else None,
                language=lang,
                domain=domain,
            )
        )
    db.commit()
