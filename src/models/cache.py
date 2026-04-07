"""Cache data models"""

from pydantic import BaseModel, Field
from typing import Any, Optional
from datetime import datetime


class CacheEntry(BaseModel):
    """Represents a cache entry with expiry"""

    key: str = Field(..., description="Cache key (query hash)")
    value: Any = Field(..., description="Cached research result")
    stored_at: datetime = Field(default_factory=datetime.now)
    expires_at: datetime = Field(..., description="Expiry timestamp")
    ttl_seconds: int = Field(..., description="Time-to-live in seconds")

    def is_expired(self) -> bool:
        """Check if cache entry has expired"""
        return datetime.now() > self.expires_at
