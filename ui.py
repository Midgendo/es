import pygame
import pygame_gui
import pytweening

from config import ColourScheme
from sprites import Agent, Exit, has_wall_collision, has_agent_collision


class Tween:
    def __init__(self, start, end, duration=0.7, easing=pytweening.easeOutQuad):
        self.start = start
        self.end = end
        self.duration = duration
        self.easing = easing

        self.value = start
        self.progress = 0.0
        self._started = False
        self._delay = 0.0

    def enter(self, delay=0.0):
        self._started = True
        self.progress = 0.0
        self.value = self.start
        self._delay = delay

    def update(self, dt):
        if not self._started or self.progress >= 1.0:
            return
        if self._delay > 0:
            self._delay -= dt
            return
        self.progress = min(self.progress + dt / self.duration, 1.0)
        self.value = self.start + (self.end - self.start) * self.easing(self.progress)


class SceneData:
    def __init__(self, ppm=50.0):
        self.agents = []
        self.exits = []
        self.floorplan = None
        self.ppm = ppm

    def set_floorplan(self, floorplan):
        self.floorplan = floorplan

    def add_agent(self, screen_x, screen_y, agent_type):
        local_x, local_y = self.floorplan.screen_to_sim(screen_x, screen_y)
        max_radius_px = agent_type.max_radius_px(self.ppm)

        if has_wall_collision(local_x, local_y, max_radius_px, self.floorplan.wall_polygons):
            return False
        if has_agent_collision((local_x, local_y), max_radius_px, self.agents):
            return False

        agent = Agent(local_x, local_y, agent_type, self.ppm)
        self.agents.append(agent)
        return True

    def remove_agent_at(self, screen_x, screen_y):
        local_x, local_y = self.floorplan.screen_to_sim(screen_x, screen_y)
        for agent in self.agents:
            if agent.rect.collidepoint((local_x, local_y)):
                self.agents.remove(agent)
                return True
        return False

    def remove_agents_of_type(self, agent_type):
        self.agents = [a for a in self.agents if a.agent_type != agent_type]

    def update_agents_of_type(self, agent_type, radius_m_range=None, speed_mps_range=None):
        if radius_m_range is not None:
            agent_type.radius_m_range = radius_m_range
        if speed_mps_range is not None:
            agent_type.speed_mps_range = speed_mps_range

        for agent in self.agents:
            if agent.agent_type is agent_type:
                if radius_m_range is not None:
                    agent.radius = int(agent_type.rand_radius_px(self.ppm))
                    agent.rebuild_image()
                if speed_mps_range is not None:
                    agent.speed = agent_type.rand_speed_px(self.ppm)

    def add_exit(self, screen_x, screen_y, sim_config):
        local_x, local_y = self.floorplan.screen_to_sim(screen_x, screen_y)
        if has_wall_collision(local_x, local_y, sim_config.agent_size, self.floorplan.wall_polygons):
            return False

        exit_obj = Exit(
            local_x, local_y,
            number=len(self.exits) + 1,
            radius=sim_config.agent_size * 1.2,
            colour=(0, 200, 0),
        )
        self.exits.append(exit_obj)
        return True

    def remove_exit_at(self, screen_x, screen_y):
        local_x, local_y = self.floorplan.screen_to_sim(screen_x, screen_y)
        for exit_obj in self.exits:
            if exit_obj.rect.collidepoint((local_x, local_y)):
                self.exits.remove(exit_obj)
                for idx, e in enumerate(self.exits, 1):
                    e.set_number(idx)
                return True
        return False

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

    AGENT_DETAILS = pygame.font.Font(None, 18)


def create_gradient(width, height, colour1, colour2, alpha1=255, alpha2=255):
    surface = pygame.Surface((width, height), pygame.SRCALPHA)
    for y in range(height):
        t = y / height
        rgb = tuple(int(colour1[i] + (colour2[i] - colour1[i]) * t) for i in range(3))
        alpha = int(alpha1 + (alpha2 - alpha1) * t)
        pygame.draw.line(surface, rgb + (alpha,), (0, y), (width, y))
    return surface


def format_time(seconds):
    m = int(seconds // 60)
    s = int(seconds % 60)
    ms = int((seconds % 1) * 1000)
    return f"{m:02d}:{s:02d}.{ms:03d}"


# Status label + colour per app-state
STATE_LABELS = {
    "LOADING": ("Loading...", (255, 255, 0)),
    "RUNNING": ("Running", (0, 0, 255)),
    "EDITING": ("Editing", (255, 100, 100)),
    "COMPLETED": ("All agents evacuated!!", (0, 255, 0)),
}

# Help text per app-state
INSTRUCTIONS = {
    "EDITING": ["Left click to place", "Right click to remove"],
    "RUNNING": ["Click to override target"],
}


class UIPanel:
    """Left-hand control panel."""

    SHADOW_OFFSET = 3
    SHADOW_COLOUR = (50, 50, 50)
    PAD = 10
    TITLE_BLOCK_WIDTH = 80

    def __init__(self, manager, floorplan_options, current_floorplan, colours, state_getter):
        self.colours = colours
        self.manager = manager
        self.state_getter = state_getter

        # Animation
        self.tween = Tween(
            start=-UIConfig.PANEL_WIDTH - UIConfig.BORDER,
            end=UIConfig.BORDER,
            duration=0.7,
        )

        # Floorplan dropdown
        self.floorplan_picker = pygame_gui.elements.UIDropDownMenu(
            options_list=floorplan_options,
            starting_option=current_floorplan,
            relative_rect=pygame.Rect((0, 0), (UIConfig.PANEL_WIDTH, UIConfig.BUTTON_HEIGHT)),
            manager=manager,
            object_id="#floorplan_picker",
        )

        # Buttons
        half_w = (UIConfig.PANEL_WIDTH - 5) // 2
        self.buttons = {
            "clear":        self.make_button("Clear",  UIConfig.PANEL_WIDTH),
            "tool_agent":   self.make_button("Agents", half_w),
            "tool_exit":    self.make_button("Exits",  half_w),
            "load":         self.make_button("Load",   half_w),
            "save":         self.make_button("Save",   half_w),
            "start":        self.make_button("Start",  UIConfig.PANEL_WIDTH),
            "pause_resume": self.make_button("Pause",  UIConfig.PANEL_WIDTH),
            "stop":         self.make_button("Stop",   UIConfig.PANEL_WIDTH),
        }

    def make_button(self, text, width):
        return pygame_gui.elements.UIButton(
            relative_rect=pygame.Rect((0, 0), (width, UIConfig.BUTTON_HEIGHT)),
            text=text,
            manager=self.manager,
            visible=False,
        )

    def hide_all_buttons(self):
        for btn in self.buttons.values():
            btn.hide()

    def show_editing_buttons(self):
        for name in ("clear", "tool_agent", "tool_exit", "load", "save", "start"):
            self.buttons[name].show()
        self.floorplan_picker.show()
        self.buttons["tool_agent"].disable()
        self.buttons["tool_exit"].enable()

    def show_running_buttons(self):
        self.buttons["pause_resume"].set_text("Pause")
        self.buttons["pause_resume"].show()
        self.buttons["stop"].show()
        self.floorplan_picker.hide()

    def show_completed_buttons(self):
        self.buttons["stop"].show()

    def enter(self, delay=0.0):
        self.tween.enter(delay)

    def layout_buttons(self, x):
        gap = 2
        half_w = (UIConfig.PANEL_WIDTH - gap) // 2
        row_h = UIConfig.BUTTON_HEIGHT + gap
        bottom = UIConfig.BORDER + UIConfig.PANEL_HEIGHT - gap

        self.buttons["start"].set_relative_position((x, bottom - row_h))
        self.buttons["stop"].set_relative_position((x, bottom - row_h))

        self.buttons["load"].set_relative_position((x, bottom - row_h * 2))
        self.buttons["save"].set_relative_position((x + half_w + gap, bottom - row_h * 2))
        self.buttons["pause_resume"].set_relative_position((x, bottom - row_h * 2))

        self.buttons["tool_agent"].set_relative_position((x, bottom - row_h * 3))
        self.buttons["tool_exit"].set_relative_position((x + half_w + gap, bottom - row_h * 3))

        self.buttons["clear"].set_relative_position((x, bottom - row_h * 4))
        self.floorplan_picker.set_relative_position((x, bottom - row_h * 5))

    def draw(self, surface, state, fps, dt, running_time=0.0, simulation_time=0.0, num_agents=0, evacuated_agents=0):
        self.tween.update(dt)
        x = self.tween.value
        self.layout_buttons(x)

        title_grad = create_gradient(
            UIConfig.PANEL_WIDTH, self.TITLE_BLOCK_WIDTH, self.colours.ui_panel, self.colours.ui_panel, 80, 255,
        )
        surface.blit(title_grad, (x, UIConfig.BORDER))

        body_rect = pygame.Rect(x, UIConfig.BORDER + self.TITLE_BLOCK_WIDTH, UIConfig.PANEL_WIDTH, UIConfig.PANEL_HEIGHT - self.TITLE_BLOCK_WIDTH)
        pygame.draw.rect(surface, self.colours.ui_panel, body_rect)

        cursor = TextCursor(surface, x, self.PAD, self.SHADOW_OFFSET, self.SHADOW_COLOUR)
        cursor.y = 30

        # Title
        cursor.render("Evacuation", Fonts.TITLE, self.colours.ui_text, shadow=True)
        cursor.render("Simulator",  Fonts.TITLE, self.colours.ui_text, shadow=True, space_after=5)

        # Timer background
        timer_h = Fonts.TIMER.get_height() + Fonts.TIMER2.get_height() + 12
        timer_bg = pygame.Surface((UIConfig.PANEL_WIDTH, timer_h), pygame.SRCALPHA)
        pygame.draw.rect(timer_bg, (0, 0, 0, 128), timer_bg.get_rect())
        surface.blit(timer_bg, (x, cursor.y))
        cursor.y += 2

        # Simulation timer
        surface.blit(
            Fonts.TIMER.render("88:88.888", True, self.SHADOW_COLOUR),
            (x + self.PAD + self.SHADOW_OFFSET, cursor.y + self.SHADOW_OFFSET),
        )
        text = format_time(simulation_time) if state in ("RUNNING", "COMPLETED") else "--:--.---"
        cursor.render(text, Fonts.TIMER, (255, 165, 0), space_after=5)

        # Real-time timer
        surface.blit(
            Fonts.TIMER2.render("88:88.888", True, self.SHADOW_COLOUR),
            (x + self.PAD + self.SHADOW_OFFSET - 1, cursor.y + self.SHADOW_OFFSET - 1),
        )
        text = format_time(running_time) if state in ("RUNNING", "COMPLETED") else "--:--.---"
        cursor.render(text, Fonts.TIMER2, (0, 225, 0), space_after=6, advance=False)
        cursor.render(
            "Rt", Fonts.DEFAULT_SMALL_ITALIC, (0, 225, 0), x_offset=100 + self.PAD, shadow=True, space_before=8, shadow_offset=self.SHADOW_OFFSET - 1
        )

        # Status info
        label, label_colour = STATE_LABELS.get(state, ("Unknown", (255, 255, 255)))
        remaining = num_agents - evacuated_agents

        cursor.render(label, colour=label_colour, space_before=4, space_after=5)
        cursor.render(f"Evacuees: {remaining}")
        cursor.render(f"Evacuated: {evacuated_agents}/{num_agents}")
        cursor.render(f"FPS: {int(fps)}", space_after=10)

        for line in INSTRUCTIONS.get(state, []):
            cursor.render(line)


class TextCursor:
    """Tracks a vertical cursor position for rendering text lines."""

    def __init__(self, surface, panel_x, pad, shadow_offset, shadow_colour):
        self.surface = surface
        self.panel_x = panel_x
        self.pad = pad
        self.shadow_offset = shadow_offset
        self.shadow_colour = shadow_colour
        self.y = 0

    def render(self, content, font=Fonts.DEFAULT, colour=(255, 255, 255),
             space_after=0, shadow=False, advance=True, x_offset=0, space_before=0, shadow_offset=0):
        draw_y = self.y + space_before
        draw_x = self.panel_x + self.pad + x_offset

        if shadow:
            if shadow_offset:
                self.shadow_offset = shadow_offset
            self.surface.blit(
                font.render(content, True, self.shadow_colour),
                (draw_x + self.shadow_offset, draw_y + self.shadow_offset),
            )
        self.surface.blit(font.render(content, True, colour), (draw_x, draw_y))

        if advance:
            self.y += space_before + space_after + font.get_height()


class Crosshair:

    COLOUR = (255, 0, 0, 128)
    COORD_FONT_SIZE = 18

    def __init__(self, floorplan, sim_config):
        self.floorplan = floorplan
        self.sim_config = sim_config
        self.font = pygame.font.Font(None, self.COORD_FONT_SIZE)

    def draw(self, surface, mouse_pos, tool="agent"):
        mx, my = mouse_pos
        if not self.floorplan.is_within_bounds(mx, my, 0):
            return

        fp = self.floorplan
        x, y = fp.screen_to_sim(mx, my)

        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)

        # Cross lines
        pygame.draw.line(overlay, self.COLOUR, (x, 0), (x, fp.height), 1)
        pygame.draw.line(overlay, self.COLOUR, (0, y), (fp.width, y), 1)

        size = self.sim_config.agent_size
        if tool == "exit":
            side = size * 2.4
            pygame.draw.rect(overlay, self.COLOUR, (x - side / 2, y - side / 2, side, side), 1)
        else:
            pygame.draw.circle(overlay, self.COLOUR, (x, y), size, 1)

        # Coordinate tooltip
        mpp = self.sim_config.meters_per_pixel
        bg_rect = pygame.Rect(x + 14, y + 3, 60, 25)
        pygame.draw.rect(overlay, (0, 0, 0, 128), bg_rect)
        overlay.blit(self.font.render(f"x: {x * mpp:.1f}m", True, (255, 255, 255)), (x + 16, y + 3))
        overlay.blit(self.font.render(f"y: {y * mpp:.1f}m", True, (255, 255, 255)), (x + 16, y + 14))

        surface.blit(overlay, (0, 0))


class SimWindow:
    """Simulation viewport."""

    BORDER_THICKNESS = 3
    ROADMAP_COLOURS = [
        (0, 100, 255, 128),
        (255, 100, 0, 128),
        (0, 255, 100, 128),
        (255, 0, 255, 128),
        (255, 255, 0, 128),
        (0, 255, 255, 128),
    ]

    def __init__(self, sim_config, colours=None):
        self.sim_config = sim_config
        self.colours = colours or ColourScheme()

        self.floorplan = None
        self.crosshair = None
        self.grid_surface = None

        self.opacity_tween = Tween(start=0, end=255, duration=0.7)

    def update_floorplan(self, floorplan):
        self.floorplan = floorplan
        self.crosshair = Crosshair(floorplan, self.sim_config)
        self.build_grid()

    def build_grid(self):
        if self.floorplan is None:
            self.grid_surface = None
            return

        spacing = int(self.sim_config.pixels_per_meter)
        if spacing <= 0:
            self.grid_surface = None
            return

        grid_colour = (200, 200, 200, 128)
        grid = pygame.Surface((self.floorplan.width, self.floorplan.height), pygame.SRCALPHA)
        for x in range(0, self.floorplan.width, spacing):
            pygame.draw.line(grid, grid_colour, (x, 0), (x, self.floorplan.height))
        for y in range(0, self.floorplan.height, spacing):
            pygame.draw.line(grid, grid_colour, (0, y), (self.floorplan.width, y))

        self.grid_surface = grid

    def is_within_bounds(self, x, y, margin=0):
        if self.floorplan is None:
            return False
        return self.floorplan.is_within_bounds(x, y, margin)

    def get_mouse_override(self, mouse_pos):
        mx, _ = mouse_pos
        if mx > self.floorplan.offset_x:
            return mouse_pos

    def enter(self, delay=0.0):
        self.opacity_tween.enter(delay)

    def draw(self, surface, simulation, dt, scene_data=None, show_paths=False,
             show_crosshair=False, mouse_pos=None, tool="agent", roadmap_index=0):
        fp = self.floorplan

        buffer = pygame.Surface((fp.width, fp.height), pygame.SRCALPHA)

        # Background layers
        buffer.blit(fp.bg_surface, (0, 0))
        buffer.blit(self.grid_surface, (0, 0))
        buffer.blit(fp.walls_surface, (0, 0))

        # Border
        pygame.draw.rect(buffer, (0, 0, 0),
                         pygame.Rect(0, 0, fp.width, fp.height),
                         self.BORDER_THICKNESS)

        exits = scene_data.exits  if scene_data else simulation.exits
        agents = scene_data.agents if scene_data else simulation.agents

        for exit_obj in exits:
            buffer.blit(exit_obj.image, exit_obj.rect)

        if show_paths and simulation.roadmaps:
            self.draw_roadmap(buffer, simulation, roadmap_index)

        for agent in agents:
            buffer.blit(agent.image, agent.rect)

        if show_crosshair and self.crosshair and mouse_pos:
            self.crosshair.draw(buffer, mouse_pos, tool)

        self.opacity_tween.update(dt)
        buffer.set_alpha(int(self.opacity_tween.value))
        surface.blit(buffer, (fp.offset_x, fp.offset_y))

    def draw_roadmap(self, surface, simulation, roadmap_index=0):
        roadmaps = list(simulation.roadmaps.values())
        if not roadmaps:
            return
        idx = roadmap_index % len(roadmaps)
        roadmap = roadmaps[idx]
        colour = self.ROADMAP_COLOURS[idx % len(self.ROADMAP_COLOURS)]
        for i, vertex in enumerate(roadmap.vertices):
            for j in vertex.neighbors:
                if j > i:
                    start = vertex.position
                    end = roadmap.vertices[j].position
                    pygame.draw.line(surface, colour, start, end, 1)
