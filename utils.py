import math


def euc_distance(lat1: float, lng1: float, lat2: float, lng2: float):  # utils?
    R = 6371
    lat1_rad = math.radians(lat1)
    lng1_rad = math.radians(lng1)
    lat2_rad = math.radians(lat2)
    lng2_rad = math.radians(lng2)

    dlat = lat2_rad - lat1_rad
    dlng = lng2_rad - lng1_rad

    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlng / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c

def sample_route_strategically(route_points, num_samples=3, skip_start=True):
    """
    Sample evenly-spaced points along a route
    
    Args:
        route_points: List of (lat, lng) tuples from polyline.decode()
        num_samples: Number of points to sample (default 3)
        skip_start: If True, skip the start point (0%) since all routes share it
    
    Returns:
        List of sample point dicts with lat, lng, route_index, route_progress
    """
    if not route_points:
        return []
    
    total_points = len(route_points)
    
    if total_points <= num_samples:
        # Return all points if route is short
        return [
            {
                'lat': pt[0] if isinstance(pt, tuple) else pt['lat'],
                'lng': pt[1] if isinstance(pt, tuple) else pt['lng'],
                'route_index': i,
                'route_progress': round((i / max(total_points - 1, 1)) * 100, 1)
            }
            for i, pt in enumerate(route_points)
        ]
    
    indices = []
    
    if skip_start:
        # Sample at 33%, 66%, 100%
        indices = [
            int(total_points * 0.33),  # 33% along route
            int(total_points * 0.66),  # 66% along route
            total_points - 1           # 100% (endpoint)
        ]
    else:
        # Traditional: 0%, 50%, 100%
        indices = [
            0,                          # Start
            total_points // 2,          # Middle
            total_points - 1            # End
        ]
    
    sample_points = []
    for idx in indices:
        point = route_points[idx]
        
        # Handle both tuple and dict formats
        if isinstance(point, dict):
            lat, lng = point['lat'], point['lng']
        else:
            lat, lng = point[0], point[1]
        
        sample_points.append({
            'lat': lat,
            'lng': lng,
            'route_index': idx,
            'route_progress': round((idx / (total_points - 1)) * 100, 1)
        })
    
    return sample_points