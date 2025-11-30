# src/run_sse.py
import uvicorn
from mcp.server.sse import SseServerTransport
from starlette.applications import Starlette
from starlette.routing import Route
from server import mcp  # Import the mcp object from your server.py

async def handle_sse(request):
    async with mcp.server.create_initialization_session() as session:
        # Connect the SSE transport
        transport = SseServerTransport("/messages")
        await session.accept(transport)
        # Keep the connection open indefinitely
        await transport.handle_sse(request)

async def handle_messages(request):
    # Handle incoming POST messages from the client
    return await mcp.server.process_message(request)

# Define the routes for the web server
routes = [
    Route("/sse", endpoint=handle_sse),
    Route("/messages", endpoint=handle_messages, methods=["POST"])
]

app = Starlette(debug=True, routes=routes)

if __name__ == "__main__":
    print("🚀 Starting Amadeus MCP Server (SSE Mode) on port 8500...")
    # Bind to 0.0.0.0 to ensure it's accessible via SSH tunnel or external IP
    uvicorn.run(app, host="0.0.0.0", port=8500)
