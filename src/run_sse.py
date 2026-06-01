"""
TravelWise AI: Amadeus SSE Transport Layer

This module provides the Server-Sent Events (SSE) web server for the MCP application.
It acts strictly as the delivery mechanism, wrapping the core Amadeus tools
in a secure, asynchronous Starlette application designed to be accessed
via a Zero-Trust SSH tunnel.
"""

import uvicorn
from server import mcp  # FastMCP instance from mcp.server.fastmcp

if __name__ == "__main__":
    print("🚀 Starting Amadeus MCP Server (SSE Mode) on port 8000...")
    uvicorn.run(mcp.sse_app(), host="0.0.0.0", port=8000)