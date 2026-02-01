import pygame
import pygame_gui
import pytweening
from config import ColourScheme, AgentType, CustomAgentDefaults


class UIConfig:
    PANEL_WIDTH = 260
    PANEL_HEIGHT = 750
    BORDER = 25
    BUTTON_HEIGHT = 40


pygame.font.init()


class Fonts:
    DEFAULT = pygame.font.Font(None, 24)
    TITLE = pygame.font.Font(None, 40)
    TITLE.set_italic(True)
    TIMER = pygame.font.Font("DSEG7Classic-BoldItalic.ttf", 28)
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
    def __init__(self, manager, floorplan_options, current_floorplan, colours):
        self.start_pos = -UIConfig.PANEL_WIDTH - UIConfig.BORDER
        self.end_pos = UIConfig.BORDER
        self.current_pos = self.start_pos
        self.duration = 0.7
        self.tween_progress = 0.0
        self.animation_started = False
        self.animation_delay = 0.0
        
        self.colours = colours
        self.manager = manager
        
        self.floorplan_picker = pygame_gui.elements.UIDropDownMenu(
            options_list=floorplan_options,
            starting_option=current_floorplan,
            relative_rect=pygame.Rect((0, 0), (UIConfig.PANEL_WIDTH, UIConfig.BUTTON_HEIGHT)),
            manager=manager,
            object_id="#floorplan_picker"
        )
        
        half_width = (UIConfig.PANEL_WIDTH - 5) // 2
        
        self.buttons = {
            "clear": self._create_button("Clear", UIConfig.PANEL_WIDTH),
            "tool_agent": self._create_button("Agents", half_width),
            "tool_exit": self._create_button("Exits", half_width),
            "load": self._create_button("Load", half_width),
            "save": self._create_button("Save", half_width),
            "start": self._create_button("Start", UIConfig.PANEL_WIDTH),
            "pause_resume": self._create_button("Pause", UIConfig.PANEL_WIDTH),
            "stop": self._create_button("Stop", UIConfig.PANEL_WIDTH),
        }
        
    def _create_button(self, text, width):
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
    
    def _update_animation(self, dt):
        if not self.animation_started or self.tween_progress >= 1.0:
            return
        if self.animation_delay > 0:
            self.animation_delay -= dt
            return
        self.tween_progress = min(self.tween_progress + dt / self.duration, 1.0)
        eased = pytweening.easeOutQuad(self.tween_progress)
        self.current_pos = self.start_pos + (self.end_pos - self.start_pos) * eased
    
    def _update_button_positions(self, state, dt):
        self._update_animation(dt)
        
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
        self._update_button_positions(state, dt)
        x = self.current_pos
        
        panel_rect = pygame.Rect(x, UIConfig.BORDER + 80, UIConfig.PANEL_WIDTH, UIConfig.PANEL_HEIGHT - 80)
        title_gradient = create_gradient(UIConfig.PANEL_WIDTH, 80, self.colours.ui_panel, self.colours.ui_panel, 125, 255)
        surface.blit(title_gradient, (x, UIConfig.BORDER))
        pygame.draw.rect(surface, self.colours.ui_panel, panel_rect)
        
        shadow_offset = 3
        shadow_colour = (50, 50, 50)
        
        title_shadow1 = Fonts.TITLE.render("Evacuation", True, shadow_colour)
        title_shadow2 = Fonts.TITLE.render("Simulator", True, shadow_colour)
        title_text1 = Fonts.TITLE.render("Evacuation", True, self.colours.ui_text)
        title_text2 = Fonts.TITLE.render("Simulator", True, self.colours.ui_text)
        
        minutes = int(simulation_time // 60)
        seconds = int(simulation_time % 60)
        milliseconds = int((simulation_time % 1) * 1000)
        timer_text = Fonts.TIMER.render(f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}", True, (255, 165, 0))
        timer_shadow = Fonts.TIMER.render("88:88.888", True, shadow_colour)
        
        timer_bg_rect = pygame.Rect(x, 88, UIConfig.PANEL_WIDTH, timer_text.get_height() + 4)
        timer_bg_surface = pygame.Surface((timer_bg_rect.width, timer_bg_rect.height), pygame.SRCALPHA)
        pygame.draw.rect(timer_bg_surface, (0, 0, 0, 128), timer_bg_surface.get_rect())
        surface.blit(timer_bg_surface, timer_bg_rect.topleft)
        
        state_info = {
            "running": ("Running", (0, 0, 255)),
            "editing": ("Editing", (255, 100, 100)),
            "completed": ("All agents evacuated!!", (0, 255, 0))
        }
        status, status_colour = state_info.get(state, ("Unknown", (255, 255, 255)))
        
        remaining = num_agents - evacuated_agents
        
        surface.blit(title_shadow1, (x + 10 + shadow_offset, 30 + shadow_offset))
        surface.blit(title_text1, (x + 10, 30))
        surface.blit(title_shadow2, (x + 10 + shadow_offset, 55 + shadow_offset))
        surface.blit(title_text2, (x + 10, 55))
        surface.blit(timer_shadow, (x + 10 + shadow_offset, 90 + shadow_offset))
        surface.blit(timer_text, (x + 10, 90))
        surface.blit(Fonts.DEFAULT.render(status, True, status_colour), (x + 10, 125))
        surface.blit(Fonts.DEFAULT.render(f"Evacuees: {remaining}", True, self.colours.ui_text), (x + 10, 145))
        surface.blit(Fonts.DEFAULT.render(f"Evacuated: {evacuated_agents}/{num_agents}", True, self.colours.ui_text), (x + 10, 160))
        surface.blit(Fonts.DEFAULT.render(f"FPS: {int(fps)}", True, self.colours.ui_text), (x + 10, 185))
        
        instructions = {
            "editing": ["Left click to place", "Right click to remove"],
            "running": ["Click to override target"]
        }
        
        y_offset = 210
        for line in instructions.get(state, []):
            surface.blit(Fonts.DEFAULT.render(line, True, self.colours.ui_text), (x + 10, y_offset))
            y_offset += 20


class AgentTypeCard:
    WIDTH = 178
    HEIGHT = 180
    CHIP_SIZE = 30

    def __init__(self, agent_type, colour=(0, 0, 0, 150), manager=None, colours=None):
        self.agent_type = agent_type
        self.colour = colour
        self.manager = manager
        self.colours = colours or ColourScheme()
        
        self.edit_size = False
        self.edit_speed = False
        self.size_rect = pygame.Rect()
        self.speed_rect = pygame.Rect()
        self.size_input = None
        self.speed_input = None
        self._prev_size_m = None
        self._prev_speed_m = None
    
    def handle_click(self, mx, my, pixels_per_meter):
        if self.size_input is not None and self.size_rect.collidepoint(mx, my):
            return
        if self.speed_input is not None and self.speed_rect.collidepoint(mx, my):
            return
        if self.size_rect.collidepoint(mx, my):
            self._begin_edit_size(pixels_per_meter)
        elif self.speed_rect.collidepoint(mx, my):
            self._begin_edit_speed(pixels_per_meter)

    def _begin_edit_size(self, pixels_per_meter):
        self.edit_size = True
        self.edit_speed = False
        self._prev_size_m = self._get_size_meters(pixels_per_meter)
        if self.size_input is None:
            self.size_input = pygame_gui.elements.UITextEntryLine(
                relative_rect=self.size_rect,
                manager=self.manager,
                object_id="#agent_size_input"
            )
            self.size_input.text_length_limit=4
        self.size_input.set_text(f"{self._prev_size_m:.1f}")
        if self.speed_input is not None:
            self.speed_input.kill()
            self.speed_input = None

    def _begin_edit_speed(self, pixels_per_meter):
        self.edit_speed = True
        self.edit_size = False
        self._prev_speed_m = self._get_speed_meters(pixels_per_meter)
        if self.speed_input is None:
            self.speed_input = pygame_gui.elements.UITextEntryLine(
                relative_rect=self.speed_rect,
                manager=self.manager,
                object_id="#agent_speed_input"
            )
            self.speed_input.text_length_limit=4
        self.speed_input.set_text(f"{self._prev_speed_m:.1f}")
        if self.size_input is not None:
            self.size_input.kill()
            self.size_input = None

    def _get_size_meters(self, pixels_per_meter):
        return (self.agent_type.radius * 2) / pixels_per_meter

    def _get_speed_meters(self, pixels_per_meter):
        return self.agent_type.speed / pixels_per_meter

    def commit_edits(self, simulation, pixels_per_meter):
        committed = False
        if self.edit_size and self.size_input is not None:
            raw = self.size_input.get_text().strip()
            try:
                value = float(raw)
            except ValueError:
                value = None
            if value is not None and 0.1 <= value <= 2.0:
                radius_px = (value / 2.0) * pixels_per_meter
                simulation.update_agents_of_type(self.agent_type, radius=radius_px)
                committed = True
            else:
                if self._prev_size_m is not None:
                    self.size_input.set_text(f"{self._prev_size_m:.1f}")
            self.size_input.kill()
            self.size_input = None
            self.edit_size = False

        if self.edit_speed and self.speed_input is not None:
            raw = self.speed_input.get_text().strip()
            try:
                value = float(raw)
            except ValueError:
                value = None
            if value is not None and 0.0 <= value <= 10.0:
                speed_px = value * pixels_per_meter
                simulation.update_agents_of_type(self.agent_type, speed=speed_px)
                committed = True
            else:
                if self._prev_speed_m is not None:
                    self.speed_input.set_text(f"{self._prev_speed_m:.1f}")
            self.speed_input.kill()
            self.speed_input = None
            self.edit_speed = False

        return committed
            

    def draw(self, surface, x, y, pixels_per_meter, selected=False):
        points = [
            (0, 0),
            (self.WIDTH - self.CHIP_SIZE, 0),
            (self.WIDTH, self.CHIP_SIZE),
            (self.WIDTH, self.HEIGHT),
            (0, self.HEIGHT)
        ]
        temp_surface = pygame.Surface((int(self.WIDTH), int(self.HEIGHT + self.CHIP_SIZE)), pygame.SRCALPHA)
        card_colour = (180, 180, 180, 220) if selected else self.colour
        pygame.draw.polygon(temp_surface, card_colour, points)
        
        if selected:
            preview_gradient = create_gradient(
                60, 60,
                self.colours.sim_bg_top,
                self.colours.sim_bg_bottom
            )
            temp_surface.blit(preview_gradient, (10, 10))
        else:
            preview_gradient = create_gradient(
                60, 60,
                (150, 150, 150),
                (255, 255, 255)
            )
            temp_surface.set_alpha(200)
            temp_surface.blit(preview_gradient, (10, 10))
        
        surface.blit(temp_surface, (x, y))
        
        if self.agent_type:
            name = self.agent_type.name if hasattr(self.agent_type, 'name') else str(self.agent_type)
            text = Fonts.DEFAULT.render(name, True, (255, 255, 255))
            surface.blit(text, (x + 80, y + 15))
            pygame.draw.circle(
                surface, self.agent_type.colour,
                (int(x + 40), int(y + 40)),
                int(self.agent_type.radius / pixels_per_meter * 50)
            )
            
            if name.startswith("Type ") and len(name) > 5:
                letter = name.split()[1]
                letter_font = pygame.font.Font(None, 24)
                letter_text = letter_font.render(letter, True, (255, 255, 255))
                letter_x = x + 40 - letter_text.get_width() // 2
                letter_y = y + 40 - letter_text.get_height() // 2
                surface.blit(letter_text, (letter_x, letter_y))
            
            size_text = Fonts.AGENT_DETAILS.render(f"Size: {self.agent_type.radius * 2 / pixels_per_meter} m", True, (255, 255, 255))
            speed_text = Fonts.AGENT_DETAILS.render(f"Speed: {self.agent_type.speed / pixels_per_meter} m/s", True, (255, 255, 255))

            text_x = x + 80
            size_y = y + 34
            speed_y = y + 50

            box_x = x + 80
            box_y_offset = -2
            box_w = 92
            box_h = 22
            self.size_rect = pygame.Rect(box_x, size_y + box_y_offset, box_w, box_h)
            self.speed_rect = pygame.Rect(box_x, speed_y + box_y_offset, box_w, box_h)

            if self.size_input is not None:
                self.size_input.set_relative_position(self.size_rect.topleft)
                self.size_input.set_dimensions(self.size_rect.size)
            else:
                surface.blit(size_text, (text_x, size_y))

            if self.speed_input is not None:
                self.speed_input.set_relative_position(self.speed_rect.topleft)
                self.speed_input.set_dimensions(self.speed_rect.size)
            else:
                surface.blit(speed_text, (text_x, speed_y))


class AgentPanel:
    X = 310
    WIDTH = 1080
    HEIGHT = 150
    LINE_SIZE = 2
    CARD_SPACING = 180
    MAX_VISIBLE_CARDS = 6
    
    def __init__(self, manager, pixels_per_meter=50.0, colours=None, simulation = None):
        self.manager = manager
        self.pixels_per_meter = pixels_per_meter
        self.colours = colours or ColourScheme()
        self.start_pos = 800
        self.end_pos = 800 - 108
        self.current_pos = self.start_pos
        self.duration = 0.5
        self.tween_progress = 0.0
        self.animation_started = False
        self.animation_delay = 0.0
        self.cards = []
        self.focused_index = None
        self.custom_defaults = CustomAgentDefaults()
        self.simulation = simulation
    
    def enter(self, delay=0.0):
        self.animation_started = True
        self.tween_progress = 0.0
        self.animation_delay = delay

    
    def _update_animation(self, dt):
        if not self.animation_started or self.tween_progress >= 1.0:
            return
        if self.animation_delay > 0:
            self.animation_delay -= dt
            return
        self.tween_progress = min(self.tween_progress + dt / self.duration, 1.0)
        eased = pytweening.easeOutQuad(self.tween_progress)
        self.current_pos = self.start_pos + (self.end_pos - self.start_pos) * eased
    
    def _add_agent_type(self, agent_type, colour=(0, 0, 0, 150)):
        if len(self.cards) < self.MAX_VISIBLE_CARDS:
            self.cards.append(AgentTypeCard(agent_type=agent_type, colour=colour, manager=self.manager, colours=self.colours))
    
    def _delete_agent_type(self, index):
        card = self.cards[index]
        if card.size_input is not None:
            card.size_input.kill()
            card.size_input = None
        if card.speed_input is not None:
            card.speed_input.kill()
            card.speed_input = None
        del self.cards[index]
        if self.focused_index == index:
            self.focused_index = 0
            
    def clear_cards(self):
        self.cards = []
        self.focused_index = None
    
    def get_card_position(self, index):
        return (self.X + index * self.CARD_SPACING + 2, self.current_pos + 1)
    
    def handle_click(self, mouse_pos):
        mx, my = mouse_pos
        for i in range(len(self.cards)):
            card_x, card_y = self.get_card_position(i)
            if (card_x <= mx <= card_x + AgentTypeCard.WIDTH and 
                card_y <= my <= card_y + AgentTypeCard.HEIGHT):
                
                rx = mx - card_x  # relative x
                ry = my - card_y  # relative y
                
                chip_size = AgentTypeCard.CHIP_SIZE
                diagonal_offset = AgentTypeCard.WIDTH - chip_size
                in_delete_chip = (
                    rx >= diagonal_offset
                    and ry <= chip_size
                    and ry <= rx - diagonal_offset
                )
                if in_delete_chip:
                    if self.cards[i].agent_type.name == "Default":
                        return False
                    self.simulation.remove_agents(self.cards[i].agent_type)
                    self._delete_agent_type(i)
                    return True
                else:
                    if self.focused_index != i:
                        self.focused_index = i
                    self.cards[i].handle_click(mx, my, self.pixels_per_meter)
                    return True
        
        if len(self.cards) < self.MAX_VISIBLE_CARDS:
            plus_card_x = self.X + len(self.cards) * self.CARD_SPACING
            plus_card_y = self.current_pos
            
            if (plus_card_x <= mx <= plus_card_x + AgentTypeCard.WIDTH and 
                plus_card_y <= my <= plus_card_y + AgentTypeCard.HEIGHT):
                
                rx = mx - plus_card_x
                ry = my - plus_card_y
                
                if rx + ry <= AgentTypeCard.WIDTH:
                    used_letters = set()
                    for card in self.cards:
                        name = card.agent_type.name
                        if name.startswith("Type ") and len(name) > 5:
                            used_letters.add(name.split()[1])
                    
                    type_letter = None
                    for i in range(5):
                        letter = chr(65 + i)
                        if letter not in used_letters:
                            type_letter = letter
                            break
                    
                    if type_letter is None:
                        return False
                    
                    defaults = self.custom_defaults
                    colour_index = (ord(type_letter) - 65) % len(defaults.colours)
                    cfg = self.simulation.sim_config
                    neighbor_dist = cfg.neighbor_dist * self.pixels_per_meter
                    max_neighbors = cfg.max_neighbors
                    time_horizon = cfg.time_horizon
                    time_horizon_obst = cfg.time_horizon_obst
                    new_type = AgentType(
                        name=f"Type {type_letter}",
                        speed=defaults.speed_meters_per_sec * self.pixels_per_meter,
                        radius=defaults.radius_meters * self.pixels_per_meter,
                        colour=defaults.colours[colour_index],
                        neighbor_dist=neighbor_dist,
                        max_neighbors=max_neighbors,
                        time_horizon=time_horizon,
                        time_horizon_obst=time_horizon_obst
                    )
                    self._add_agent_type(new_type)
                    self.focused_index = len(self.cards) - 1
                    return True
            
        return False

    def handle_outside_click(self, mouse_pos):
        mx, my = mouse_pos
        for card in self.cards:
            if card.size_input is not None or card.speed_input is not None:
                if card.size_rect.collidepoint(mx, my):
                    return False
                if card.speed_rect.collidepoint(mx, my):
                    return False
                card.commit_edits(self.simulation, self.pixels_per_meter)
                return True
        return False

    def handle_text_entry_finished(self, ui_element):
        for card in self.cards:
            if ui_element == card.size_input or ui_element == card.speed_input:
                card.commit_edits(self.simulation, self.pixels_per_meter)
                return True
        return False

    def draw(self, surface, dt, pixels_per_meter):
        self._update_animation(dt)
        
        x, y = self.X, self.current_pos
        border_colour = (255, 255, 255)
        
        pygame.draw.line(surface, border_colour, (x, y), (x, y + self.HEIGHT), 1)
        pygame.draw.line(surface, border_colour, (x + self.WIDTH, y), (x + self.WIDTH, y + self.HEIGHT), 1)
        pygame.draw.line(surface, border_colour, (x, y), (x + self.WIDTH, y), 1)

        for i in range(6):
            pygame.draw.line(
                surface, border_colour,
                (x + i * (self.WIDTH // 6), y),
                (x + i * (self.WIDTH // 6), y + self.HEIGHT),
                self.LINE_SIZE
            )
            chip_size = AgentTypeCard.CHIP_SIZE
            pygame.draw.line(
                surface, border_colour,
                (x + (self.CARD_SPACING * (i + 1)) - chip_size, y),
                (x + (self.CARD_SPACING * (i + 1)), y + chip_size),
                self.LINE_SIZE
            )

        for i, card in enumerate(self.cards):
            card_x, card_y = self.get_card_position(i)
            is_selected = (i == self.focused_index)
            card.draw(surface, card_x, card_y, pixels_per_meter, is_selected)

            chip_size = card.CHIP_SIZE
            temp_surface = pygame.Surface((chip_size - 3, chip_size - 3), pygame.SRCALPHA)
            pygame.draw.polygon(
                temp_surface, (255, 0, 0, 0),
                [(0, 0), (chip_size - 3, 0), (chip_size - 3, chip_size - 3), (0, 0)]
            )
            minus_text = pygame.font.Font(None, 60).render("-", True, (255, 255, 255))
            minus_text.set_alpha(150)
            temp_surface.blit(minus_text, (12, -14))
            surface.blit(temp_surface, (card_x + card.WIDTH - chip_size + 3, card_y + 1))
        
        if len(self.cards) < self.MAX_VISIBLE_CARDS:
            circle_x = x + len(self.cards) * self.CARD_SPACING + self.CARD_SPACING // 2
            circle_y = y + self.HEIGHT - 90
            circle_radius = 30

            temp_surface = pygame.Surface((circle_radius * 2, circle_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(temp_surface, (200, 200, 200, 150), (circle_radius, circle_radius), circle_radius, 2)

            plus_text = pygame.font.Font(None, 80).render("+", True, (200, 200, 200))
            plus_text.set_alpha(150)
            plus_x = circle_x - plus_text.get_width() // 2
            plus_y = circle_y - plus_text.get_height() // 2
            temp_surface.blit(plus_text, (plus_x - circle_x + circle_radius, plus_y - circle_y + circle_radius))
            surface.blit(temp_surface, (circle_x - circle_radius, circle_y - circle_radius))


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
        self._build_grid()
        self._update_border_rect()
    
    def _update_border_rect(self):
        if self.floorplan is None:
            self.border_rect = None
            return
        self.border_rect = pygame.Rect(
            self.floorplan.offset_x,
            self.floorplan.offset_y,
            self.floorplan.width,
            self.floorplan.height
        )
    
    def _build_grid(self):
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
    
    def _draw_roadmap(self, surface, simulation):
        for i, vertex in enumerate(simulation.roadmap):
            for neighbor_idx in vertex.neighbors:
                if neighbor_idx > i:
                    start = self.floorplan.sim_to_screen(*vertex.position)
                    end = self.floorplan.sim_to_screen(*simulation.roadmap[neighbor_idx].position)
                    pygame.draw.line(surface, (0, 100, 255, 128), start, end, 1)
    
    def draw(self, surface, simulation, show_paths=False, show_crosshair=False, mouse_pos=None, tool="agent"):
        surface.blit(self.floorplan.walls_surface, (self.floorplan.offset_x, self.floorplan.offset_y))
        if self.grid_surface is not None:
            surface.blit(self.grid_surface, (self.floorplan.offset_x, self.floorplan.offset_y))
        if self.border_rect is not None:
            pygame.draw.rect(surface, (0, 0, 0), self.border_rect, self.BORDER_THICKNESS)

        for exit_obj in simulation.exits:
            surface.blit(exit_obj.image, exit_obj.rect)

        if show_paths and simulation.roadmap:
            self._draw_roadmap(surface, simulation)

        for agent in simulation.agents:
            surface.blit(agent.image, agent.rect)

        if show_crosshair and self.crosshair and mouse_pos:
            self.crosshair.draw(surface, mouse_pos, tool)
