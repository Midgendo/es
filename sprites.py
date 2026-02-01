import pygame
from shapely.geometry import Point



def has_wall_collision(sim_x, sim_y, radius, wall_polygons):
    circle = Point(sim_x, sim_y).buffer(radius)
    return any(circle.intersects(poly) for poly in wall_polygons)


def has_agent_collision(sim_pos, radius, all_agents, exclude_agent=None):
    test_circle = Point(sim_pos).buffer(radius)
    return any(
        test_circle.intersects(Point(agent.sim_pos).buffer(agent.radius))
        for agent in all_agents if agent != exclude_agent
    )


class Agent(pygame.sprite.Sprite):
    def __init__(self, x, y, agent_type, offset_x=0, offset_y=0):
        super().__init__()
        self.agent_type = agent_type
        self.radius = int(agent_type.radius)
        self.speed = agent_type.speed
        self.colour = agent_type.colour
        self.offset_x = offset_x
        self.offset_y = offset_y
        
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        self.rect = self.image.get_rect(center=(x, y))
        self.rebuild_image()
        
        self.target_pos = (x, y)
        self.sim_pos = (x - offset_x, y - offset_y)
        self.reached_threshold = 40
        self.rvo_id = None

    def rebuild_image(self):
        center = self.rect.center
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        pygame.draw.circle(self.image, self.colour, (self.radius, self.radius), self.radius)
        
        if self.agent_type.name.startswith("Type ") and len(self.agent_type.name) > 5:
            letter = self.agent_type.name.split()[1]
            font = pygame.font.Font(None, max(20, self.radius))
            letter_surface = font.render(letter, True, (255, 255, 255))
            letter_rect = letter_surface.get_rect(center=(self.radius, self.radius))
            self.image.blit(letter_surface, letter_rect)
        
        self.rect = self.image.get_rect(center=center)

    def set_preferred_velocity(self, rvo_sim):
        if self.rvo_id is None:
            return
        
        diff_x = self.target_pos[0] - self.rect.centerx
        diff_y = self.target_pos[1] - self.rect.centery
        distance = (diff_x ** 2 + diff_y ** 2) ** 0.5
        
        if distance > 1.0:
            pref_vel = (
                (diff_x / distance) * self.speed,
                (diff_y / distance) * self.speed
            )
        else:
            pref_vel = (0.0, 0.0)
            
        rvo_sim.set_agent_pref_velocity(self.rvo_id, pref_vel)
    
    def update_position(self, rvo_sim):
        if self.rvo_id is None:
            return
        
        position = rvo_sim.get_agent_position(self.rvo_id)
        self.sim_pos = (position.x, position.y)
        self.rect.center = (position.x + self.offset_x, position.y + self.offset_y)
        
    def register_with_rvo(self, rvo_sim, sim_config):
        neighbor_dist, max_neighbors, time_horizon, time_horizon_obst = self.agent_type.resolve_rvo_params(sim_config)
        self.rvo_id = rvo_sim.add_agent(
            (self.sim_pos[0], self.sim_pos[1]),
            neighbor_dist,
            max_neighbors,
            time_horizon,
            time_horizon_obst,
            self.radius,
            self.speed,
            (0.0, 0.0)
        )


class Exit(pygame.sprite.Sprite):
    def __init__(self, x, y, number, radius=20, colour=(0, 200, 0), offset_x=0, offset_y=0):
        super().__init__()
        self.radius = int(radius)
        self.colour = colour
        self.number = number
        self.offset_x = offset_x
        self.offset_y = offset_y
        
        self.image = pygame.Surface((self.radius * 2, self.radius * 2), pygame.SRCALPHA)
        self._draw_image()
        self.rect = self.image.get_rect(center=(x, y))
        self.sim_pos = (x - offset_x, y - offset_y)
        
    def _draw_image(self):
        self.image.fill((0, 0, 0, 0))
        pygame.draw.rect(self.image, self.colour, (0, 0, self.radius * 2, self.radius * 2))
        font = pygame.font.Font(None, 20)
        text = font.render(str(self.number), True, (255, 255, 255))
        text_rect = text.get_rect(center=(self.radius, self.radius))
        self.image.blit(text, text_rect)
        
    def set_number(self, number):
        self.number = number
        self._draw_image()

