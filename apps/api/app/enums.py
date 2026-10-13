from enum import StrEnum


class Role(StrEnum):
    OWNER = "owner"  # the account owner: every action, including approval
    ASSISTANT = "assistant"  # prepares material; never approves or publishes
    SYSADMIN = "sysadmin"  # users and audit only; never touches content


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


RISK_ORDER = {RiskLevel.LOW: 0, RiskLevel.MEDIUM: 1, RiskLevel.HIGH: 2, RiskLevel.CRITICAL: 3}


class Stage(StrEnum):
    DRAFT = "draft"
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


class RedLineKind(StrEnum):
    TOPIC = "topic"  # judged semantically (tone review); needs a model
    PHRASE = "phrase"  # exact wording, matched case-insensitively
