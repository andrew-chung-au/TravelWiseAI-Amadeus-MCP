# Amadeus MCP Server

[![smithery badge](https://smithery.ai/badge/@donghyun-chae/mcp-amadeus)](https://smithery.ai/server/@donghyun-chae/mcp-amadeus)

**MCP-Amadeus is a community-developed [Model Context Protocol (MCP)](https://github.com/modelcontextprotocol) server that integrates with the Amadeus Flight Offers Search & Hotel API.**

Compatible with any MCP client (e.g., Claude Desktop), it enables users to search for flight options and hotel accommodations using natural language. It was created to support [Travelwise: A Hybrid-Cloud Multi-Agent Concierge](https://kaggle.com/competitions/agents-intensive-capstone-project/writeups/new-writeup-1763433677466).

This project uses the official [amadeus-python SDK](https://github.com/amadeus4dev/amadeus-python).

> **Disclaimer:** This is an open-source project *not affiliated with or endorsed by Amadeus IT Group.* Amadeus® is a registered trademark of Amadeus IT Group.

---

> ⚠️ **SUNSET NOTICE (July 2026):** Amadeus has officially decommissioned their Self-Service API tier as of July 17, 2026. Consequently, live data fetching via this MCP server is no longer functional without an Enterprise Amadeus account. 
>
> **This repository is now maintained as an Architectural Reference.** The core Python application, Server-Sent Events (SSE) implementation, Graceful Degradation engine, and Terraform deployment pipeline remain fully valid demonstrations of enterprise software design and MCP tool orchestration.

---

## ✨ Features

### ✈️ Flight Offers Search
Retrieve flight options between two locations for specified dates.
> "Find me nonstop flights from JFK to LHR on June 15th for 1 adult."

### 🏨 Hotel Offers Search
Retrieve available hotel offers for a specific city.
> "Find hotels in Paris (PAR) for 2 adults checking in on July 10th and out on July 15th."

### 🔄 Level C Mock Engine (Graceful Degradation)
Fully testable without API credentials. The server automatically detects invalid or missing API keys and seamlessly falls back to a highly realistic, randomized Mock Engine that perfectly adheres to the Amadeus JSON schemas.

---

## 🏛️ Architecture & Design

This application was engineered with a focus on enterprise patterns, system resilience, and clear separation of concerns.

* **Dependency Injection (DI):** The application decouples the business logic (fetching travel data) from the network state. The `app_lifespan` context injects either the real Amadeus client or a `MockAmadeusClient` at boot. Tool functions remain perfectly clean and interface-agnostic.
* **Graceful Degradation:** To prevent hard crashes caused by upstream rate limits or the API sunset, the application intercepts authentication failures and falls back to dynamic "Level C" polyfills, utilizing Python's `random` and `datetime` libraries to mimic live data variation.
* **Transport Agnosticism:** The core Model Context Protocol (MCP) engine is isolated from its delivery mechanism. `server.py` contains the application logic and defaults to `stdio` (for local desktop clients), while `run_sse.py` wraps the application in a Starlette web server for Server-Sent Events (SSE) to serve remote agents.
* **Reproducible Builds:** Dependency drift is eliminated by strictly utilizing `uv.lock` for package management across local development, Docker distribution, and AWS EC2 bootstrapping.

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
git clone [https://github.com/donghyun-chae/mcp-amadeus.git](https://github.com/donghyun-chae/mcp-amadeus.git)
cd mcp-amadeus
uv sync
```

#### 2. Environment Configuration
Create your local environment file:

```bash
cp .env.example .env
```

Edit `.env` to add your credentials.

Evaluation Mode: If you do not have an Amadeus account, leave these variables as dummy placeholders (e.g., `mock_client_id`). The server will detect this and automatically activate the Mock Travel Engine.

#### 3. Configure MCP Client
Register this server in your MCP client (e.g., Claude for Desktop). Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```JSON
{
  "mcpServers": {
    "amadeus": {
      "command": "/path/to/your/uv",
      "args": [
        "--directory",
        "/ABSOLUTE/PATH/TO/mcp-amadeus/",
        "run",
        "--env-file",
        "/ABSOLUTE/PATH/TO/mcp-amadeus/.env",
        "src/server.py"
      ]
    }
  }
}
```

---

## ☁️ Infrastructure as Code: AWS Deployment (SSE Mode)
For remote client connections (e.g., connecting a local Claude Desktop to a remote server or a dynamic cloud agent), this project includes a fully automated deployment via Terraform.

To demonstrate responsible cloud usage and avoid ongoing costs, the infrastructure is designed as a spin-up-on-demand model utilizing an EC2 instance. Credentials are handled securely via AWS Secrets Manager rather than static `.env` files, and access is strictly gated behind a Zero-Trust SSH tunnel.

To deploy the server:
1. Navigate to the `infrastructure/` directory.
2. Copy the variables template: `cp terraform.tfvars.example terraform.tfvars` and add your deployment targets.
3. Run the deployment:

```bash
terraform init
terraform apply
```

Terraform will output the dynamic SSH tunnel connection string and the local SSE Endpoint URL. Point your MCP client to this URL.

When testing is complete, tear down the infrastructure to ensure zero ongoing costs:

```bash
terraform destroy
```

For a detailed breakdown of the architectural decisions, IAM roles, and networking, see the **[Infrastructure README](infrastructure/README.md)**.

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
* [Travelwise: A Hybrid-Cloud Multi-Agent Concierge](https://kaggle.com/competitions/agents-intensive-capstone-project/writeups/new-writeup-1763433677466)

---

## 📝 License

MIT License

Original implementation by donghyun-chae.  
Modifications, Graceful Degradation architecture, and AWS Infrastructure implementation by Andrew Chung.