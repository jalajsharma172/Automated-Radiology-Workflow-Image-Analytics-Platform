from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel
from app.schemas.scan_schema import ScanResponse

class StudyResponse(BaseModel):
    id: str
    patient_id: Optional[str] = None
    study_date: Optional[str] = None
    priority: str
    status: str
    created_at: datetime
    scans: List[ScanResponse] = []

    class Config:
        from_attributes = True

class StudyUploadResponse(BaseModel):
    study_id: str
    status: str
    message: str

    class Config:
        from_attributes = True
