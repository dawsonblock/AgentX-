#!/usr/bin/env python3
"""Initialize database."""

import sys
import os

# Add parent to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.session import init_db

def main():
    """Initialize database tables."""
    print("Initializing database...")
    init_db()
    print("Database ready!")


if __name__ == "__main__":
    main()
