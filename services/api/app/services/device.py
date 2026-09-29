from sqlalchemy.orm import Session

from app.repository.device import get_or_create_device
from app.repository.models import DeviceUser


def resolve_device(session: Session, device_id: str) -> DeviceUser:
    return get_or_create_device(session, device_id)
