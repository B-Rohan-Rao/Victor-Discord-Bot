"""LLM topic categorizer for subscription update strategy."""

import re
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage
from src.models.subscription import SubscriptionCategory
from src.utils.logger import logger


class TopicCategorizerNode:
    """Classifies topics into dynamic, semi-static, or static."""

    def __init__(self, llm: BaseChatModel):
        self.llm = llm

    async def categorize(self, topic: str) -> SubscriptionCategory:
        """Run one-shot categorization with safe fallback."""
        prompt = f"""
        Classify the topic below into exactly one category:
        - dynamic: rapidly changing topics (stocks, politics, breaking news, fast-moving tech)
        - semi-static: occasional change topics (industry trends, product comparisons)
        - static: rarely changing topics (history, established scientific facts, landmarks)

        Topic: {topic}

        Return only one lowercase token:
        dynamic OR semi-static OR static
        """

        try:
            response = await self.llm.ainvoke([HumanMessage(content=prompt)])
            content = response.content if isinstance(response.content, str) else str(response.content)
            normalized = content.strip().lower()
            match = re.search(r"dynamic|semi-static|static", normalized)
            if match:
                category = match.group(0)
                logger.info(f"Topic categorized as {category}: {topic}")
                return category  # type: ignore[return-value]

            logger.warning(f"Categorizer returned unexpected response: {content}")
            return "semi-static"
        except Exception as exc:
            logger.error(f"Topic categorization failed for '{topic}': {exc}")
            return "semi-static"
