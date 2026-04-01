#!/usr/bin/env python3
"""Main entry point for the Santara AI Engine.

Usage:
    # Run with uvicorn directly
    uvicorn src.main:app --reload --host 0.0.0.0 --port 8000

    # Or run this script
    python -m src.main
"""

import uvicorn

from src.api.rest_router import app
from src.config import get_settings


def main() -> None:
    """Run the FastAPI application."""
    settings = get_settings()

    uvicorn.run(
        "src.api.rest_router:app",
        host=settings.host,
        port=settings.port,
        reload=True,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    main()
