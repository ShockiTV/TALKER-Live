#!/usr/bin/env python3
"""Entry point for running the TALKER service."""

import os
import sys
import platform
import warnings
from pathlib import Path

# Load .env.local (or .env) into os.environ BEFORE any other imports,
# so that keys like OPENAI_API_KEY are visible to os.environ.get().
# pydantic-settings reads the same files but does NOT inject into os.environ.
from dotenv import load_dotenv

_env_override = os.getenv("TALKER_SERVICE_ENV_FILE", "").strip()
if _env_override:
    load_dotenv(_env_override, override=True)
else:
    # .env.local first (higher priority), then .env as fallback
    load_dotenv(".env.local", override=True)
    load_dotenv(".env", override=False)  # won't overwrite keys already set

# Fix for Windows: pyzmq requires SelectorEventLoop, not ProactorEventLoop
# Must be set BEFORE importing anything that uses asyncio
if platform.system() == "Windows":
    import asyncio
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    # Suppress the tornado fallback warning (it's working, just noisy)
    warnings.filterwarnings("ignore", message=".*Proactor event loop.*", category=RuntimeWarning)

# Add src to path for development
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

from talker_service.__main__ import main

if __name__ == "__main__":
    main()
