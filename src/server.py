<<<<<<< HEAD
# --- IMPORTS ---
import os
import sys
import json
import random
from typing import List, Dict, Any, Optional
=======
import os
import json
from amadeus import Client, ResponseError
>>>>>>> e6acde6a8d3c9680117475c566a09ccbd21b99a0
from dataclasses import dataclass
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

<<<<<<< HEAD
# MCP SERVER IMPORTS (from the forked project's structure)
from mcp.server.fastmcp import FastMCP, Context
from amadeus import Client, ResponseError # Amadeus SDK, installed via uv sync

# --- AMADEUS CLIENT LIFECYCLE MANAGEMENT ---
=======
from mcp.server.fastmcp import FastMCP, Context
>>>>>>> e6acde6a8d3c9680117475c566a09ccbd21b99a0

@dataclass
class AppContext:
    amadeus_client: Client

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
<<<<<<< HEAD
    """Manage Amadeus client lifecycle using AMADEUS_API_KEY/SECRET environment variables."""
=======
    """Manage Amadeus client lifecycle"""
>>>>>>> e6acde6a8d3c9680117475c566a09ccbd21b99a0
    api_key = os.environ.get("AMADEUS_API_KEY")
    api_secret = os.environ.get("AMADEUS_API_SECRET")

    if not api_key or not api_secret:
<<<<<<< HEAD
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
=======
        raise ValueError("AMADEUS_API_KEY and AMADEUS_API_SECRET must be set as environment variables")

    amadeus_client = Client(
        client_id=api_key,
        client_secret=api_secret
    )

    try:
        yield AppContext(amadeus_client=amadeus_client)
    finally:
        pass

mcp = FastMCP("Amadeus API", dependencies=["amadeus"], lifespan=app_lifespan)

>>>>>>> e6acde6a8d3c9680117475c566a09ccbd21b99a0
@mcp.tool()
def search_flight_offers(
    originLocationCode: str,
    destinationLocationCode: str,
    departureDate: str,
    adults: int,
    ctx: Context,
    returnDate: str = None,
<<<<<<< HEAD
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
=======
    children: int = None,
    infants: int = None,
    travelClass: str = None,
    includedAirlineCodes: str = None,
    excludedAirlineCodes: str = None,
    nonStop: bool = None,
    currencyCode: str = None,
    maxPrice: int = None,
    max: int = 250
) -> str:
    """
    Search for flight offers using the Amadeus API

    Args:
        originLocationCode: IATA code of the departure city/airport (e.g., SYD for Sydney)
        destinationLocationCode: IATA code of the destination city/airport (e.g., BKK for Bangkok)
        departureDate: Departure date in ISO 8601 format (YYYY-MM-DD, e.g., 2023-05-02)
        adults: Number of adult travelers (age 12+), must be 1-9
        returnDate: Return date in ISO 8601 format (YYYY-MM-DD), if round-trip is desired
        children: Number of child travelers (age 2-11)
        infants: Number of infant travelers (age <= 2)
        travelClass: Travel class (ECONOMY, PREMIUM_ECONOMY, BUSINESS, FIRST)
        includedAirlineCodes: Comma-separated IATA airline codes to include (e.g., '6X,7X')
        excludedAirlineCodes: Comma-separated IATA airline codes to exclude (e.g., '6X,7X')
        nonStop: If true, only non-stop flights are returned
        currencyCode: ISO 4217 currency code (e.g., EUR for Euro)
        maxPrice: Maximum price per traveler, positive integer with no decimals
        max: Maximum number of flight offers to return
    """
    if adults and not (1 <= adults <= 9):
        return json.dumps({"error": "Adults must be between 1 and 9"})

    if children and infants and adults and (adults + children > 9):
        return json.dumps({"error": "Total number of seated travelers (adults + children) cannot exceed 9"})

    if infants and adults and (infants > adults):
        return json.dumps({"error": "Number of infants cannot exceed number of adults"})

    amadeus_client = ctx.request_context.lifespan_context.amadeus_client
    params = {}
    params["originLocationCode"] = originLocationCode
    params["destinationLocationCode"] = destinationLocationCode
    params["departureDate"] = departureDate
    params["adults"] = adults

    if returnDate:
        params["returnDate"] = returnDate
    if children is not None:
        params["children"] = children
    if infants is not None:
        params["infants"] = infants
    if travelClass:
        params["travelClass"] = travelClass
    if includedAirlineCodes:
        params["includedAirlineCodes"] = includedAirlineCodes
    if excludedAirlineCodes:
        params["excludedAirlineCodes"] = excludedAirlineCodes
    if nonStop is not None:
        params["nonStop"] = nonStop
    if currencyCode:
        params["currencyCode"] = currencyCode
    if maxPrice is not None:
        params["maxPrice"] = maxPrice
    if max is not None:
        params["max"] = max

    try:
        ctx.info(f"Searching flights from {originLocationCode} to {destinationLocationCode}")
        ctx.info(f"API parameters: {json.dumps(params)}")

        response = amadeus_client.shopping.flight_offers_search.get(**params)
        return json.dumps(response.body)
    except ResponseError as error:
        error_msg = f"Amadeus API error: {str(error)}"
        ctx.info(f"Error: {error_msg}")
        return json.dumps({"error": error_msg})
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        ctx.info(f"Error: {error_msg}")
        return json.dumps({"error": error_msg})

@mcp.prompt()
def flight_search_prompt(origin: str, destination: str, date: str) -> str:
    """Create a flight search prompt"""
    return f"""
    Please search for flights from {origin} to {destination} on {date}.

    I'd like to see options sorted by price, with information about the airlines,
    departure/arrival times, and any layovers.
    """

if __name__ == "__main__":
    mcp.run()
>>>>>>> e6acde6a8d3c9680117475c566a09ccbd21b99a0
