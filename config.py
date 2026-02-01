class DisplayConfig:
    def __init__(self):
        self.fps = 60
        self.screen_width = 1420
        self.screen_height = 800
        self.window_borders = 25
        self.ui_panel_width = 260
        self.ui_panel_height = 750
        self.max_sim_width = 1080
        self.max_sim_height = 640


class SimulationConfig:
    def __init__(self):
        self.pixels_per_meter = 50.0
        self.agent_radius_meters = 0.3
        self.grid_spacing_meters = 0.5
        self.neighbor_dist = 5.0
        self.max_neighbors = 20
        self.time_horizon = 1.5
        self.time_horizon_obst = 0.5
        self.max_speed = 3.0

    @property
    def meters_per_pixel(self):
        return 1.0 / self.pixels_per_meter

    @property
    def agent_size(self):
        return int(self.agent_radius_meters * self.pixels_per_meter)


class AgentType:
    def __init__(self, name, speed, radius, colour,
                 neighbor_dist=None, max_neighbors=None, time_horizon=None, time_horizon_obst=None):
        self.name = name
        self.speed = speed
        self.radius = radius
        self.colour = colour
        self.neighbor_dist = neighbor_dist
        self.max_neighbors = max_neighbors
        self.time_horizon = time_horizon
        self.time_horizon_obst = time_horizon_obst
        
    @classmethod
    def default(cls, sim_config):
        return cls(
            name="Default",
            speed=sim_config.max_speed * sim_config.pixels_per_meter,
            radius=sim_config.agent_radius_meters * sim_config.pixels_per_meter,
            colour=(255, 255, 0),
            neighbor_dist=sim_config.neighbor_dist * sim_config.pixels_per_meter,
            max_neighbors=sim_config.max_neighbors,
            time_horizon=sim_config.time_horizon,
            time_horizon_obst=sim_config.time_horizon_obst
        )

    def resolve_rvo_params(self, sim_config):
        return self.neighbor_dist, self.max_neighbors, self.time_horizon, self.time_horizon_obst


class CustomAgentDefaults:
    """Default properties for custom agent types"""

    def __init__(self):
        self.speed_meters_per_sec = 3.0
        self.radius_meters = 0.3
        # Colors for custom types A-F
        self.colours = [
            (255, 100, 100),  # Type A - Red
            (100, 255, 100),  # Type B - Green
            (100, 100, 255),  # Type C - Blue
            (255, 150, 0),    # Type D - Orange
            (255, 100, 255),  # Type E - Magenta
            (100, 255, 255),  # Type F - Cyan
        ]


class RoadmapVertex:
    def __init__(self, position, neighbors=None, dist_to_exit=float("inf")):
        if neighbors is None:
            neighbors = []
        self.position = position
        self.neighbors = neighbors
        self.dist_to_exit = dist_to_exit


class ColourScheme:
    def __init__(self):
        self.bg_top = (0, 0, 50)
        self.bg_bottom = (0, 0, 255)
        self.sim_bg_top = (110, 200, 255)
        self.sim_bg_bottom = (255, 255, 255)
        self.wall = (65, 65, 65)
        self.ui_panel = (160, 160, 160)
        self.ui_text = (255, 255, 255)
