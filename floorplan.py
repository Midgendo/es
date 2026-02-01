import os
import glob
import json
import pygame
from shapely.geometry import Polygon
from shapely.ops import unary_union

from ui import create_gradient


class Floorplan:
    def __init__(self, filename, display_config, sim_config, colours):
        self.filename = filename
        self.display_config = display_config
        self.sim_config = sim_config
        self.colours = colours
        
        self.image = None
        self.wall_polygons = []
        self.walls_surface = None
        self.width = 0
        self.height = 0
        self.offset_x = 0
        self.offset_y = 0
        
    def load(self, rvo_sim):
        floorplan_path = os.path.join("floorplans", self.filename)
        self.image = pygame.image.load(floorplan_path)
        
        floorplan_width, floorplan_height = self.image.get_size()
        aspect_ratio = floorplan_width / floorplan_height
        
        max_w = self.display_config.max_sim_width
        max_h = self.display_config.max_sim_height
        
        if aspect_ratio > (max_w / max_h):
            self.width = max_w
            self.height = int(max_w / aspect_ratio)
        else:
            self.height = max_h
            self.width = int(max_h * aspect_ratio)
        
        self.offset_x = (
            self.display_config.ui_panel_width + 
            (self.display_config.window_borders * 2) + 
            (max_w - self.width) // 2
        )
        self.offset_y = (
            self.display_config.window_borders + 
            (max_h - self.height) // 2
        )
        
        self._load_config()
        self._extract_walls(rvo_sim)
        self._add_border_obstacles(rvo_sim)
        
    def _load_config(self):
        try:
            config_filename = os.path.join(
                "floorplans", 
                f"{self.filename.rsplit('.', 1)[0]}.json"
            )
            with open(config_filename, 'r') as f:
                data = json.load(f)
                self.sim_config.pixels_per_meter = data.get(
                    "pixels_per_meter", 
                    self.sim_config.pixels_per_meter
                )
        except FileNotFoundError:
            pass
            
    def _extract_walls(self, rvo_sim):
        scale = min(
            self.width / self.image.get_size()[0],
            self.height / self.image.get_size()[1]
        )
        
        wall_threshold = 50
        walls_mask = (pygame.surfarray.array3d(self.image).mean(axis=2)) < wall_threshold
        
        pixel_polygons = []
        for y in range(self.image.get_size()[1]):
            for x in range(self.image.get_size()[0]):
                if walls_mask[x, y]:
                    x1, y1 = x * scale, y * scale
                    x2, y2 = (x + 1) * scale, (y + 1) * scale
                    pixel_polygons.append(Polygon([(x1, y1), (x2, y1), (x2, y2), (x1, y2)]))
        
        walls = unary_union(pixel_polygons)
        walls = walls.simplify(tolerance=1.0, preserve_topology=True)
        
        if walls.geom_type == 'Polygon':
            self.wall_polygons = [walls]
        elif walls.geom_type == 'MultiPolygon':
            self.wall_polygons = list(walls.geoms)
        else:
            self.wall_polygons = []
        
        self._create_walls_surface()
        self._add_wall_obstacles(rvo_sim)
        
    def _create_walls_surface(self):
        self.walls_surface = pygame.Surface((self.width, self.height), pygame.SRCALPHA)
        sim_bg = create_gradient(
            self.width, self.height, 
            self.colours.sim_bg_top, 
            self.colours.sim_bg_bottom
        )
        self.walls_surface.blit(sim_bg, (0, 0))
        
        for poly in self.wall_polygons:
            pygame.draw.polygon(
                self.walls_surface, 
                self.colours.wall, 
                list(poly.exterior.coords)
            )
            
    def _add_wall_obstacles(self, rvo_sim):
        for poly in self.wall_polygons:
            exterior_coords = list(poly.exterior.coords)
            vertices = [(float(x), float(y)) for x, y in exterior_coords[:-1]]
            vertices.reverse()
            if len(vertices) >= 2:
                rvo_sim.add_obstacle(vertices)
            
            for interior in poly.interiors:
                interior_coords = list(interior.coords)
                interior_vertices = [(float(x), float(y)) for x, y in interior_coords[:-1]]
                if len(interior_vertices) >= 2:
                    rvo_sim.add_obstacle(interior_vertices)
                    
    def _add_border_obstacles(self, rvo_sim):
        w, h = self.width, self.height
        rvo_sim.add_obstacle([(0, 0), (w, 0), (w, 1), (0, 1)])
        rvo_sim.add_obstacle([(0, h - 1), (w, h - 1), (w, h), (0, h)])
        rvo_sim.add_obstacle([(0, 0), (1, 0), (1, h), (0, h)])
        rvo_sim.add_obstacle([(w - 1, 0), (w, 0), (w, h), (w - 1, h)])
        
    def is_within_bounds(self, x, y, margin=0):
        return (
            self.offset_x + margin <= x <= self.offset_x + self.width - margin and
            self.offset_y + margin <= y <= self.offset_y + self.height - margin
        )
        
    def screen_to_sim(self, screen_x, screen_y):
        return (screen_x - self.offset_x, screen_y - self.offset_y)
        
    def sim_to_screen(self, sim_x, sim_y):
        return (sim_x + self.offset_x, sim_y + self.offset_y)


class FloorplanManager:
    FOLDER = "floorplans"
    
    @staticmethod
    def get_available():
        png_files = glob.glob(f"{FloorplanManager.FOLDER}/*.png")
        basenames = [os.path.basename(f) for f in png_files]
        return sorted(basenames) if basenames else ["floorplan.png"]

    @staticmethod
    def get_pixels_per_meter(filename, default_value):
        config_filename = os.path.join(
            FloorplanManager.FOLDER,
            f"{filename.rsplit('.', 1)[0]}.json"
        )
        try:
            with open(config_filename, 'r') as f:
                data = json.load(f)
            return data.get("pixels_per_meter", default_value)
        except FileNotFoundError:
            return default_value
