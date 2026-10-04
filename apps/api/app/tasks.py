import logging

from app.ai import get_gateway
from app.ai.gateway import extract_json
from app.analysis import normalize_analysis
from app.celery_app import celery
from app.db import SessionLocal
from app.enums import SignalStatus
from app.models import Signal

log = logging.getLogger("ncr.tasks")


@celery.task(name="signals.analyze")
def analyze_signal(signal_id: str) -> None:
    with SessionLocal() as db:
        signal = db.get(Signal, signal_id)
        if not signal:
            return
        try:
            result = get_gateway().run(
                db, "signal_analysis", {"text": signal.raw_item.text[:8000]}, max_tokens=800
            )
            for key, value in normalize_analysis(extract_json(result.text)).items():
                setattr(signal, key, value)
            signal.status, signal.error = SignalStatus.READY.value, None
        except Exception as e:  # noqa: BLE001 - any failure must surface on the signal, not vanish
            log.exception("signal analysis failed")
            signal.status = SignalStatus.FAILED.value
            signal.error = f"{e.__class__.__name__}: {str(e)[:300]}"
        db.commit()
