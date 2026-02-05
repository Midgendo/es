import heapq
import pygame
import pyrvo

from config import RoadmapVertex
from sprites import Agent, Exit, has_wall_collision, has_agent_collision


class Simulation:
    def __init__(self, display_config, sim_config):
        self.display_config = display_config
        self.sim_config = sim_config
        
        self.agents = pygame.sprite.Group()
        self.exits = pygame.sprite.Group()
        self.roadmap = []
        self.exit_indices = []
        self.grid_nodes = []
        
        self.rvo_sim = None
        self.time = 0.0
        self.simulation_time = 0.0
        self.evacuated_count = 0
        self.paused = False
        
        self.floorplan = None

        self.agent_types = []
        
    def initialize_rvo(self):
        cfg = self.sim_config
        self.rvo_sim = pyrvo.RVOSimulator(
            1.0 / self.display_config.fps,
            cfg.neighbor_dist * cfg.pixels_per_meter,
            cfg.max_neighbors,
            cfg.time_horizon,
            cfg.time_horizon_obst,
            cfg.agent_radius_meters * cfg.pixels_per_meter,
            cfg.max_speed * cfg.pixels_per_meter,
            pyrvo.Vector2(0.0, 0.0)
        )
        
    def set_floorplan(self, floorplan):
        self.floorplan = floorplan
        self.generate_grid_nodes()
        
    def generate_grid_nodes(self):
        spacing = self.sim_config.grid_spacing_meters * self.sim_config.pixels_per_meter
        agent_radius = self.sim_config.pixels_per_meter * 0.4
        
        self.grid_nodes = []
        for y in range(int(spacing), int(self.floorplan.height), int(spacing)):
            for x in range(int(spacing), int(self.floorplan.width), int(spacing)):
                if not has_wall_collision(x, y, agent_radius, self.floorplan.wall_polygons):
                    self.grid_nodes.append((float(x), float(y)))
                    
    def reset(self, clear_agents=True):
        if clear_agents:
            self.agents.empty()
            self.exits.empty()
        self.roadmap = []
        self.exit_indices = []
        self.time = 0.0
        self.evacuated_count = 0
        self.paused = False

    def reset_run_state(self):
        self.time = 0.0
        self.simulation_time = 0.0
        self.evacuated_count = 0
        self.paused = False
        
    def add_agent(self, screen_x, screen_y, agent_type):
        sim_x, sim_y = self.floorplan.screen_to_sim(screen_x, screen_y)
        agent_size = int(agent_type.radius)
        
        if has_wall_collision(sim_x, sim_y, agent_size, self.floorplan.wall_polygons):
            return False
        if has_agent_collision((sim_x, sim_y), agent_size, self.agents):
            return False
            
        agent = Agent(
            screen_x, screen_y,
            agent_type=agent_type,
            offset_x=self.floorplan.offset_x,
            offset_y=self.floorplan.offset_y
        )
        self.agents.add(agent)
        return True
        
    def remove_agent_at(self, screen_x, screen_y):
        for agent in self.agents:
            if agent.rect.collidepoint((screen_x, screen_y)):
                self.agents.remove(agent)
                return True
        return False
    
    def remove_agents(self, agent_type):
        to_remove = [agent for agent in self.agents if agent.agent_type == agent_type]
        for agent in to_remove:
            self.agents.remove(agent)
        return len(to_remove)

    def update_agents_of_type(self, agent_type, radius=None, speed=None):
        if radius is not None:
            agent_type.radius = radius
        if speed is not None:
            agent_type.speed = speed
        for agent in self.agents:
            if agent.agent_type != agent_type:
                continue
            if radius is not None:
                agent.radius = int(radius)
                agent.rebuild_image()
            if speed is not None:
                agent.speed = speed
            if agent.rvo_id is not None and self.rvo_sim is not None:
                if radius is not None:
                    if hasattr(self.rvo_sim, "set_agent_radius"):
                        self.rvo_sim.set_agent_radius(agent.rvo_id, agent.radius)
                    elif hasattr(self.rvo_sim, "setAgentRadius"):
                        self.rvo_sim.setAgentRadius(agent.rvo_id, agent.radius)
                if speed is not None:
                    if hasattr(self.rvo_sim, "set_agent_max_speed"):
                        self.rvo_sim.set_agent_max_speed(agent.rvo_id, agent.speed)
                    elif hasattr(self.rvo_sim, "setAgentMaxSpeed"):
                        self.rvo_sim.setAgentMaxSpeed(agent.rvo_id, agent.speed)
        
    def add_exit(self, screen_x, screen_y):
        sim_x, sim_y = self.floorplan.screen_to_sim(screen_x, screen_y)
        agent_size = self.sim_config.agent_size
        
        if has_wall_collision(sim_x, sim_y, agent_size, self.floorplan.wall_polygons):
            return False
            
        exit_number = len(self.exits) + 1
        exit_obj = Exit(
            screen_x, screen_y,
            exit_number,
            radius=agent_size * 1.2,
            colour=(0, 200, 0),
            offset_x=self.floorplan.offset_x,
            offset_y=self.floorplan.offset_y
        )
        self.exits.add(exit_obj)
        self.rebuild_roadmap()
        return True
        
    def remove_exit_at(self, screen_x, screen_y):
        for exit_obj in self.exits:
            if exit_obj.rect.collidepoint((screen_x, screen_y)):
                self.exits.remove(exit_obj)
                for idx, e in enumerate(self.exits, 1):
                    e.set_number(idx)
                self.rebuild_roadmap()
                return True
        return False
        
    def rebuild_roadmap(self):
        if len(self.exits) > 0 and len(self.grid_nodes) > 0:
            self.roadmap, self.exit_indices = self._build_roadmap()
        else:
            self.roadmap = []
            self.exit_indices = []
            
    def _build_roadmap(self):
        roadmap = []
        exit_indices = []
        agent_radius = self.sim_config.agent_size
        
        for exit_obj in self.exits:
            exit_indices.append(len(roadmap))
            roadmap.append(RoadmapVertex(position=exit_obj.sim_pos))
        
        for node_pos in self.grid_nodes:
            roadmap.append(RoadmapVertex(position=node_pos))
        
        max_neighbor_dist = self.sim_config.grid_spacing_meters * self.sim_config.pixels_per_meter * 2.5
        
        for i, node in enumerate(roadmap):
            for j, other_node in enumerate(roadmap):
                if i != j:
                    dx = other_node.position[0] - node.position[0]
                    dy = other_node.position[1] - node.position[1]
                    dist = (dx ** 2 + dy ** 2) ** 0.5
                    
                    if dist <= max_neighbor_dist:
                        if self.rvo_sim.query_visibility(node.position, other_node.position, agent_radius):
                            node.neighbors.append(j)
        
        self._compute_distances_to_exits(roadmap, exit_indices)
        return roadmap, exit_indices
        
    def _compute_distances_to_exits(self, roadmap, exit_indices):
        dist = [float("inf")] * len(roadmap)
        pq = []
        
        for exit_idx in exit_indices:
            dist[exit_idx] = 0.0
            heapq.heappush(pq, (0.0, exit_idx))
        
        while pq:
            d_u, u = heapq.heappop(pq)
            if d_u != dist[u]:
                continue
            for v in roadmap[u].neighbors:
                dx = roadmap[v].position[0] - roadmap[u].position[0]
                dy = roadmap[v].position[1] - roadmap[u].position[1]
                w = (dx ** 2 + dy ** 2) ** 0.5
                if dist[v] > d_u + w:
                    dist[v] = d_u + w
                    heapq.heappush(pq, (dist[v], v))
        
        for i, vertex in enumerate(roadmap):
            vertex.dist_to_exit = dist[i]
            
    def start(self):
        self.time = 0.0
        self.simulation_time = 0.0
        self.evacuated_count = 0
        self.paused = False
        
        self.rebuild_roadmap()
        
        for agent in self.agents:
            if agent.rvo_id is None:
                agent.register_with_rvo(self.rvo_sim, self.sim_config)
                
    def update(self, dt, mouse_override=None):
        if self.paused:
            return False
            
        self.time += dt
        agents_to_remove = []
        
        if self.roadmap:
            self._set_preferred_velocities_roadmap()
            
            for agent in self.agents:
                for exit_idx in self.exit_indices:
                    exit_pos = self.roadmap[exit_idx].position
                    dx = agent.sim_pos[0] - exit_pos[0]
                    dy = agent.sim_pos[1] - exit_pos[1]
                    if (dx ** 2 + dy ** 2) < agent.reached_threshold ** 2:
                        if agent not in agents_to_remove:
                            agents_to_remove.append(agent)
                        break
        
        if mouse_override:
            self._apply_mouse_override(mouse_override)
        
        self.rvo_sim.do_step()
        
        self.simulation_time = self.rvo_sim.get_global_time()
        
        for agent in self.agents:
            if agent not in agents_to_remove:
                agent.update_position(self.rvo_sim)
        
        for agent in agents_to_remove:
            self.agents.remove(agent)
            self.evacuated_count += 1
        
        return len(self.agents) == 0
        
    def _set_preferred_velocities_roadmap(self):
        for agent in self.agents:
            if agent.rvo_id is None:
                continue
            
            pos = agent.sim_pos
            min_dist = float("inf")
            best_vertex = -1
            
            for j, vertex in enumerate(self.roadmap):
                dx = vertex.position[0] - pos[0]
                dy = vertex.position[1] - pos[1]
                dist_to_vertex = (dx ** 2 + dy ** 2) ** 0.5
                total_dist = dist_to_vertex + vertex.dist_to_exit
                
                if total_dist < min_dist:
                    if self.rvo_sim.query_visibility(pos, vertex.position, agent.radius):
                        min_dist = total_dist
                        best_vertex = j
            
            if best_vertex >= 0:
                target = self.roadmap[best_vertex].position
                dx = target[0] - pos[0]
                dy = target[1] - pos[1]
                dist = (dx ** 2 + dy ** 2) ** 0.5
                
                if dist > 1.0:
                    pref_vel = (dx / dist * agent.speed, dy / dist * agent.speed)
                else:
                    pref_vel = (0.0, 0.0)
            else:
                pref_vel = (0.0, 0.0)
            
            self.rvo_sim.set_agent_pref_velocity(agent.rvo_id, pref_vel)
            
    def _apply_mouse_override(self, target_pos):
        sim_target = self.floorplan.screen_to_sim(target_pos[0], target_pos[1])
        
        for agent in self.agents:
            if agent.rvo_id is not None:
                dx = sim_target[0] - agent.sim_pos[0]
                dy = sim_target[1] - agent.sim_pos[1]
                dist = (dx ** 2 + dy ** 2) ** 0.5
                if dist > 1.0:
                    pref_vel = (dx / dist * agent.speed, dy / dist * agent.speed)
                    self.rvo_sim.set_agent_pref_velocity(agent.rvo_id, pref_vel)
                    
    @property
    def agent_count(self):
        return len(self.agents)
        
    def toggle_pause(self):
        self.paused = not self.paused
        return self.paused
