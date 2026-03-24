#!/usr/bin/env python3
"""Start the AgentX API server."""

import sys
import os

# Ensure runtime is in path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from runtime.api.main import app
import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "runtime.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
