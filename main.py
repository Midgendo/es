import sys
import os
from datetime import datetime

import pygame
from pygame.locals import *
import pygame_gui

from config import DisplayConfig, SimulationConfig, ColourScheme, AgentType, AppState
from floorplan import Floorplan, FloorplanManager
from simulation import Simulation
from ui import UIPanel, SimWindow, SceneData, create_gradient
from agent_ui import AgentPanel
import state_loading


DEBUG = True


def log(message, level='I'):
    timestamp = datetime.now()
    if level == 'D' and not DEBUG:
        return
    prefix = {'D': 'DBG', 'I': '', 'E': 'ERR'}.get(level, '')
    print(f"{timestamp} {prefix} {message}")


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
        self.scene_data = SceneData(ppm=self.sim_config.pixels_per_meter)
        self.floorplan = None
        self.floorplan_filename = "wall.png"
        
        self.available_floorplans = FloorplanManager.get_available()
        
        self.ui_panel = UIPanel(
            self.ui_manager,
            self.available_floorplans,
            self.floorplan_filename,
            self.colours
        )
        self.agent_panel = AgentPanel(
            self.ui_manager, 
            self.sim_config.pixels_per_meter, 
            self.colours, 
            sim_config=self.sim_config,
            scene_data=self.scene_data,
            state_getter=lambda: self.state
        )
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
                    idx = self.agent_panel.focused_index
                    if idx is not None and idx < len(self.agent_panel.cards):
                        self.editing_agent_type = self.agent_panel.cards[idx].agent_type
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
            self.scene_data.clear()
            
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
            self._set_state(AppState.RUNNING)
            
        elif event.ui_element == buttons["pause_resume"]:
            paused = self.simulation.toggle_pause()
            buttons["pause_resume"].set_text("Resume" if paused else "Pause")
            
        elif event.ui_element == buttons["stop"]:
            self.simulation.reset()
            self._set_state(AppState.EDITING, reset_sim=False)
            
    def _handle_editing_click(self, event):
        mx, my = event.pos
        
        if not self.sim_window.is_within_bounds(mx, my, self.sim_config.agent_size):
            return
            
        if event.button == 1:
            if self.tool == "agent":
                self.scene_data.add_agent(mx, my, self.editing_agent_type)
            else:
                self.scene_data.add_exit(mx, my, self.sim_config)
                
        elif event.button == 3:
            if self.tool == "agent":
                self.scene_data.remove_agent_at(mx, my)
            else:
                self.scene_data.remove_exit_at(mx, my)
                
    def _load_state(self):
        filename = os.path.join(
            "floorplans",
            f"{self.floorplan_filename.rsplit('.', 1)[0]}-state.json"
        )
        state_loading.load_to_scene(
            self.scene_data,
            filename,
            self.sim_config,
            self.floorplan,
            log
        )
        
    def _save_state(self):
        filename = os.path.join(
            "floorplans",
            f"{self.floorplan_filename.rsplit('.', 1)[0]}-state.json"
        )
        state_loading.save_from_scene(
            self.scene_data,
            filename,
            self.sim_config.pixels_per_meter,
            self.floorplan_filename,
            log
        )
        
    def _set_state(self, new_state, reset_sim=True):
        self.state = new_state
        log(f"State changed to: {new_state.name}", 'D')
        
        self.ui_panel.hide_all_buttons()
        
        if new_state == AppState.LOADING:
            self.scene_data.clear()
            self._load_floorplan()
            self._set_state(AppState.EDITING)
            
        elif new_state == AppState.EDITING:
            if reset_sim:
                self.simulation.reset(False)
            self.tool = "agent"
            
            self.agent_panel.focused_index = 0
            self.editing_agent_type = self.default_agent_type
            
            self.ui_panel.show_editing_buttons()
            
        elif new_state == AppState.RUNNING:
            self.simulation.agents.empty()
            self.simulation.exits.empty()
            for agent in self.scene_data.agents:
                self.simulation.agents.add(agent.copy())
            for exit_obj in self.scene_data.exits:
                self.simulation.exits.add(exit_obj.copy())
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
        new_ppm = self.sim_config.pixels_per_meter
        
        if new_ppm != old_ppm:
            self.scene_data.update_ppm(new_ppm)
            self.agent_panel.pixels_per_meter = new_ppm

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
        self.scene_data.set_floorplan(self.floorplan)
        
        if self._first_load:
            self.ui_panel.enter(delay=0.25)
            self.agent_panel.enter(delay=0.35)
            self.agent_panel._add_agent_type(self.default_agent_type)

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
        
        if self.state == AppState.EDITING:
            num_agents = len(self.scene_data.agents)
            evacuated = 0
        else:
            num_agents = self.simulation.agent_count + self.simulation.evacuated_count
            evacuated = self.simulation.evacuated_count
        
        self.ui_panel.draw(
            self.screen,
            state_str,
            self.clock.get_fps(),
            dt,
            self.simulation.time,
            self.simulation.simulation_time,
            num_agents,
            evacuated
        )
        self.agent_panel.draw(self.screen, dt, self.sim_config.pixels_per_meter)
        
        show_crosshair = (
            self.state == AppState.EDITING and
            (pygame.mouse.get_pressed()[0] or pygame.mouse.get_pressed()[2])
        )
        mouse_pos = pygame.mouse.get_pos() if show_crosshair else None
        
        scene = self.scene_data if self.state == AppState.EDITING else None
        self.sim_window.draw(
            self.screen,
            self.simulation,
            scene_data=scene,
            show_paths=self.show_paths,
            show_crosshair=show_crosshair,
            mouse_pos=mouse_pos,
            tool=self.tool
        )
                
        self.ui_manager.draw_ui(self.screen)
        
if __name__ == "__main__":
    app = EvacuationSimulator()
    app.run()
