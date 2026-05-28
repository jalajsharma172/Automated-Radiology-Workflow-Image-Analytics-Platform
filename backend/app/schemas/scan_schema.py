from datetime import datetime
from pydantic import BaseModel
from app.models.scan import ScanStatus

class ScanResponse(BaseModel):
    id: str
    user_id: int
    file_url: str
    status: ScanStatus
    uploaded_at: datetime

    class Config:
        from_attributes = True

class ScanUploadResponse(BaseModel):
    scan_id: str
    status: ScanStatus
    message: str

    class Config:
        from_attributes = True
