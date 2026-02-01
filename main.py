import sys
import os
from datetime import datetime
from enum import Enum, auto

import pygame
from pygame.locals import *
import pygame_gui

from config import DisplayConfig, SimulationConfig, ColourScheme, AgentType
from floorplan import Floorplan, FloorplanManager
from simulation import Simulation
from ui import UIPanel, AgentPanel, SimWindow, create_gradient
import state_loading


DEBUG = True


def log(message, level='I'):
    timestamp = datetime.now()
    if level == 'D' and not DEBUG:
        return
    prefix = {'D': 'DBG', 'I': '', 'E': 'ERR'}.get(level, '')
    print(f"{timestamp} {prefix} {message}")


class AppState(Enum):
    LOADING = auto()
    EDITING = auto()
    RUNNING = auto()
    COMPLETED = auto()


class EvacuationSimulator:
    def __init__(self):
        pygame.init()
        
        self.display_config = DisplayConfig()
        self.sim_config = SimulationConfig()
        self.colours = ColourScheme()
        
        self.screen = pygame.display.set_mode(
            (self.display_config.screen_width, self.display_config.screen_height)
        )
        pygame.display.set_caption("Evacuation Simulator")
        
        self.clock = pygame.time.Clock()
        self.display_config.fps = pygame.display.get_current_refresh_rate()
        
        self.ui_manager = pygame_gui.UIManager(
            (self.display_config.screen_width, self.display_config.screen_height),
            'ui_theme.json'
        )
        
        self.simulation = Simulation(self.display_config, self.sim_config)
        self.floorplan = None
        self.floorplan_filename = "wall.png"
        
        self.available_floorplans = FloorplanManager.get_available()
        
        self.ui_panel = UIPanel(
            self.ui_manager,
            self.available_floorplans,
            self.floorplan_filename,
            self.colours
        )
        self.agent_panel = AgentPanel(self.ui_manager, self.sim_config.pixels_per_meter, self.colours, simulation=self.simulation)
        self.sim_window = SimWindow(self.sim_config, self.colours)
        
        self.background = create_gradient(
            self.display_config.screen_width,
            self.display_config.screen_height,
            self.colours.bg_top,
            self.colours.bg_bottom
        )
        
        self.state = AppState.LOADING
        self.tool = "agent"
        self.show_paths = False
        self._first_load = True
        
        self.default_agent_type = AgentType.default(self.sim_config)
        self.editing_agent_type = self.default_agent_type
        self.last_selected_agent_index = None
        
    def run(self):
        self._set_state(AppState.LOADING)
        
        while True:
            dt = self.clock.get_time() / 1000.0
            
            self._handle_events()
            self._update(dt)
            self._render(dt)
            
            pygame.display.update()
            self.clock.tick(self.display_config.fps)
            
    def _handle_events(self):
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()
                
            if event.type == KEYDOWN:
                self._handle_keydown(event)
                
            if event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
                if event.ui_element == self.ui_panel.floorplan_picker:
                    new_floorplan = event.text
                    if new_floorplan != self.floorplan_filename:
                        self.floorplan_filename = new_floorplan
                        self._set_state(AppState.LOADING)
                        
            if event.type == pygame_gui.UI_BUTTON_PRESSED:
                self._handle_button_press(event)

            if event.type == pygame_gui.UI_TEXT_ENTRY_FINISHED:
                self.agent_panel.handle_text_entry_finished(event.ui_element)
                
            if event.type == MOUSEBUTTONUP and self.state == AppState.EDITING:
                self._handle_editing_click(event)
                
            if event.type == MOUSEBUTTONDOWN:
                self.agent_panel.handle_outside_click(event.pos)
                if self.agent_panel.handle_click(event.pos):
                    self.editing_agent_type = self.agent_panel.cards[self.agent_panel.focused_index].agent_type
                    if self.tool == "exit":
                        self.tool = "agent"
                        buttons = self.ui_panel.buttons
                        buttons["tool_agent"].disable()
                        buttons["tool_exit"].enable()
            
            self.ui_manager.process_events(event)
            
    def _handle_keydown(self, event):
        if event.key == K_p:
            self.show_paths = not self.show_paths
            log(f"Path visibility: {'ON' if self.show_paths else 'OFF'}", 'D')
            
    def _handle_button_press(self, event):
        buttons = self.ui_panel.buttons
        
        if event.ui_element == buttons["clear"]:
            self.simulation.reset()
            
        elif event.ui_element == buttons["tool_agent"]:
            self.tool = "agent"
            buttons["tool_agent"].disable()
            buttons["tool_exit"].enable()
            if self.last_selected_agent_index is not None:
                self.agent_panel.focused_index = self.last_selected_agent_index
                self.editing_agent_type = self.agent_panel.cards[self.last_selected_agent_index].agent_type
            else:
                self.agent_panel.focused_index = 0
                self.editing_agent_type = self.agent_panel.cards[0].agent_type
            
        elif event.ui_element == buttons["tool_exit"]:
            self.tool = "exit"
            buttons["tool_exit"].disable()
            buttons["tool_agent"].enable()
            self.last_selected_agent_index = self.agent_panel.focused_index
            self.agent_panel.focused_index = None
            
        elif event.ui_element == buttons["load"]:
            self._load_state()
            
        elif event.ui_element == buttons["save"]:
            self._save_state()
            
        elif event.ui_element == buttons["start"]:
            self._save_state(memory=True)
            self._set_state(AppState.RUNNING)
            
        elif event.ui_element == buttons["pause_resume"]:
            paused = self.simulation.toggle_pause()
            buttons["pause_resume"].set_text("Resume" if paused else "Pause")
            
        elif event.ui_element == buttons["stop"]:
            self._set_state(AppState.EDITING, reset_sim=False)
            self._load_state(memory=True)
            self.simulation.reset_run_state()
            self.simulation.rebuild_roadmap()
            
    def _handle_editing_click(self, event):
        mx, my = event.pos
        
        if not self.sim_window.is_within_bounds(mx, my, self.sim_config.agent_size):
            return
            
        if event.button == 1:
            if self.tool == "agent":
                self.simulation.add_agent(mx, my, self.editing_agent_type)
            else:
                self.simulation.add_exit(mx, my)
                
        elif event.button == 3:
            if self.tool == "agent":
                self.simulation.remove_agent_at(mx, my)
            else:
                self.simulation.remove_exit_at(mx, my)
                
    def _load_state(self, memory=False):
        if not memory:
            filename = os.path.join(
                "floorplans",
                f"{self.floorplan_filename.rsplit('.', 1)[0]}-state.json"
            )
        else:
            filename = ""
        agent_count, success = state_loading.load(
            self.simulation.agents,
            self.simulation.exits,
            filename,
            self.sim_config.pixels_per_meter,
            self.sim_config.agent_size,
            self.sim_config.max_speed,
            self.sim_config.pixels_per_meter,
            self.floorplan.offset_x,
            self.floorplan.offset_y,
            self._create_agent_from_data,
            self._create_exit_from_data,
            log,
            memory=memory
        )
        if success and not memory:
            self.simulation.rebuild_roadmap()
            
    def _create_agent_from_data(self, x, y, speed, radius, colour, offset_x, offset_y,agent_type):
        from sprites import Agent
        agent_type = AgentType(
            speed=speed,
            radius=radius,
            colour=tuple(colour),
            neighbor_dist=self.sim_config.neighbor_dist * self.sim_config.pixels_per_meter,
            max_neighbors=self.sim_config.max_neighbors,
            time_horizon=self.sim_config.time_horizon,
            time_horizon_obst=self.sim_config.time_horizon_obst,
            name=agent_type
        )
        return Agent(x, y, agent_type, offset_x, offset_y)
        
    def _create_exit_from_data(self, x, y, number, radius, colour, offset_x, offset_y):
        from sprites import Exit
        return Exit(x, y, number, radius, tuple(colour), offset_x, offset_y)
        
    def _save_state(self, memory=False):
        if not memory:
            filename = os.path.join(
                "floorplans",
                f"{self.floorplan_filename.rsplit('.', 1)[0]}-state.json"
            )
        else:
            filename = ""
        state_loading.save(
            self.simulation.agents,
            self.simulation.exits,
            filename,
            self.sim_config.pixels_per_meter,
            self.floorplan_filename,
            log,
            memory=memory
        )
        
    def _set_state(self, new_state, reset_sim=True):
        self.state = new_state
        log(f"State changed to: {new_state.name}", 'D')
        
        self.ui_panel.hide_all_buttons()
        
        if new_state == AppState.LOADING:
            self._load_floorplan()
            self._set_state(AppState.EDITING)
            
        elif new_state == AppState.EDITING:
            if reset_sim:
                self.simulation.reset()
            self.tool = "agent"
            
            self.agent_panel.clear_cards()
            self.agent_panel._add_agent_type(self.default_agent_type)
            self.agent_panel.focused_index = 0
            self.editing_agent_type = self.default_agent_type
            
            self.ui_panel.show_editing_buttons()
            
        elif new_state == AppState.RUNNING:
            self.simulation.start()
            self.ui_panel.show_running_buttons()
            self.last_selected_agent_index = self.agent_panel.focused_index
            self.agent_panel.focused_index = None
            
        elif new_state == AppState.COMPLETED:
            self.ui_panel.show_completed_buttons()
            self.last_selected_agent_index = self.agent_panel.focused_index
            self.agent_panel.focused_index = None
            log(f"Agents evacuated in {self.simulation.time:.2f} seconds")
            
    def _load_floorplan(self):
        if self.floorplan_filename not in self.available_floorplans:
            self.floorplan_filename = self.available_floorplans[0]

        old_ppm = self.sim_config.pixels_per_meter
        self.sim_config.pixels_per_meter = FloorplanManager.get_pixels_per_meter(
            self.floorplan_filename,
            self.sim_config.pixels_per_meter
        )
        if self.sim_config.pixels_per_meter != old_ppm:
            self.default_agent_type = AgentType.default(self.sim_config)
            self.editing_agent_type = self.default_agent_type
            self.agent_panel.pixels_per_meter = self.sim_config.pixels_per_meter

        self.simulation.initialize_rvo()
            
        self.floorplan = Floorplan(
            self.floorplan_filename,
            self.display_config,
            self.sim_config,
            self.colours
        )
        self.floorplan.load(self.simulation.rvo_sim)
        self.simulation.rvo_sim.process_obstacles()
        
        self.simulation.set_floorplan(self.floorplan)
        self.sim_window.update_floorplan(self.floorplan)
        
        if self._first_load:
            self.ui_panel.enter(delay=0.25)
            self.agent_panel.enter(delay=0.35)
            self._first_load = False
        
        log(f"Loaded floorplan: {self.floorplan_filename}")
        
    def _update(self, dt):
        self.ui_manager.update(dt)
        
        if self.state == AppState.RUNNING:
            mouse_override = None
            if pygame.mouse.get_pressed()[0]:
                pos = pygame.mouse.get_pos()
                mouse_override = self.sim_window.get_mouse_override(pos)
                    
            all_evacuated = self.simulation.update(dt, mouse_override)
            if all_evacuated:
                self._set_state(AppState.COMPLETED)
                
    def _render(self, dt):
        self.screen.blit(self.background, (0, 0))
        
        state_str = self.state.name.lower()
        self.ui_panel.draw(
            self.screen,
            state_str,
            self.clock.get_fps(),
            dt,
            self.simulation.time,
            self.simulation.simulation_time,
            self.simulation.agent_count + self.simulation.evacuated_count,
            self.simulation.evacuated_count
        )
        self.agent_panel.draw(self.screen, dt, self.sim_config.pixels_per_meter)
        
        show_crosshair = (
            self.state == AppState.EDITING and
            (pygame.mouse.get_pressed()[0] or pygame.mouse.get_pressed()[2])
        )
        mouse_pos = pygame.mouse.get_pos() if show_crosshair else None
        self.sim_window.draw(
            self.screen,
            self.simulation,
            show_paths=self.show_paths,
            show_crosshair=show_crosshair,
            mouse_pos=mouse_pos,
            tool=self.tool
        )
                
        self.ui_manager.draw_ui(self.screen)
        
if __name__ == "__main__":
    app = EvacuationSimulator()
    app.run()
