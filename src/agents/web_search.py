"""
Web Search Agent Node
Searches the web using Serper
"""

from typing import List
import httpx
from src.models.research import ResearchQuery, Citation
from src.utils.logger import logger
from src.config.settings import settings


class WebSearchNode:
    """
    Performs web searches using Serper
    Gathers multiple sources for each sub-query
    """

    def __init__(self):
        self.api_url = "https://google.serper.dev/search"
        self.api_key = settings.serper_api_key
        self.timeout = settings.request_timeout
        self.max_results = settings.max_search_results

    async def search(self, query: str) -> List[Citation]:
        """
        Search for information on a query
        Returns list of citations with URLs
        """
        logger.info(f"Searching for: {query}")

        if not self.api_key:
            logger.error("SERPER_API_KEY is missing. Set it in .env to enable web search.")
            return []

        try:
            headers = {
                "X-API-KEY": self.api_key,
                "Content-Type": "application/json",
            }
            payload = {
                "q": query,
                "num": self.max_results,
            }

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(self.api_url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()

            results = data.get("organic", [])

            citations = []
            for result in results:
                try:
                    citation = Citation(
                        title=result.get("title", "Unknown"),
                        url=result.get("link", ""),
                        source_type="web",
                        credibility_score=0.70,  # Default, will be updated by prioritizer
                        snippet=result.get("snippet", "")[:200]  # First 200 chars
                    )
                    if citation.url:
                        citations.append(citation)
                except Exception as e:
                    logger.warning(f"Error creating citation: {e}")

            logger.info(f"Found {len(citations)} sources")
            return citations

        except Exception as e:
            logger.error(f"Search error: {e}")
            return []

    async def process(self, query: ResearchQuery) -> List[Citation]:
        """
        Search for all sub-queries
        Returns aggregated citations
        """
        all_citations = []

        sub_queries = query.sub_queries if query.sub_queries else [query.query]

        for sub_query in sub_queries:
            citations = await self.search(sub_query)
            all_citations.extend(citations)

        # Remove duplicates by URL
        seen_urls = set()
        unique_citations = []
        for citation in all_citations:
            if citation.url not in seen_urls:
                seen_urls.add(citation.url)
                unique_citations.append(citation)

        logger.info(f"Total unique sources found: {len(unique_citations)}")
        return unique_citations
