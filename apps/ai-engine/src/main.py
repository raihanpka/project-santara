#!/usr/bin/env python3
"""Main entry point for the Santara AI Engine.

Usage:
    # Run REST API (default)
    python -m src.main

    # Run gRPC server
    python -m src.main --grpc

    # Run both servers
    python -m src.main --both

    # Run with uvicorn directly (REST only)
    uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
"""

import argparse
import asyncio
import signal
import sys
from concurrent.futures import ThreadPoolExecutor

import uvicorn

from src.api.rest_router import app
from src.config import get_settings
from src.logging import configure_logging, get_logger

logger = get_logger(__name__)


def run_rest_server() -> None:
    """Run the FastAPI REST server."""
    settings = get_settings()

    logger.info(
        "starting_rest_server",
        host=settings.host,
        port=settings.port,
    )

    uvicorn.run(
        "src.api.rest_router:app",
        host=settings.host,
        port=settings.port,
        reload=False,
        log_level=settings.log_level.lower(),
    )


async def run_grpc_server() -> None:
    """Run the gRPC server."""
    from src.api.grpc_servicer import run_grpc_server as grpc_main

    await grpc_main()


async def run_both_servers() -> None:
    """Run both REST and gRPC servers concurrently."""
    settings = get_settings()

    logger.info(
        "starting_both_servers",
        rest_port=settings.port,
        grpc_port=settings.grpc_port,
    )

    # Run REST server in a thread (since uvicorn blocks)
    loop = asyncio.get_event_loop()
    executor = ThreadPoolExecutor(max_workers=1)

    # Start REST server in background thread
    rest_future = loop.run_in_executor(executor, run_rest_server)

    # Run gRPC server in the main async loop
    try:
        await run_grpc_server()
    except KeyboardInterrupt:
        pass
    finally:
        executor.shutdown(wait=False)


def main() -> None:
    """Main entry point with CLI argument parsing."""
    parser = argparse.ArgumentParser(
        description="Santara AI Engine - Inference Gateway",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python -m src.main              # Run REST API server
  python -m src.main --grpc       # Run gRPC server
  python -m src.main --both       # Run both servers

Environment variables:
  LLM_SERVICE     - LLM provider (gemini, anthropic, openai)
  LLM_MODEL       - Model identifier
  LLM_API_KEY     - API key for the provider
  NEO4J_URI       - Neo4j connection URI
  LOCALE_COUNTRY  - Country code for localization (ID, US, IN, PH)
        """,
    )

    parser.add_argument(
        "--grpc",
        action="store_true",
        help="Run gRPC server instead of REST API",
    )

    parser.add_argument(
        "--both",
        action="store_true",
        help="Run both REST and gRPC servers",
    )

    parser.add_argument(
        "--rest",
        action="store_true",
        help="Run REST API server (default)",
    )

    args = parser.parse_args()

    # Configure logging
    configure_logging()

    if args.both:
        logger.info("mode_selected", mode="both")
        asyncio.run(run_both_servers())
    elif args.grpc:
        logger.info("mode_selected", mode="grpc")
        asyncio.run(run_grpc_server())
    else:
        logger.info("mode_selected", mode="rest")
        run_rest_server()


if __name__ == "__main__":
    main()
