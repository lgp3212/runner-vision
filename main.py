from fastapi import FastAPI
from ai_agents import SafetyAnalysisAgent

# from test_google_routes import GoogleRoutesAPI
import get_routes
import polyline_safety_analysis as p

app = FastAPI(title="runsafe-ai", version="0.1.0")

safety_ai = None


def get_safety_ai():
    global safety_ai
    if safety_ai is None:
        try:
            print("Attempting to initialize SafetyAnalysisAgent...")
            safety_ai = SafetyAnalysisAgent()
            print("SafetyAnalysisAgent initialized successfully!")
        except Exception as e:
            print(f"Could not initialize AI agent: {e}")
            print(f"Error type: {type(e)}")
            import traceback

            traceback.print_exc()
            return None
    return safety_ai


@app.get("/api/routes/generate")
def generate_running_routes(
    start_lat: float, start_lng: float, target_distance_km: float = 5.0
):
    """Generate routes and get AI recommendations"""

    # Generate routes with safety analysis
    try:
        enhanced_routes = p.generate_running_routes_with_polyline_safety(
            start_lat, start_lng, target_distance_km, get_routes.optimized_route_finder
        )

        # prep metadata for LLM
        route_metadata = {
            "start_location": {"lat": start_lat, "lng": start_lng},
            "target_distance_km": target_distance_km,
            "route_options": enhanced_routes,
        }

        ai_agent = get_safety_ai()
        return ai_agent.make_call_to_llm(route_metadata)
    except:
        print("no service!!")
