"""
TravelWise AI: Amadeus API Server (MCP)

Provides both live and mock-backed implementations of the Amadeus Travel API,
exposing them as Model Context Protocol (MCP) tools for autonomous agents.
Implements Graceful Degradation and Dependency Injection for offline testing.
"""
import os
import sys
import json
import random
from datetime import datetime, timedelta
from dataclasses import dataclass
from contextlib import asynccontextmanager
from typing import Optional
from collections.abc import AsyncIterator

from amadeus import Client, ResponseError
from mcp.server.fastmcp import FastMCP, Context

# -------------------------
# Mock Data Layer Strategy
# -------------------------
class MockAmadeusClient:
    """
    Simulates the Amadeus SDK behavior to enable offline testing.
    Incorporates randomized Level C mock data for realistic demonstrations.
    The mock engine implements the Amadeus SDK interface contract exactly,
    meaning tool functions operate identically against live and mock data.
    """
    class MockShopping:
        class MockFlightOffersSearch:
            def get(self, **params):
                airlines = ["QF", "VA", "JQ", "EK", "SQ"]
                airline = random.choice(airlines)
                flight_number = f"{airline}{random.randint(100, 999)}"
                price = f"{round(random.uniform(450.00, 1200.00), 2):.2f}"
                currency = params.get("currencyCode", "USD")
                
                origin = params.get("originLocationCode", "SYD")
                destination = params.get("destinationLocationCode", "LHR")
                
                date_str = params.get("departureDate", datetime.today().strftime("%Y-%m-%d"))
                
                hours = random.randint(8, 15)
                mins = random.randint(0, 59)
                dep_hour = random.randint(6, 22)
                
                # BUG FIX: Accurate Datetime progression across midnights
                try:
                    dep_dt = datetime.strptime(f"{date_str}T{dep_hour:02d}:00:00", "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    dep_dt = datetime.now().replace(hour=dep_hour, minute=0, second=0, microsecond=0)
                    
                arr_dt = dep_dt + timedelta(hours=hours, minutes=mins)
                
                return type('Response', (object,), {
                    "data": [{
                        "type": "flight-offer",
                        "id": "1",
                        "source": "GDS",
                        "itineraries": [
                            {
                                "duration": f"PT{hours}H{mins}M",
                                "segments": [{
                                    "departure": {
                                        "iataCode": origin,
                                        "at": dep_dt.strftime("%Y-%m-%dT%H:%M:%S")
                                    },
                                    "arrival": {
                                        "iataCode": destination,
                                        "at": arr_dt.strftime("%Y-%m-%dT%H:%M:%S")
                                    },
                                    "carrierCode": airline,
                                    "number": flight_number,
                                    "numberOfStops": 0
                                }]
                            }
                        ],
                        "price": {"currency": currency, "total": price}
                    }]
                })()

        class MockHotelOffersSearch:
            def get(self, **params):
                price = f"{round(random.uniform(150.00, 450.00), 2):.2f}"
                currency = params.get("currency", "USD")
                
                requested_ids = params.get("hotelIds", "MOCK123").split(",")
                primary_id = requested_ids[0] if requested_ids else "MOCK123"
                
                return type('Response', (object,), {
                    "data": [{
                        "type": "hotel-offer",
                        "hotel": {"hotelId": primary_id, "name": "Grand Central Premium"},
                        "available": True,
                        "offers": [{"id": "O1", "price": {"currency": currency, "total": price}}]
                    }]
                })()

    class MockReferenceData:
        class MockLocations:
            class MockHotels:
                class MockByCity:
                    def get(self, **params):
                        return type('Response', (object,), {
                            "data": [{"hotelId": "MOCK123", "name": "Grand Central Premium", "cityCode": params.get("cityCode")}]
                        })()

    def __init__(self):
        # type() dynamically constructs anonymous classes mirroring the Amadeus SDK's nested
        # attribute paths. Tools call client.shopping.flight_offers_search.get() identically
        # regardless of whether they hold a real Client or this mock.
        self.shopping = type('Shopping', (object,), {
            "flight_offers_search": self.MockShopping.MockFlightOffersSearch(),
            "hotel_offers_search": self.MockShopping.MockHotelOffersSearch()
        })()
        self.reference_data = type('RefData', (object,), {
            "locations": type('Locs', (object,), {
                "hotels": type('Hotels', (object,), {
                    "by_city": self.MockReferenceData.MockLocations.MockHotels.MockByCity()
                })()
            })()
        })()


# -------------------------
# Application context (lifespan)
# -------------------------
@dataclass
class AppContext:
    amadeus_client: Client | MockAmadeusClient
    is_mock: bool

@asynccontextmanager
async def app_lifespan(server: FastMCP) -> AsyncIterator[AppContext]:
    """
    Manages client initialization lifecycle. Acts as the Dependency Injection injector:
    decides once at boot which client (live or mock) to provision, then makes it available
    to all tools via context; so tools remain completely agnostic to which engine they're using.
    """
    mock_active = os.getenv("MOCK_MODE", "false").lower() == "true"
    client_id = os.getenv("AMADEUS_CLIENT_ID")
    client_secret = os.getenv("AMADEUS_CLIENT_SECRET")

    # Detect placeholder/dummy credentials injected by Terraform for demo deployments.
    # This allows the full AWS infrastructure chain to be validated (Secrets Manager → EC2 → env vars)
    # without requiring a live Amadeus account.
    is_placeholder = "mock" in (client_id or "").lower() or "dummy" in (client_id or "").lower()

    if mock_active or not client_id or not client_secret or is_placeholder:
        print("⚠️ Running in MOCK MODE: Utilizing high-fidelity simulated travel engine.", file=sys.stderr)
        yield AppContext(amadeus_client=MockAmadeusClient(), is_mock=True)
        return

    print(f"✅ Live Amadeus Client Initializing with ID: {client_id[:4]}****", file=sys.stderr)
    try:
        amadeus_client = Client(
            client_id=client_id, 
            client_secret=client_secret,
            log_level='silent' 
        )
        yield AppContext(amadeus_client=amadeus_client, is_mock=False)
    except Exception as e:
        # DESIGN CHOICE: We intentionally 'fail loudly' here rather than falling back to mock.
        # If a developer explicitly provides credentials, masking a failure with mock data 
        # causes debugging confusion. 
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
def _get_amadeus_client(ctx: Context) -> Client | MockAmadeusClient:
    """
    Helper to retrieve the injected client from context.
    Also surfaces the mock status to the MCP Client logs for transparency.
    """
    try:
        app_ctx = ctx.request_context.lifespan_context
        if app_ctx.is_mock:
            ctx.info("🔧 [MOCK MODE] Request routed to simulated travel engine")
        return app_ctx.amadeus_client
    except AttributeError:
        raise RuntimeError("Amadeus client not found in context. Server failed to start correctly.")

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

    # BUG FIX: Style consistency matching the children logic below
    if infants is not None and infants > adults:
        return json.dumps({"error": "Number of infants cannot exceed number of adults"})

    try:
        client = _get_amadeus_client(ctx)

        params = {
            "originLocationCode": originLocationCode,
            "destinationLocationCode": destinationLocationCode,
            "departureDate": departureDate,
            "adults": adults,
            "max": max,
            "currencyCode": currencyCode
        }

        if returnDate: params["returnDate"] = returnDate
        if children is not None: params["children"] = children
        if infants is not None: params["infants"] = infants
        if travelClass: params["travelClass"] = travelClass
        if includedAirlineCodes: params["includedAirlineCodes"] = includedAirlineCodes
        if excludedAirlineCodes: params["excludedAirlineCodes"] = excludedAirlineCodes
        if nonStop is not None: params["nonStop"] = str(nonStop).lower()
        if maxPrice: params["maxPrice"] = maxPrice

        ctx.info(f"✈️ Searching flights: {originLocationCode} -> {destinationLocationCode} on {departureDate}")
        
        response = client.shopping.flight_offers_search.get(**params)
        
        if not response.data:
            return json.dumps({"info": "No flights found matching criteria."})

        return json.dumps(response.data)

    except ResponseError as error:
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
    Two-step process required by the Amadeus API design:
      Step 1: Discover hotel IDs by city (reference_data endpoint)
      Step 2: Query live availability for those IDs (shopping endpoint)
    The Amadeus shopping endpoint requires known hotel IDs — it cannot search by city directly.
    """
    if not (1 <= adults <= 9):
        return json.dumps({"error": "Adults must be between 1 and 9"})

    try:
        client = _get_amadeus_client(ctx)

        ctx.info(f"🏨 Step 1: Finding hotels in {cityCode}...")
        try:
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

        found_hotels = hotels_response.data[:max]
        hotel_ids = [h.get("hotelId") for h in found_hotels if h.get("hotelId")]

        if not hotel_ids:
            return json.dumps({"error": "Hotels found but had no valid IDs."})

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
    # Provides stdio transport when executed directly (e.g. for Claude Desktop testing).
    # Note: production SSE transport is handled via run_sse.py.
    mcp.run()