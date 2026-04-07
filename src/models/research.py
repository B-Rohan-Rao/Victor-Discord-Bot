"""
Pydantic models for type-safe research data structures
These ensure data consistency throughout the pipeline
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
from datetime import datetime


class Citation(BaseModel):
    """Represents a source citation"""

    title: str = Field(..., description="Title of the source")
    url: str = Field(..., description="URL to the source")
    source_type: str = Field(
        default="web",
        description="Type of source: academic, news, official, blog, etc."
    )
    credibility_score: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Credibility score (0-1)"
    )
    accessed_at: datetime = Field(default_factory=datetime.now)
    snippet: Optional[str] = Field(default=None, description="Excerpt from the source")


class ClaimWithCitation(BaseModel):
    """A research claim linked to its source"""

    claim: str = Field(..., description="The research claim or statement")
    citations: List[Citation] = Field(default_factory=list, description="Supporting citations")
    confidence: float = Field(
        default=0.8,
        ge=0.0,
        le=1.0,
        description="Confidence score for this claim"
    )
    is_hallucination_flagged: bool = Field(default=False)


class ResearchQuery(BaseModel):
    """Input: A research query to process"""

    query: str = Field(..., description="Main research question")
    query_id: str = Field(default="", description="Unique query identifier")
    sub_queries: List[str] = Field(default_factory=list, description="Decomposed search queries")
    requested_at: datetime = Field(default_factory=datetime.now)
    user_id: Optional[str] = Field(default=None, description="User who requested the research")


class ResearchResult(BaseModel):
    """Output: The complete research result"""

    query: str
    query_id: str
    status: str = Field(default="pending", description="pending, processing, completed, failed")
    summary: str = Field(default="", description="Main research summary")
    claims: List[ClaimWithCitation] = Field(
        default_factory=list,
        description="Research claims with citations"
    )
    all_sources: List[Citation] = Field(
        default_factory=list,
        description="All unique sources found"
    )
    confidence_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Overall confidence in the research"
    )
    hallucination_flags: List[str] = Field(
        default_factory=list,
        description="Any claims flagged as potential hallucinations"
    )
    retry_count: int = Field(default=0, description="Number of retries attempted")
    processing_time_seconds: float = Field(default=0.0)
    completed_at: Optional[datetime] = Field(default=None)
    cache_hit: bool = Field(default=False, description="Whether result was from cache")

    def to_dict_for_discord(self) -> Dict[str, Any]:
        """Convert research result to Discord-friendly format"""
        return {
            "query": self.query,
            "summary": self.summary,
            "claims_count": len(self.claims),
            "sources_count": len(self.all_sources),
            "confidence": f"{self.confidence_score * 100:.0f}%",
            "hallucination_flags": self.hallucination_flags,
        }
