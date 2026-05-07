from sqlalchemy import Column, String, ForeignKey, text, TIMESTAMP, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from .base import Base

class UserTenantMembership(Base):
    __tablename__ = "user_tenant_memberships"
    __table_args__ = (
        UniqueConstraint('user_id', 'tenant_id', name='uq_user_tenant_membership'),
    )
    
    id = Column(UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()"))
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String(50), nullable=False, default='member')
    created_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"))
    updated_at = Column(TIMESTAMP(timezone=True), nullable=False, server_default=text("NOW()"), onupdate=text("NOW()"))
