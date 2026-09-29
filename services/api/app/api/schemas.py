from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadyResponse(BaseModel):
    status: str


class DeviceResponse(BaseModel):
    deviceId: str
