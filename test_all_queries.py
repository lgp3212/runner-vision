import get_routes
import get_crashes
import get_weather
import get_closures
import polyline_safety_analysis as psa

def test_all_queries(start_lat, start_lng, target_distance_km, 
                     run_safety=True, run_closures=True):
    """
    Test all data queries together with optional components
    
    Args:
        start_lat: Starting latitude
        start_lng: Starting longitude
        target_distance_km: Target distance in km
        run_safety: Whether to run safety analysis (default True)
        run_closures: Whether to run closure analysis (default True)
    """
    print("="*60)
    print("TESTING ALL QUERIES")
    print("="*60)
    print(f"Location: ({start_lat}, {start_lng})")
    print(f"Distance: {target_distance_km}km")
    print(f"Analysis: Safety={run_safety}, Closures={run_closures}")
    print()
    
    # 1. ROUTE GENERATION
    print("1️⃣  ROUTE GENERATION")
    print("-"*60)
    routes = get_routes.optimized_route_finder(start_lat, start_lng, target_distance_km)
    print(f"✓ Generated {len(routes)} routes")
    for i, route in enumerate(routes, 1):
        print(f"   Route {i}: {route['direction']} - {route['accuracy']:.1f}% accuracy")
    print()
    
    # 2. SAFETY AND/OR CLOSURE ANALYSIS
    enhanced_routes = []
    
    if run_safety or run_closures:
        analysis_type = []
        if run_safety:
            analysis_type.append("Safety")
        if run_closures:
            analysis_type.append("Closures")
        
        print(f"2️⃣  {' & '.join(analysis_type).upper()} ANALYSIS")
        print("-"*60)
        
        if run_safety and run_closures:
            print("   Analyzing safety AND closures at same sample points (efficient!)")
        print()
        
        all_closures_combined = []
        
        for i, route in enumerate(routes, 1):
            print(f"   Analyzing route {i}/{len(routes)}: {route['direction']}")
            
            # Single function handles both (or just one)
            enhanced_route = psa.analyze_route_comprehensive(
                route, 
                check_safety=run_safety,
                check_closures=run_closures
            )
            enhanced_routes.append(enhanced_route)
            
            # Print results based on what was analyzed
            if run_safety:
                safety_score = enhanced_route["safety_analysis"]["overall_safety_score"]
                dangerous_count = len(enhanced_route["safety_analysis"]["dangerous_segments"])
                print(f"   ✓ Safety: {safety_score:.1f}/100, Dangerous segments: {dangerous_count}")
            
            if run_closures:
                closure_count = enhanced_route["closure_analysis"]["total_closures"]
                print(f"   ✓ Closures: {closure_count} found along route")
                
                # Collect all closures across routes
                if enhanced_route["closure_analysis"]["closures"]:
                    all_closures_combined.extend(enhanced_route["closure_analysis"]["closures"])
            
            print()
        
        # Deduplicate closures across all routes (if closures were checked)
        total_unique_closures = 0
        unique_all_closures = {}
        
        if run_closures:
            for closure in all_closures_combined:
                key = f"{closure.get('street_name', '')}_{closure.get('work_start_date', '')}"
                if key not in unique_all_closures:
                    unique_all_closures[key] = closure
            total_unique_closures = len(unique_all_closures)
    else:
        enhanced_routes = routes
        total_unique_closures = 0
        unique_all_closures = {}
    
    # 3. WEATHER DATA
    print("3️⃣  WEATHER DATA")
    print("-"*60)
    weather = get_weather.get_weather_conditions(start_lat, start_lng)
    weather_risk = get_weather.assess_weather_risk(weather)
    print(f"✓ Weather: {weather.get('description', 'unknown')}, {weather.get('temperature_f', 0):.0f}°F")
    print(f"✓ Visibility: {weather.get('visibility_meters', 0)}m")
    print(f"✓ Risk level: {weather_risk['risk_level']}")
    print()
    
    # SUMMARY
    print("="*60)
    print("SUMMARY")
    print("="*60)
    print(f"Routes generated: {len(routes)}")
    
    if run_safety or run_closures:
        analysis_parts = []
        if run_safety:
            analysis_parts.append("safety")
        if run_closures:
            analysis_parts.append("closures")
        print(f"Routes analyzed: {len(enhanced_routes)} ({' + '.join(analysis_parts)})")
        print(f"Sample strategy: 33%, 66%, 100% per route (skipping shared start)")
    
    print(f"Weather risk: {weather_risk['risk_level']}")
    
    if run_closures:
        print(f"Total unique closures across all routes: {total_unique_closures}")
    
    print()
    
    # Return all data
    return {
        "routes": enhanced_routes,
        "weather": weather,
        "weather_risk": weather_risk,
        "total_closures_all_routes": total_unique_closures if run_closures else None,
        "all_closures": list(unique_all_closures.values()) if run_closures else None
    }


if __name__ == "__main__":
    # Test location: Central Park
    test_lat = 40.7580
    test_lng = -73.9855
    target_distance = 5.0
    
    # You can now toggle what to test
    result = test_all_queries(
        test_lat, 
        test_lng, 
        target_distance,
        run_safety=True,      # Toggle this
        run_closures=True     # Toggle this
    )
    
    print("="*60)
    print("ALL QUERIES COMPLETE ✓")
    print("="*60)