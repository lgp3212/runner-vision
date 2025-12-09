import requests
import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()


def fetch_year_of_crashes():
    """Fetch last 6+ months of crash data from NYC Open Data"""
    cutoff_date = "2024-12-01"  # Adjust as needed
    url = "https://data.cityofnewyork.us/resource/h9gi-nx95.json"

    params = {
        "$limit": 50000,
        "$order": "crash_date DESC",
        "$where": f"latitude IS NOT NULL AND longitude IS NOT NULL AND crash_date >= '{cutoff_date}'",
    }

    print(f"Fetching crashes since {cutoff_date}...")
    response = requests.get(url, params=params)
    crashes = response.json()
    print(f"✓ Fetched {len(crashes)} crashes from NYC Open Data")
    return crashes


def insert_crashes_to_supabase(crashes):
    """Insert crashes into Supabase database"""

    # Get Supabase connection string from .env
    db_url = os.getenv("SUPABASE_DB_URL")

    if not db_url:
        print("ERROR: SUPABASE_DB_URL not found in .env file")
        return

    print(f"Connecting to Supabase...")
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()
    print(f"✓ Connected!")

    inserted = 0
    skipped = 0
    total = len(crashes)

    print(f"Inserting {total} crashes...")

    for i, crash in enumerate(crashes, 1):
        try:
            cursor.execute(
                """
                INSERT INTO crashes (collision_id, crash_date, latitude, longitude, injuries, fatalities)
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (collision_id) DO NOTHING
            """,
                (
                    crash.get("collision_id"),
                    crash.get("crash_date"),
                    float(crash.get("latitude", 0)),
                    float(crash.get("longitude", 0)),
                    int(crash.get("number_of_persons_injured", 0)),
                    int(crash.get("number_of_persons_killed", 0)),
                ),
            )
            if cursor.rowcount > 0:
                inserted += 1
        except Exception as e:
            skipped += 1
            if skipped <= 5:  # Only print first 5 errors
                print(f"   Error inserting crash {crash.get('collision_id')}: {e}")

        # Progress indicator every 1000 rows
        if i % 1000 == 0:
            print(
                f"   Progress: {i}/{total} ({i/total*100:.1f}%) - Inserted: {inserted}, Skipped: {skipped}"
            )
            conn.commit()  # Commit every 1000 rows

    conn.commit()
    conn.close()

    print(f"✓ Inserted {inserted} new crashes")
    print(f"  Skipped {skipped} duplicates")
    print(f"✓ Database updated successfully")


if __name__ == "__main__":
    print("=" * 60)
    print("SUPABASE DATABASE BACKFILL")
    print("=" * 60)

    crashes = fetch_year_of_crashes()
    insert_crashes_to_supabase(crashes)

    print("\n" + "=" * 60)
    print("DONE!")
    print("=" * 60)
