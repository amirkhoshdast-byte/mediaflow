from enum import StrEnum


class Role(StrEnum):
    TREND_ANALYST = "trend_analyst"
    MEDIA_MONITOR = "media_monitor"
    AI_OPERATOR = "ai_operator"
    CONTENT_LEAD = "content_lead"
    NARRATIVE_STRATEGIST = "narrative_strategist"
    DIPLOMATIC_EDITOR = "diplomatic_editor"
    PRESIDENT_OFFICE = "president_office"
    SYSADMIN = "sysadmin"


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}


class Stage(StrEnum):
    DRAFT = "draft"
    TONE_REVIEW = "tone_review"
    APPROVED = "approved"
    PUBLISHED = "published"


class DraftFormat(StrEnum):
    TWEET = "tweet"
    THREAD = "thread"
    REPLY = "reply"
    QUOTE = "quote"


class SourceType(StrEnum):
    RSS = "rss"
    GDELT = "gdelt"
    X = "x"
    MANUAL = "manual"


class SignalStatus(StrEnum):
    ANALYZING = "analyzing"
    READY = "ready"
    FAILED = "failed"


class Approach(StrEnum):
    MONITOR_ONLY = "monitor_only"
    STRATEGIC_SILENCE = "strategic_silence"
    ORIGINAL_POST = "original_post"
    REPLY = "reply"
    QUOTE = "quote"


class Sensitivity(StrEnum):
    NORMAL = "normal"
    SENSITIVE = "sensitive"


class Decision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"
