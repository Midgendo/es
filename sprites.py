"""Sprite classes for agents and exits, plus collision helpers."""

import pygame
from shapely.geometry import Point


def has_wall_collision(sim_x, sim_y, radius, wall_polygons):
    circle = Point(sim_x, sim_y).buffer(radius)
    return any(circle.intersects(poly) for poly in wall_polygons)


def has_agent_collision(sim_pos, radius, all_agents, exclude_agent=None):
    test_circle = Point(sim_pos).buffer(radius)
    return any(
        test_circle.intersects(Point(agent.sim_pos).buffer(agent.radius))
        for agent in all_agents
        if agent != exclude_agent
    )


class Agent(pygame.sprite.Sprite):
    """
    A single evacuee. Wraps an AgentType with position, image and optional RVO agent handle.
    """

    REACHED_EXIT_THRESHOLD = 40 # pixels

    def __init__(self, x, y, agent_type, ppm=50.0):
        super().__init__()

        self.agent_type = agent_type
        self.ppm = ppm

        self.radius = int(agent_type.radius_px(ppm))
        self.speed = agent_type.speed_px(ppm)
        self.colour = agent_type.colour

        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.rebuild_image()

        self.target_pos = (x, y)
        self.sim_pos = (x, y)
        self.rvo_id = None

    def update_ppm(self, ppm):
        self.ppm = ppm
        self.radius = int(self.agent_type.radius_px(ppm))
        self.speed = self.agent_type.speed_px(ppm)
        self.rebuild_image()

    def rebuild_image(self):
        center = self.rect.center
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, self.colour, (self.radius, self.radius), self.radius)

        letter = self.agent_type.type_letter()
        if letter:
            font = pygame.font.Font(None, max(20, self.radius))
            glyph = font.render(letter, True, (255, 255, 255))
            self.image.blit(glyph, glyph.get_rect(center=(self.radius, self.radius)))

        self.rect = self.image.get_rect(center=center)

    def update_position(self, rvo_sim):
        if self.rvo_id is None:
            return

        pos = rvo_sim.get_agent_position(self.rvo_id)
        self.sim_pos = (pos.x, pos.y)
        self.rect.center = (pos.x, pos.y)

    def register_with_rvo(self, rvo_sim):
        nd, mn, th, tho = self.agent_type.resolve_rvo_params(self.ppm)
        self.rvo_id = rvo_sim.add_agent(
            self.sim_pos, nd, mn, th, tho,
            self.radius, self.speed, (0.0, 0.0),
        )

    def copy(self):
        return Agent(
            self.rect.centerx, self.rect.centery,
            self.agent_type,
            self.ppm,
        )


class Exit(pygame.sprite.Sprite):
    def __init__(self, x, y, number, radius=20, colour=(0, 200, 0)):
        super().__init__()

        self.radius = int(radius)
        self.colour = colour
        self.number = number

        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        self.draw_image()

        self.rect = self.image.get_rect(center=(x, y))
        self.sim_pos = (x, y)

    def draw_image(self):
        self.image.fill((0, 0, 0, 0))
        pygame.draw.rect(self.image, self.colour, (0, 0, self.radius * 2, self.radius * 2))

        font = pygame.font.Font(None, 20)
        text = font.render(str(self.number), True, (255, 255, 255))
        self.image.blit(text, text.get_rect(center=(self.radius, self.radius)))

    def set_number(self, number):
        self.number = number
        self.draw_image()

    def copy(self):
        return Exit(
            self.rect.centerx, self.rect.centery,
            self.number, self.radius, self.colour,
        )

