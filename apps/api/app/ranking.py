"""How signals are ranked for attention; shared by the live overview and the daily reports."""

from app.enums import RISK_ORDER, RiskLevel
from app.models import Signal

MIN_RELEVANCE = 30  # below this a signal is noise for this account (sport, celebrity, local crime)


def relevance_of(s: Signal) -> int:
    return s.relevance if s.relevance is not None else 50


def priority(s: Signal) -> int:
    """Relevance first; higher risk breaks ties so a risky item is never buried."""
    return relevance_of(s) * 10 + RISK_ORDER[RiskLevel(s.risk or "medium")]
