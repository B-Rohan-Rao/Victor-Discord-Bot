"""
Summarizer Agent Node
Generates research summary from scraped content
"""

from typing import Dict
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from src.models.research import ResearchQuery
from src.utils.logger import logger


class SummarizerNode:
    """
    Creates a comprehensive summary of research findings
    Incorporates information from multiple sources
    """

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    async def process(
        self,
        query: ResearchQuery,
        url_content_map: Dict[str, str]
    ) -> str:
        """
        Generate summary from scraped content
        """
        logger.info(f"Generating summary for: {query.query}")

        # Prepare content context
        context = "\n\n".join([
            f"Source: {url}\nContent: {content[:500]}..."
            for url, content in list(url_content_map.items())[:5]  # Use top 5 sources
        ])

        prompt = f"""
        Based on the following research materials about "{query.query}", 
        create a comprehensive but concise summary (150-300 words).
        
        Focus on:
        - Main findings and key concepts
        - Important facts and statistics
        - Recent developments
        - Practical applications
        
        Research Materials:
        {context}
        
        Please provide a well-structured summary.
        """

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            summary = response.content if isinstance(response.content, str) else str(response.content)
            logger.info("Summary generated successfully")
            return summary

        except Exception as e:
            logger.error(f"Error generating summary: {e}")
            return "Unable to generate summary at this time."
