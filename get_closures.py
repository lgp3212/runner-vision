import requests
from datetime import datetime, timedelta
from langfuse import observe

@observe()
def get_street_closures(lat: float, lng: float, radius_km: float = 0.5, days_back: int = 14):
    """
    Get street closures near a location from NYC DOT data
    
    Args:
        lat: Latitude
        lng: Longitude
        radius_km: Search radius in kilometers
        days_back: How many days back to search (default 14 days)
    
    Returns:
        dict with closure information
    """
    
    url = "https://data.cityofnewyork.us/resource/i6b5-j7bu.json"
    
    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days_back)
    start_date_str = start_date.strftime('%Y-%m-%d')
    
    # Calculate bounding box
    lat_buffer = radius_km / 111.0
    lng_buffer = radius_km / (111.0 * 0.8)
    
    # Get recent closures
    params = {
        "$limit": 5000,
        "$where": f"work_start_date >= '{start_date_str}' AND the_geom IS NOT NULL",
        "$order": "work_start_date DESC"
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        closures = response.json()
        
        print(f"   Fetched {len(closures)} total closures from API")
        
        # Filter by location - check if street segment is near our point
        nearby_closures = []
        for closure in closures:
            try:
                geom = closure.get("the_geom")
                if not geom or not geom.get("coordinates"):
                    continue
                
                # MultiLineString format: [[[lng1, lat1], [lng2, lat2]]]
                # Get all coordinate pairs from all line segments
                all_coords = []
                for line in geom["coordinates"]:
                    for coord in line:
                        # coord is [longitude, latitude]
                        all_coords.append(coord)
                
                # Check if ANY point on the street segment is within our radius
                is_nearby = False
                for coord in all_coords:
                    coord_lng, coord_lat = coord[0], coord[1]
                    
                    if (abs(coord_lat - lat) <= lat_buffer and 
                        abs(coord_lng - lng) <= lng_buffer):
                        is_nearby = True
                        # Use first point of segment as representative location
                        rep_lng, rep_lat = all_coords[0][0], all_coords[0][1]
                        break
                
                if is_nearby:
                    nearby_closures.append({
                        "work_start_date": closure.get("work_start_date"),
                        "work_end_date": closure.get("work_end_date"),
                        "street_name": closure.get("onstreetname"),
                        "from_street": closure.get("fromstreetname"),
                        "to_street": closure.get("tostreetname"),
                        "borough": closure.get("borough_code"),
                        "purpose": closure.get("purpose"),
                        "location": {
                            "lat": rep_lat,
                            "lng": rep_lng
                        }
                    })
                    
            except (ValueError, TypeError, KeyError, IndexError) as e:
                continue
        
        print(f"   Found {len(nearby_closures)} closures within {radius_km}km")
        
        return {
            "search_location": {"lat": lat, "lng": lng},
            "search_radius_km": radius_km,
            "days_searched": days_back,
            "total_closures": len(nearby_closures),
            "closures": nearby_closures
        }
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Street closure API request failed: {str(e)}"}
    except Exception as e:
        return {"error": f"Unexpected error: {str(e)}"}

@observe()
def assess_closure_impact(closures_data: dict) -> dict:
    """
    Assess how street closures might impact running route
    """
    if "error" in closures_data:
        return {"impact": "unknown", "reason": closures_data["error"]}
    
    total_closures = closures_data.get("total_closures", 0)
    
    if total_closures == 0:
        return {
            "impact": "none",
            "message": "No active street closures in the area"
        }
    elif total_closures <= 2:
        return {
            "impact": "low",
            "message": f"{total_closures} street closure(s) nearby - minor impact expected"
        }
    elif total_closures <= 5:
        return {
            "impact": "moderate",
            "message": f"{total_closures} street closures nearby - may need alternate routes"
        }
    else:
        return {
            "impact": "high",
            "message": f"{total_closures} street closures nearby - significant construction activity"
        }


if __name__ == "__main__":
    # Test the closure functions
    print("Testing street closure functions...")
    print("="*60)
    
    # Central Park coordinates
    test_lat = 40.7580
    test_lng = -73.9855
    
    print(f"\nFetching closures near ({test_lat}, {test_lng})...")
    closures = get_street_closures(test_lat, test_lng, radius_km=1.0, days_back=14)
    
    print("\nClosure Data:")
    print(f"Total closures found: {closures.get('total_closures', 0)}")
    
    if closures.get('total_closures', 0) > 0:
        print("\nFirst few closures:")
        for i, closure in enumerate(closures['closures'][:3], 1):
            print(f"\n{i}. {closure['street_name']}")
            print(f"   Dates: {closure['work_start_date']} to {closure.get('work_end_date', 'ongoing')}")
            print(f"   Type: {closure.get('work_type', 'unknown')}")
    
    print("\nImpact Assessment:")
    impact = assess_closure_impact(closures)
    print(impact)