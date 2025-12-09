import polyline  # pip install polyline
import psycopg2
import math
import utils

import os
from dotenv import load_dotenv
from langfuse import observe

load_dotenv()


def get_db_connection():
    """Get database connection (Supabase or local fallback)"""
    db_url = os.getenv("SUPABASE_DB_URL")
    if db_url:
        return psycopg2.connect(db_url)
    else:
        return psycopg2.connect(
            host="localhost", database="runsafe_db", user="lpietrewicz", password=""
        )


def decode_route_polyline(encoded_polyline):
    """Decode Google's polyline to get all route coordinates"""
    if not encoded_polyline:
        return []
    try:
        coordinates = polyline.decode(encoded_polyline)
        return [{"lat": lat, "lng": lng} for lat, lng in coordinates]
    except Exception as e:
        print(f"Error decoding polyline: {e}")
        return []


def sample_route_points(route_points, max_samples=10):
    """Sample points along route to avoid too many API calls"""
    if not route_points or len(route_points) <= max_samples:
        return route_points

    step = len(route_points) // max_samples
    sampled_points = []

    for i in range(0, len(route_points), step):
        sampled_points.append(
            {
                **route_points[i],
                "route_index": i,
                "route_progress": round(
                    (i / len(route_points)) * 100, 1
                ),  # percentage along route
            }
        )

    # always include the last point
    if route_points[-1] not in sampled_points:
        sampled_points.append(
            {
                **route_points[-1],
                "route_index": len(route_points) - 1,
                "route_progress": 100.0,
            }
        )

    return sampled_points


def analyze_route_safety_detailed(route):
    """
    Comprehensive safety analysis using strategic polyline sampling
    """
    encoded_polyline = route.get("polyline", "")
    route_points = decode_route_polyline(encoded_polyline)

    # Use shared sampling function with optimized parameters
    sample_points = utils.sample_route_strategically(route_points, num_samples=3)

    print(f"   Sampling {len(sample_points)} points along route for safety analysis")

    segment_analyses = []

    for i, point in enumerate(sample_points):
        print(
            f"   Analyzing point {i+1}/{len(sample_points)}: {point['route_progress']:.0f}% along route"
        )

        # Query with larger radius to compensate for fewer samples
        crashes_response = get_crashes_near_me(
            point["lat"],
            point["lng"],
            radius_km=0.75,  # Increased from 0.5km
            days_back=60,
        )

        segment_analysis = {
            "point_index": i,
            "route_progress": point.get("route_progress", 0),
            "coordinates": {"lat": point["lat"], "lng": point["lng"]},
            "counts": crashes_response["summary"],
            "safety_score": crashes_response["safety"],
        }
        segment_analyses.append(segment_analysis)

    safety_scores = [seg["safety_score"] for seg in segment_analyses]
    overall_safety = sum(safety_scores) / len(safety_scores)

    dangerous_segments = [seg for seg in segment_analyses if seg["safety_score"] < 80]

    return {
        **route,
        "safety_analysis": {
            "overall_safety_score": round(overall_safety, 1),
            "dangerous_segments": dangerous_segments,
            "sample_points": len(sample_points),  # Add metadata
        },
    }


def generate_running_routes_with_polyline_safety(
    start_lat, start_lng, target_distance_km, get_routes_function
):
    """
    Main function to generate routes with detailed polyline-based safety analysis
    """
    routes = get_routes_function(start_lat, start_lng, target_distance_km)
    if not routes:
        return {}

    enhanced_routes = []
    for route in routes:
        enhanced_route = analyze_route_safety_detailed(route)
        enhanced_routes.append(enhanced_route)
    return enhanced_routes


def get_area_crash_percentiles(
    lat: float, lng: float, radius_km: float = 1.0, attr="injuries"
):
    """Calculate crash percentiles for areas similar to the query location"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # create a grid of sample points around the area to get distribution
        grid_size = 0.01
        sample_points = []

        sql = {
            f"{attr}": f"COALESCE(SUM({attr}), 0)",
            "crashes": "COUNT(*)",
        }

        for lat_offset in [-2 * grid_size, -grid_size, 0, grid_size, 2 * grid_size]:
            for lng_offset in [-2 * grid_size, -grid_size, 0, grid_size, 2 * grid_size]:
                sample_lat = lat + lat_offset
                sample_lng = lng + lng_offset

                lat_buffer = radius_km / 111.0
                lng_buffer = radius_km / (111.0 * math.cos(math.radians(sample_lat)))

                cursor.execute(
                    f"""
                    SELECT 
                        {sql[f"{attr}"]} as {attr}
                    FROM crashes
                    WHERE latitude BETWEEN %s AND %s
                    AND longitude BETWEEN %s AND %s
                    """,
                    (
                        sample_lat - lat_buffer,
                        sample_lat + lat_buffer,
                        sample_lng - lng_buffer,
                        sample_lng + lng_buffer,
                    ),
                )

                count = cursor.fetchone()[0]
                sample_points.append(count)

        conn.close()

        sample_points.sort()
        p50_index = int(0.5 * len(sample_points))

        return sample_points[p50_index]

    except Exception as e:
        return {"error": f"Percentile calculation failed: {str(e)}"}


def get_crashes_near_me(
    lat: float, lng: float, radius_km: float = 0.5, days_back: int = 60
):
    try:
        conn = get_db_connection()
        cursor = conn.cursor()

        # bounding box for query
        lat_buffer = radius_km / 111.0
        lng_buffer = radius_km / (111.0 * math.cos(math.radians(lat)))

        cursor.execute(
            """
            SELECT collision_id, crash_date, latitude, longitude, injuries, fatalities
            FROM crashes
            WHERE latitude BETWEEN %s AND %s
            AND longitude BETWEEN %s AND %s
        """,
            (lat - lat_buffer, lat + lat_buffer, lng - lng_buffer, lng + lng_buffer),
        )

        rough_crashes = cursor.fetchall()
        conn.close()

        # filter by exact distance
        nearby_crashes = []
        for crash in rough_crashes:
            collision_id, crash_date, crash_lat, crash_lng, injuries, fatalities = crash
            distance = utils.euc_distance(lat, lng, float(crash_lat), float(crash_lng))

            if distance <= radius_km:
                clean_crash = {
                    "crash_id": collision_id,
                    "date": str(crash_date),
                    "distance_km": round(distance, 2),
                    "location": {"lat": float(crash_lat), "lng": float(crash_lng)},
                    "injuries": injuries or 0,
                    "fatalities": fatalities or 0,
                }
                nearby_crashes.append(clean_crash)

        # summary
        safety_score, total_crashes, total_injuries, total_fatalities = safety_wrapper(
            lat, lng, radius_km, nearby_crashes
        )

        return {
            "search_location": {"lat": lat, "lng": lng},
            "search_radius_km": radius_km,
            "days_searched": days_back,
            "summary": {
                "total_crashes": total_crashes,
                "total_injuries": total_injuries,
                "total_fatalities": total_fatalities,
            },
            "safety": safety_score,
        }

    except Exception as e:
        return {"error": f"Database query failed: {str(e)}"}


def calculate_safety_score_logarithmic(crash_ratio, injury_ratio, fatality_ratio):
    """Calculate safety score using logarithmic scaling for extreme ratios"""
    crash_penalty = min(30, max(0, 15 * math.log(max(crash_ratio, 0.1))))
    injury_penalty = min(35, max(0, 20 * math.log(max(injury_ratio, 0.1))))
    if fatality_ratio == 0:
        fatality_penalty = 0
    else:
        fatality_penalty = min(50, max(0, 25 * math.log(max(fatality_ratio, 0.1))))

    safety_score = 100 - crash_penalty - injury_penalty - fatality_penalty
    return max(0, min(100, safety_score))


def safety_wrapper(lat, lng, radius_km, nearby_crashes):
    total_crashes = len(nearby_crashes)
    total_injuries = sum(crash["injuries"] for crash in nearby_crashes)
    total_fatalities = sum(crash["fatalities"] for crash in nearby_crashes)

    percentile50_crashes = get_area_crash_percentiles(
        lat, lng, radius_km=radius_km, attr="crashes"
    )
    percentile50_injuries = get_area_crash_percentiles(
        lat, lng, radius_km=radius_km, attr="injuries"
    )
    percentile50_fatalities = get_area_crash_percentiles(
        lat, lng, radius_km=radius_km, attr="fatalities"
    )
    try:
        fatality_r = total_fatalities / percentile50_fatalities
    except ZeroDivisionError:
        fatality_r = total_fatalities

    crash_r = total_crashes / percentile50_crashes
    injury_r = total_injuries / percentile50_injuries

    safety_score = calculate_safety_score_logarithmic(crash_r, injury_r, fatality_r)
    return safety_score, total_crashes, total_injuries, total_fatalities


@observe()
def analyze_route_comprehensive(route, check_safety=True, check_closures=False):
    """
    Analyze safety and/or closures at the same sample points
    Efficient combined analysis when both are needed

    Args:
        route: Route dict with polyline
        check_safety: Whether to check crash safety data (default True)
        check_closures: Whether to check street closures (default False)

    Returns:
        Enhanced route with safety_analysis and/or closure_analysis
    """
    # If neither is requested, just return the route
    if not check_safety and not check_closures:
        return route

    encoded_polyline = route.get("polyline", "")
    route_points = decode_route_polyline(encoded_polyline)

    if not route_points:
        # No polyline data - return route with empty analyses
        result = {**route}
        if check_safety:
            result["safety_analysis"] = {
                "overall_safety_score": None,
                "dangerous_segments": [],
                "sample_points": 0,
                "error": "No polyline data available",
            }
        if check_closures:
            result["closure_analysis"] = {
                "total_closures": 0,
                "closures": [],
                "error": "No polyline data available",
            }
        return result

    # Sample at 33%, 66%, 100% (skip start since all routes share it)
    sample_points = utils.sample_route_strategically(
        route_points, num_samples=3, skip_start=True
    )

    print(f"   Sampling {len(sample_points)} points along route (33%, 66%, 100%)")

    segment_analyses = [] if check_safety else None
    all_closures = [] if check_closures else None

    for i, point in enumerate(sample_points):
        print(
            f"   Analyzing point {i+1}/{len(sample_points)}: {point['route_progress']:.0f}% along route"
        )

        # SAFETY: Query crashes (if requested)
        if check_safety:
            crashes_response = get_crashes_near_me(
                point["lat"], point["lng"], radius_km=0.75, days_back=60
            )

            segment_analysis = {
                "point_index": i,
                "route_progress": point.get("route_progress", 0),
                "coordinates": {"lat": point["lat"], "lng": point["lng"]},
                "counts": crashes_response["summary"],
                "safety_score": crashes_response["safety"],
            }
            segment_analyses.append(segment_analysis)

        # CLOSURES: Query at the same points (if requested)
        if check_closures:
            import get_closures

            closures_at_point = get_closures.get_street_closures(
                point["lat"], point["lng"], radius_km=0.75, days_back=14
            )
            if closures_at_point.get("closures"):
                all_closures.extend(closures_at_point["closures"])

    # Build result dict
    result = {**route}

    # Add safety analysis if requested
    if check_safety:
        safety_scores = [seg["safety_score"] for seg in segment_analyses]
        overall_safety = sum(safety_scores) / len(safety_scores) if safety_scores else 0
        dangerous_segments = [
            seg for seg in segment_analyses if seg["safety_score"] < 80
        ]

        result["safety_analysis"] = {
            "overall_safety_score": round(overall_safety, 1),
            "dangerous_segments": dangerous_segments,
            "sample_points": len(sample_points),
            "sample_strategy": "33%, 66%, 100% (skipping shared start point)",
        }

    # Add closure analysis if requested
    if check_closures:
        # Deduplicate closures
        unique_closures = {}
        for closure in all_closures:
            key = (
                f"{closure.get('street_name', '')}_{closure.get('work_start_date', '')}"
            )
            if key not in unique_closures:
                unique_closures[key] = closure

        result["closure_analysis"] = {
            "total_closures": len(unique_closures),
            "closures": list(unique_closures.values()),
            "sample_points": len(sample_points),
            "sample_strategy": "33%, 66%, 100% (skipping shared start point)",
        }

    return result
