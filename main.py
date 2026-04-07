"""
Main CLI Application
Entry point for the Autonomous Research Agent
"""

import asyncio
import sys
from pathlib import Path

# Add src to path


from src.orchestrator import ResearchOrchestrator
from src.utils.logger import logger
from src.config.settings import settings


async def main():
    """
    Main entry point
    Demonstrates how to use the research agent
    """
    print("\n" + "="*60)
    print("🔬 Autonomous Research Agent")
    print("="*60)

    # Check configuration
    if not settings.groq_api_key:
        logger.error("GROQ_API_KEY not set in .env file")
        print("❌ Error: GROQ_API_KEY not configured")
        print("Please create a .env file with your Groq API key")
        print("See .env.example for reference")
        return

    if not settings.discord_webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL not set - Discord notifications disabled")

    # Initialize orchestrator
    logger.info("Initializing research orchestrator...")
    orchestrator = ResearchOrchestrator()

    # Example research queries
    example_queries = [
        "What are the latest developments in quantum computing?",
        "How does machine learning work?",
        "What is blockchain technology used for?"
    ]

    # Get user input or use example
    print("📝 Enter a research query:")
    print("(Press Enter to use an example query)")

    user_input = input("> ").strip()

    if user_input:
        query = user_input
    else:
        query = example_queries[0]
        print(f"Using example query: {query}")

    # Validate query
    from src.utils.validators import validate_query
    is_valid, error_msg = validate_query(query)

    if not is_valid:
        logger.error(f"Invalid query: {error_msg}")
        print(f"❌ Error: {error_msg}")
        return

    # Execute research
    print(f"🔍 Researching: {query}")
    print("(This may take a minute...)\n")

    try:
        result = await orchestrator.execute(query)

        # Display results
        print("\n" + "="*60)
        print("✅ Research Complete!")
        print("="*60)
        print(f"📊 Query: {result.query}")
        print(f"📝 Summary:{result.summary[:500]}...")
        print(f"📍 Sources Found: {len(result.all_sources)}")
        print(f"📊 Confidence: {result.confidence_score * 100:.0f}%")

        if result.hallucination_flags:
            print(f"⚠️  Flags ({len(result.hallucination_flags)}):")
            for flag in result.hallucination_flags[:3]:
                print(f"  {flag}")
    
        if settings.discord_webhook_url:
            print(f"✉️  Report sent to Discord!")

        print("\n" + "="*60 + "\n")

    except Exception as e:
        logger.error(f"Error executing research: {e}")
        print(f"❌ Error: {str(e)}")
        print("Check logs for details")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("❌ Interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unhandled exception: {e}")
        print(f"❌ Fatal error: {e}")
        sys.exit(1)
