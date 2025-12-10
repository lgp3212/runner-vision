from typing import TypedDict, Literal
from langgraph.graph import StateGraph, END
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

import get_routes
import polyline_safety_analysis as psa
import get_weather
import get_closures

from langfuse.langchain import CallbackHandler
import os
from dotenv import load_dotenv

load_dotenv()

# Initialize LangFuse handler
langfuse_handler = CallbackHandler()


# state defn
class RunnerVisionState(TypedDict):
    # user inputs
    query: str
    start_lat: float
    start_lng: float
    target_distance_km: float

    # router decisions (determines conditional execution)
    needs_safety: bool
    needs_weather: bool
    needs_closures: bool

    # agent outputs
    routes: list  # from route gen agent
    safety_analysis: list  # from safety analysis agent
    weather_data: dict  # from contextual intelligence agent
    closures_data: dict  # from street closure agenet

    # final output
    recommendation: str
    error_messages: list


llm = ChatOpenAI(
    model="gpt-4o-mini", temperature=0.3, api_key=os.getenv("OPENAI_API_KEY")
)


def router_agent(state: RunnerVisionState) -> RunnerVisionState:

    query = state["query"].lower()

    # key words for mentioning safety
    state["needs_safety"] = any(
        word in query
        for word in [
            "safe",
            "danger",
            "crash",
            "accident",
            "traffic",
            "risk",
            "hazard",
            "pedestrian",
            "vehicle",
            "collision",
        ]
    )

    # weather: always check
    state["needs_weather"] = True

    # closures: check if mentioned or will be determined after weather
    state["needs_closures"] = any(
        word in query
        for word in [
            "closure",
            "construction",
            "closed",
            "detour",
            "blocked",
            "permit",
            "work",
            "maintenance",
            "roadwork",
        ]
    )

    print(f"query: '{state['query']}'")
    print(f"    safety analysis: {'yes' if state['needs_safety'] else 'skip'}")
    print(f"    weather check: always (affects all runs)")
    print(
        f"    closure check: {'yes' if state['needs_closures'] else 'pending (depends on weather)'}"
    )
    print()

    return state


def route_generation_agent(state: RunnerVisionState) -> RunnerVisionState:
    print(f"generating routes from ({state['start_lat']:.4f}, {state['start_lng']:.4f})")
    print(f"target distance: {state['target_distance_km']}km\n")

    try:
        routes = get_routes.optimized_route_finder(
            state["start_lat"], state["start_lng"], state["target_distance_km"]
        )

        if not routes:
            print("No routes generated")
            state["routes"] = []
            state["error_messages"] = state.get("error_messages", []) + ["Route generation failed"]
            return state

        state["routes"] = routes
        print(f"generated {len(routes)} routes")
        for i, route in enumerate(routes, 1):
            print(f"   {i}. {route['direction']}: {route['accuracy']:.1f}% accuracy")
        print()

    except Exception as e:
        print(f"Route generation failed: {e}")
        state["routes"] = []
        state["error_messages"] = state.get("error_messages", []) + [f"Route generation error: {str(e)}"]

    return state


def safety_analysis_agent(state: RunnerVisionState) -> RunnerVisionState:
    if not state.get("needs_safety", False):
        print("safety analysis agent skipped")
        state["safety_analysis"] = []
        return state

    if not state.get("routes"):
        print("no routes available for safety analysis")
        state["safety_analysis"] = []
        return state

    print(f"analyzing crash data for {len(state['routes'])} routes...\n")

    try:
        top_3_routes = sorted(state["routes"], key=lambda x: x["accuracy"], reverse=True)[:3]
        print(f"   analyzing top 3 most accurate routes (out of {len(state['routes'])} total)\n")

        enhanced_routes = []
        for i, route in enumerate(top_3_routes, 1):
            try:
                print(f"   analyzing route {i}/3: {route['direction']} ({route['accuracy']:.1f}% accuracy)...")
                enhanced_route = psa.analyze_route_safety_detailed(route)
                enhanced_routes.append(enhanced_route)

                safety_score = enhanced_route["safety_analysis"]["overall_safety_score"]
                dangerous_count = len(enhanced_route["safety_analysis"]["dangerous_segments"])
                print(f"    safety score: {safety_score:.1f}/100")
                print(f"    dangerous segments: {dangerous_count}\n")

            except Exception as e:
                print(f"    ⚠️ Failed to analyze route {i}: {e}")
                # Continue with other routes
                continue

        if not enhanced_routes:
            print("all routes failed safety analysis")
            state["error_messages"] = state.get("error_messages", []) + ["Safety analysis failed"]

        state["safety_analysis"] = enhanced_routes
        print("safety analysis complete\n")

    except Exception as e:
        print(f"safety analysis failed: {e}")
        state["safety_analysis"] = []
        state["error_messages"] = state.get("error_messages", []) + [f"Safety analysis error: {str(e)}"]

    return state

def contextual_intelligence_agent(state: RunnerVisionState) -> RunnerVisionState:
    print(f"checking weather at ({state['start_lat']:.4f}, {state['start_lng']:.4f})...\n")

    try:
        weather = get_weather.get_weather_conditions(state["start_lat"], state["start_lng"])
        
        if "error" in weather:
            print(f"weather check failed: {weather['error']}")
            state["weather_data"] = {}
            state["error_messages"] = state.get("error_messages", []) + ["Weather data unavailable"]
            return state

        weather_risk = get_weather.assess_weather_risk(weather)
        state["weather_data"] = {"conditions": weather, "risk_assessment": weather_risk}

        print(f"current conditions: {weather.get('description', 'unknown')}")
        print(f"   temperature: {weather.get('temperature_f', 0):.0f}°F")
        print(f"   visibility: {weather.get('visibility_meters', 0)}m")
        print(f"   risk level: {weather_risk['risk_level']}")

        if weather_risk["risk_level"] == "high":
            state["weather_too_dangerous"] = True
            print(f"    dangerous conditions - outdoor running not recommended\n")
            return state

        if weather_risk["risk_level"] == "moderate" and not state.get("needs_closures"):
            state["needs_closures"] = True
            print(f"    weather risk is moderate - will check closures")

        print()

    except Exception as e:
        print(f"weather check failed: {e}")
        state["weather_data"] = {}
        state["error_messages"] = state.get("error_messages", []) + [f"Weather error: {str(e)}"]

    return state


def street_closure_agent(state: RunnerVisionState) -> RunnerVisionState:
    if not state.get("needs_closures", False):
        print("street closure agent - skipped")
        state["closures_data"] = {}
        return state

    if not state.get("routes"):
        print("⚠️ No routes available for closure checking")
        state["closures_data"] = {}
        return state

    print(f"checking closures along route polyline...")

    try:
        top_route = state["routes"][0]
        
        import polyline
        import utils

        route_points = polyline.decode(top_route["polyline"])
        sample_points = utils.sample_route_strategically(route_points, num_samples=3)

        print(f"   Sampling {len(sample_points)} points along route for closure detection")

        all_closures = []
        for i, point in enumerate(sample_points):
            try:
                print(f"   Checking closures at point {i+1}/{len(sample_points)}: {point['route_progress']:.0f}% along route")

                closures = get_closures.get_street_closures(
                    point["lat"],
                    point["lng"],
                    radius_km=0.75,
                    days_back=14,
                )

                if "error" in closures:
                    print(f"    ⚠️ Closure check failed for point {i+1}")
                    continue

                if closures.get("closures"):
                    all_closures.extend(closures["closures"])

            except Exception as e:
                print(f"    ⚠️ Error checking point {i+1}: {e}")
                continue

        # Deduplicate
        unique_closures = {}
        for closure in all_closures:
            key = f"{closure.get('street_name', '')}_{closure.get('work_start_date', '')}"
            if key not in unique_closures:
                unique_closures[key] = closure

        closure_list = list(unique_closures.values())

        state["closures_data"] = {
            "closures": {"total_closures": len(closure_list), "closures": closure_list},
            "impact_assessment": get_closures.assess_closure_impact(
                {"total_closures": len(closure_list)}
            ),
        }

        print(f"   Found {len(closure_list)} unique closures along route\n")

    except Exception as e:
        print(f"closure detection failed: {e}")
        state["closures_data"] = {}
        state["error_messages"] = state.get("error_messages", []) + [f"Closure detection error: {str(e)}"]

    return state

def synthesis_agent(state: RunnerVisionState) -> RunnerVisionState:
    print("\ngenerating final recommendation...\n")

    try:
        # Check if we have minimum required data
        if not state.get("routes"):
            state["recommendation"] = "unable to generate routes. Please try a different location or distance."
            return state

        # Build context
        context = {
            "user_query": state["query"],
            "location": {"lat": state["start_lat"], "lng": state["start_lng"]},
            "target_distance_km": state["target_distance_km"],
            "routes_generated": len(state["routes"]),
            "route_details": [
                {
                    "direction": r["direction"],
                    "accuracy": f"{r['accuracy']:.1f}%",
                    "total_distance_km": r["distance"]["total_distance"],
                }
                for r in state["routes"]
            ],
        }

        # Add conditional data
        if state.get("safety_analysis"):
            context["safety_data"] = [
                {
                    "direction": sa["direction"],
                    "overall_safety_score": sa["safety_analysis"]["overall_safety_score"],
                    "dangerous_segments": len(sa["safety_analysis"]["dangerous_segments"]),
                }
                for sa in state["safety_analysis"]
            ]

        if state.get("weather_data"):
            context["weather"] = state["weather_data"]

        if state.get("closures_data"):
            context["closures"] = {
                "total_closures": state["closures_data"]["closures"].get("total_closures", 0),
                "impact": state["closures_data"]["impact_assessment"]["impact"],
            }

        # Add error messages if any
        if state.get("error_messages"):
            context["warnings"] = state["error_messages"]

        # Call LLM
        messages = [
            SystemMessage(content="""You are RunnerVision AI, a running safety expert.

Provide practical recommendations with clear reasoning. If any warnings are present, acknowledge them.
Be concise but informative."""),
            HumanMessage(content=f"Analyze this data and provide a recommendation:\n\n{context}")
        ]

        response = llm.invoke(messages)
        state["recommendation"] = response.content

    except Exception as e:
        print(f"Synthesis failed: {e}")
        state["recommendation"] = f"unable to generate recommendation: {str(e)}\n\nPlease try again or adjust your query."

    print()
    return state


def create_runner_vision_graph():

    workflow = StateGraph(RunnerVisionState)

    # add all agent nodes
    workflow.add_node("router", router_agent)
    workflow.add_node("route_generation", route_generation_agent)
    workflow.add_node("safety_analysis", safety_analysis_agent)
    workflow.add_node("contextual_intelligence", contextual_intelligence_agent)
    workflow.add_node("street_closures", street_closure_agent)
    workflow.add_node("synthesis", synthesis_agent)

    # define sequential flow
    # router → route generation → conditionals → synthesis
    workflow.set_entry_point("router")
    workflow.add_edge("router", "route_generation")
    workflow.add_edge("route_generation", "safety_analysis")
    workflow.add_edge("safety_analysis", "contextual_intelligence")
    workflow.add_edge("contextual_intelligence", "street_closures")
    workflow.add_edge("street_closures", "synthesis")
    workflow.add_edge("synthesis", END)

    return workflow.compile()


def run_runner_vision(
    query: str, start_lat: float, start_lng: float, target_distance_km: float
) -> dict:
    
    # Input validation
    if not query or len(query.strip()) < 3:
        return {"error": "Query must be at least 3 characters"}
    
    if not (-90 <= start_lat <= 90) or not (-180 <= start_lng <= 180):
        return {"error": "Invalid coordinates"}
    
    if target_distance_km <= 0 or target_distance_km > 50:
        return {"error": "Distance must be between 0 and 50 km"}

    graph = create_runner_vision_graph()

    initial_state = {
        "query": query,
        "start_lat": start_lat,
        "start_lng": start_lng,
        "target_distance_km": target_distance_km,
        "needs_safety": False,
        "needs_weather": False,
        "needs_closures": False,
        "routes": [],
        "safety_analysis": [],
        "weather_data": {},
        "closures_data": {},
        "recommendation": "",
        "error_messages": [],  # ADD THIS
    }
    
    try:
        result = graph.invoke(initial_state, config={"callbacks": [langfuse_handler]})
        return result
    except Exception as e:
        print(f"workflow failed: {e}")
        return {
            "error": f"System error: {str(e)}",
            "recommendation": "Unable to process request. Please try again."
        }


# test cases !!!!!
def test_query_1_minimal():
    print("test 1: minimal query")
    print()

    result = run_runner_vision(
        query="Give me a 5k route from Central Park",
        start_lat=40.7580,
        start_lng=-73.9855,
        target_distance_km=5.0,
    )

    print("\nfinal recommendation: ")
    print(result["recommendation"])
    print("\n")

    return result


def test_query_2_safety():
    print("\ntest 2: safety-focused query")
    print()

    result = run_runner_vision(
        query="I need a safe 5k running route, what areas should I avoid due to crashes?",
        start_lat=40.7580,
        start_lng=-73.9855,
        target_distance_km=5.0,
    )

    print("\nfinal recommendation: ")
    print(result["recommendation"])
    print("\n")

    return result


def test_query_3_comprehensive():
    print("\ntest 3: comprehensive query")
    print()

    result = run_runner_vision(
        query="Find me a safe 5k route with good weather conditions and no construction",
        start_lat=40.7580,
        start_lng=-73.9855,
        target_distance_km=5.0,
    )

    print("\nfinal recommendation: ")
    print(result["recommendation"])
    print("\n")

    return result


if __name__ == "__main__":
    print("\n")
    print("runnervision ai: multi-agent langgraph system")
    print("🏃" * 30 + "\n")

    print("running 3 test cases with varying complexity...\n")

    test_query_1_minimal()
    test_query_2_safety()
    test_query_3_comprehensive()
