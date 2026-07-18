from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..auth import require_phone_token
from ..database import get_db
from ..schemas import PhoneEventInput
from ..config import settings
from ..services.core import phone_usage_for_date, record_phone_event


router = APIRouter(prefix="/api/phone", dependencies=[Depends(require_phone_token)])


@router.post("/events")
def phone_event(payload: PhoneEventInput, db: Session = Depends(get_db)):
    item = record_phone_event(db, payload)
    db.commit()
    return {
        "success": True,
        "data": {
            "id": item.id,
            "app_name": item.app_name,
            "event_type": item.event_type,
            "occurred_at": item.occurred_at.isoformat(),
        },
    }


@router.get("/usage")
def phone_usage(
    day: date | None = Query(default=None, alias="date"),
    device_id: str = "iphone",
    db: Session = Depends(get_db),
):
    local_today = datetime.now(timezone.utc).astimezone(settings.timezone).date()
    return {"success": True, "data": phone_usage_for_date(db, day or local_today, device_id)}
