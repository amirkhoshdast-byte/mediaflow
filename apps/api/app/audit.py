from sqlalchemy.orm import Session

from app.models import AuditLog


def log(
    db: Session,
    user_id: str | None,
    action: str,
    entity: str | None = None,
    entity_id: str | None = None,
    detail: dict | None = None,
) -> None:
    db.add(
        AuditLog(user_id=user_id, action=action, entity=entity, entity_id=entity_id, detail=detail)
    )
