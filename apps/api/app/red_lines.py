"""Red-line list: topics and wording the account must not touch without a higher approval level.

The starting list is taken from the account's voice guide. It is a draft until the President's
Office approves it (proposal section 4) and is edited through the API afterwards.
"""

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.enums import RedLineKind as K
from app.enums import RiskLevel as R
from app.models import AuditLog, RedLine

# (kind, pattern, description, severity)
STARTER: list[tuple[K, str, str, R]] = [
    (K.TOPIC, "عملیات نظامی", "منطقه قرمز راهنمای صدا: موضع رسمی کار وزارت خارجه است", R.HIGH),
    (K.TOPIC, "اتهام امنیتی و پرونده قضایی", "منطقه قرمز راهنمای صدا", R.HIGH),
    (K.TOPIC, "جزئیات مذاکرات", "منطقه قرمز راهنمای صدا", R.HIGH),
    (K.TOPIC, "سیاست داخلی کشورهای دیگر", "منطقه قرمز راهنمای صدا", R.HIGH),
    (K.TOPIC, "انتخابات", "منطقه قرمز راهنمای صدا", R.HIGH),
    (K.TOPIC, "درگیری با اشخاص یا حساب‌ها", "منطقه قرمز راهنمای صدا", R.HIGH),
    (K.PHRASE, "محکوم می‌کنیم", "واژه پرهیز: «محکوم می‌کنیم» در آغاز جمله", R.MEDIUM),
    (K.PHRASE, "we condemn", "Avoid as an opener (voice guide)", R.MEDIUM),
    (K.PHRASE, "arrogant powers", "Labelling vocabulary (voice guide)", R.MEDIUM),
    (K.PHRASE, "so-called", "Dismissive vocabulary (voice guide)", R.MEDIUM),
    (K.PHRASE, "قدرت‌های مستکبر", "واژگان برچسب‌زننده (راهنمای صدا)", R.MEDIUM),
    (K.PHRASE, "دشمن", "دشمن‌سازی (راهنمای صدا)", R.MEDIUM),
]


def seed_red_lines(db: Session) -> None:
    """Only on a pristine system: once anyone has touched the list, never put entries back."""
    touched = db.scalar(select(func.count()).select_from(RedLine)) or db.scalar(
        select(func.count()).select_from(AuditLog).where(AuditLog.action.like("redline.%"))
    )
    if touched:
        return
    db.add_all(
        RedLine(kind=k.value, pattern=p, description=d, severity=s.value) for k, p, d, s in STARTER
    )
    db.commit()
