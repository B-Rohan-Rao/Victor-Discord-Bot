"""Subscription models for weekly topic updates."""

from datetime import datetime, timedelta, timezone
from typing import Literal
from pydantic import BaseModel, Field


SubscriptionCategory = Literal["dynamic", "semi-static", "static"]
SubscriptionStatus = Literal["active", "expired"]


class Subscription(BaseModel):
    """Topic subscription persisted in MongoDB."""

    user_id: str = Field(..., description="Discord user ID")
    topic: str = Field(..., min_length=1, description="Original subscribed topic")
    category: SubscriptionCategory = Field(..., description="LLM category for cadence")
    execution_day: int = Field(..., ge=0, le=6, description="0=Monday ... 6=Sunday")
    last_known_urls: list[str] = Field(default_factory=list)
    last_checked: datetime | None = Field(default=None)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc) + timedelta(days=60)
    )
    status: SubscriptionStatus = Field(default="active")
