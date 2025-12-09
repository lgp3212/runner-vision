from enum import StrEnum, IntEnum


class MapsApi(StrEnum):
    COMPUTE_ROUTES = "https://routes.googleapis.com/directions/v2:computeRoutes"
    GEOCODING = "https://maps.googleapis.com/maps/api/geocode/json"
    FIELD_MASK = "routes.duration,routes.distanceMeters,routes.polyline.encodedPolyline"
    CONTENT = "application/json"
    # PLACES = "https://maps.googleapis.com/maps/api/place/nearbysearch/json"


class SafetyApi(StrEnum):
    URL = "https://data.cityofnewyork.us/resource/h9gi-nx95.json"


class Direction(StrEnum):
    NORTH = "North"
    NORTHEAST = "Northeast"
    EAST = "East"
    SOUTHEAST = "Southeast"
    SOUTH = "South"
    SOUTHWEST = "Southwest"
    WEST = "West"
    NORTHWEST = "Northwest"


class CompassBearing(IntEnum):
    NORTH = 0
    NORTHEAST = 45
    EAST = 90
    SOUTHEAST = 135
    SOUTH = 180
    SOUTHWEST = 225
    WEST = 270
    NORTHWEST = 315


class DatabaseConfig(StrEnum):
    HOST = "localhost"
    DATABASE = "runsafe_db"
    USER = "lpietrewicz"
    PASSWORD = ""


class APIConfig(StrEnum):
    NYC_CRASHES_URL = "https://data.cityofnewyork.us/resource/h9gi-nx95.json"
    REQUEST_LIMIT = "50000"


class ScheduleConfig(StrEnum):
    DAILY_TIME = "02:00"
    LOG_LEVEL = "INFO"


ignore = [
    "North America",
    "Atlantic Ocean",
    "Hudson River",
    "East River",
    "New York Harbor",
    "Unnamed Road",
    "Jersey",
    "NJ",
    "Long Island",
    "Astoria",
    "+",
    "Plus Code",
]

R = 6371  # earth's radius in kilometers
