import json
import os
from datetime import datetime

from sprites import Agent, Exit
from config import AgentType


def load_to_scene(scene_data, filename, sim_config, log):
    if not os.path.exists(filename):
        log("No state saved", level="E")
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
            type_map[type_name] = build_agent_type(entry, sim_config)
        agent_type = type_map[type_name]

        pos = entry["position"]
        agent = Agent(
            pos[0], pos[1], agent_type, ppm,
            radius=entry.get("radius"),
            speed=entry.get("speed"),
        )
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


def build_agent_type(entry, sim_config):
    """Reconstruct an AgentType from a saved JSON entry."""
    return AgentType(
        name=entry.get("agent_type", "Default"),
        colour=tuple(entry.get("colour", [255, 255, 0])),
        sim_config=sim_config,
        speed_mps_range=tuple(entry["speed_mps_range"]) if "speed_mps_range" in entry else (3.7, 4.5),
        radius_m_range=tuple(entry["radius_m_range"]) if "radius_m_range" in entry else (0.175, 0.225),
    )


def save_from_scene(scene_data, filename, pixels_per_meter, floorplan_filename, log):
    data = {
        "timestamp":          datetime.now().isoformat(),
        "pixels_per_meter":   pixels_per_meter,
        "floorplan_filename": floorplan_filename,
        "agents": [
            {
                "agent_type":      a.agent_type.name,
                "position":        list(a.rect.center),
                "speed":           a.speed,
                "radius":          a.radius,
                "speed_mps_range": list(a.agent_type.speed_mps_range),
                "radius_m_range":  list(a.agent_type.radius_m_range),
                "colour":          list(a.colour),
            }
            for a in scene_data.agents
        ],
        "exits": [
            {
                "position": list(e.rect.center),
                "number":   e.number,
                "radius":   e.radius,
                "colour":   list(e.colour),
            }
            for e in scene_data.exits
        ],
    }

    with open(filename, "w") as f:
        json.dump(data, f, indent=2)

    log(f"Saved to {filename}")
