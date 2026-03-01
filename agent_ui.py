"""Bottom agent-type panel"""

import pygame
import pygame_gui

from config import ColourScheme, AgentType, AppState
from ui import Fonts, create_gradient, Tween


class AgentTypeCard:
    """A single card in the agent panel representing an AgentType."""

    WIDTH = 178
    HEIGHT = 180
    CHIP_SIZE = 30

    # Preview circle scale (independent of floorplan PPM so the card looks consistent)
    PREVIEW_AGENT_PPM = 50

    @staticmethod
    def is_in_delete_chip(rx, ry):
        offset = AgentTypeCard.WIDTH - AgentTypeCard.CHIP_SIZE
        return rx >= offset and ry <= AgentTypeCard.CHIP_SIZE and ry <= rx - offset

    def __init__(self, agent_type, manager=None, colours=None):
        self.agent_type = agent_type
        self.manager = manager
        self.colours = colours

        self.size_rect = pygame.Rect()
        self.speed_rect = pygame.Rect()
        self.active_field = None   # "size" or "speed"
        self.active_input = None   # the UITextEntryLine widget
        self.prev_value = None

        self.tween = Tween(start=self.HEIGHT, end=1, duration=0.4)
        self.tween.enter()

    def handle_click(self, mx, my):
        if self.active_input is not None:
            return
        if self.size_rect.collidepoint(mx, my):
            self.open_editor("size", self.agent_type.radius_m * 2)
        elif self.speed_rect.collidepoint(mx, my):
            self.open_editor("speed", self.agent_type.speed_mps)

    def open_editor(self, field, current_value):
        self.close_editor()
        self.active_field = field
        self.prev_value = current_value
        rect = self.size_rect if field == "size" else self.speed_rect
        self.active_input = pygame_gui.elements.UITextEntryLine(
            relative_rect=rect, manager=self.manager, object_id=f"#agent_input"
        )
        self.active_input.text_length_limit = 4
        self.active_input.set_text(f"{current_value:.1f}")

    def close_editor(self):
        if self.active_input is not None:
            self.active_input.kill()
            self.active_input = None
        self.active_field = None
        self.prev_value = None

    def commit_edit(self, scene_data):
        if self.active_input is None:
            return False

        lo, hi = (0.1, 1.5) if self.active_field == "size" else (0.0, 10.0)

        try:
            value = float(self.active_input.get_text().strip())
        except ValueError:
            self.close_editor()
            return False

        if lo <= value <= hi:
            if self.active_field == "size":
                scene_data.update_agents_of_type(self.agent_type, radius_m=value / 2.0)
            else:
                scene_data.update_agents_of_type(self.agent_type, speed_mps=value)
            self.close_editor()
            return True

        self.close_editor()
        return False

    def draw(self, surface, x, y, dt, selected=False, panel_offset=(0, 0)):
        cs = self.CHIP_SIZE
        buffer = pygame.Surface((self.WIDTH, self.HEIGHT + cs), pygame.SRCALPHA)

        # Card polygon (top-right corner cut)
        points = [(0, 0), (self.WIDTH - cs, 0), (self.WIDTH, cs), (self.WIDTH, self.HEIGHT), (0, self.HEIGHT)]
        
        p_surface = pygame.Surface((60, 60), pygame.SRCALPHA)
        if selected:
            colour = (180, 180, 180, 220)
            preview_background = create_gradient(60, 60, self.colours.sim_bg_top, self.colours.sim_bg_bottom)
            p_surface.set_alpha(220)
        else:
            colour = (0, 0, 0, 150)
            preview_background = create_gradient(60, 60, (150, 150, 150), (255, 255, 255))
            p_surface.set_alpha(150)
            
        pygame.draw.polygon(buffer, colour, points)
        p_surface.blit(preview_background, (0, 0))
        
        buffer.blit(p_surface, (10, 10))

        if self.agent_type:
            at = self.agent_type

            buffer.blit(Fonts.DEFAULT.render(at.name, True, (255, 255, 255)), (80, 15))

            # Agent Preview
            preview_r = int(at.radius_m * self.PREVIEW_AGENT_PPM)
            pygame.draw.circle(buffer, at.colour, (40, 40), preview_r)

            letter = at.type_letter()
            if letter:
                glyph = pygame.font.Font(None, 24).render(letter, True, (255, 255, 255))
                buffer.blit(glyph, (40 - glyph.get_width() // 2, 40 - glyph.get_height() // 2))

            # Screen-space rects for pygame_gui inline editors
            screen_x = x + panel_offset[0]
            screen_y = y + panel_offset[1]
            BOX_Y_OFFSET, BOX_W, BOX_H = -2, 92, 22
            self.size_rect = pygame.Rect(screen_x + 80, screen_y + 34 + BOX_Y_OFFSET, BOX_W, BOX_H)
            self.speed_rect = pygame.Rect(screen_x + 80, screen_y + 50 + BOX_Y_OFFSET, BOX_W, BOX_H)

            # Size / speed labels (or inline editors)
            self.draw_field(buffer, "size",  f"Size: {at.radius_m * 2} m",  80, 34)
            self.draw_field(buffer, "speed", f"Speed: {at.speed_mps} m/s", 80, 50)
        
        y = self.tween.value
        self.tween.update(dt)
        surface.blit(buffer, (x, y))

    def draw_field(self, surface, field, label_text, text_x, text_y):
        if self.active_field == field and self.active_input is not None:
            rect = self.size_rect if field == "size" else self.speed_rect
            self.active_input.set_relative_position(rect.topleft)
            self.active_input.set_dimensions(rect.size)
        else:
            surface.blit(Fonts.AGENT_DETAILS.render(label_text, True, (255, 255, 255)), (text_x, text_y))




class AgentPanel:
    """Bottom panel holding AgentTypeCards and a '+' button."""

    X = 310
    WIDTH = 1080
    HEIGHT = 150
    LINE_SIZE = 2
    CARD_SPACING = 180
    MAX_VISIBLE = 6
    PLUS_CIRCLE_R = 30

    def __init__(self, manager, colours=None,
                 sim_config=None, scene_data=None, state_getter=None):
        self.manager = manager
        self.colours = colours
        self.sim_config = sim_config
        self.scene_data = scene_data
        self.state_getter = state_getter

        # Animation
        self.tween = Tween(start=800, end=800 - 108, duration=0.5)

        self.cards = []
        self.focused_index = None


        self.mask_surface = create_gradient(
            self.WIDTH, self.HEIGHT, (255, 255, 255), (255, 255, 255), alpha1=255, alpha2=50,
        )

    def enter(self, delay=0.0):
        self.tween.enter(delay)

    def add_agent_type(self, agent_type):
        if len(self.cards) < self.MAX_VISIBLE:
            self.cards.append(
                AgentTypeCard(agent_type=agent_type, manager=self.manager, colours=self.colours)
            )

    def delete_agent_type(self, index):
        card = self.cards[index]
        card.close_editor()
        del self.cards[index]

        if not self.cards:
            self.focused_index = None
        elif self.focused_index is not None and self.focused_index >= len(self.cards):
            self.focused_index = len(self.cards) - 1

    def clear_cards(self):
        for card in self.cards:
            card.close_editor()
        self.cards = []
        self.focused_index = None

    def sync_from_scene(self, scene_data, default_agent_type):
        self.clear_cards()

        # Collect unique types (preserving shared identity from loading)
        seen = {}
        for agent in scene_data.agents:
            if agent.agent_type.name not in seen:
                seen[agent.agent_type.name] = agent.agent_type

        self.add_agent_type(seen.get("Default", default_agent_type))
        for name in sorted(seen.keys() - {"Default"}):
            self.add_agent_type(seen[name])
        self.focused_index = 0

    def card_position(self, index):
        return (self.X + index * self.CARD_SPACING + 2, self.tween.value + 1)

    def card_rect(self, index):
        x, y = self.card_position(index)
        return pygame.Rect(x, y, AgentTypeCard.WIDTH, AgentTypeCard.HEIGHT)

    def create_next_agent_type(self):
        used = {
            c.agent_type.name.split()[1]
            for c in self.cards
            if c.agent_type.name.startswith("Type ") and len(c.agent_type.name) > 5
        }
        letter = next((chr(65 + i) for i in range(5) if chr(65 + i) not in used), None)
        if letter is None:
            return False

        cfg = self.sim_config
        colours = cfg.custom_agent_colours
        new_type = AgentType.from_config(
            cfg,
            name=f"Type {letter}",
            colour=colours[(ord(letter) - 65) % len(colours)],
        )
        self.add_agent_type(new_type)
        self.focused_index = len(self.cards) - 1
        return True

    def handle_click(self, mouse_pos):
        mx, my = mouse_pos

        # Existing cards
        for i, card in enumerate(self.cards):
            if not self.card_rect(i).collidepoint(mx, my):
                continue

            card_x, card_y = self.card_position(i)
            rx, ry = mx - card_x, my - card_y

            # Delete chip
            if AgentTypeCard.is_in_delete_chip(rx, ry):
                self.scene_data.remove_agents_of_type(card.agent_type)
                if card.agent_type.name != "Default":
                    self.delete_agent_type(i)
                return True

            # Select + possibly open inline editor
            self.focused_index = i
            card.handle_click(mx, my)
            return True

        # "+" card
        if len(self.cards) < self.MAX_VISIBLE and self.state_getter() == AppState.EDITING:
            plus_rect = pygame.Rect(
                self.X + len(self.cards) * self.CARD_SPACING, self.tween.value,
                AgentTypeCard.WIDTH, AgentTypeCard.HEIGHT,
            )
            if plus_rect.collidepoint(mx, my):
                rx, ry = mx - plus_rect.x, my - plus_rect.y
                if rx + ry <= AgentTypeCard.WIDTH:
                    return self.create_next_agent_type()

        return False

    def handle_outside_click(self, mouse_pos):
        for card in self.cards:
            if card.active_input is None:
                continue
            if card.size_rect.collidepoint(mouse_pos) or card.speed_rect.collidepoint(mouse_pos):
                return False
            card.commit_edit(self.scene_data)
            return True
        return False

    def handle_text_entry_finished(self, ui_element):
        for card in self.cards:
            if ui_element is card.active_input:
                card.commit_edit(self.scene_data)
                return True
        return False

    def draw(self, surface, dt):
        self.tween.update(dt)

        x, y = self.X, self.tween.value
        border_colour = (255, 255, 255)

        panel = pygame.Surface((self.WIDTH, self.HEIGHT), pygame.SRCALPHA)
        px, py = -x, -y

        # Panel border lines
        pygame.draw.line(panel, border_colour, (0, 0), (0, self.HEIGHT), 1)
        pygame.draw.line(panel, border_colour, (self.WIDTH - 1, 0), (self.WIDTH - 1, self.HEIGHT), 1)
        pygame.draw.line(panel, border_colour, (0, 0), (self.WIDTH, 0), 1)

        # Column dividers + chip diagonals
        for i in range(6):
            col_x = i * (self.WIDTH // 6)
            pygame.draw.line(panel, border_colour, (col_x, 0), (col_x, self.HEIGHT), self.LINE_SIZE)

            cs = AgentTypeCard.CHIP_SIZE
            diag_x = self.CARD_SPACING * (i + 1)
            pygame.draw.line(panel, border_colour, (diag_x - cs, 0), (diag_x - 1, cs - 1), self.LINE_SIZE)

        # Cards
        for i, card in enumerate(self.cards):
            card_x, card_y = self.card_position(i)
            card.draw(panel, card_x + px, card_y + py, dt,
                      selected=(i == self.focused_index), panel_offset=(x, y))

            # Delete chip "−" label
            self.draw_delete_chip(panel, card, card_x + px, card_y + py)

        # "+" card
        if len(self.cards) < self.MAX_VISIBLE and self.state_getter() == AppState.EDITING:
            self.draw_plus_card(panel)

        # Alpha mask
        panel.blit(self.mask_surface, (0, self.HEIGHT // 4), special_flags=pygame.BLEND_RGBA_MULT)
        surface.blit(panel, (x, y))

    @staticmethod
    def draw_delete_chip(panel, card, cx, cy):
        cs = card.CHIP_SIZE
        chip = pygame.Surface((cs - 3, cs - 3), pygame.SRCALPHA)
        pygame.draw.polygon(chip, (255, 0, 0, 0), [(0, 0), (cs - 3, 0), (cs - 3, cs - 3), (0, 0)])
        minus = pygame.font.Font(None, 60).render("-", True, (255, 255, 255))
        minus.set_alpha(150)
        chip.blit(minus, (12, -14))
        panel.blit(chip, (cx + card.WIDTH - cs + 3, cy + 1))

    def draw_plus_card(self, panel):
        r = self.PLUS_CIRCLE_R
        cx = len(self.cards) * self.CARD_SPACING + self.CARD_SPACING // 2
        cy = self.HEIGHT - 94

        temp = pygame.Surface((r * 2, r * 2), pygame.SRCALPHA)
        pygame.draw.circle(temp, (200, 200, 200, 150), (r, r), r, 2)

        plus = pygame.font.Font(None, 80).render("+", True, (200, 200, 200))
        plus.set_alpha(150)
        temp.blit(plus, (cx - plus.get_width() // 2 - cx + r, cy - plus.get_height() // 2 - cy + r))
        panel.blit(temp, (cx - r, cy - r))
