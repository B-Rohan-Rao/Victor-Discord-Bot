"""
Main Orchestrator using LangGraph
Coordinates the entire research pipeline
"""

from typing import TypedDict, Optional, Dict, Any, List
from langchain_groq import ChatGroq
from langgraph.graph import StateGraph, END
from pydantic import SecretStr
import uuid

from src.config.settings import settings
from src.cache.manager import CacheManager
from src.models.research import ResearchQuery, ResearchResult
from src.agents.query_planner import QueryPlannerNode
from src.agents.web_search import WebSearchNode
from src.agents.content_scraper import ContentScraperNode
from src.agents.summarizer import SummarizerNode
from src.agents.citation_builder import CitationBuilderNode
from src.agents.hallucination_detector import HallucinationDetectorNode
from src.agents.report_generator import ReportGeneratorNode
from src.agents.discord_notifier import DiscordNotificationNode
from src.utils.logger import logger
from src.utils.source_prioritizer import PrioritizeSources


class ResearchState(TypedDict):
    """LangGraph state for research pipeline"""

    query: str
    query_id: str
    status: str
    research_query: Optional[ResearchQuery]
    url_content_map: Dict[str, str]
    all_citations: List[Any]
    summary: str
    claims_with_citations: List[Any]
    hallucination_flags: List[str]
    result: Optional[ResearchResult]
    retry_count: int
    error: Optional[str]
    notify_discord: bool


class ResearchOrchestrator:
    """
    Main orchestrator that coordinates the research pipeline
    Manages state flow and retry logic
    Integrates caching and Discord notifications
    """

    def __init__(self):
        # Initialize LLM
        self.llm = ChatGroq(
            api_key=SecretStr(settings.groq_api_key),
            model=settings.groq_model_name,
            temperature=0.3,  # Lower temp for more factual responses
            max_tokens=2048
        )

        # Initialize cache
        self.cache = CacheManager()

        # Initialize agent nodes
        self.query_planner = QueryPlannerNode(self.llm)
        self.web_search = WebSearchNode()
        self.content_scraper = ContentScraperNode()
        self.summarizer = SummarizerNode(self.llm)
        self.citation_builder = CitationBuilderNode(self.llm)
        self.hallucination_detector = HallucinationDetectorNode(self.llm)
        self.report_generator = ReportGeneratorNode()
        self.discord_notifier = DiscordNotificationNode()

        # Build graph
        self.graph = self._build_graph()

    def _build_graph(self) -> Any:
        """Build LangGraph workflow"""
        workflow = StateGraph(ResearchState)

        # Add nodes
        workflow.add_node("check_cache", self.node_check_cache)
        workflow.add_node("plan_query", self.node_plan_query)
        workflow.add_node("web_search", self.node_web_search)
        workflow.add_node("scrape_content", self.node_scrape_content)
        workflow.add_node("generate_summary", self.node_generate_summary)
        workflow.add_node("build_citations", self.node_build_citations)
        workflow.add_node("detect_hallucinations", self.node_detect_hallucinations)
        workflow.add_node("generate_report", self.node_generate_report)
        workflow.add_node("send_discord", self.node_send_discord)
        workflow.add_node("cache_result", self.node_cache_result)

        # Add edges (control flow)
        workflow.set_entry_point("check_cache")

        # Check cache → Plan or Return
        workflow.add_conditional_edges(
            "check_cache",
            self.should_use_cache,
            {
                "use_cache": "send_discord",
                "fetch_data": "plan_query"
            }
        )

        # Linear pipeline
        workflow.add_edge("plan_query", "web_search")
        workflow.add_edge("web_search", "scrape_content")
        workflow.add_edge("scrape_content", "generate_summary")
        workflow.add_edge("generate_summary", "build_citations")
        workflow.add_edge("build_citations", "detect_hallucinations")
        workflow.add_edge("detect_hallucinations", "generate_report")
        workflow.add_edge("generate_report", "cache_result")
        workflow.add_edge("cache_result", "send_discord")
        workflow.add_edge("send_discord", END)

        return workflow.compile()

    async def node_check_cache(self, state: ResearchState) -> ResearchState:
        """Check if research result is cached"""
        logger.info(f"Checking cache for: {state['query']}")

        cached_result = await self.cache.get(state['query'])

        if cached_result:
            logger.info("Cache hit!")
            if isinstance(cached_result, ResearchResult):
                state['result'] = cached_result
            else:
                state['result'] = ResearchResult.model_validate(cached_result)
            if state['result'] is not None:
                state['result'].cache_hit = True
            state['status'] = "completed_from_cache"
            return state

        state['status'] = "fetching_data"
        return state

    def should_use_cache(self, state: ResearchState) -> str:
        """Decide whether to use cached result"""
        return "use_cache" if state['result'] else "fetch_data"

    async def node_plan_query(self, state: ResearchState) -> ResearchState:
        """Break query into sub-queries"""
        query_obj = ResearchQuery(
            query=state['query'],
            query_id=state['query_id']
        )

        query_obj = await self.query_planner.process(query_obj)
        state['research_query'] = query_obj
        state['status'] = "query_planned"

        return state

    async def node_web_search(self, state: ResearchState) -> ResearchState:
        """Search the web for information"""
        research_query = state['research_query'] or ResearchQuery(query=state['query'], query_id=state['query_id'])
        citations = await self.web_search.process(research_query)

        # Prioritize sources for production workload
        citations = PrioritizeSources.rank_sources(citations)
        citations = PrioritizeSources.get_top_sources(citations, limit=10)

        state['all_citations'] = citations
        state['status'] = "web_search_complete"

        return state

    async def node_scrape_content(self, state: ResearchState) -> ResearchState:
        """Scrape content from found URLs"""
        state['url_content_map'] = await self.content_scraper.process(state['all_citations'])
        state['status'] = "content_scraped"

        return state

    async def node_generate_summary(self, state: ResearchState) -> ResearchState:
        """Generate research summary"""
        research_query = state['research_query'] or ResearchQuery(query=state['query'], query_id=state['query_id'])
        state['summary'] = await self.summarizer.process(
            research_query,
            state['url_content_map']
        )
        state['status'] = "summary_generated"

        return state

    async def node_build_citations(self, state: ResearchState) -> ResearchState:
        """Build citations for claims"""
        research_query = state['research_query'] or ResearchQuery(query=state['query'], query_id=state['query_id'])
        state['claims_with_citations'] = await self.citation_builder.process(
            state['summary'],
            state['all_citations'],
            research_query
        )
        state['status'] = "citations_built"

        return state

    async def node_detect_hallucinations(self, state: ResearchState) -> ResearchState:
        """Detect potential hallucinations"""
        state['hallucination_flags'] = await self.hallucination_detector.process(
            state['claims_with_citations'],
            state['url_content_map']
        )
        state['status'] = "hallucinations_checked"

        return state

    async def node_generate_report(self, state: ResearchState) -> ResearchState:
        """Generate final report"""
        state['result'] = await self.report_generator.process(
            query=state['query'],
            query_id=state['query_id'],
            summary=state['summary'],
            claims=state['claims_with_citations'],
            all_citations=state['all_citations'],
            hallucination_flags=state['hallucination_flags']
        )
        state['status'] = "report_generated"

        return state

    async def node_cache_result(self, state: ResearchState) -> ResearchState:
        """Cache the research result"""
        if state['result']:
            ttl = settings.cache_ttl
            await self.cache.set(state['query'], state['result'].model_dump(mode="json"), ttl)
            logger.info(f"Result cached for {ttl} seconds")

        return state

    async def node_send_discord(self, state: ResearchState) -> ResearchState:
        """Send report to Discord"""
        if state['notify_discord'] and state['result']:
            await self.discord_notifier.send_report(state['result'])

        return state

    async def execute(self, query: str, notify_discord: bool = True) -> ResearchResult:
        """
        Execute the research pipeline
        Main entry point for the orchestrator
        """
        query_id = str(uuid.uuid4())[:8]
        logger.info(f"Starting research pipeline for: {query} (ID: {query_id})")

        initial_state: ResearchState = {
            "query": query,
            "query_id": query_id,
            "status": "initialized",
            "research_query": None,
            "url_content_map": {},
            "all_citations": [],
            "summary": "",
            "claims_with_citations": [],
            "hallucination_flags": [],
            "result": None,
            "retry_count": 0,
            "error": None,
            "notify_discord": notify_discord,
        }

        try:
            # Run the graph
            result_state = await self.graph.ainvoke(initial_state)
            logger.info(f"Pipeline complete. Status: {result_state['status']}")

            result = result_state.get('result')
            if isinstance(result, ResearchResult):
                return result
            if result is not None:
                return ResearchResult.model_validate(result)

            raise RuntimeError("Pipeline completed without generating a ResearchResult")

        except Exception as e:
            logger.error(f"Pipeline execution error: {e}")
            if notify_discord:
                await self.discord_notifier.send_error_report(query, str(e))
            raise
