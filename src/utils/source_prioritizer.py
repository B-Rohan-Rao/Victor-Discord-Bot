"""
Source prioritization for production-grade research
Scores and ranks sources based on credibility
"""

from typing import List, Optional
from src.models.research import Citation
from src.config.settings import settings


class PrioritizeSources:
    """Prioritize research sources for production workloads"""

    # Source type credibility scores (0-1)
    SOURCE_CREDIBILITY = {
        "academic": 0.95,
        "official": 0.90,
        "news": 0.75,
        "whitepaper": 0.85,
        "blog": 0.40,
        "social_media": 0.10,
        "wiki": 0.65,
        "web": 0.50,
    }

    # Domain reputation scores
    TRUSTED_DOMAINS = {
        "arxiv.org": 0.98,
        "nature.com": 0.97,
        "science.org": 0.97,
        "ieee.org": 0.96,
        "acm.org": 0.95,
        "github.com": 0.88,
        "stackoverflow.com": 0.85,
        "wikipedia.org": 0.70,
        "medium.com": 0.60,
        "reddit.com": 0.40,
    }

    @staticmethod
    def extract_domain(url: str) -> str:
        """Extract domain from URL"""
        try:
            from urllib.parse import urlparse
            domain = urlparse(url).netloc.lower()
            # Remove www.
            if domain.startswith("www."):
                domain = domain[4:]
            return domain
        except:
            return ""

    @staticmethod
    def score_citation(citation: Citation) -> float:
        """
        Score a citation based on multiple factors
        Returns score between 0 and 1
        """
        base_score = PrioritizeSources.SOURCE_CREDIBILITY.get(
            citation.source_type, 0.50
        )

        domain = PrioritizeSources.extract_domain(citation.url)
        domain_score = PrioritizeSources.TRUSTED_DOMAINS.get(domain, 0.50)

        # Weight: domain reputation (40%) + source type (40%) + custom credibility (20%)
        final_score = (domain_score * 0.4) + (base_score * 0.4) + (citation.credibility_score * 0.2)

        return min(1.0, max(0.0, final_score))

    @staticmethod
    def rank_sources(citations: List[Citation]) -> List[Citation]:
        """
        Rank citations by credibility
        Returns sorted list (highest credibility first)
        """
        scored = [
            (citation, PrioritizeSources.score_citation(citation))
            for citation in citations
        ]
        scored.sort(key=lambda x: x[1], reverse=True)
        return [citation for citation, _ in scored]

    @staticmethod
    def filter_by_preferred_sources(
        citations: List[Citation],
        preferred: Optional[List[str]] = None
    ) -> List[Citation]:
        """
        Filter citations to only include preferred source types
        Useful for production workloads that need high-quality sources
        """
        if preferred is None:
            preferred = settings.preferred_sources_list

        return [
            citation for citation in citations
            if citation.source_type in preferred
        ]

    @staticmethod
    def get_top_sources(
        citations: List[Citation],
        limit: Optional[int] = None,
        min_credibility: float = 0.5
    ) -> List[Citation]:
        """
        Get top N sources above credibility threshold
        Ideal for production use where source quality matters
        """
        limit = limit or settings.max_search_results

        ranked = PrioritizeSources.rank_sources(citations)
        filtered = [
            c for c in ranked
            if PrioritizeSources.score_citation(c) >= min_credibility
        ]

        return filtered[:limit]
