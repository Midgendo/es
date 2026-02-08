import json
from datetime import datetime
from sprites import Agent, Exit
from config import AgentType


def load_to_scene(scene_data, filename, sim_config, floorplan, log):
    with open(filename, 'r') as f:
        data = json.load(f)
    
    scene_data.clear()
    
    ppm = sim_config.pixels_per_meter
    for agent_data in data.get("agents", []):
        pos = agent_data["position"]
        agent_type = AgentType(
            speed_mps=agent_data.get("speed_mps", sim_config.max_speed),
            radius_m=agent_data.get("radius_m", sim_config.agent_size / ppm),
            colour=tuple(agent_data.get("colour", [255, 255, 0])),
            neighbor_dist_m=sim_config.neighbor_dist,
            max_neighbors=sim_config.max_neighbors,
            time_horizon=sim_config.time_horizon,
            time_horizon_obst=sim_config.time_horizon_obst,
            name=agent_data.get("agent_type", "Default")
        )
        agent = Agent(pos[0], pos[1], agent_type, floorplan.offset_x, floorplan.offset_y, ppm)
        scene_data.agents.append(agent)
    
    for exit_data in data.get("exits", []):
        pos = exit_data["position"]
        exit_obj = Exit(
            pos[0], pos[1],
            exit_data["number"],
            radius=exit_data.get("radius", sim_config.agent_size),
            colour=tuple(exit_data.get("colour", [0, 200, 0])),
            offset_x=floorplan.offset_x,
            offset_y=floorplan.offset_y
        )
        scene_data.exits.append(exit_obj)
    
    log(f"Loaded from {filename}")


def save_from_scene(scene_data, filename, pixels_per_meter, floorplan_filename, log):
    data = {
        "timestamp": datetime.now().isoformat(),
        "pixels_per_meter": pixels_per_meter,
        "floorplan_filename": floorplan_filename,
        "agents": [],
        "exits": []
    }
    
    for agent in scene_data.agents:
        data["agents"].append({
            "agent_type": agent.agent_type.name,
            "position": list(agent.rect.center),
            "sim_position": list(agent.sim_pos),
            "speed_mps": agent.agent_type.speed_mps,
            "radius_m": agent.agent_type.radius_m,
            "colour": agent.colour
        })
    
    for exit_obj in scene_data.exits:
        data["exits"].append({
            "position": list(exit_obj.rect.center),
            "number": exit_obj.number,
            "radius": exit_obj.radius,
            "colour": exit_obj.colour
        })
    
    with open(filename, 'w') as f:
        json.dump(data, f, indent=2)
    log(f"Saved to {filename}")
