# Amadeus MCP Server

[![smithery badge](https://smithery.ai/badge/@donghyun-chae/mcp-amadeus)](https://smithery.ai/server/@donghyun-chae/mcp-amadeus)

**MCP-Amadeus is a community-developed [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol) server that integrates with the Amadeus Flight Offers Search & Hotel API.**

Built for use with MCP-compatible clients (e.g., Claude Desktop), this project enables users to search for flight options and hotel accommodations using natural language.

This project uses the official [amadeus-python SDK](https://github.com/amadeus4dev/amadeus-python).

> **Disclaimer:** This is an open-source project *not affiliated with or endorsed by Amadeus IT Group.* Amadeus® is a registered trademark of Amadeus IT Group.

---

## ✨ Features

### ✈️ Flight Offers Search
Retrieve flight options between two locations for specified dates.
> "Find me nonstop flights from JFK to LHR on June 15th for 1 adult."

### 🏨 Hotel Offers Search
**[NEW]** Retrieve available hotel offers for a specific city.
> "Find hotels in Paris (PAR) for 2 adults checking in on July 10th and out on July 15th."

---

## 🚀 Quick Start

### Installing via Smithery

To install Amadeus MCP Server for Claude Desktop automatically via [Smithery](https://smithery.ai/server/@donghyun-chae/mcp-amadeus):
```bash
npx -y @smithery/cli install @donghyun-chae/mcp-amadeus --client claude
```

### Manual Installation

#### 1. Clone and Setup
```bash
git clone https://github.com/donghyun-chae/mcp-amadeus.git
cd mcp-amadeus
uv sync
```

#### 2. Get Your API Key

1. Sign up on https://developers.amadeus.com/
2. Create an app to obtain your `Client ID` and `Client Secret`.
3. Create a `.env` file:
```bash
cp .env.example .env
```

Add your credentials to `.env`:
```bash
AMADEUS_CLIENT_ID=your_client_id
AMADEUS_CLIENT_SECRET=your_client_secret
```

#### 3. Configure MCP Client

Register this server in your MCP client (e.g., Claude for Desktop). Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:
```json
{
  "mcpServers": {
    "amadeus": {
      "command": "/path/to/your/uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/mcp-amadeus/src/",
        "run",
        "--env-file",
        "/ABSOLUTE/PATH/TO/mcp-amadeus/.env",
        "server.py"
      ]
    }
  }
}
```

**Note:** Ensure you provide the absolute path to your `uv` executable (e.g., `/Users/username/.local/bin/uv`) and the absolute path to your project folder.

---

### ☁️ Remote / AWS Deployment (SSE Mode)
If you are running this server on a remote machine (e.g., AWS EC2) and connecting via SSH Tunnel or HTTP, you must use the SSE (Server-Sent Events) entry point instead of the standard Stdio server.py.

1. Requirements
Ensure uvicorn and starlette are installed:
```bash
uv add uvicorn starlette
```

2. Run the SSE Server
Run the run_sse.py script. This exposes the server on port 8500.
```bash
# Run on the remote server
uv run src/run_sse.py
```

3. Connect via SSH Tunnel
If you are connecting from a local client to the remote AWS server:
Establish Tunnel:
```bash
ssh -L 8500:localhost:8500 user@your-aws-ip
```

Connect Client: Point your MCP client or test script to:
```text
http://localhost:8500/sse
```

---

## 🛠️ Tools

### 1. `get_flight_offers`

Retrieves flight offers from the Amadeus Flight Offers Search API.

**Parameters:**

| Name | Type | Required | Description | Example |
|------|------|----------|-------------|---------|
| `originLocationCode` | string | Yes | IATA code of departure city/airport | `JFK` |
| `destinationLocationCode` | string | Yes | IATA code of destination city/airport | `LHR` |
| `departureDate` | string | Yes | Departure date (YYYY-MM-DD) | `2025-06-15` |
| `adults` | integer | Yes | Number of adults (1-9) | `1` |
| `returnDate` | string | No | Return date (YYYY-MM-DD) | `2025-06-20` |
| `children` | integer | No | Number of children (2-11) | `1` |
| `infants` | integer | No | Number of infants (≤2) | `0` |
| `travelClass` | string | No | `ECONOMY`, `BUSINESS`, `FIRST` | `ECONOMY` |
| `nonStop` | boolean | No | If true, only non-stop flights | `true` |
| `currencyCode` | string | No | Currency in ISO 4217 | `USD` |
| `maxPrice` | integer | No | Max price per traveler | `1000` |
| `max` | integer | No | Max number of results (Default: 250) | `10` |

### 2. `get_hotel_offers`

Retrieves hotel offers for a specific city. The server first looks up hotels in the city, then fetches offers for those specific hotels.

**Parameters:**

| Name | Type | Required | Description | Example |
|------|------|----------|-------------|---------|
| `cityCode` | string | Yes | IATA City Code | `PAR` |
| `checkInDate` | string | Yes | Check-in date (YYYY-MM-DD) | `2025-07-10` |
| `checkOutDate` | string | Yes | Check-out date (YYYY-MM-DD) | `2025-07-15` |
| `adults` | integer | No | Number of guests (Default: 2) | `2` |
| `currency` | string | No | Currency code (Default: USD) | `EUR` |
| `max` | integer | No | Max number of hotels to check (Default: 10) | `5` |

---

## 📚 References

* [Model Context Protocol Python SDK](https://github.com/modelcontextprotocol)
* [Amadeus Python SDK](https://github.com/amadeus4dev/amadeus-python)
* [Amadeus API Documentation](https://developers.amadeus.com/)

---

## 📝 License

MIT License

Original implementation by donghyun-chae.  
Modifications and Hotel Search implementation added by Andrew Chung.
