from langchain_core.tools import tool
import get_routes
import polyline_safety_analysis as psa


@tool
def generate_running_routes(
    start_lat: float, start_lng: float, target_distance_km: float
):
    """Generate 3 optimized running routes from a starting location."""
    return get_routes.optimized_route_finder(start_lat, start_lng, target_distance_km)


@tool
def analyze_route_safety(route_dict: dict):
    """Analyze crash safety for a route using its polyline."""
    return psa.analyze_route_safety_detailed(route_dict)


@tool
def get_weather_conditions(lat: float, lng: float):
    """Get current weather conditions for route planning."""
    import requests
    import os

    api_key = os.getenv("OPENWEATHER_API_KEY")
    response = requests.get(
        f"https://api.openweathermap.org/data/2.5/weather?lat={lat}&lon={lng}&appid={api_key}&units=imperial"
    )
    data = response.json()
    return {
        "temperature": data["main"]["temp"],
        "description": data["weather"][0]["description"],
        "visibility": data.get("visibility", 10000),  # meters
    }
