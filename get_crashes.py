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
        # Fallback to local
        return psycopg2.connect(
            host="localhost", database="runsafe_db", user="lpietrewicz", password=""
        )


@observe()
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


@observe()
def get_crashes_near_me(
    lat: float, lng: float, radius_km: float = 0.5, days_back: int = 60
):
    try:
        # WIP - move this out
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
