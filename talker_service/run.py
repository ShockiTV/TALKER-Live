#!/usr/bin/env python3
"""Entry point for running the TALKER service."""

import sys
import platform
import warnings
from pathlib import Path

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
