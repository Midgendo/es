import json
from datetime import datetime

DATA = {}

def load(all_agents, all_exits, filename, PIXELS_PER_METER, AGENT_SIZE, maxSpeed, PIXELS_PER_METER_SCALE, SIM_OFFSET_X, SIM_OFFSET_Y, Agent, Exit, log, memory=False):
    try:
        if not memory:
            with open(filename, 'r') as f:
                data = json.load(f)
        else:
            data = DATA
        
        all_agents.empty()
        all_exits.empty()
        
        if data.get("pixels_per_meter") != PIXELS_PER_METER:
            log("Incompatible scale in JSON file.", 'E')
            return False
        
        for agent_data in data.get("agents", []):
            pos = agent_data["position"]
            agent = Agent(
                pos[0], pos[1],
                speed=agent_data.get("speed", maxSpeed * PIXELS_PER_METER_SCALE),
                radius=agent_data.get("radius", AGENT_SIZE),
                colour=tuple(agent_data.get("colour", [255, 255, 0])),
                offset_x=SIM_OFFSET_X,
                offset_y=SIM_OFFSET_Y,
                agent_type=agent_data.get("agent_type")
            )
            all_agents.add(agent)
        
        exits_data = data.get("exits", [])
        for exit_data in exits_data:
            pos = exit_data["position"]
            exit = Exit(
                pos[0], pos[1],
                exit_data["number"],
                radius=exit_data.get("radius", AGENT_SIZE),
                colour=tuple(exit_data.get("colour", [0, 200, 0])),
                offset_x=SIM_OFFSET_X,
                offset_y=SIM_OFFSET_Y
            )
            all_exits.add(exit)
        
        if not memory:
            log(f"Loaded from {filename}")
        return len(data.get('agents', [])), True
        
    except FileNotFoundError:
        log(f"{filename} not found.", 'E')
        return 0, False
    except Exception as e:
        log(f"Error:{e}", 'E')
        return 0, False


def save(all_agents, all_exits, filename, PIXELS_PER_METER, FLOORPLAN_FILENAME, log, memory=False):
    data = {
        "timestamp": datetime.now().isoformat(),
        "pixels_per_meter": PIXELS_PER_METER,
        "floorplan_filename": FLOORPLAN_FILENAME,
        "agents": [],
        "exits": []
    }
    
    for agent in all_agents:
        agent_data = {
            "agent_type": agent.agent_type.name,
            "position": list(agent.rect.center),
            "sim_position": list(agent.sim_pos),
            "speed": agent.speed,
            "radius": agent.radius,
            "colour": agent.colour
        }
        data["agents"].append(agent_data)
    
    for exit in all_exits:
        exit_data = {
            "position": list(exit.rect.center),
            "number": exit.number,
            "radius": exit.radius,
            "colour": exit.colour
        }
        data["exits"].append(exit_data)
    
    if not memory:
        try:
            with open(filename, 'w') as f:
                json.dump(data, f, indent=2)
            log(f"Saved to {filename}")
        except Exception as e:
            log(f"Error: {e}", 'E')
    else:
        global DATA
        DATA = data