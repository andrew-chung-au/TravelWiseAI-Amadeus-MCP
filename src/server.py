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
    Initialize the Amadeus client using standard env vars.
    """
    client_id = os.getenv("AMADEUS_CLIENT_ID")
    client_secret = os.getenv("AMADEUS_CLIENT_SECRET")

    if not client_id or not client_secret:
        print(
            "ERROR: AMADEUS_CLIENT_ID or AMADEUS_CLIENT_SECRET is not set.\n"
            "Amadeus client cannot be initialised. Server will not start.",
            file=sys.stderr,
        )
        raise ValueError(
            "AMADEUS_CLIENT_ID and AMADEUS_CLIENT_SECRET must be set as environment variables"
        )

    # Helpful for debugging that the MCP server actually sees the env
    print(
        f"SERVER using AMADEUS_CLIENT_ID: {client_id[:8]}...",
        file=sys.stderr,
    )

    amadeus_client = Client(client_id=client_id, client_secret=client_secret)

    try:
        yield AppContext(amadeus_client=amadeus_client)
    finally:
        # Amadeus SDK doesn't need explicit shutdown
        pass


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
    Retrieve the Amadeus client instance from lifespan/context.
    """
    client = ctx.request_context.lifespan_context.amadeus_client
    if client is None:
        raise RuntimeError("Amadeus client is not initialised in lifespan context")
    return client


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
    currencyCode: Optional[str] = None,
    maxPrice: Optional[int] = None,
    max: int = 250,
) -> str:
    """
    Search for flight offers using Amadeus API (full parameter set).
    Returns a JSON string containing the API response body or an error object.
    """
    if adults and not (1 <= adults <= 9):
        return json.dumps({"error": "Adults must be between 1 and 9"})

    if (children or 0) + adults > 9:
        return json.dumps({
            "error": "Total number of seated travelers (adults + children) cannot exceed 9"
        })

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
        return json.dumps(response.body)

    except ResponseError as error:
        err_msg = f"Amadeus Flight API error: {str(error)}"
        ctx.info(err_msg)
        return json.dumps({"error": err_msg})
    except Exception as e:
        err_msg = f"Unexpected error in get_flight_offers: {str(e)}"
        ctx.info(err_msg)
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
    """
    if adults and not (1 <= adults <= 9):
        return json.dumps({"error": "Adults must be between 1 and 9"})

    try:
        amadeus_client = _get_amadeus_client(ctx)

        ctx.info(f"Step 1: Searching for hotels in {cityCode}...")
        try:
            hotels_response = amadeus_client.reference_data.locations.hotels.by_city.get(
                cityCode=cityCode
            )
        except ResponseError as error:
            if error.response.status_code == 404:
                return json.dumps({"error": f"No hotels found in city code: {cityCode}"})
            raise error

        if not hotels_response.data:
            return json.dumps({"error": f"No hotels found in {cityCode}"})

        found_hotels = hotels_response.data
        target_hotels = found_hotels[:max]
        hotel_ids_list = [h.get("hotelId") for h in target_hotels if h.get("hotelId")]

        if not hotel_ids_list:
            return json.dumps({"error": "Hotels found, but no valid IDs returned."})

        hotel_ids_str = ",".join(hotel_ids_list)
        ctx.info(f"Step 2: Fetching offers for {len(hotel_ids_list)} hotels: {hotel_ids_str}")

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
        err_msg = f"Unexpected error in get_hotel_offers: {str(e)}"
        ctx.info(err_msg)
        return json.dumps({"error": err_msg})


# -------------------------
# Server entrypoint
# -------------------------
if __name__ == "__main__":
    mcp.run()
