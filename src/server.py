# src/server.py
import os
import sys
import json
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
    Initialize the Amadeus client inside the FastMCP lifespan.
    Strict mode: if environment variables are missing, warn and fail-fast.
    """
    api_key = os.environ.get("AMADEUS_API_KEY")
    api_secret = os.environ.get("AMADEUS_API_SECRET")

    if not api_key or not api_secret:
        # Emit a clear warning for debugging, then fail fast.
        print(
            "WARNING: AMADEUS_API_KEY or AMADEUS_API_SECRET is not set.\n"
            "Amadeus client cannot be initialised. Server will not start.",
            file=sys.stderr,
        )
        raise ValueError(
            "AMADEUS_API_KEY and AMADEUS_API_SECRET must be set as environment variables"
        )

    amadeus_client = Client(client_id=api_key, client_secret=api_secret)

    try:
        yield AppContext(amadeus_client=amadeus_client)
    finally:
        # The Amadeus SDK does not require explicit shutdown in most cases.
        pass


# -------------------------
# FastMCP server instance
# -------------------------
mcp = FastMCP(
    "TravelWise AI Amadeus Server",
    dependencies=["amadeus"],
    lifespan=app_lifespan
)


# -------------------------
# Helpers
# -------------------------
def _get_amadeus_client(ctx: Context) -> Client:
    """
    Retrieve the Amadeus client instance from lifespan/context.
    Raises RuntimeError if not available (shouldn't happen in strict mode).
    """
    client = ctx.request_context.lifespan_context.amadeus_client
    if client is None:
        # Defensive: this should not occur because app_lifespan is strict.
        raise RuntimeError("Amadeus client is not initialised in lifespan context")
    return client


# -------------------------
# Tool: search_flight_offers
# -------------------------
@mcp.tool()
def search_flight_offers(
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
    currencyCode: Optional[str] = None,
    maxPrice: Optional[int] = None,
    max: int = 250
) -> str:
    """
    Search for flight offers using Amadeus API (full parameter set).
    Returns a JSON string containing the API response body or an error object.
    """
    # Basic validation according to Amadeus limits
    if adults and not (1 <= adults <= 9):
        return json.dumps({"error": "Adults must be between 1 and 9"})

    if (children or 0) + adults > 9:
        return json.dumps({"error": "Total number of seated travelers (adults + children) cannot exceed 9"})

    if infants and adults and (infants > adults):
        return json.dumps({"error": "Number of infants cannot exceed number of adults"})

    try:
        amadeus_client = _get_amadeus_client(ctx)

        params = {
            "originLocationCode": originLocationCode,
            "destinationLocationCode": destinationLocationCode,
            "departureDate": departureDate,
            "adults": adults,
        }

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

        ctx.info(f"Flight search params: {json.dumps(params)}")
        response = amadeus_client.shopping.flight_offers_search.get(**params)
        # Return the raw response body (stringified JSON)
        return json.dumps(response.body)

    except ResponseError as error:
        err_msg = f"Amadeus Flight API error: {str(error)}"
        ctx.info(err_msg)
        return json.dumps({"error": err_msg})
    except Exception as e:
        err_msg = f"Unexpected error in search_flight_offers: {str(e)}"
        ctx.info(err_msg)
        return json.dumps({"error": err_msg})


# -------------------------
# Tool: search_hotel_offers
# -------------------------
@mcp.tool()
def search_hotel_offers(
    ctx: Context,
    cityCode: str,
    checkInDate: str,
    checkOutDate: str,
    adults: int = 2,
    max: int = 10,
    currency: Optional[str] = "USD"
) -> str:
    """
    Retrieve hotel offers for a given city and date range.
    
    Uses Amadeus V3 logic:
    1. Finds hotels in the city (Reference Data API).
    2. Gets offers for the top 'max' hotels found (Shopping API).
    
    Returns:
        JSON string of offers or error message.
    """
    # Validation for V3 limits
    if adults and not (1 <= adults <= 9):
        return json.dumps({"error": "Adults must be between 1 and 9"})

    try:
        amadeus_client = _get_amadeus_client(ctx)

        # Step 1: Find hotels in the city
        ctx.info(f"Step 1: Searching for hotels in {cityCode}...")
        try:
            # Using the Reference Data API to get hotel IDs by city
            hotels_response = amadeus_client.reference_data.locations.hotels.by_city.get(
                cityCode=cityCode
            )
        except ResponseError as error:
            # Handle 404 or other errors specifically for the city search
            if error.response.status_code == 404:
                return json.dumps({"error": f"No hotels found in city code: {cityCode}"})
            raise error

        if not hotels_response.data:
             return json.dumps({"error": f"No hotels found in {cityCode}"})

        # Step 2: Extract Hotel IDs
        # We limit the list to 'max' to ensure the URL doesn't become too long
        # and to control the search scope.
        found_hotels = hotels_response.data
        target_hotels = found_hotels[:max]
        hotel_ids_list = [hotel.get("hotelId") for hotel in target_hotels if hotel.get("hotelId")]
        
        if not hotel_ids_list:
            return json.dumps({"error": "Hotels found, but no valid IDs returned."})

        hotel_ids_str = ",".join(hotel_ids_list)
        ctx.info(f"Step 2: Fetching offers for {len(hotel_ids_list)} hotels: {hotel_ids_str}")

        # Step 3: Search Offers for these specific IDs
        params = {
            "hotelIds": hotel_ids_str,
            "checkInDate": checkInDate,
            "checkOutDate": checkOutDate,
            "adults": adults,
            "currency": currency,
        }

        response = amadeus_client.shopping.hotel_offers_search.get(**params)
        return json.dumps(response.body)

    except ResponseError as error:
        err_msg = f"Amadeus Hotel API error: {str(error)}"
        ctx.info(err_msg)
        return json.dumps({"error": err_msg})
    except Exception as e:
        err_msg = f"Unexpected error in search_hotel_offers: {str(e)}"
        ctx.info(err_msg)
        return json.dumps({"error": err_msg})


# -------------------------
# Optional: a helpful prompt generator for flight searches
# -------------------------
@mcp.prompt()
def flight_search_prompt(origin: str, destination: str, date: str) -> str:
    return (
        f"Please search for flights from {origin} to {destination} on {date}. "
        "Return options sorted by price with airline, departure/arrival times, and layover info."
    )


# -------------------------
# Server entrypoint
# -------------------------
if __name__ == "__main__":
    mcp.run()
