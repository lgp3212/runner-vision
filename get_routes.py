import math
import requests
import os
from dotenv import load_dotenv
import constants as const
import utils
from constants import Direction, CompassBearing, MapsApi
from langfuse import observe

load_dotenv()


def generate_optimized_endpoints(
    start_lat, start_lng, target_distance_km, d=Direction, cb=CompassBearing
):
    """Generate endpoints only for good directions (based on your data analysis)"""

    # distance --> coordinates
    lat_delta = target_distance_km / 111.0  # degrees latitude
    lng_delta = target_distance_km / (
        111.0 * math.cos(math.radians(start_lat))
    )  # degrees longitude

    print(f"   Target distance: {target_distance_km} km")
    print(f"   Latitude delta: {lat_delta:.6f} degrees")
    print(f"   Longitude delta: {lng_delta:.6f} degrees")
    print()

    endpoints = []  # initializing endpoints

    for direction in d:
        bearing = cb[direction.name].value
        direction_name = direction.value
        print(f"Bearing: {bearing}, Name: {direction_name}")

        # bearing --> radians
        bearing_rad = math.radians(bearing)

        # calculate new coordinates
        new_lat = start_lat + (lat_delta * math.cos(bearing_rad))
        new_lng = start_lng + (lng_delta * math.sin(bearing_rad))

        # verify distance using Haversine
        actual_distance = utils.euc_distance(start_lat, start_lng, new_lat, new_lng)

        endpoint = {
            "lat": new_lat,
            "lng": new_lng,
            "bearing": bearing,
            "direction": direction_name,
            "calculated_distance": actual_distance,
        }
        endpoints.append(endpoint)

        print(
            f"   {direction_name:>9}: ({new_lat:.4f}, {new_lng:.4f}) - {actual_distance:.2f}km"
        )

    return endpoints

@observe()
def test_google_routes_distance(start_lat, start_lng, end_lat, end_lng, mapi=MapsApi):
    """Test actual walking distance using Google Routes API"""

    api_key = os.getenv("GOOGLE_ROUTES_API_KEY")
    url = mapi.COMPUTE_ROUTES.value

    headers = {
        "Content-Type": mapi.CONTENT.value,
        "X-Goog-Api-Key": api_key,
        "X-Goog-FieldMask": mapi.FIELD_MASK.value,
    }

    data = {
        "origin": {
            "location": {"latLng": {"latitude": start_lat, "longitude": start_lng}}
        },
        "destination": {
            "location": {"latLng": {"latitude": end_lat, "longitude": end_lng}}
        },
        "travelMode": "WALK",
    }

    try:
        response = requests.post(url, json=data, headers=headers)
        response.raise_for_status()
        result = response.json()

        if "routes" in result and result["routes"]:
            route = result["routes"][0]
            distance_meters = route.get("distanceMeters", 0)
            duration_seconds = int(route.get("duration", "0s").replace("s", ""))
            polyline = route.get("polyline", {}).get("encodedPolyline", "")

            return {
                "distance_km": distance_meters / 1000,
                "duration_minutes": duration_seconds / 60,
                "polyline": polyline,
                "success": True,
            }
    except Exception as e:
        return {"error": str(e), "success": False}

    return {"error": "No routes found", "success": False}


def calculate_and_test_endpoints(
    start_lat, start_lng, target_distance, all_routes=[], optimal_multiplier=0.4
):
    one_way_distance = target_distance * optimal_multiplier
    print(f"One-way distance entering endpoint generation: {one_way_distance:.2f}km")

    # generating optimized endpoints based on multiplier
    endpoints = generate_optimized_endpoints(start_lat, start_lng, one_way_distance)
    endpoints = reverse_geocode_and_filter(endpoints)

    phase1_routes = []

    for i, endpoint in enumerate(endpoints):
        print(f"   Testing {endpoint['direction']} route...")

        google_result = test_google_routes_distance(
            start_lat, start_lng, endpoint["lat"], endpoint["lng"]
        )

        if google_result["success"]:
            one_way_actual = google_result["distance_km"]
            total_distance = one_way_actual * 2  # out and back
            difference = abs(total_distance - target_distance)
            accuracy = 100 * (1 - difference / target_distance)

            route_info = {
                "id": i + 1,
                "direction": endpoint["direction"],
                "accuracy": accuracy,
                "distance": {
                    "target_distance": target_distance,
                    "total_distance": total_distance,
                },
                "endpoint": {"lat": endpoint["lat"], "lng": endpoint["lng"]},
                "polyline": google_result.get("polyline", ""),
            }
            phase1_routes.append(route_info)
            all_routes.append(route_info)
        else:
            continue
    print()
    return phase1_routes, all_routes

@observe()
def optimized_route_finder(start_lat, start_lng, target_distance):
    phase1_routes, all_routes = calculate_and_test_endpoints(
        start_lat, start_lng, target_distance
    )

    excellent_phase1 = [r for r in phase1_routes if r["accuracy"] >= 95]
    good_phase1 = [r for r in phase1_routes if r["accuracy"] >= 90]

    print(f"📊 Phase 1 Results:")
    print(f"   Excellent routes (≥95%): {len(excellent_phase1)}")
    print(f"   Good routes (≥90%): {len(good_phase1)}")
    print()

    # PHASE 2: Only run if we need more good routes
    if len(excellent_phase1) >= 3:
        print("✅ SUCCESS: Found 3+ excellent routes in Phase 1! Stopping here.")
        final_routes = sorted(
            excellent_phase1, key=lambda x: x["accuracy"], reverse=True
        )
    elif len(good_phase1) >= 3:
        print("✅ SUCCESS: Found 3+ good routes in Phase 1! Stopping here.")
        final_routes = sorted(good_phase1, key=lambda x: x["accuracy"], reverse=True)
    else:
        print("🔍 PHASE 2: Testing backup multipliers for better coverage")
        print("=" * 50)

        backup_multipliers = [0.35, 0.45]  # Based on your data

        for multiplier in backup_multipliers:
            _, all_routes = calculate_and_test_endpoints(
                start_lat,
                start_lng,
                target_distance,
                all_routes=all_routes,
                optimal_multiplier=multiplier,
            )
            print()

        # Select final routes from all phases
        decent_routes = [r for r in all_routes if r["accuracy"] >= 80]
        final_routes = sorted(decent_routes, key=lambda x: x["accuracy"], reverse=True)

    print(f"🏆 FINAL TOP 3 ROUTES:")
    print("=" * 60)

    for i, route in enumerate(final_routes, 1):
        print(f"{i}. {route['direction']}")
        print(f"   🎯 Accuracy: {route['accuracy']:.1f}%")
        print(
            f"   📍 Endpoint: ({route['endpoint']['lat']:.4f}, {route['endpoint']['lng']:.4f})"
        )
        print()
    return final_routes

@observe()
def reverse_geocode_and_filter(endpoints, water_keywords=const.ignore, mapi=MapsApi):
    """
    Reverse geocode endpoints and filter out water/invalid locations

    Args:
        endpoints: List of endpoint dicts with 'lat', 'lng', 'direction' keys

    Returns:
        List of valid endpoints with added 'address' field
    """

    api_key = os.getenv("GOOGLE_ROUTES_API_KEY")
    valid_endpoints = []

    print(
        f"Reverse geocoding {len(endpoints)} endpoints to filter out water locations..."
    )

    for endpoint in endpoints:
        lat = endpoint["lat"]
        lng = endpoint["lng"]
        direction = endpoint["direction"]

        # google geocoding API call
        geocoding_url = mapi.GEOCODING.value
        params = {"latlng": f"{lat},{lng}", "key": api_key}

        try:
            response = requests.get(geocoding_url, params=params, timeout=10)
            response.raise_for_status()
            result = response.json()

            if result["status"] == "OK" and result["results"]:
                address = result["results"][0]["formatted_address"]
                is_water = any(keyword in address for keyword in water_keywords)

                if is_water:
                    print(f"   {direction}: {address} (FILTERED - water/invalid)")
                else:
                    # adding address to metadata
                    endpoint["address"] = address
                    valid_endpoints.append(endpoint)
                    print(f"   ✅ {direction}: {address}")
            else:
                print(f"   {direction}: No address found (FILTERED)")

        except Exception as e:
            print(f"   {direction}: Geocoding error - {str(e)} (FILTERED)")

    print(f"\n Filtering Results:")
    print(f"   Original endpoints: {len(endpoints)}")
    print(f"   Valid endpoints: {len(valid_endpoints)}")
    print(f"   Filtered out: {len(endpoints) - len(valid_endpoints)}")

    return valid_endpoints


if __name__ == "__main__":
    print("Choose test mode:")
    print("1. Original single distance test")
    print("2. Original comprehensive test (48 API calls)")
    print("3. 🚀 NEW: Optimized smart route finder (6-18 API calls)")

    #start_lat = float(input("Enter starting latitude: "))
    #start_lng = float(input("Enter starting longitude: "))
    start_lat = 40.730182
    start_lng = -73.996770 # adding this here for easy testing 
    target_distance = float(input("Enter target distance: "))

    optimized_route_finder(start_lat, start_lng, target_distance)
