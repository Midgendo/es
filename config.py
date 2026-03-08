"""Configuration dataclasses and enums. Changing these might break things!"""

from enum import Enum, auto
import random

class AppState(Enum):
    LOADING = auto()
    EDITING = auto()
    RUNNING = auto()
    COMPLETED = auto()


class DisplayConfig:
    """Screen dimensions and fixed UI layout measurements."""

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
    """
    Physics and RVO-related constants used by the simulation engine.
    Spatial values stored in metres, converted to pixels via pixels_per_meter.
    """

    def __init__(self):
        self.pixels_per_meter = 70

        # Agent parameters (legacy code from before AgentType existed, alas these are still used in some places)
        self.agent_radius_meters = 0.3
        self.max_speed = 3.0    # m/s

        # RVO2 tuning
        # radius (meters) by which agents consider velocities of other agents
        self.neighbor_dist = 2.0
        # max number of other agents to consider
        self.max_neighbors = 10
        # how far into the future collisions with agents are anticipated (seconds)
        self.time_horizon = 0.5
        # same but for obstacles
        self.time_horizon_obst = 0.3

    @property
    def meters_per_pixel(self):
        return 1.0 / self.pixels_per_meter

    @property
    def agent_size(self):
        return int(self.agent_radius_meters * self.pixels_per_meter)


class AgentType:
    """
    Describes a category of agent (e.g. "Default", "Type A").

    Stores intrinsic properties in SI units (metres, m/s) and provides
    methods that convert to pixel-space given a PPM value.
    RVO parameters are read from the shared SimulationConfig.
    """

    def __init__(self, name, colour, sim_config,
                 speed_mps_range=(3.7, 4.5),
                 radius_m_range=(0.175, 0.225)):
        self.name = name
        self.colour = colour
        self.sim_config = sim_config

        self.speed_mps_range = speed_mps_range
        self.radius_m_range = radius_m_range

    # pixel-space conversions

    def rand_speed_px(self, ppm):
        return random.uniform(*self.speed_mps_range) * ppm

    def rand_radius_px(self, ppm):
        return random.uniform(*self.radius_m_range) * ppm

    def max_radius_px(self, ppm):
        return self.radius_m_range[1] * ppm

    @property
    def same_radius(self):
        return self.radius_m_range[0] == self.radius_m_range[1]

    @property
    def same_speed(self):
        return self.speed_mps_range[0] == self.speed_mps_range[1]

    def resolve_rvo_params(self, ppm):
        sc = self.sim_config
        return (
            sc.neighbor_dist * ppm,
            sc.max_neighbors,
            sc.time_horizon,
            sc.time_horizon_obst,
        )

    def type_letter(self):
        if self.name.startswith("Type ") and len(self.name) > 5:
            return self.name.split()[1]
        return None

    @classmethod
    def default(cls, sim_config):
        return cls("Default", (255, 255, 0), sim_config)


class ColourScheme:
    def __init__(self):
        self.bg_top = (0, 0, 50)
        self.bg_bottom = (0, 0, 255)

        self.sim_bg_top = (110, 200, 255)
        self.sim_bg_bottom = (255, 255, 255)

        self.wall = (65, 65, 65)
        self.ui_panel = (190, 190, 190)
        self.ui_text = (255, 255, 255)

        self.card_bg_sel = (180, 180, 180, 220)
        self.card_bg = (0, 0, 0, 150)

        # Palette for custom agent types
        self.custom_agent_colours = [
            (255, 100, 100),  # Type A — Red
            (100, 255, 100),  # Type B — Green
            (100, 100, 255),  # Type C — Blue
            (255, 150, 0),    # Type D — Orange
            (255, 100, 255),  # Type E — Magenta
            (100, 255, 255),  # Type F — Cyan
        ]