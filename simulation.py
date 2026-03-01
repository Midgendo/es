"""Simulation engine"""

import heapq

import pygame
import pyrvo

from config import RoadmapVertex
from sprites import Agent


SIMULATION_STEP = 1.0 / 60.0
GRID_WALL_CLEARANCE = 0.4 # metres
NEIGHBOR_DIST_METERS = 2.5


class Simulation:
    """Orchestrates agent pathfinding and crowd dynamics via RVO2."""

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

    def initialize_rvo(self):
        cfg = self.sim_config
        ppm = cfg.pixels_per_meter
        self.rvo_sim = pyrvo.RVOSimulator(
            SIMULATION_STEP,
            cfg.neighbor_dist * ppm, 
            cfg.max_neighbors,
            cfg.time_horizon,
            cfg.time_horizon_obst,
            cfg.agent_radius_meters * ppm,
            cfg.max_speed * ppm,
            pyrvo.Vector2(0.0, 0.0), # starting velocity
        )

    def set_floorplan(self, floorplan):
        self.floorplan = floorplan
        self.generate_grid_nodes()

    def start(self):
        self.time = 0.0
        self.simulation_time = 0.0
        self.evacuated_count = 0
        self.paused = False

        if self.exits and self.grid_nodes:
            self.roadmap, self.exit_indices = self.build_roadmap()
        else:
            self.roadmap = []
            self.exit_indices = []

        for agent in self.agents:
            if agent.rvo_id is None:
                agent.register_with_rvo(self.rvo_sim)

    def reset(self):
        self.agents.empty()
        self.exits.empty()

        self.roadmap = []
        self.exit_indices = []
        self.time = 0.0
        self.simulation_time = 0.0
        self.evacuated_count = 0
        self.paused = False

    def toggle_pause(self):
        self.paused = not self.paused
        return self.paused

    def update(self, dt, mouse_override=None):
        if self.paused:
            return False

        self.time += dt

        arrived = self.collect_arrived_agents()

        self.set_preferred_velocities()

        if mouse_override:
            self.apply_mouse_override(mouse_override)

        self.rvo_sim.do_step()
        self.simulation_time = self.rvo_sim.get_global_time()

        for agent in self.agents:
            if agent not in arrived:
                agent.update_position(self.rvo_sim)

        for agent in arrived:
            self.agents.remove(agent)
            self.evacuated_count += 1

        return len(self.agents) == 0


    @property
    def agent_count(self):
        return len(self.agents)

    def generate_grid_nodes(self):
        """Lay a grid over the floorplan and keep only nodes that don't collide with walls."""
        from sprites import has_wall_collision

        spacing = self.sim_config.grid_spacing_meters * self.sim_config.pixels_per_meter
        clearance = self.sim_config.pixels_per_meter * GRID_WALL_CLEARANCE

        self.grid_nodes = []
        for y in range(int(spacing), int(self.floorplan.height), int(spacing)):
            for x in range(int(spacing), int(self.floorplan.width), int(spacing)):
                if not has_wall_collision(x, y, clearance, self.floorplan.wall_polygons):
                    self.grid_nodes.append((float(x), float(y)))

    def build_roadmap(self):
        roadmap = []
        exit_indices = []
        agent_radius = self.sim_config.agent_size
        max_edge_len = self.sim_config.grid_spacing_meters * self.sim_config.pixels_per_meter * NEIGHBOR_DIST_METERS

        for exit_obj in self.exits:
            exit_indices.append(len(roadmap))
            roadmap.append(RoadmapVertex(position=exit_obj.sim_pos))

        for node_pos in self.grid_nodes:
            roadmap.append(RoadmapVertex(position=node_pos))

        # Connect roadmap vertices if they're within range and unobstructed. 
        for i, node in enumerate(roadmap):
            for j, other in enumerate(roadmap):
                if i == j:
                    continue
                dx = other.position[0] - node.position[0]
                dy = other.position[1] - node.position[1]
                dist = (dx ** 2 + dy ** 2) ** 0.5
                if dist <= max_edge_len:
                    if self.rvo_sim.query_visibility(node.position, other.position, agent_radius):
                        node.neighbors.append(j)

        self.compute_distances_to_exits(roadmap, exit_indices)
        return roadmap, exit_indices

    @staticmethod
    def compute_distances_to_exits(roadmap, exit_indices):
        """Multi-source Dijkstra from every exit."""
        dist = [float("inf")] * len(roadmap)
        pq = []

        for idx in exit_indices:
            dist[idx] = 0.0
            heapq.heappush(pq, (0.0, idx))

        while pq:
            d_u, u = heapq.heappop(pq)
            if d_u != dist[u]:
                continue  # stale entry

            for v in roadmap[u].neighbors:
                dx = roadmap[v].position[0] - roadmap[u].position[0]
                dy = roadmap[v].position[1] - roadmap[u].position[1]
                edge_len = (dx ** 2 + dy ** 2) ** 0.5

                if dist[v] > d_u + edge_len:
                    dist[v] = d_u + edge_len
                    heapq.heappush(pq, (dist[v], v))

        for i, vertex in enumerate(roadmap):
            vertex.dist_to_exit = dist[i]

    def set_preferred_velocities(self):
        """
        For every agent, find the visible roadmap vertex that minimises 
        the distance to that vertex + its distance to the nearest exit.
        """
        for agent in self.agents:
            if agent.rvo_id is None:
                continue

            pos = agent.sim_pos
            best_cost = float("inf")
            best_idx = -1

            for j, vertex in enumerate(self.roadmap):
                dx = vertex.position[0] - pos[0]
                dy = vertex.position[1] - pos[1]
                cost = (dx ** 2 + dy ** 2) ** 0.5 + vertex.dist_to_exit
                if cost < best_cost:
                    if self.rvo_sim.query_visibility(pos, vertex.position, agent.radius):
                        best_cost = cost
                        best_idx = j

            pref_vel = self.velocity_toward(
                pos, self.roadmap[best_idx].position, agent.speed
            ) if best_idx >= 0 else (0.0, 0.0)

            self.rvo_sim.set_agent_pref_velocity(agent.rvo_id, pref_vel)

    def apply_mouse_override(self, screen_target):
        sim_target = self.floorplan.screen_to_sim(*screen_target)
        for agent in self.agents:
            if agent.rvo_id is not None:
                pref_vel = self.velocity_toward(agent.sim_pos, sim_target, agent.speed)
                self.rvo_sim.set_agent_pref_velocity(agent.rvo_id, pref_vel)

    @staticmethod
    def velocity_toward(origin, target, speed):
        dx = target[0] - origin[0]
        dy = target[1] - origin[1]
        dist = (dx ** 2 + dy ** 2) ** 0.5
        if dist > 1.0:
            return (dx / dist * speed, dy / dist * speed)
        return (0.0, 0.0)

    def collect_arrived_agents(self):
        arrived = set()
        for agent in self.agents:
            for exit_idx in self.exit_indices:
                exit_pos = self.roadmap[exit_idx].position
                dx = agent.sim_pos[0] - exit_pos[0]
                dy = agent.sim_pos[1] - exit_pos[1]
                if (dx ** 2 + dy ** 2) < Agent.REACHED_EXIT_THRESHOLD ** 2:
                    arrived.add(agent)
                    break
        return arrived
