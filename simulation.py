"""Simulation engine"""

import heapq

import pygame
import pyrvo

from sprites import Agent


SIMULATION_RATE = 60
SIMULATION_STEP = 1.0 / SIMULATION_RATE
NODE_DIST_METERS = 2.0  # Distance where nodes are connected
GRID_SPACING_METRES = 0.25  # How close together nodes are
REACHED_EXIT_THRESHOLD = 40 # pixels


class Simulation:
    """Orchestrates agent pathfinding and crowd dynamics via RVO2."""

    def __init__(self, display_config, sim_config, log):
        self.display_config = display_config
        self.sim_config = sim_config
        self.log = log

        self.agents = pygame.sprite.Group()
        self.exits = pygame.sprite.Group()

        self.roadmaps: dict[int, Roadmap] = {}

        self.rvo_sim = None

        self.real_time = 0.0
        self.simulation_time = 0.0
        self.evacuated_count = 0
        self.paused = False
        self.time_accumulator = 0.0

        self.floorplan = None

        self.simulation_rate = SIMULATION_RATE

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

    def start(self):
        for agent in self.agents:
            if agent.rvo_id is None:
                agent.register_with_rvo(self.rvo_sim)
                if agent.radius not in self.roadmaps:
                    self.roadmaps[agent.radius] = self.build_roadmap(agent.radius)
        self.log(f"{len(self.roadmaps)} roadmaps built for agent radii: {list(self.roadmaps.keys())}", "D")

        self.real_time = 0.0
        self.simulation_time = 0.0
        self.evacuated_count = 0
        self.paused = False
        self.time_accumulator = 0.0

    def reset(self):
        self.agents.empty()
        self.exits.empty()

        self.roadmaps: dict[int, Roadmap] = {}

        self.real_time = 0.0
        self.simulation_time = 0.0
        self.evacuated_count = 0
        self.paused = False
        self.time_accumulator = 0.0

    def toggle_pause(self):
        self.paused = not self.paused
        return self.paused

    def update(self, dt, mouse_override=None):
        if self.paused:
            return False

        self.real_time += dt
        self.time_accumulator += dt

        if self.time_accumulator < SIMULATION_STEP:
            return False
        self.time_accumulator -= SIMULATION_STEP

        arrived = self.collect_arrived_agents()

        self.set_preferred_velocities()

        if mouse_override:
            self.apply_mouse_override(mouse_override)

        self.rvo_sim.do_step()
        self.simulation_time += SIMULATION_STEP

        for agent in self.agents:
            if agent not in arrived:
                agent.update_position(self.rvo_sim)

        for agent in arrived:
            self.rvo_sim.set_agent_radius(agent.rvo_id, 0.0)
            self.agents.remove(agent)
            self.evacuated_count += 1

        return len(self.agents) == 0


    @property
    def agent_count(self):
        return len(self.agents)

    def generate_grid_nodes(self, clearance):
        """Lay a grid over the floorplan and keep only nodes that don't collide with walls."""
        from sprites import has_wall_collision

        spacing = GRID_SPACING_METRES * self.sim_config.pixels_per_meter

        nodes = []
        for y in range(int(spacing), int(self.floorplan.height), int(spacing)):
            for x in range(int(spacing), int(self.floorplan.width), int(spacing)):
                if not has_wall_collision(x, y, clearance, self.floorplan.wall_polygons):
                    nodes.append((float(x), float(y)))
        return nodes

    def build_roadmap(self, radius):
        rm = Roadmap(radius)
        max_edge_len = GRID_SPACING_METRES * self.sim_config.pixels_per_meter * NODE_DIST_METERS

        for exit_obj in self.exits:
            rm.exit_indices.append(len(rm.vertices))
            rm.vertices.append(RoadmapVertex(position=exit_obj.sim_pos))

        grid_nodes = self.generate_grid_nodes(radius + 2)
        for node_pos in grid_nodes:
            rm.vertices.append(RoadmapVertex(position=node_pos))

        # Connect roadmap vertices if they're within range and unobstructed.
        max_edge_len_sq = max_edge_len ** 2 # Compare squared distances to avoid computing sqrt for every pair.
        verts = rm.vertices
        # Test each pair only once, edges added both ways.
        for i in range(len(verts)):
            ni = verts[i]
            for j in range(i + 1, len(verts)):
                nj = verts[j]
                dx = nj.position[0] - ni.position[0]
                dy = nj.position[1] - ni.position[1]
                if dx * dx + dy * dy <= max_edge_len_sq:
                    if self.rvo_sim.query_visibility(ni.position, nj.position, radius):
                        ni.neighbors.append(j)
                        nj.neighbors.append(i)

        self.compute_distances_to_exits(rm.vertices, rm.exit_indices)

        return rm

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
                edge_len = (dx * dx + dy * dy) ** 0.5

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

            rm = self.roadmaps[agent.radius]
            pos = agent.sim_pos
            best_cost = float("inf")
            best_idx = -1

            for j, vertex in enumerate(rm.vertices):
                if vertex.dist_to_exit >= best_cost:
                    continue
                dx = vertex.position[0] - pos[0]
                dy = vertex.position[1] - pos[1]
                # Distance to a vertex + it's distance to the nearest exit
                cost = (dx * dx + dy * dy) ** 0.5 + vertex.dist_to_exit
                if cost < best_cost:
                    if self.rvo_sim.query_visibility(pos, vertex.position, agent.radius):
                        best_cost = cost
                        best_idx = j

            pref_vel = self.velocity_toward(
                pos, rm.vertices[best_idx].position, agent.speed
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
        dist = (dx * dx + dy * dy) ** 0.5
        if dist > 1.0:
            return (dx / dist * speed, dy / dist * speed)
        return (0.0, 0.0)

    def collect_arrived_agents(self):
        arrived = set()
        REACHED_EXIT_THRESHOLD_SQ = REACHED_EXIT_THRESHOLD ** 2
        for agent in self.agents:
            rm = self.roadmaps[agent.radius]
            for exit_idx in rm.exit_indices:
                exit_pos = rm.vertices[exit_idx].position
                dx = agent.sim_pos[0] - exit_pos[0]
                dy = agent.sim_pos[1] - exit_pos[1]
                if dx * dx + dy * dy < REACHED_EXIT_THRESHOLD_SQ:
                    arrived.add(agent)
                    break
        return arrived

class RoadmapVertex:
    """A single node in the pathfinding roadmap."""
    def __init__(self, position, neighbors=None, dist_to_exit=float("inf")):
        self.position = position
        self.neighbors = neighbors if neighbors is not None else []
        self.dist_to_exit = dist_to_exit

class Roadmap:
    __slots__ = ("radius", "vertices", "exit_indices")  # Restrict instance attributes for memory efficiency

    def __init__(self, radius: int):
        self.radius = radius
        self.vertices: list[RoadmapVertex] = []
        self.exit_indices: list[int] = []