# Autonomous Research Agent 🔬

A production-grade agentic AI system that autonomously researches topics, verifies information, detects hallucinations, cites sources, and delivers reports via Discord.

## ✨ Features

- **🧠 Multi-Stage Agent Workflow** - LangGraph orchestration with 9 specialized nodes
- **🌐 Automated Web Research** - Searches using Serper with source prioritization
- **📰 Content Scraping** - Extracts and cleans content from discovered sources
- **✍️ Dynamic Summarization** - LLM-generated research summaries with context awareness
- **📚 Automatic Citations** - Links every claim to supporting sources
- **🚨 Hallucination Detection** - Validates claims against source material
- **💾 Volatile Caching** - 30-day TTL cache in Redis with MongoDB backing store
- **🔥 Gen-Z Discord Reports** - Eye-catching formatted embeds with emojis and confidence scores
- **⚡ Production-Ready** - Handles concurrent queries, rate limiting, and graceful failures

## 🏗️ Architecture

### LangGraph State Machine
```
Cache Check → Query Planning → Web Search → Content Scraping 
→ Summarization → Citation Building → Hallucination Detection 
→ Report Generation → Caching → Discord Notification
```

### Agent Nodes

| Node | Purpose |
|------|---------|
| `QueryPlannerNode` | Breaks research query into sub-queries |
| `WebSearchNode` | Searches web using Serper |
| `ContentScraperNode` | Extracts content from URLs |
| `SummarizerNode` | Generates research summary |
| `CitationBuilderNode` | Links claims to sources |
| `HallucinationDetectorNode` | Validates claims against sources |
| `ReportGeneratorNode` | Creates final report |
| `DiscordNotificationNode` | Sends formatted Discord embeds |

## 🚀 Quick Start

### 1. Prerequisites

- Python 3.11+
- Groq API key (get at https://console.groq.com)
- Discord webhook URL (optional, for Discord notifications)
- Redis and MongoDB (managed services recommended)

### 2. Installation

```bash
# Clone/navigate to project
cd "Autonomous Research Agent"

# Install dependencies using uv
uv sync

# Optional: include dev tools (pytest, ruff, black)
uv sync --extra dev
```

### 3. Configuration

```bash
# Copy example environment file
cp .env.example .env

# Edit .env with your credentials
# GROQ_API_KEY=your_key_here
# DISCORD_WEBHOOK_URL=your_webhook_here (optional)
# DISCORD_BOT_TOKEN=your_bot_token (required for /agent slash bot)
# DISCORD_GUILD_ID=your_server_id (optional, faster command sync)
# REDIS_HOST=your_redis_host
# MONGO_URI=your_mongodb_uri
```

### 4. Run the Agent

```bash
# Using Python directly
python main.py

# Or using uv (Recommended)
uv run main.py

# Run Discord slash-command bot (/agent)
uv run python -m src.discord_bot
```

## 📖 Usage Examples

### Basic Research Query

```python
import asyncio
from src.orchestrator import ResearchOrchestrator

async def research():
    orchestrator = ResearchOrchestrator()
    result = await orchestrator.execute(
        "What are the latest developments in artificial intelligence?"
    )
    
    print(result.summary)
    print(f"Confidence: {result.confidence_score * 100:.0f}%")
    print(f"Sources: {len(result.all_sources)}")
    
    if result.hallucination_flags:
        print(f"Potential issues: {result.hallucination_flags}")

asyncio.run(research())
```

### Production Batch Processing

```python
import asyncio
from src.orchestrator import ResearchOrchestrator

async def batch_research(queries):
    orchestrator = ResearchOrchestrator()
    
    tasks = [
        orchestrator.execute(query) 
        for query in queries
    ]
    
    results = await asyncio.gather(*tasks)
    return results

# Research multiple topics concurrently
queries = [
    "Quantum computing breakthroughs",
    "Neural networks explained",
    "Blockchain use cases"
]

results = asyncio.run(batch_research(queries))
```

## 🔧 Configuration Options

### Environment Variables

```env
# LLM
GROQ_API_KEY=your_api_key
GROQ_MODEL=llama-3.1-8b-instant

# Search
SERPER_API_KEY=your_serper_api_key

# Cache
CACHE_TTL=2592000              # 30 days in seconds

# Redis (primary cache)
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# MongoDB (backing store)
MONGO_URI=mongodb://localhost:27017
MONGO_DATABASE=autonomous_research_agent
MONGO_COLLECTION=research_results

# Discord
DISCORD_WEBHOOK_URL=your_webhook_url
DISCORD_BOT_TOKEN=your_bot_token
DISCORD_GUILD_ID=your_server_id_optional

# Web Scraping
MAX_SEARCH_RESULTS=5
REQUEST_TIMEOUT=10
USER_AGENT=Mozilla/5.0...

# Production
MAX_CONCURRENT_QUERIES=5
HALLUCINATION_THRESHOLD=0.75   # 0-1, higher = stricter
LOG_LEVEL=INFO                 # Debug, Info, Warning, Error
DEBUG_MODE=False
```

## 🎯 Key Design Decisions (Production-Grade)

### 1. **Source Prioritization**
The system automatically rates sources:
- Academic sources (0.95) > Official (0.90) > News (0.75) > Blogs (0.40)
- Trusted domains (arXiv, Nature, IEEE) get reputation bonuses
- Filters to high-quality sources for production workloads

### 2. **Citation Grounding**
Every research claim must have:
- A supporting source URL
- Confidence score (0-1)
- Direct link to evidence

Hallucinations without sources are flagged.

### 3. **Caching Strategy**
- 30-day TTL prevents redundant scraping
- Uses Redis for low-latency cache hits and MongoDB for durable recovery
- Query hashing for consistent cache keys
- Automatic expiry via TTL checks

### 4. **Concurrency & Scaling**
- Async/await throughout for non-blocking operations
- Parallel URL scraping using `asyncio.gather()`
- Queue-based request management
- Graceful error handling per-request

### 5. **Hallucination Mitigation**
- LLM validates claims against source material
- Low confidence claims are flagged, not removed
- User sees transparency about verification confidence
- Retry logic available (but disabled by default to keep results fast)

### 6. **Discord Gen-Z Formatting**
- Emojis and colors for visual interest
- Confidence scores with emoji indicators
- Clean structured embeds with collapsible sections
- Direct links to sources
- Timestamps and status indicators

## 📊 State Flow

### ResearchState TypedDict

```python
{
    "query": str,                          # Original research query
    "query_id": str,                       # Unique run ID
    "status": str,                         # Pipeline status
    "research_query": ResearchQuery,       # Decomposed sub-queries
    "url_content_map": Dict[str, str],    # URL → scraped content
    "all_citations": List[Citation],      # All sources found
    "summary": str,                        # Research summary
    "claims_with_citations": List[...],   # Claims linked to sources
    "hallucination_flags": List[str],     # Potential issues
    "result": ResearchResult,              # Final output
    "retry_count": int,                    # Number of retries
    "error": Optional[str]                 # Error message if any
}
```

## 🧪 Testing

```bash
# Run tests
pytest tests/

# With coverage
pytest --cov=src tests/

# Specific test
pytest tests/test_cache.py -v
```

## 📚 Project Structure

```
Autonomous Research Agent/
├── src/
│   ├── agents/                 # Agent node modules
│   │   ├── query_planner.py
│   │   ├── web_search.py
│   │   ├── content_scraper.py
│   │   ├── summarizer.py
│   │   ├── citation_builder.py
│   │   ├── hallucination_detector.py
│   │   ├── report_generator.py
│   │   └── discord_notifier.py
│   ├── cache/                  # Caching layer
│   │   ├── manager.py
│   │   ├── redis_cache.py
│   │   └── mongodb_store.py
│   ├── config/                 # Settings & configuration
│   │   └── settings.py
│   ├── models/                 # Pydantic data models
│   │   ├── research.py
│   │   └── cache.py
│   ├── utils/                  # Utilities & helpers
│   │   ├── logger.py
│   │   ├── validators.py
│   │   └── source_prioritizer.py
│   └── orchestrator.py         # Main LangGraph orchestrator
├── tests/                      # Test suite
├── main.py                     # CLI entry point
├── pyproject.toml              # Dependencies
├── .env.example                # Configuration template
└── README.md                   # This file
```

## 🔍 Debugging

### Enable Debug Logging

```env
LOG_LEVEL=DEBUG
DEBUG_MODE=True
```

### Check Logs

```bash
tail -f logs/research_agent.log
```

### Inspect Cache

```bash
# Redis
redis-cli
> KEYS *
> GET key_name

# MongoDB
mongosh
> use autonomous_research_agent
> db.research_results.find().sort({created_at:-1}).limit(3)
```

## ⚠️ Limitations & Future Work

### Current Limitations
- LLM hallucination detection is not 100% reliable (use as a flag, not guarantee)
- Web scraping depends on site structure (may fail on JavaScript-heavy sites)
- Rate limiting applies per source (respects robots.txt)
- Discord notifications require active webhook

### Future Enhancements
- [ ] Multi-model support (Claude, GPT-4, local models)
- [ ] Custom source prioritization rules
- [ ] A/B testing for different research strategies
- [ ] Research history & trend analysis
- [ ] Fact-checking with external APIs
- [ ] Streaming results in real-time
- [ ] User authentication & per-user caching

## 📄 License

MIT

## 🤝 Contributing

Contributions welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📞 Support

For issues, questions, or suggestions:
- Create an issue on GitHub
- Check logs in `logs/research_agent.log`
- Review configuration in `.env`

---

**Built with ❤️ for production-grade AI research automation**
