import streamlit as st
import folium
from streamlit_folium import st_folium
import polyline

# Import the LangGraph workflow!
from lang import run_runner_vision

# Page config
st.set_page_config(
    page_title="RunnerVision AI",
    page_icon="🏃",
    layout="wide"
)

# Custom CSS
st.markdown("""
<style>
    .stAlert {
        padding: 0.5rem;
        margin-bottom: 1rem;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🏃 RunnerVision AI")
st.subheader("Multi-Agent System for Safety-Aware Running Routes")

# Sidebar
with st.sidebar:
    st.header("Route Parameters")
    
    # Location presets
    location_presets = {
        "Custom": None,
        "Central Park": (40.7580, -73.9855),
        "Brooklyn Bridge": (40.7061, -73.9969),
        "Prospect Park": (40.6602, -73.9690),
        "East River Park": (40.7156, -73.9764),
        "Washington Square Park": (40.7308, -73.9973),
    }
    
    selected_preset = st.selectbox(
        "📍 Choose a location:",
        list(location_presets.keys())
    )
    
    if selected_preset == "Custom":
        col1, col2 = st.columns(2)
        with col1:
            start_lat = st.number_input("Latitude", value=40.7580, format="%.4f")
        with col2:
            start_lng = st.number_input("Longitude", value=-73.9855, format="%.4f")
    else:
        start_lat, start_lng = location_presets[selected_preset]
        st.info(f"📍 {selected_preset}: ({start_lat:.4f}, {start_lng:.4f})")
    
    # Distance
    target_distance = st.slider(
        "🎯 Target Distance (km)", 
        min_value=1.0, 
        max_value=15.0, 
        value=5.0, 
        step=0.5
    )
    
    st.markdown("---")
    
    # Natural language query (for router agent)
    st.subheader("🗣️ Your Preferences")
    user_query = st.text_area(
        "What are you looking for?",
        placeholder="e.g., 'I need a safe 5k route, avoid construction'",
        height=100,
        help="The Router Agent will analyze your query to determine which analyses to run"
    )
    
    if not user_query:
        user_query = f"Give me a {target_distance}km route"
    
    st.markdown("---")
    
    # Show what the system will do
    st.subheader("🤖 Multi-Agent System")
    st.caption("""
    Our LangGraph workflow orchestrates:
    1. **Router Agent** - Analyzes your query
    2. **Route Generation Agent** - Finds routes
    3. **Safety Analysis Agent** - Checks crashes
    4. **Weather Agent** - Checks conditions
    5. **Closure Agent** - Checks construction
    6. **Synthesis Agent** - LLM recommendation
    """)
    
    # Generate button
    generate_button = st.button("🚀 Run Multi-Agent Analysis", type="primary", use_container_width=True)
    
    if 'results' in st.session_state:
        if st.button("🗑️ Clear Results", use_container_width=True):
            del st.session_state.results
            st.rerun()

# Main content
if generate_button:
    if 'results' in st.session_state:
        del st.session_state.results
    
    with st.spinner("🤖 Running multi-agent workflow..."):
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        try:
            status_text.text("🔍 Starting LangGraph workflow...")
            progress_bar.progress(10)
            
            # Call the LangGraph workflow!
            result = run_runner_vision(
                query=user_query,
                start_lat=start_lat,
                start_lng=start_lng,
                target_distance_km=target_distance
            )
            
            progress_bar.progress(100)
            status_text.text("✅ Multi-agent analysis complete!")
            
            # Store in session state
            st.session_state.results = result
            
            import time
            time.sleep(1)
            progress_bar.empty()
            status_text.empty()
            
        except Exception as e:
            st.error(f"❌ Error during analysis: {str(e)}")
            import traceback
            with st.expander("🐛 Debug Info"):
                st.code(traceback.format_exc())

# display
if 'results' in st.session_state:
    result = st.session_state.results
    
    # ALWAYS get all routes from route generation
    all_routes = result.get('routes', [])
    
    # Get safety analysis if it ran
    safety_analysis = result.get('safety_analysis', [])
    
    # Merge: Use routes from all_routes, add safety data if available
    routes_to_display = []
    for i, route in enumerate(all_routes[:3]):  # Top 3 by accuracy
        display_route = route.copy()
        
        # If this route has safety analysis, add it
        for analyzed in safety_analysis:
            if analyzed.get('direction') == route.get('direction'):
                display_route['safety_analysis'] = analyzed.get('safety_analysis')
                break
        
        routes_to_display.append(display_route)
    
    routes = routes_to_display
    
    if routes:
        st.success(f"✅ Multi-agent workflow complete! Generated {len(all_routes)} routes, displaying top {len(routes)}")
    else:
        st.error("No routes found")
        st.stop()
    
    # Show LLM Recommendation First (most important!)
    st.header("🤖 AI Recommendation")
    
    recommendation = result.get('recommendation', '')
    if recommendation:
        st.markdown(f"""
        <div style="background-color: #f0f8ff; padding: 1.5rem; border-radius: 0.5rem; border-left: 4px solid #1e90ff;">
        {recommendation}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.warning("No LLM recommendation generated")
    
    st.markdown("---")
    
    # Create two columns
    col_left, col_right = st.columns([2, 1])
    
    with col_left:
        st.header("📍 Route Map")
        
        # Create map
        m = folium.Map(
            location=[result.get('start_lat', start_lat), result.get('start_lng', start_lng)],
            zoom_start=14,
            tiles="OpenStreetMap"
        )
        
        # Start marker
        folium.Marker(
            [result.get('start_lat', start_lat), result.get('start_lng', start_lng)],
            popup="<b>🏁 Start Location</b>",
            icon=folium.Icon(color="green", icon="play", prefix='fa')
        ).add_to(m)
        
        # Plot routes
        route_colors = ['blue', 'red', 'purple', 'orange', 'darkblue']
        
        for i, route in enumerate(routes[:3]):  # Top 3
            if 'polyline' in route and route['polyline']:
                coords = polyline.decode(route['polyline'])
                
                # Color by safety
                color = route_colors[i % len(route_colors)]
                if 'safety_analysis' in route:
                    safety_score = route['safety_analysis'].get('overall_safety_score', 0)
                    if safety_score >= 85:
                        color = 'green'
                    elif safety_score >= 75:
                        color = 'orange'
                    else:
                        color = 'red'
                
            if coords:
                endpoint_lat = coords[-1][0]
                endpoint_lng = coords[-1][1]
                
                # Enhanced popup with endpoint info
                popup_text = f"""
                <b>{route['direction']}</b><br>
                Accuracy: {route['accuracy']:.1f}%<br>
                """
                
                if 'safety_analysis' in route:
                    popup_text += f"Safety: {route['safety_analysis']['overall_safety_score']:.1f}/100<br>"
                
                # Add endpoint coordinates
                popup_text += f"<hr style='margin: 5px 0;'>"
                popup_text += f"<b>🏁 Turnaround Point:</b><br>"
                popup_text += f"({endpoint_lat:.4f}, {endpoint_lng:.4f})<br>"
                popup_text += f"<small>Copy coordinates to navigate</small>"
                
                # Route line
                folium.PolyLine(
                    coords,
                    color=color,
                    weight=6,
                    opacity=0.8,
                    popup=folium.Popup(popup_text, max_width=300)
                ).add_to(m)
            
            # Enhanced endpoint marker with better popup
            endpoint_popup = f"""
            <div style='min-width: 200px;'>
                <h4 style='margin: 0 0 10px 0;'>🏁 {route['direction']} Turnaround</h4>
                <p style='margin: 5px 0;'><b>Coordinates:</b></p>
                <p style='margin: 0; font-family: monospace;'>{endpoint_lat:.6f}, {endpoint_lng:.6f}</p>
                <hr style='margin: 10px 0;'>
                <p style='margin: 5px 0;'><b>Route:</b> {route['direction']}</p>
                <p style='margin: 5px 0;'><b>Distance:</b> {route['distance']['total_distance']:.2f}km</p>
                <p style='margin: 5px 0;'><small>Click to copy coordinates</small></p>
            </div>
            """
            
            folium.Marker(
                [endpoint_lat, endpoint_lng],
                popup=folium.Popup(endpoint_popup, max_width=300),
                tooltip=f"🏁 {route['direction']} Turnaround",  # Shows on hover!
                icon=folium.Icon(color=color, icon="flag", prefix='fa')
            ).add_to(m)
        
        # Legend
        legend_html = '''
        <div style="position: fixed; 
                    bottom: 50px; left: 50px; width: 200px;
                    background-color: white; z-index:9999; font-size:14px;
                    border:2px solid grey; border-radius: 5px; padding: 10px">
        <p style="margin:0; font-weight:bold;">Route Safety</p>
        <p style="margin:5px 0;"><span style="color:green;">●</span> Safe (≥85)</p>
        <p style="margin:5px 0;"><span style="color:orange;">●</span> Moderate (75-85)</p>
        <p style="margin:5px 0;"><span style="color:red;">●</span> Dangerous (<75)</p>
        <p style="margin:5px 0;"><span style="color:darkred;">🔴</span> Dangerous Segment</p>
        </div>
        '''
        m.get_root().html.add_child(folium.Element(legend_html))
        
        st_folium(m, width=700, height=500)
    
    with col_right:
        st.header("📊 Analysis Summary")
        
        # Agent execution summary
        with st.expander("🤖 Agent Workflow", expanded=True):
            st.write("**Agents Executed:**")
            if result.get('needs_safety'):
                st.write("✅ Safety Analysis Agent")
            if result.get('needs_weather'):
                st.write("✅ Weather Agent")
            if result.get('needs_closures'):
                st.write("✅ Closure Agent")
            st.write("✅ Synthesis Agent (LLM)")
        
        # Weather
        if result.get('weather_data'):
            with st.expander("🌤️ Weather", expanded=True):
                weather = result['weather_data']['conditions']
                risk = result['weather_data']['risk_assessment']
                
                risk_emoji = {'low': '🟢', 'moderate': '🟡', 'high': '🔴'}.get(risk['risk_level'], '⚪')
                
                st.write(f"**Conditions:** {weather.get('description', 'N/A')}")
                st.write(f"**Temperature:** {weather.get('temperature_f', 0):.0f}°F")
                st.write(f"**Risk:** {risk_emoji} {risk['risk_level'].upper()}")
        
        # Closures
        if result.get('closures_data'):
            with st.expander("🚧 Closures", expanded=False):
                closures = result['closures_data']['closures']
                impact = result['closures_data']['impact_assessment']
                
                st.write(f"**Total:** {closures.get('total_closures', 0)}")
                st.write(f"**Impact:** {impact['impact'].upper()}")
        
        # Route comparison
        st.subheader("🏆 Top Routes")
        for i, route in enumerate(routes[:3], 1):
            with st.container():
                st.write(f"**{i}. {route['direction']}**")
                st.write(f"   Accuracy: {route['accuracy']:.1f}%")
                if 'safety_analysis' in route:
                    safety = route['safety_analysis']['overall_safety_score']
                    st.write(f"   Safety: {safety:.1f}/100")
    
    # Detailed analysis
    st.markdown("---")
    st.header("🔍 Detailed Route Analysis")
    
    for i, route in enumerate(routes[:3]):
        with st.expander(f"Route {i+1}: {route['direction']} - {route['accuracy']:.1f}%", expanded=(i==0)):
            cols = st.columns(3)
            
            with cols[0]:
                st.metric("Accuracy", f"{route['accuracy']:.1f}%")
            
            if 'safety_analysis' in route:
                with cols[1]:
                    st.metric("Safety", f"{route['safety_analysis']['overall_safety_score']:.1f}/100")
                with cols[2]:
                    st.metric("Dangers", len(route['safety_analysis']['dangerous_segments']))
                
                if route['safety_analysis']['dangerous_segments']:
                    st.write("**⚠️ Dangerous Segments:**")
                    for j, seg in enumerate(route['safety_analysis']['dangerous_segments'], 1):
                        st.write(f"{j}. {seg['route_progress']:.0f}% along route - Safety: {seg['safety_score']:.1f}/100")
    
    # Methodology
    with st.expander("🔬 Multi-Agent System Architecture", expanded=False):
        st.markdown("""
        ### LangGraph Workflow
        
        Our system uses a **state-based multi-agent architecture** built with LangGraph:
        
        1. **Router Agent** analyzes your natural language query to determine which agents to invoke
        2. **Route Generation Agent** interfaces with Google Maps API
        3. **Safety Analysis Agent** queries NYC crash database at 3 sample points per route
        4. **Weather Agent** checks OpenWeatherMap for current conditions
        5. **Closure Agent** queries NYC DOT for construction zones
        6. **Synthesis Agent** uses GPT-4o-mini to generate natural language recommendations
        
        **Conditional Execution:** Router agent intelligently skips unnecessary agents based on your query.
        
        **State Management:** Shared state object flows through the graph, updated by each agent.
        """)

else:
    # Landing page
    st.info("👈 Configure your route in the sidebar and run the multi-agent analysis!")
    
    st.markdown("""
    ## 🤖 Multi-Agent LLM System
    
    RunnerVision uses **LangGraph** to orchestrate specialized agents that work together 
    to provide safety-aware route recommendations.
    
    ### How It Works
    
    **1. Router Agent** 🧭
    - Analyzes your natural language query
    - Determines which analyses are needed
    - Optimizes agent execution
    
    **2. Route Generation Agent** 🗺️
    - Generates 8 directional options
    - Filters invalid/water locations
    - Selects top routes by accuracy
    
    **3. Safety Analysis Agent** 🔍
    - Samples 3 points per route (33%, 66%, 100%)
    - Queries 60 days of crash data
    - Compares to NYC safety percentiles
    
    **4. Weather Agent** 🌤️
    - Checks real-time conditions
    - Assesses visibility and precipitation
    - Provides risk classification
    
    **5. Closure Agent** 🚧
    - Checks construction along full route
    - Identifies navigation obstacles
    - Assesses impact level
    
    **6. Synthesis Agent** 💬
    - **LLM-powered** natural language recommendations
    - Weighs competing factors (safety vs accuracy)
    - Provides actionable advice
    
    ### Example Query
    
    **Input:** "I need a safe 5k route, avoid construction"
    
    **Router Decision:**
    - ✅ Run safety analysis (keyword: "safe")
    - ✅ Run closure check (keyword: "construction")
    - ✅ Run weather (always)
    
    **LLM Output:** Natural language recommendation explaining which route to choose and why.
    """)

# Footer
st.markdown("---")
st.caption("🎓 RunnerVision AI - Multi-Agent System with LangGraph")
st.caption("👥 Henry Yuan, Raymond Zhang, Lindsey Pietrewicz | NYU DS-UA 301")