"""
API Cache Model
Persistent caching for API responses to reduce credit consumption.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text, Index
from datetime import datetime, timezone, timedelta
import json
from app.database import Base


class APICache(Base):
    __tablename__ = "api_cache"
    __table_args__ = (
        Index("ix_apicache_key_expires", "key", "expires_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    data = Column(Text)  # Store JSON as text for maximum compatibility
    source = Column(String, index=True)
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=True, index=True)

    def to_dict(self):
        return json.loads(self.data)

    @staticmethod
    def from_dict(key, data, source, ttl_seconds: int = 3600):
        now = datetime.now(timezone.utc)
        return APICache(
            key=key,
            data=json.dumps(data),
            source=source,
            timestamp=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
        )
