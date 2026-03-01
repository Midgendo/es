import os
import glob
import json

import pygame
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ui import create_gradient


WALL_BRIGHTNESS_THRESHOLD = 50   # pixels darker than this are treated as walls
WALL_SIMPLIFY_TOLERANCE = 1.0  # Shapely simplification tolerance (px)


class Floorplan:
    """Loads a floorplan PNG, extracts wall geometry and registers it with RVO as obstacles."""

    def __init__(self, filename, display_config, sim_config, colours):
        self.filename = filename
        self.display_config = display_config
        self.sim_config = sim_config
        self.colours = colours

        self.image = None
        self.wall_polygons = []
        self.bg_surface = None
        self.walls_surface = None

        self.width = self.height = self.offset_x = self.offset_y = 0

    def load(self, rvo_sim):
        self.load_and_scale_image()
        self.extract_walls(rvo_sim)
        self.add_border_obstacles(rvo_sim)

    def is_within_bounds(self, x, y, margin=0):
        return (
            self.offset_x + margin <= x <= self.offset_x + self.width  - margin and
            self.offset_y + margin <= y <= self.offset_y + self.height - margin
        )

    def screen_to_sim(self, screen_x, screen_y):
        return (screen_x - self.offset_x, screen_y - self.offset_y)

    def sim_to_screen(self, sim_x, sim_y):
        return (sim_x + self.offset_x, sim_y + self.offset_y)

    def load_and_scale_image(self):
        floorplan_path = os.path.join("floorplans", self.filename)
        self.image = pygame.image.load(floorplan_path)

        raw_w, raw_h = self.image.get_size()
        aspect = raw_w / raw_h

        max_w = self.display_config.max_sim_width
        max_h = self.display_config.max_sim_height

        if aspect > (max_w / max_h):
            self.width = max_w
            self.height = int(max_w / aspect)
        else:
            self.height = max_h
            self.width = int(max_h * aspect)

        self.offset_x = (
            self.display_config.ui_panel_width
            + self.display_config.window_borders * 2
            + (max_w - self.width) // 2
        )
        self.offset_y = (
            self.display_config.window_borders
            + (max_h - self.height) // 2
        )


    def extract_walls(self, rvo_sim):
        im_w, im_h = self.image.get_size()
        scale = min(self.width / im_w, self.height / im_h)

        # Build per-pixel quads for every "wall" pixel
        brightness = pygame.surfarray.array3d(self.image).mean(axis=2)
        is_wall = brightness < WALL_BRIGHTNESS_THRESHOLD

        pixel_quads = []
        for y in range(im_h):
            for x in range(im_w):
                if is_wall[x, y]:
                    x1, y1 = x * scale, y * scale
                    x2, y2 = (x + 1) * scale, (y + 1) * scale
                    pixel_quads.append(Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)]))

        # Merge & simplify
        merged = unary_union(pixel_quads)
        merged = merged.simplify(WALL_SIMPLIFY_TOLERANCE, preserve_topology=True)

        if merged.geom_type == "Polygon":
            self.wall_polygons = [merged]
        elif merged.geom_type == "MultiPolygon":
            self.wall_polygons = list(merged.geoms)
        else:
            self.wall_polygons = []

        self.build_walls_surface()
        self.register_wall_obstacles(rvo_sim)

    def build_walls_surface(self):
        self.bg_surface = create_gradient(
            self.width, self.height,
            self.colours.sim_bg_top,
            self.colours.sim_bg_bottom,
        )
        self.walls_surface = pygame.Surface(
            (self.width, self.height), pygame.SRCALPHA
        )
        for poly in self.wall_polygons:
            pygame.draw.polygon(
                self.walls_surface,
                self.colours.wall,
                list(poly.exterior.coords),
            )

    def register_wall_obstacles(self, rvo_sim):
        for poly in self.wall_polygons:
            # RVO2 expects counter-clockwise winding
            exterior = [(float(x), float(y)) for x, y in poly.exterior.coords[:-1]]
            exterior.reverse()
            if len(exterior) >= 2:
                rvo_sim.add_obstacle(exterior)

            for hole in poly.interiors:
                interior = [(float(x), float(y)) for x, y in hole.coords[:-1]]
                if len(interior) >= 2:
                    rvo_sim.add_obstacle(interior)

    def add_border_obstacles(self, rvo_sim):
        w, h = self.width, self.height
        rvo_sim.add_obstacle([(0, 0), (w, 0), (w, 1), (0, 1)])        # top
        rvo_sim.add_obstacle([(0, h - 1), (w, h - 1), (w, h), (0, h)])  # bottom
        rvo_sim.add_obstacle([(0, 0), (1, 0), (1, h), (0, h)])        # left
        rvo_sim.add_obstacle([(w - 1, 0), (w, 0), (w, h), (w - 1, h)])  # right


class FloorplanManager:
    """Utility for listing available floorplan PNGs and reading their config."""

    FOLDER = "floorplans"

    @staticmethod
    def get_available():
        png_paths = glob.glob(f"{FloorplanManager.FOLDER}/*.png")
        names = [os.path.basename(p) for p in png_paths]
        return sorted(names) if names else ["floorplan.png"]

    @staticmethod
    def get_pixels_per_meter(filename, default_value):
        config_path = os.path.join(
            FloorplanManager.FOLDER,
            f"{filename.rsplit('.', 1)[0]}.json",
        )
        try:
            with open(config_path, "r") as f:
                data = json.load(f)
            return data.get("pixels_per_meter", default_value)
        except FileNotFoundError:
            return default_value
