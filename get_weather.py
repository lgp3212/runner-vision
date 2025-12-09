import os
import requests
from dotenv import load_dotenv
from langfuse import observe

load_dotenv()

@observe()
def get_weather_conditions(lat: float, lng: float):
    """
    Get current weather conditions from OpenWeatherMap API
    
    Returns relevant data for runner safety:
    - Temperature
    - Weather description (rain, snow, etc)
    - Visibility (important per Shore et al.)
    - Precipitation
    """
    api_key = os.getenv("OPENWEATHER_API_KEY")
    
    if not api_key:
        return {"error": "OPENWEATHER_API_KEY not found in .env"}
    
    url = "https://api.openweathermap.org/data/2.5/weather"
    params = {
        "lat": lat,
        "lon": lng,
        "appid": api_key,
        "units": "imperial"  # Fahrenheit
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        # Extract relevant fields
        # go back and print relevant fields, we prob need geocoding
        weather_info = {
            "temperature_f": data["main"]["temp"],
            "feels_like_f": data["main"]["feels_like"],
            "description": data["weather"][0]["description"],
            "main_condition": data["weather"][0]["main"],  # Rain, Snow, Clear, etc
            "visibility_meters": data.get("visibility", 10000),  # default 10km if not provided
            "humidity_percent": data["main"]["humidity"],
            "wind_speed_mph": data["wind"]["speed"],
        }
        
        # Add precipitation if present
        if "rain" in data:
            weather_info["rain_mm_1h"] = data["rain"].get("1h", 0)
        else:
            weather_info["rain_mm_1h"] = 0
            
        if "snow" in data:
            weather_info["snow_mm_1h"] = data["snow"].get("1h", 0)
        else:
            weather_info["snow_mm_1h"] = 0
        
        return weather_info
        
    except requests.exceptions.RequestException as e:
        return {"error": f"Weather API request failed: {str(e)}"}
    except KeyError as e:
        return {"error": f"Unexpected weather API response format: {str(e)}"}

@observe()
def assess_weather_risk(weather_data: dict) -> dict:
    """
    Assess weather-related running risk based on Shore et al. findings
    
    Shore et al. found that 5/8 fatal incidents occurred in afternoon/evening
    when visibility may be reduced.
    """
    if "error" in weather_data:
        return {"risk_level": "unknown", "reasons": [weather_data["error"]]}
    
    risk_factors = []
    risk_score = 0  # 0 = safe, higher = more risky
    
    # Visibility check (Shore et al. - low light conditions)
    visibility = weather_data.get("visibility_meters", 10000)
    if visibility < 1000:  # Less than 1km
        risk_factors.append("Very low visibility (< 1km)")
        risk_score += 3
    elif visibility < 3000:  # Less than 3km
        risk_factors.append("Reduced visibility (< 3km)")
        risk_score += 1
    
    # Precipitation check (affects traction)
    rain = weather_data.get("rain_mm_1h", 0)
    snow = weather_data.get("snow_mm_1h", 0)
    
    if rain > 5:
        risk_factors.append("Heavy rain (affects traction)")
        risk_score += 2
    elif rain > 0:
        risk_factors.append("Light rain (minor traction concern)")
        risk_score += 1
    
    if snow > 0:
        risk_factors.append("Snow (affects traction and visibility)")
        risk_score += 2
    
    # Temperature extremes
    temp = weather_data.get("temperature_f", 60)
    if temp < 20:
        risk_factors.append("Very cold temperature (< 20°F)")
        risk_score += 1
    elif temp > 95:
        risk_factors.append("Very hot temperature (> 95°F)")
        risk_score += 1
    
    # Determine risk level
    if risk_score == 0:
        risk_level = "low"
    elif risk_score <= 2:
        risk_level = "moderate"
    else:
        risk_level = "high"
    
    return {
        "risk_level": risk_level,
        "risk_score": risk_score,
        "risk_factors": risk_factors if risk_factors else ["Good running conditions"],
        "weather_summary": f"{weather_data.get('description', 'unknown')}, {temp:.0f}°F"
    }


if __name__ == "__main__":
    # Test the weather functions
    print("Testing weather functions...")
    print("="*60)
    
    # Central Park coordinates
    test_lat = 40.7580
    test_lng = -73.9855
    
    print(f"\nFetching weather for ({test_lat}, {test_lng})...")
    weather = get_weather_conditions(test_lat, test_lng)
    
    print("\nWeather Data:")
    print(weather)
    
    print("\nRisk Assessment:")
    risk = assess_weather_risk(weather)
    print(risk)