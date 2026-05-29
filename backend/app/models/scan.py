import enum
from datetime import datetime
from typing import List, Optional, TYPE_CHECKING
from sqlalchemy import String, DateTime, ForeignKey, func, Enum
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.user import User
    from app.models.prediction import Prediction
    from app.models.report import Report
    from app.models.study import Study

class ScanStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

class Scan(Base):
    __tablename__ = "scans"

    id: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), 
        nullable=False
    )
    study_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("studies.id", ondelete="CASCADE"), 
        nullable=True
    )
    scan_type: Mapped[Optional[str]] = mapped_column(
        String(50), 
        nullable=True
    )
    file_url: Mapped[str] = mapped_column(String(512), nullable=False)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    file_size: Mapped[int] = mapped_column(nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[ScanStatus] = mapped_column(
        Enum(ScanStatus, name="scan_status_enum", native_enum=False),
        default=ScanStatus.UPLOADED,
        nullable=False
    )
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="scans")
    study: Mapped[Optional["Study"]] = relationship("Study", back_populates="scans")
    predictions: Mapped[List["Prediction"]] = relationship(
        "Prediction", 
        back_populates="scan", 
        cascade="all, delete-orphan"
    )
    report: Mapped[Optional["Report"]] = relationship(
        "Report", 
        back_populates="scan", 
        uselist=False, 
        cascade="all, delete-orphan"
    )
