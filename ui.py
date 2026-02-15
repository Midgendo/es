import pygame
import pygame_gui
import pytweening
from config import ColourScheme
from sprites import Agent, Exit, has_wall_collision, has_agent_collision


class SceneData:
    def __init__(self, ppm=50.0):
        self.agents = []
        self.exits = []
        self.floorplan = None
        self.ppm = ppm
    
    def set_floorplan(self, floorplan):
        self.floorplan = floorplan
    
    def add_agent(self, screen_x, screen_y, agent_type):
        sim_x, sim_y = self.floorplan.screen_to_sim(screen_x, screen_y)
        radius_px = agent_type.radius_px(self.ppm)
        if has_wall_collision(sim_x, sim_y, radius_px, self.floorplan.wall_polygons):
            return False
        if has_agent_collision((sim_x, sim_y), radius_px, self.agents):
            return False
        agent = Agent(screen_x, screen_y, agent_type, self.floorplan.offset_x, self.floorplan.offset_y, self.ppm)
        self.agents.append(agent)
        return True
    
    def remove_agent_at(self, screen_x, screen_y):
        for agent in self.agents:
            if agent.rect.collidepoint((screen_x, screen_y)):
                self.agents.remove(agent)
                return True
        return False
    
    def remove_agents_of_type(self, agent_type):
        self.agents = [a for a in self.agents if a.agent_type != agent_type]
    
    def add_exit(self, screen_x, screen_y, sim_config):
        sim_x, sim_y = self.floorplan.screen_to_sim(screen_x, screen_y)
        if has_wall_collision(sim_x, sim_y, sim_config.agent_size, self.floorplan.wall_polygons):
            return False
        exit_obj = Exit(
            screen_x, screen_y, len(self.exits) + 1,
            radius=sim_config.agent_size * 1.2, colour=(0, 200, 0),
            offset_x=self.floorplan.offset_x, offset_y=self.floorplan.offset_y
        )
        self.exits.append(exit_obj)
        return True
    
    def remove_exit_at(self, screen_x, screen_y):
        for exit_obj in self.exits:
            if exit_obj.rect.collidepoint((screen_x, screen_y)):
                self.exits.remove(exit_obj)
                for idx, e in enumerate(self.exits, 1):
                    e.set_number(idx)
                return True
        return False
    
    def update_agents_of_type(self, agent_type, radius_m=None, speed_mps=None):
        if radius_m is not None:
            agent_type.radius_m = radius_m
        if speed_mps is not None:
            agent_type.speed_mps = speed_mps
        for agent in self.agents:
            if agent.agent_type is agent_type:
                agent.radius = int(agent_type.radius_px(self.ppm))
                agent.speed = agent_type.speed_px(self.ppm)
                agent.rebuild_image()
    
    def update_ppm(self, ppm):
        self.ppm = ppm
        for agent in self.agents:
            agent.update_ppm(ppm)
    
    def clear(self):
        self.agents = []
        self.exits = []


class UIConfig:
    PANEL_WIDTH = 260
    PANEL_HEIGHT = 750
    BORDER = 25
    BUTTON_HEIGHT = 40


pygame.font.init()


class Fonts:
    DEFAULT = pygame.font.Font(None, 24)
    DEFAULT_SMALL = pygame.font.Font(None, 18)
    DEFAULT_SMALL_ITALIC = pygame.font.Font(None, 18)
    DEFAULT_SMALL_ITALIC.set_italic(True)
    TITLE = pygame.font.Font(None, 40)
    TITLE.set_italic(True)
    TIMER = pygame.font.Font("DSEG7Classic-BoldItalic.ttf", 28)
    TIMER2 = pygame.font.Font("DSEG7Classic-BoldItalic.ttf", 18)
    AGENT_DETAILS = pygame.font.Font(None, 20)


def create_gradient(width, height, colour1, colour2, alpha1=255, alpha2=255):
    gradient_surface = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(height):
        ratio = y / height
        colour = tuple(int(colour1[i] + (colour2[i] - colour1[i]) * ratio) for i in range(3))
        alpha = int(alpha1 + (alpha2 - alpha1) * ratio)
        pygame.draw.line(gradient_surface, colour + (alpha,), (0, y), (width, y))
    return gradient_surface


class UIPanel:
    def __init__(self, manager, floorplan_options, current_floorplan, colours, state_getter):
        self.start_pos = -UIConfig.PANEL_WIDTH - UIConfig.BORDER
        self.end_pos = UIConfig.BORDER
        self.current_pos = self.start_pos
        self.duration = 0.7
        self.tween_progress = 0.0
        self.animation_started = False
        self.animation_delay = 0.0
        
        self.colours = colours
        self.manager = manager
        self.state_getter = state_getter
        
        self.floorplan_picker = pygame_gui.elements.UIDropDownMenu(
            options_list=floorplan_options,
            starting_option=current_floorplan,
            relative_rect=pygame.Rect((0, 0), (UIConfig.PANEL_WIDTH, UIConfig.BUTTON_HEIGHT)),
            manager=manager,
            object_id="#floorplan_picker"
        )
        
        half_width = (UIConfig.PANEL_WIDTH - 5) // 2
        
        self.buttons = {
            "clear": self.create_button("Clear", UIConfig.PANEL_WIDTH),
            "tool_agent": self.create_button("Agents", half_width),
            "tool_exit": self.create_button("Exits", half_width),
            "load": self.create_button("Load", half_width),
            "save": self.create_button("Save", half_width),
            "start": self.create_button("Start", UIConfig.PANEL_WIDTH),
            "pause_resume": self.create_button("Pause", UIConfig.PANEL_WIDTH),
            "stop": self.create_button("Stop", UIConfig.PANEL_WIDTH),
        }
        
    def create_button(self, text, width):
        return pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (width, UIConfig.BUTTON_HEIGHT)),
            text=text,
            manager=self.manager,
            visible=False
        )
    
    def hide_all_buttons(self):
        for btn in self.buttons.values():
            btn.hide()
            
    def show_editing_buttons(self):
        self.buttons["clear"].show()
        self.buttons["tool_agent"].show()
        self.buttons["tool_exit"].show()
        self.buttons["load"].show()
        self.buttons["save"].show()
        self.buttons["start"].show()
        self.buttons["tool_agent"].disable()
        self.buttons["tool_exit"].enable()
        
    def show_running_buttons(self):
        self.buttons["pause_resume"].set_text("Pause")
        self.buttons["pause_resume"].show()
        self.buttons["stop"].show()
        
    def show_completed_buttons(self):
        self.buttons["stop"].show()
    
    def enter(self, delay=0.0):
        self.animation_started = True
        self.tween_progress = 0.0
        self.animation_delay = delay
    
    def update_animation(self, dt):
        if not self.animation_started or self.tween_progress >= 1.0:
            return
        if self.animation_delay > 0:
            self.animation_delay -= dt
            return
        self.tween_progress = min(self.tween_progress + dt / self.duration, 1.0)
        eased = pytweening.easeOutQuad(self.tween_progress)
        self.current_pos = self.start_pos + (self.end_pos - self.start_pos) * eased
    
    def update_button_positions(self, state, dt):
        self.update_animation(dt)
        
        gap = 2
        half_width = (UIConfig.PANEL_WIDTH - gap) // 2
        row_height = UIConfig.BUTTON_HEIGHT + gap
        bottom = UIConfig.BORDER + UIConfig.PANEL_HEIGHT - gap
        x = self.current_pos

        self.buttons["start"].set_relative_position((x, bottom - row_height))
        self.buttons["stop"].set_relative_position((x, bottom - row_height))
        
        self.buttons["load"].set_relative_position((x, bottom - row_height * 2))
        self.buttons["save"].set_relative_position((x + half_width + gap, bottom - row_height * 2))
        self.buttons["pause_resume"].set_relative_position((x, bottom - row_height * 2))
        
        self.buttons["tool_agent"].set_relative_position((x, bottom - row_height * 3))
        self.buttons["tool_exit"].set_relative_position((x + half_width + gap, bottom - row_height * 3))
        
        self.buttons["clear"].set_relative_position((x, bottom - row_height * 4))
        self.floorplan_picker.set_relative_position((x, bottom - row_height * 5))
        
        if state in ("running", "completed"):
            self.floorplan_picker.hide()
        else:
            self.floorplan_picker.show()
    
    def draw(self, surface, state, fps, dt, running_time=0.0, simulation_time=0.0, num_agents=0, evacuated_agents=0):
        self.update_button_positions(state, dt)
        x = self.current_pos
        
        panel_rect = pygame.Rect(x, UIConfig.BORDER + 80, UIConfig.PANEL_WIDTH, UIConfig.PANEL_HEIGHT - 80)
        title_gradient = create_gradient(UIConfig.PANEL_WIDTH, 80, self.colours.ui_panel, self.colours.ui_panel, 125, 255)
        surface.blit(title_gradient, (x, UIConfig.BORDER))
        pygame.draw.rect(surface, self.colours.ui_panel, panel_rect)
        
        shadow_offset = 3
        shadow_colour = (50, 50, 50)
        pad = 10
        cursor_y = 30

        last_advance = 0

        def draw_text(text, font=Fonts.DEFAULT, colour=self.colours.ui_text, spacing=0, shadow=False, same_line=False, x_offset=0, y_offset=0):
            nonlocal cursor_y, last_advance
            draw_y = (cursor_y - last_advance if same_line else cursor_y) + y_offset
            if shadow:
                surface.blit(font.render(text, True, shadow_colour), (x + pad + shadow_offset + x_offset, draw_y + shadow_offset))
            surface.blit(font.render(text, True, colour), (x + pad + x_offset, draw_y))
            if not same_line:
                last_advance = font.get_height() + spacing
                cursor_y += last_advance

        def format_time(t):
            m, s, ms = int(t // 60), int(t % 60), int((t % 1) * 1000)
            return f"{m:02d}:{s:02d}.{ms:03d}"

        # Title
        draw_text("Evacuation", Fonts.TITLE, self.colours.ui_text, shadow=True)
        draw_text("Simulator", Fonts.TITLE, self.colours.ui_text, spacing=5, shadow=True)

        # Timer background
        timer_h = Fonts.TIMER.get_height() + Fonts.TIMER2.get_height() + 12
        timer_bg = pygame.Surface((UIConfig.PANEL_WIDTH, timer_h), pygame.SRCALPHA)
        pygame.draw.rect(timer_bg, (0, 0, 0, 128), timer_bg.get_rect())
        surface.blit(timer_bg, (x, cursor_y))

        # Simulation timer + shadow
        surface.blit(Fonts.TIMER.render("88:88.888", True, shadow_colour), (x + pad + shadow_offset, cursor_y + shadow_offset + 2))
        draw_text(format_time(simulation_time), Fonts.TIMER, (255, 165, 0), spacing=5, y_offset=2)

        # Real time timer
        surface.blit(Fonts.TIMER2.render("88:88.888", True, shadow_colour), (x + pad + shadow_offset, cursor_y + shadow_offset + 2))
        draw_text(format_time(running_time), Fonts.TIMER2, (0, 255, 0), spacing=6, y_offset=2)
        draw_text("RT", Fonts.DEFAULT_SMALL_ITALIC, (0, 255, 0), same_line=True, x_offset=110, shadow=True, y_offset=10)

        # Status info
        state_info = {
            "running": ("Running", (0, 0, 255)),
            "editing": ("Editing", (255, 100, 100)),
            "completed": ("All agents evacuated!!", (0, 255, 0))
        }
        status, status_colour = state_info.get(state, ("Unknown", (255, 255, 255)))
        remaining = num_agents - evacuated_agents

        draw_text(status, colour=status_colour, y_offset=4, spacing=5)
        draw_text(f"Evacuees: {remaining}")
        draw_text(f"Evacuated: {evacuated_agents}/{num_agents}")
        draw_text(f"FPS: {int(fps)}", spacing=10)

        # Instructions
        instructions = {
            "editing": ["Left click to place", "Right click to remove"],
            "running": ["Click to override target"]
        }
        for line in instructions.get(state, []):
            draw_text(line)


class Crosshair:
    COLOUR = (255, 0, 0, 128)
    COORD_FONT_SIZE = 18
    
    def __init__(self, floorplan, sim_config):
        self.floorplan = floorplan
        self.sim_config = sim_config
        self.font = pygame.font.Font(None, self.COORD_FONT_SIZE)
        
    def draw(self, surface, mouse_pos, tool='agent'):
        mx, my = mouse_pos
        if not self.floorplan.is_within_bounds(mx, my, 0):
            return
        
        fp = self.floorplan
        crosshair_surface = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        
        pygame.draw.line(crosshair_surface, self.COLOUR, (mx, fp.offset_y), (mx, fp.offset_y + fp.height), 1)
        pygame.draw.line(crosshair_surface, self.COLOUR, (fp.offset_x, my), (fp.offset_x + fp.width, my), 1)
        
        agent_size = self.sim_config.agent_size
        if tool == 'exit':
            rect_size = agent_size * 2.4
            pygame.draw.rect(crosshair_surface, self.COLOUR, 
                           (mx - rect_size/2, my - rect_size/2, rect_size, rect_size), 1)
        else:
            pygame.draw.circle(crosshair_surface, self.COLOUR, (mx, my), agent_size, 1)
        
        sim_x, sim_y = fp.screen_to_sim(mx, my)
        sim_x_m = sim_x * self.sim_config.meters_per_pixel
        sim_y_m = sim_y * self.sim_config.meters_per_pixel
        
        bg_rect = pygame.Rect(mx + 14, my + 3, 60, 25)
        pygame.draw.rect(crosshair_surface, (0, 0, 0, 128), bg_rect)
        crosshair_surface.blit(self.font.render(f"x: {sim_x_m:.1f}m", True, (255, 255, 255)), (mx + 16, my + 3))
        crosshair_surface.blit(self.font.render(f"y: {sim_y_m:.1f}m", True, (255, 255, 255)), (mx + 16, my + 14))
        
        surface.blit(crosshair_surface, (0, 0))

class SimWindow:
    MAX_SIM_WIDTH = 1080
    MAX_SIM_HEIGHT = 640
    LINE_THICKNESS = 1
    BORDER_THICKNESS = 3
    BOX_SIZE = 50
    
    def __init__(self, sim_config, colours=None):
        self.sim_config = sim_config
        self.colours = colours or ColourScheme()
        self.floorplan = None
        self.crosshair = None
        self.grid_surface = None
        self.border_rect = None
    
    def update_floorplan(self, floorplan):
        self.floorplan = floorplan
        self.crosshair = Crosshair(floorplan, self.sim_config)
        self.build_grid()
        self.update_border_rect()
    
    def update_border_rect(self):
        if self.floorplan is None:
            self.border_rect = None
            return
        self.border_rect = pygame.Rect(
            self.floorplan.offset_x,
            self.floorplan.offset_y,
            self.floorplan.width,
            self.floorplan.height
        )
    
    def build_grid(self):
        if self.floorplan is None:
            self.grid_surface = None
            return
        spacing = int(self.sim_config.pixels_per_meter)
        if spacing <= 0:
            self.grid_surface = None
            return
        grid_colour = (200, 200, 200, 128)
        grid_surface = pygame.Surface((self.floorplan.width, self.floorplan.height), pygame.SRCALPHA)
        
        for x in range(0, self.floorplan.width, spacing):
            pygame.draw.line(grid_surface, grid_colour, (x, 0), (x, self.floorplan.height))
        for y in range(0, self.floorplan.height, spacing):
            pygame.draw.line(grid_surface, grid_colour, (0, y), (self.floorplan.width, y))
            
        self.grid_surface = grid_surface
    
    def is_within_bounds(self, x, y, margin=0):
        if self.floorplan is None:
            return False
        return self.floorplan.is_within_bounds(x, y, margin)
    
    def get_mouse_override(self, mouse_pos):
        mx, _ = mouse_pos
        if mx > self.floorplan.offset_x:
            return mouse_pos
    
    def draw_roadmap(self, surface, simulation):
        for i, vertex in enumerate(simulation.roadmap):
            for neighbor_idx in vertex.neighbors:
                if neighbor_idx > i:
                    start = self.floorplan.sim_to_screen(*vertex.position)
                    end = self.floorplan.sim_to_screen(*simulation.roadmap[neighbor_idx].position)
                    pygame.draw.line(surface, (0, 100, 255, 128), start, end, 1)
    
    def draw(self, surface, simulation, scene_data=None, show_paths=False, show_crosshair=False, mouse_pos=None, tool="agent"):
        surface.blit(self.floorplan.bg_surface, (self.floorplan.offset_x, self.floorplan.offset_y))
        if self.grid_surface is not None:
            surface.blit(self.grid_surface, (self.floorplan.offset_x, self.floorplan.offset_y))
        surface.blit(self.floorplan.walls_surface, (self.floorplan.offset_x, self.floorplan.offset_y))
        if self.border_rect is not None:
            pygame.draw.rect(surface, (0, 0, 0), self.border_rect, self.BORDER_THICKNESS)

        exits = scene_data.exits if scene_data else simulation.exits
        agents = scene_data.agents if scene_data else simulation.agents

        for exit_obj in exits:
            surface.blit(exit_obj.image, exit_obj.rect)

        if show_paths and simulation.roadmap:
            self.draw_roadmap(surface, simulation)

        for agent in agents:
            surface.blit(agent.image, agent.rect)

        if show_crosshair and self.crosshair and mouse_pos:
            self.crosshair.draw(surface, mouse_pos, tool)
