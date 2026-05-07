from sqlalchemy import Column, String, ForeignKey, text, TIMESTAMP, Date
from sqlalchemy.dialects.postgresql import UUID, JSONB
from .base import Base

class RawMetric(Base):
    __tablename__ = "raw_metrics"
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    import_batch = Column(UUID(as_uuid=True), nullable=False, index=True)
    raw_data = Column(JSONB, nullable=False)
    normalized = Column(JSONB)
    metric_date = Column(Date, index=True)
    campaign_id = Column(String(255))
    imported_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
