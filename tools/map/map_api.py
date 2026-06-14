"""高德地图 API 响应解析工具（内部依赖，不是 Tool）。"""


def parse_poi_response(data: dict) -> dict:
    """解析 POI 搜索响应（fuzzy_search / nearby_search 共用）。"""
    result = {
        "status": data.get("status"),
        "info": data.get("info"),
        "count": data.get("count"),
        "pois": [],
    }

    for poi in data.get("pois", []):
        result["pois"].append(
            {
                "id": poi.get("id"),
                "name": poi.get("name"),
                "location": poi.get("location"),
                "address": poi.get("address"),
                "cityname": poi.get("cityname"),
                "adname": poi.get("adname"),
                "type": poi.get("type"),
            }
        )

    return result


def parse_transit_response(json_data: dict) -> dict:
    """解析高德公交路线规划 v3 API 响应。"""
    result = {
        "status": json_data.get("status"),
        "count": json_data.get("count"),
        "routes": [],
    }

    route = json_data.get("route", {})
    transits = route.get("transits", [])

    for t_key, transit in enumerate(transits):
        walking_dist = transit.get("walking_distance", 0)
        if isinstance(walking_dist, list):
            walking_dist = walking_dist[0] if walking_dist else 0
        elif isinstance(walking_dist, str) and not walking_dist.isdigit():
            walking_dist = 0

        route_info = {
            "cost": float(transit.get("cost", 0)),
            "duration": int(transit.get("duration", 0)),
            "walking_distance": int(walking_dist),
            "segments": [],
        }

        for segment in transit.get("segments", []):
            segment_info = {"walking": None, "bus": None}

            walking_info = segment.get("walking")
            if walking_info and walking_info.get("steps"):
                walk_data = {"distance": int(walking_info.get("distance", 0)), "steps": []}
                for step in walking_info.get("steps", []):
                    walk_data["steps"].append(
                        {
                            "instruction": step.get("instruction", ""),
                            "assistant_action": step.get("assistant_action", ""),
                            "road": step.get("road", ""),
                            "distance": int(step.get("distance", 0)),
                        }
                    )
                segment_info["walking"] = walk_data

            bus_info = segment.get("bus")
            if bus_info and bus_info.get("buslines"):
                bus_data = {"lines": []}
                for busline in bus_info.get("buslines", []):
                    bus_data["lines"].append(
                        {
                            "type": busline.get("type", ""),
                            "name": busline.get("name", ""),
                            "departure_stop": busline.get("departure_stop", {}).get("name", ""),
                            "arrival_stop": busline.get("arrival_stop", {}).get("name", ""),
                            "via_num": int(busline.get("via_num", 0)),
                            "distance": int(busline.get("distance", 0)),
                            "duration": int(busline.get("duration", 0)),
                        }
                    )
                segment_info["bus"] = bus_data

            route_info["segments"].append(segment_info)

        result["routes"].append(route_info)

    return result


def parse_cycling_response(json_data: dict) -> dict:
    """解析高德骑行路线规划 v4 API 响应。"""
    result = {
        "status": json_data.get("errcode", -1),
        "message": json_data.get("errmsg", ""),
        "origin": None,
        "destination": None,
        "paths": [],
    }

    data = json_data.get("data", {})
    if not data:
        return result

    result["origin"] = data.get("origin")
    result["destination"] = data.get("destination")

    for path in data.get("paths", []):
        path_info = {
            "distance": int(path.get("distance", 0)),
            "duration": int(path.get("duration", 0)),
            "steps": [],
        }

        for step in path.get("steps", []):
            path_info["steps"].append(
                {
                    "instruction": step.get("instruction", ""),
                    "orientation": step.get("orientation", ""),
                    "road": step.get("road", ""),
                    "distance": int(step.get("distance", 0)),
                    "duration": int(step.get("duration", 0)),
                    "action": step.get("action", ""),
                    "assistant_action": step.get("assistant_action", ""),
                    "polyline": step.get("polyline", ""),
                }
            )

        result["paths"].append(path_info)

    return result
