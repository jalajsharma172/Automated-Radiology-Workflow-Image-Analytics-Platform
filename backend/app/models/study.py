from datetime import datetime
from typing import List, TYPE_CHECKING
from sqlalchemy import String, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.scan import Scan

class Study(Base):
    __tablename__ = "studies"

    id: Mapped[str] = mapped_column(String(100), primary_key=True, index=True)
    patient_id: Mapped[str] = mapped_column(String(100), nullable=True)
    study_date: Mapped[str] = mapped_column(String(50), nullable=True)
    priority: Mapped[str] = mapped_column(String(20), default="LOW", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="uploaded", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now(), 
        nullable=False
    )

    # Relationships
    scans: Mapped[List["Scan"]] = relationship(
        "Scan", 
        back_populates="study", 
        cascade="all, delete-orphan"
    )
