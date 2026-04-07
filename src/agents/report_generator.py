"""
Report Generator Agent Node
Creates the final research report in structured format
"""

from src.models.research import ResearchResult, ClaimWithCitation, Citation
from src.utils.logger import logger
from typing import List
from datetime import datetime


class ReportGeneratorNode:
    """
    Generates the final research report
    Structures findings with citations and confidence scores
    """

    async def process(
        self,
        query: str,
        query_id: str,
        summary: str,
        claims: List[ClaimWithCitation],
        all_citations: List[Citation],
        hallucination_flags: List[str]
    ) -> ResearchResult:
        """
        Create final research report
        """
        logger.info(f"Generating report for query: {query}")

        # Calculate overall confidence
        if claims:
            avg_confidence = sum(c.confidence for c in claims) / len(claims)
        else:
            avg_confidence = 0.8

        # Create result
        result = ResearchResult(
            query=query,
            query_id=query_id,
            status="completed",
            summary=summary,
            claims=claims,
            all_sources=all_citations,
            confidence_score=avg_confidence,
            hallucination_flags=hallucination_flags,
            completed_at=datetime.now()
        )

        logger.info(f"Report generated. Confidence: {avg_confidence:.0%}")
        return result
