"""
Content Scraper Agent Node
Extracts and parses content from URLs
"""

from typing import Dict, List
from bs4 import BeautifulSoup
import asyncio
import httpx
from src.models.research import Citation
from src.utils.logger import logger
from src.config.settings import settings


class ContentScraperNode:
    """
    Scrapes content from URLs found in search results
    Extracts main text and relevant information
    """

    def __init__(self):
        self.timeout = settings.request_timeout
        self.user_agent = settings.user_agent

    async def scrape_url(self, citation: Citation) -> str:
        """
        Scrape content from a single URL
        Returns cleaned text content
        """
        try:
            headers = {"User-Agent": self.user_agent}

            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(citation.url, headers=headers)
                response.raise_for_status()

                # Parse HTML
                soup = BeautifulSoup(response.text, "html.parser")

                # Remove script and style elements
                for script in soup(["script", "style"]):
                    script.decompose()

                # Get text
                text = soup.get_text(separator=" ", strip=True)

                # Clean up whitespace
                lines = (line.strip() for line in text.splitlines())
                chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                text = " ".join(chunk for chunk in chunks if chunk)

                return text[:2000]  # Limit to 2000 chars

        except Exception as e:
            logger.warning(f"Error scraping {citation.url}: {e}")
            return citation.snippet or ""

    async def process(self, citations: List[Citation]) -> Dict[str, str]:
        """
        Scrape all citations in parallel
        Returns dict of {url: content}
        """
        logger.info(f"Scraping {len(citations)} URLs")

        tasks = [self.scrape_url(citation) for citation in citations]
        contents = await asyncio.gather(*tasks, return_exceptions=True)

        url_content_map = {}
        for citation, content in zip(citations, contents):
            if isinstance(content, str):
                url_content_map[citation.url] = content
            else:
                logger.warning(f"Failed to scrape {citation.url}")

        logger.info(f"Successfully scraped {len(url_content_map)} URLs")
        return url_content_map
