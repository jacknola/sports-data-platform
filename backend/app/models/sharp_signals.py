from datetime import datetime
from enum import Enum
from typing import Optional
from dataclasses import dataclass, field


class DataQuality(str, Enum):
    """Data quality levels for sharp money signals."""
    LIVE = "live"
    PARTIAL = "partial"
    MOCK = "mock"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    INFERRED = "inferred"


class DataSource(str, Enum):
    """Data sources for sharp money signals."""
    ODDS_API = "odds_api"
    PUBLIC_FEED = "public_feed"
    CACHED = "cached"
    SIMULATED = "simulated"
    INFERRED = "inferred"
    LINE_MOVEMENT_PROXY = "line_movement_proxy"
    BOOK_DIVERGENCE = "book_divergence"


@dataclass
class SignalMetadata:
    """Metadata for sharp money signals."""
    quality: DataQuality
    source: DataSource
    timestamp: datetime = field(default_factory=datetime.utcnow)
    freshness_seconds: Optional[int] = None
    inference_method: Optional[str] = None
    provider: Optional[str] = None
    
    def __post_init__(self):
        if self.freshness_seconds is None:
            self.freshness_seconds = int(
                (datetime.utcnow() - self.timestamp).total_seconds()
            )
    
    @property
    def is_fresh(self) -> bool:
        return self.freshness_seconds < 300 if self.freshness_seconds else False
    
    @property
    def is_production_ready(self) -> bool:
        return self.quality in [
            DataQuality.LIVE, DataQuality.PARTIAL, DataQuality.INFERRED
        ] and self.source not in [DataSource.SIMULATED]


@dataclass  
class SharpSignal:
    """Base class for sharp money signals with metadata."""
    signal_type: str
    confidence: float
    metadata: SignalMetadata
    description: Optional[str] = None