#!/usr/bin/env python3
"""Simple HTTP server for the dashboard.

Serves the dashboard at http://localhost:8080
"""

import http.server
import socketserver
import os
import webbrowser
from pathlib import Path

PORT = 8080
DIRECTORY = Path(__file__).parent


class Handler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(DIRECTORY), **kwargs)

    def log_message(self, format, *args):
        # Custom logging
        print(f"[Dashboard] {format % args}")


def main():
    print(f"Starting AgentX Dashboard Server...")
    print(f"Dashboard: http://localhost:{PORT}")
    print(f"API (should be running): http://localhost:8000")
    print(f"\nPress Ctrl+C to stop")
    
    # Open browser
    webbrowser.open(f"http://localhost:{PORT}")
    
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down...")


if __name__ == "__main__":
    main()
