"""
Query Planner Agent Node
Breaks down a research query into more specific sub-queries
"""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from src.models.research import ResearchQuery
from src.utils.logger import logger


class QueryPlannerNode:
    """
    Decomposes a research query into sub-queries
    
    Example:
        Input: "What is quantum computing?"
        Output: [
            "What are quantum bits?",
            "How do quantum computers work?",
            "What are the applications of quantum computing?",
            "What are the challenges in quantum computing?"
        ]
    """

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    async def process(self, query: ResearchQuery) -> ResearchQuery:
        """
        Break query into sub-queries
        """
        logger.info(f"Planning query: {query.query}")

        prompt = f"""
        You are a research planning assistant. Break down the following research query into 3-5 specific, 
        focused sub-queries that will help thoroughly research the topic.
        
        Original Query: {query.query}
        
        Requirements:
        - Each sub-query should be specific and searchable
        - Cover different aspects of the topic
        - Make them distinct from each other
        - Format as a JSON list: ["query1", "query2", "query3"]
        
        Return ONLY the JSON list, no other text.
        """

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            response_text = response.content if isinstance(response.content, str) else str(response.content)

            # Parse the response
            import json
            import re

            # Extract JSON from response
            json_match = re.search(r"\[.*\]", response_text, re.DOTALL)
            if json_match:
                sub_queries = json.loads(json_match.group())
                if isinstance(sub_queries, list):
                    query.sub_queries = [str(item) for item in sub_queries]
                else:
                    query.sub_queries = [query.query]
                logger.info(f"Created {len(sub_queries)} sub-queries")
            else:
                logger.warning("Could not parse sub-queries from response")
                query.sub_queries = [query.query]  # Fallback to original query

        except Exception as e:
            logger.error(f"Error in query planning: {e}")
            query.sub_queries = [query.query]  # Fallback

        return query
