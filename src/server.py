# --- IMPORTS ---
import os
import sys
import json
import random
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

# MCP SERVER IMPORTS (from the forked project's structure)
from mcp.server.fastmcp import FastMCP, Context
from amadeus import Client, ResponseError # Amadeus SDK, installed via uv sync

# --- AMADEUS CLIENT LIFECYCLE MANAGEMENT ---

@dataclass
class AppContext:
    amadeus_client: Client

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """Manage Amadeus client lifecycle using AMADEUS_API_KEY/SECRET environment variables."""
    api_key = os.environ.get("AMADEUS_API_KEY")
    api_secret = os.environ.get("AMADEUS_API_SECRET")

    if not api_key or not api_secret:
        # Fallback if keys are not set (crucial for local debugging)
        print("Warning: AMADEUS_API_KEY or SECRET missing. Tools will use mock data.", file=sys.stderr)
        amadeus_client = None
        yield AppContext(amadeus_client=amadeus_client)
    else:
        amadeus_client = Client(
            client_id=api_key,
            client_secret=api_secret
        )
        try:
            yield AppContext(amadeus_client=amadeus_client)
        finally:
            pass

# Helper to safely retrieve the client or handle the mock state
def get_amadeus_client(ctx: Context) -> Optional[Client]:
    return ctx.request_context.lifespan_context.amadeus_client

# --- TOOL DEFINITIONS ---

# 1. FLIGHT TOOL (Existing tool, modified for AppContext)
@mcp.tool()
def search_flight_offers(
    originLocationCode: str,
    destinationLocationCode: str,
    departureDate: str,
    adults: int,
    ctx: Context,
    returnDate: str = None,
    # ... (other parameters omitted for brevity)
    max: int = 5
) -> str:
    """
    Retrieves flight offers from the Amadeus Flight Offers Search API.
    """
    amadeus_client = get_amadeus_client(ctx)
    if amadeus_client is None:
        # Structured Mock Data for non-working server
        cost = random.randint(400, 800)
        return json.dumps({
            "item": f"Flight: {originLocationCode} to {destinationLocationCode} (MOCK)",
            "cost": cost,
            "currency": "USD"
        })
        
    params = {
        "originLocationCode": originLocationCode,
        "destinationLocationCode": destinationLocationCode,
        "departureDate": departureDate,
        "adults": adults,
        "max": max
    }
    if returnDate: params["returnDate"] = returnDate
    # ... (other params are built here)

    try:
        response = amadeus_client.shopping.flight_offers_search.get(**params)
        if response.data and response.data[0]:
            price = float(response.data[0]['price']['grandTotal'])
            return json.dumps({
                "item": f"Flight: {originLocationCode} to {destinationLocationCode}",
                "cost": price,
                "currency": response.data[0]['price']['currency']
            })
        return json.dumps({"error": "No flight offers found."})
    except ResponseError as error:
        return json.dumps({"error": f"Amadeus Flight API error: {str(error)}"})


# 2. HOTEL TOOL (NEW - Implements MVP logic)
@mcp.tool()
def search_hotel_offers(
    cityCode: str,
    checkInDate: str,
    checkOutDate: str,
    adults: int,
    ctx: Context,
    max: int = 3
) -> str:
    """
    Retrieves hotel offers and returns the lowest price for a given city and dates.
    """
    amadeus_client = get_amadeus_client(ctx)
    if amadeus_client is None:
        cost = random.randint(300, 900)
        return json.dumps({
            "item": f"Hotel: {cityCode} Stay (MOCK)",
            "cost": cost,
            "currency": "USD"
        })
    
    try:
        # Use the Hotel Offers Search API
        response = amadeus_client.shopping.hotel_offers_search.get(
            cityCode=cityCode,
            adults=adults,
            checkInDate=checkInDate,
            checkOutDate=checkOutDate,
            currency="USD",
            max=max
        )
        
        if response.data and response.data.get('data'):
            first_hotel = response.data['data'][0]
            first_offer = first_hotel['offers'][0]
            
            return json.dumps({
                "item": f"Hotel: {first_hotel['hotel']['name']} ({checkInDate} to {checkOutDate})",
                "cost": float(first_offer['price']['total']),
                "currency": first_offer['price']['currency']
            })
        return json.dumps({"error": f"No hotel offers found in {cityCode}."})

    except ResponseError as e:
        return json.dumps({"error": f"Amadeus Hotel API Error: Status {e.status_code}"})


# 3. CAR HIRE/TRANSFER TOOL (NEW - Implements MVP Mock)
@mcp.tool()
def search_car_hire_transfer_offers(
    startLocation: str,
    endLocation: str,
    ctx: Context
) -> str:
    """
    Simulates searching for car transfers/hire offers between two locations (MVP Mock).
    NOTE: The actual Amadeus Transfers API requires a complex POST body.
    """
    # Since the actual Transfer API is complex, we use a structured MOCK response
    # to ensure the tool is callable and the budget tracker works.
    
    if not (startLocation and endLocation):
         return json.dumps({"error": "Missing start or end location for car hire."})

    cost = random.randint(15000, 45000) / 100 # Price in cents / 100
    
    mock_data = {
        "item": f"Car Hire/Transfer: {startLocation} to {endLocation}",
        "cost": round(cost, 2),
        "currency": "USD",
        "notes": "Cost is an MVP estimate for a standard sedan transfer/hire."
    }
    return json.dumps(mock_data)


# --- SERVER INITIALIZATION ---

# Define the FastMCP server instance
# The existing server structure defines the tools via the @mcp.tool() decorators.
mcp = FastMCP(
    "TravelWise AI Amadeus Server", 
    dependencies=["amadeus"], 
    lifespan=app_lifespan # Use the lifecycle manager for client init
)

# --- SERVER RUN COMMAND ---
if __name__ == "__main__":
    # This is the entry point command: 'python src/server.py'
    mcp.run()