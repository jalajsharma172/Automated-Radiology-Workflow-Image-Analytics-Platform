from typing import TYPE_CHECKING
from sqlalchemy import String, ForeignKey, Float, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base

if TYPE_CHECKING:
    from app.models.scan import Scan

class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    scan_id: Mapped[str] = mapped_column(
        ForeignKey("scans.id", ondelete="CASCADE"), 
        nullable=False
    )
    model_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Stores raw model prediction structures (e.g. bounding boxes, class labels, probabilities)
    prediction: Mapped[dict] = mapped_column(JSON, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    heatmap_url: Mapped[str] = mapped_column(String(512), nullable=True)

    # Relationships
    scan: Mapped["Scan"] = relationship("Scan", back_populates="predictions")
