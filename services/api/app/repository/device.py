from sqlalchemy.orm import Session

from app.repository.models import DeviceUser


def get_or_create_device(session: Session, device_id: str) -> DeviceUser:
    device = session.get(DeviceUser, device_id)
    if device is None:
        device = DeviceUser(device_id=device_id)
        session.add(device)
        session.commit()
        session.refresh(device)
    return device
