"""
API Cache Model
Persistent caching for API responses to reduce credit consumption.
"""
from sqlalchemy import Column, Integer, String, DateTime, Text
import datetime
import json
from app.database import Base


class APICache(Base):
    __tablename__ = "api_cache"
    __table_args__ = {"extend_existing": True}
    
    id = Column(Integer, primary_key=True, index=True)
    key = Column(String, unique=True, index=True)
    data = Column(Text)  # Store JSON as text for maximum compatibility
    source = Column(String, index=True)
    timestamp = Column(DateTime, default=datetime.datetime.utcnow)
    
    def to_dict(self):
        return json.loads(self.data)
    
    @staticmethod
    def from_dict(key, data, source):
        return APICache(
            key=key,
            data=json.dumps(data),
            source=source,
            timestamp=datetime.datetime.utcnow()
        )
