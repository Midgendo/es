import pygame
import pygame_gui
import pytweening
from config import ColourScheme, AgentType, CustomAgentDefaults, AppState
from ui import Fonts, create_gradient


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
        return self.agent_type.radius_m * 2

    def _get_speed_meters(self, pixels_per_meter):
        return self.agent_type.speed_mps

    def commit_edits(self, scene_data, pixels_per_meter):
        committed = False
        if self.edit_size and self.size_input is not None:
            raw = self.size_input.get_text().strip()
            try:
                value = float(raw)
            except ValueError:
                value = None
            if value is not None and 0.1 <= value <= 2.0:
                scene_data.update_agents_of_type(self.agent_type, radius_m=value / 2.0)
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
                scene_data.update_agents_of_type(self.agent_type, speed_mps=value)
                committed = True
            else:
                if self._prev_speed_m is not None:
                    self.speed_input.set_text(f"{self._prev_speed_m:.1f}")
            self.speed_input.kill()
            self.speed_input = None
            self.edit_speed = False

        return committed
            

    def draw(self, surface, x, y, pixels_per_meter, selected=False, panel_offset=(0, 0)):
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
                int(self.agent_type.radius_m * 50)  # Scale for preview
            )
            
            if name.startswith("Type ") and len(name) > 5:
                letter = name.split()[1]
                letter_font = pygame.font.Font(None, 24)
                letter_text = letter_font.render(letter, True, (255, 255, 255))
                letter_x = x + 40 - letter_text.get_width() // 2
                letter_y = y + 40 - letter_text.get_height() // 2
                surface.blit(letter_text, (letter_x, letter_y))
            
            size_text = Fonts.AGENT_DETAILS.render(f"Size: {self.agent_type.radius_m * 2} m", True, (255, 255, 255))
            speed_text = Fonts.AGENT_DETAILS.render(f"Speed: {self.agent_type.speed_mps} m/s", True, (255, 255, 255))

            text_x = x + 80
            size_y = y + 34
            speed_y = y + 50

            box_x = x + panel_offset[0] + 80
            box_y_offset = -2
            box_w = 92
            box_h = 22
            self.size_rect = pygame.Rect(box_x, size_y + panel_offset[1] + box_y_offset, box_w, box_h)
            self.speed_rect = pygame.Rect(box_x, speed_y + panel_offset[1] + box_y_offset, box_w, box_h)

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
    
    def __init__(self, manager, pixels_per_meter=50.0, colours=None, sim_config=None, scene_data=None, state_getter=None):
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
        self.sim_config = sim_config
        self.scene_data = scene_data
        self.state_getter = state_getter
        self.mask_surface = create_gradient(self.WIDTH, self.HEIGHT, (255, 255, 255), (255, 255, 255), alpha1=255, alpha2=50)
    
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
        if len(self.cards) == 0:
            self.focused_index = None
        elif self.focused_index is not None and self.focused_index >= len(self.cards):
            self.focused_index = len(self.cards) - 1
            
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
                    self.scene_data.remove_agents_of_type(self.cards[i].agent_type)
                    self._delete_agent_type(i)
                    return True
                else:
                    if self.focused_index != i:
                        self.focused_index = i
                    self.cards[i].handle_click(mx, my, self.pixels_per_meter)
                    return True
        
        # Plus card
        if len(self.cards) < self.MAX_VISIBLE_CARDS and self.state_getter() == AppState.EDITING:
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
                    cfg = self.sim_config
                    new_type = AgentType(
                        name=f"Type {type_letter}",
                        speed_mps=defaults.speed_meters_per_sec,
                        radius_m=defaults.radius_meters,
                        colour=defaults.colours[colour_index],
                        neighbor_dist_m=cfg.neighbor_dist,
                        max_neighbors=cfg.max_neighbors,
                        time_horizon=cfg.time_horizon,
                        time_horizon_obst=cfg.time_horizon_obst
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
                card.commit_edits(self.scene_data, self.pixels_per_meter)
                return True
        return False

    def handle_text_entry_finished(self, ui_element):
        for card in self.cards:
            if ui_element == card.size_input or ui_element == card.speed_input:
                card.commit_edits(self.scene_data, self.pixels_per_meter)
                return True
        return False

    def draw(self, surface, dt, pixels_per_meter):
        self._update_animation(dt)
        
        x, y = self.X, self.current_pos
        border_colour = (255, 255, 255)

        # Draw all panel content onto a temporary surface
        panel_surface = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        px, py = -x, -y  # offset to draw relative to panel origin
        
        pygame.draw.line(panel_surface, border_colour, (0, 0), (0, self.HEIGHT), 1)
        pygame.draw.line(panel_surface, border_colour, (self.WIDTH - 1, 0), (self.WIDTH - 1, self.HEIGHT), 1)
        pygame.draw.line(panel_surface, border_colour, (0, 0), (self.WIDTH, 0), 1)

        for i in range(6):
            pygame.draw.line(
                panel_surface, border_colour,
                (i * (self.WIDTH // 6), 0),
                (i * (self.WIDTH // 6), self.HEIGHT),
                self.LINE_SIZE
            )
            chip_size = AgentTypeCard.CHIP_SIZE
            pygame.draw.line(
                panel_surface, border_colour,
                ((self.CARD_SPACING * (i + 1)) - chip_size, 0),
                ((self.CARD_SPACING * (i + 1)), chip_size),
                self.LINE_SIZE
            )

        for i, card in enumerate(self.cards):
            card_x, card_y = self.get_card_position(i)
            is_selected = (i == self.focused_index)
            card.draw(panel_surface, card_x + px, card_y + py, pixels_per_meter, is_selected, panel_offset=(x, y))

            chip_size = card.CHIP_SIZE
            temp_surface = pygame.Surface((chip_size - 3, chip_size - 3), pygame.SRCALPHA)
            pygame.draw.polygon(
                temp_surface, (255, 0, 0, 0),
                [(0, 0), (chip_size - 3, 0), (chip_size - 3, chip_size - 3), (0, 0)]
            )
            minus_text = pygame.font.Font(None, 60).render("-", True, (255, 255, 255))
            minus_text.set_alpha(150)
            temp_surface.blit(minus_text, (12, -14))
            panel_surface.blit(temp_surface, (card_x + px + card.WIDTH - chip_size + 3, card_y + py + 1))

        
        # Plus card
        if len(self.cards) < self.MAX_VISIBLE_CARDS and self.state_getter() == AppState.EDITING:
            circle_x = len(self.cards) * self.CARD_SPACING + self.CARD_SPACING // 2
            circle_y = self.HEIGHT - 90
            circle_radius = 30

            temp_surface = pygame.Surface((circle_radius * 2, circle_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(temp_surface, (200, 200, 200, 150), (circle_radius, circle_radius), circle_radius, 2)

            plus_text = pygame.font.Font(None, 80).render("+", True, (200, 200, 200))
            plus_text.set_alpha(150)
            plus_x = circle_x - plus_text.get_width() // 2
            plus_y = circle_y - plus_text.get_height() // 2
            temp_surface.blit(plus_text, (plus_x - circle_x + circle_radius, plus_y - circle_y + circle_radius))
            panel_surface.blit(temp_surface, (circle_x - circle_radius, circle_y - circle_radius))

        # Apply alpha mask: multiplies per-pixel alpha so panel fades to transparent at bottom
        panel_surface.blit(self.mask_surface, (0, self.HEIGHT // 4), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(panel_surface, (x, y))
