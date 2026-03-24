#!/usr/bin/env python3
"""Start the runtime API server.

This script handles the Python path setup for proper package imports.
"""

import sys
import os
from pathlib import Path

# Add the product directory to Python path for proper imports
product_dir = Path(__file__).parent.parent
sys.path.insert(0, str(product_dir))

if __name__ == "__main__":
    import uvicorn
    
    # Run using the full module path
    uvicorn.run(
        "runtime.api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info"
    )
