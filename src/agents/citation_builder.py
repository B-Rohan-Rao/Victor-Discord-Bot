"""
Citation Builder Agent Node
Builds citations for specific claims from the research
"""

from typing import List
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from src.models.research import ClaimWithCitation, Citation, ResearchQuery
from src.utils.logger import logger
import json
import re


class CitationBuilderNode:
    """
    Links research claims to their source citations
    Ensures every claim has supporting evidence
    """

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    async def process(
        self,
        summary: str,
        citations: List[Citation],
        query: ResearchQuery
    ) -> List[ClaimWithCitation]:
        """
        Extract claims from summary and link citations
        """
        logger.info("Building citations for claims")

        # Format available sources
        sources_text = "\n".join([
            f"- {c.title} ({c.url}): {c.source_type}"
            for c in citations[:5]  # Use top sources
        ])

        prompt = f"""
        From the following research summary, extract 3-5 important claims/facts.
        For each claim, determine which of the provided sources best support it.
        
        Summary:
        {summary}
        
        Available Sources:
        {sources_text}
        
        Return a JSON array with this structure:
        [
            {{
                "claim": "The specific claim or fact",
                "citation_index": 0,
                "confidence": 0.85
            }}
        ]
        
        Return ONLY the JSON array, no other text.
        """

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            response_text = response.content if isinstance(response.content, str) else str(response.content)

            # Extract JSON
            json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
            if json_match:
                claims_data = json.loads(json_match.group())
                if not isinstance(claims_data, list):
                    logger.warning("Claims payload is not a list")
                    return []
            else:
                logger.warning("Could not parse claims from response")
                return []

            # Build ClaimWithCitation objects
            claims_with_citations = []
            for claim_data in claims_data:
                try:
                    citation_idx = claim_data.get("citation_index", 0)
                    if 0 <= citation_idx < len(citations):
                        citation = citations[citation_idx]
                        cwc = ClaimWithCitation(
                            claim=claim_data.get("claim", ""),
                            citations=[citation],
                            confidence=claim_data.get("confidence", 0.8)
                        )
                        claims_with_citations.append(cwc)
                except Exception as e:
                    logger.warning(f"Error creating citation: {e}")

            logger.info(f"Created {len(claims_with_citations)} cited claims")
            return claims_with_citations

        except Exception as e:
            logger.error(f"Error building citations: {e}")
            return []
