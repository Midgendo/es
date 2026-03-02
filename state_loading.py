"""Serialisation helpers for saving/loading scene state to JSON."""

import json
import os
from datetime import datetime

from sprites import Agent, Exit
from config import AgentType


def load_to_scene(scene_data, filename, sim_config, log):
    if not os.path.exists(filename):
        log(f"No state saved", level="E")
        return

    with open(filename, "r") as f:
        data = json.load(f)

    scene_data.clear()
    ppm = sim_config.pixels_per_meter

    # Deduplicate AgentType instances by name
    type_map = {}

    for entry in data.get("agents", []):
        type_name = entry.get("agent_type", "Default")
        if type_name not in type_map:
            type_map[type_name] = agent_type_from_dict(entry, sim_config, ppm)
        agent_type = type_map[type_name]

        pos = entry["position"]
        agent = Agent(pos[0], pos[1], agent_type, ppm)
        scene_data.agents.append(agent)

    for entry in data.get("exits", []):
        pos = entry["position"]
        exit_obj = Exit(
            pos[0], pos[1],
            entry["number"],
            radius=entry.get("radius", sim_config.agent_size),
            colour=tuple(entry.get("colour", [0, 200, 0])),
        )
        scene_data.exits.append(exit_obj)

    log(f"Loaded from {filename}")


def agent_type_from_dict(entry, sim_config, ppm):
    agent_type = AgentType(
        name=entry.get("agent_type", "Default"),
        speed_mps=entry.get("speed_mps", sim_config.max_speed),
        radius_m=entry.get("radius_m", sim_config.agent_size / ppm),
        colour=tuple(entry.get("colour", [255, 255, 0])),
        neighbor_dist_m=sim_config.neighbor_dist,
        max_neighbors=sim_config.max_neighbors,
        time_horizon=sim_config.time_horizon,
        time_horizon_obst=sim_config.time_horizon_obst,
    )

    if "speed_mps_range" in entry:
        agent_type.speed_mps_range = tuple(entry["speed_mps_range"])
    if "radius_m_range" in entry:
        agent_type.radius_m_range = tuple(entry["radius_m_range"])

    return agent_type


def save_from_scene(scene_data, filename, pixels_per_meter, floorplan_filename, log):
    data = {
        "timestamp":          datetime.now().isoformat(),
        "pixels_per_meter":   pixels_per_meter,
        "floorplan_filename": floorplan_filename,
        "agents": [
            {
                "agent_type":      agent.agent_type.name,
                "position":        list(agent.rect.center),
                "speed_mps":       agent.agent_type.speed_mps,
                "radius_m":        agent.agent_type.radius_m,
                "speed_mps_range": list(agent.agent_type.speed_mps_range),
                "radius_m_range":  list(agent.agent_type.radius_m_range),
                "colour":          agent.colour,
            }
            for agent in scene_data.agents
        ],
        "exits": [
            {
                "position":     list(exit_obj.rect.center),
                "number":       exit_obj.number,
                "radius":       exit_obj.radius,
                "colour":       exit_obj.colour,
            }
            for exit_obj in scene_data.exits
        ],
    }

    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

    log(f"Saved to {filename}")
