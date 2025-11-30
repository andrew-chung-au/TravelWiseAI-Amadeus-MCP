import os
import sys
import json
import asyncio
from dataclasses import dataclass
from contextlib import asynccontextmanager
from typing import Optional
from collections.abc import AsyncIterator

from amadeus import Client, ResponseError
from mcp.server.fastmcp import FastMCP, Context

# -------------------------
# Application context (lifespan)
# -------------------------
@dataclass
class AppContext:
    amadeus_client: Client

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """
    Initialize the Amadeus client using standard env vars.
    This runs once when the server starts.
    """
    client_id = os.getenv("AMADEUS_CLIENT_ID")
    client_secret = os.getenv("AMADEUS_CLIENT_SECRET")

    if not client_id or not client_secret:
        error_msg = (
            "ERROR: AMADEUS_CLIENT_ID or AMADEUS_CLIENT_SECRET is not set.\n"
            "Server cannot start without credentials."
        )
        print(error_msg, file=sys.stderr)
        raise ValueError("Missing Amadeus API Credentials")

    # Helpful debug log
    print(f"✅ Amadeus Client Initializing with ID: {client_id[:4]}****", file=sys.stderr)

    try:
        # Initialize the Amadeus Client
        # We disable log_level by default to keep MCP communication clean, 
        # unless you specifically want SDK debug logs.
        amadeus_client = Client(
            client_id=client_id, 
            client_secret=client_secret,
            log_level='silent' 
        )
        
        yield AppContext(amadeus_client=amadeus_client)
        
    except Exception as e:
        print(f"❌ Failed to initialize Amadeus Client: {e}", file=sys.stderr)
        raise

# -------------------------
# FastMCP server instance
# -------------------------
mcp = FastMCP(
    "TravelWise AI Amadeus Server",
    dependencies=["amadeus"],
    lifespan=app_lifespan,
)

# -------------------------
# Helpers
# -------------------------
def _get_amadeus_client(ctx: Context) -> Client:
    """
    Helper to retrieve the Amadeus client from the global context.
    """
    try:
        client = ctx.request_context.lifespan_context.amadeus_client
        if client is None:
            raise RuntimeError("Amadeus client is None")
        return client
    except AttributeError:
        raise RuntimeError("Amadeus client not found in context. Server might have failed to start correctly.")

# -------------------------
# Tool: get_flight_offers
# -------------------------
@mcp.tool()
def get_flight_offers(
    ctx: Context,
    originLocationCode: str,
    destinationLocationCode: str,
    departureDate: str,
    adults: int,
    returnDate: Optional[str] = None,
    children: Optional[int] = None,
    infants: Optional[int] = None,
    travelClass: Optional[str] = None,
    includedAirlineCodes: Optional[str] = None,
    excludedAirlineCodes: Optional[str] = None,
    nonStop: Optional[bool] = None,
    currencyCode: Optional[str] = "USD",
    maxPrice: Optional[int] = None,
    max: int = 10,
) -> str:
    """
    Search for flight offers using Amadeus API.
    Returns a JSON string of available flights.
    """
    # Validation
    if not (1 <= adults <= 9):
        return json.dumps({"error": "Adults must be between 1 and 9"})
    
    total_travelers = adults + (children or 0)
    if total_travelers > 9:
        return json.dumps({"error": f"Total travelers ({total_travelers}) cannot exceed 9"})

    if infants and (infants > adults):
        return json.dumps({"error": "Number of infants cannot exceed number of adults"})

    try:
        client = _get_amadeus_client(ctx)

        # Build parameters dictionary dynamically to avoid sending None values
        params = {
            "originLocationCode": originLocationCode,
            "destinationLocationCode": destinationLocationCode,
            "departureDate": departureDate,
            "adults": adults,
            "max": max,
            "currencyCode": currencyCode
        }

        if returnDate: params["returnDate"] = returnDate
        if children: params["children"] = children
        if infants: params["infants"] = infants
        if travelClass: params["travelClass"] = travelClass
        if includedAirlineCodes: params["includedAirlineCodes"] = includedAirlineCodes
        if excludedAirlineCodes: params["excludedAirlineCodes"] = excludedAirlineCodes
        if nonStop is not None: params["nonStop"] = str(nonStop).lower() # API expects "true"/"false" string sometimes, or boolean. SDK handles it, but good to be safe.
        if maxPrice: params["maxPrice"] = maxPrice

        ctx.info(f"✈️ Searching flights: {originLocationCode} -> {destinationLocationCode} on {departureDate}")
        
        response = client.shopping.flight_offers_search.get(**params)
        
        # Check if response body is empty
        if not response.data:
            return json.dumps({"info": "No flights found matching criteria."})

        return json.dumps(response.data)

    except ResponseError as error:
        # Amadeus specific API errors
        err_msg = f"Amadeus API Error [{error.response.status_code}]: {error.code} - {error.description}"
        ctx.error(err_msg)
        return json.dumps({"error": err_msg})
    except Exception as e:
        err_msg = f"Unexpected error: {str(e)}"
        ctx.error(err_msg)
        return json.dumps({"error": err_msg})


# -------------------------
# Tool: get_hotel_offers
# -------------------------
@mcp.tool()
def get_hotel_offers(
    ctx: Context,
    cityCode: str,
    checkInDate: str,
    checkOutDate: str,
    adults: int = 2,
    max: int = 10,
    currency: Optional[str] = "USD",
) -> str:
    """
    Retrieve hotel offers for a given city and date range.
    Note: This is a 2-step process (Find Hotels in City -> Check their Availability).
    """
    if not (1 <= adults <= 9):
        return json.dumps({"error": "Adults must be between 1 and 9"})

    try:
        client = _get_amadeus_client(ctx)

        # Step 1: Find hotels in the city
        ctx.info(f"🏨 Step 1: Finding hotels in {cityCode}...")
        try:
            # We fetch slightly more hotels than requested to increase odds of finding availability
            hotels_response = client.reference_data.locations.hotels.by_city.get(
                cityCode=cityCode,
                radius=10,
                radiusUnit='KM'
            )
        except ResponseError as error:
            if error.response.status_code == 404:
                return json.dumps({"error": f"No hotels found in city code: {cityCode}"})
            raise error

        if not hotels_response.data:
            return json.dumps({"error": f"No hotels found in {cityCode}"})

        # Get list of Hotel IDs (limit to max to prevent URL too long errors)
        found_hotels = hotels_response.data[:max]
        hotel_ids = [h.get("hotelId") for h in found_hotels if h.get("hotelId")]

        if not hotel_ids:
            return json.dumps({"error": "Hotels found but had no valid IDs."})

        # Step 2: Check availability for these specific hotels
        ids_str = ",".join(hotel_ids)
        ctx.info(f"🏨 Step 2: Checking availability for {len(hotel_ids)} hotels...")

        params = {
            "hotelIds": ids_str,
            "checkInDate": checkInDate,
            "checkOutDate": checkOutDate,
            "adults": adults,
            "currency": currency,
        }

        response = client.shopping.hotel_offers_search.get(**params)
        
        if not response.data:
             return json.dumps({"info": f"Hotels exist in {cityCode}, but none have offers for these dates/parameters."})

        return json.dumps(response.data)

    except ResponseError as error:
        err_msg = f"Amadeus Hotel API error: {str(error)}"
        ctx.error(err_msg)
        return json.dumps({"error": err_msg})
    except Exception as e:
        err_msg = f"Unexpected error: {str(e)}"
        ctx.error(err_msg)
        return json.dumps({"error": err_msg})


# -------------------------
# Entrypoint
# -------------------------
if __name__ == "__main__":
    # Default to Stdio (Standard Input/Output)
    # This is what Claude Desktop uses.
    mcp.run()
