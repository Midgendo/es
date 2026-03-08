"""Evacuation Simulator"""

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

def log(message, level="I"):
    if level == "D" and not DEBUG:
        return
    prefix = {"D": "DBG", "I": "", "E": "ERR"}.get(level, "")
    print(f"{datetime.now()} {prefix} {message}")


class EvacuationSimulator:
    def __init__(self):
        pygame.init()

        self.display_config = DisplayConfig()
        self.sim_config = SimulationConfig()
        self.colours = ColourScheme()

        self.screen = pygame.display.set_mode(
            (self.display_config.screen_width, self.display_config.screen_height),
        )
        pygame.display.set_caption("Evacuation Simulator")
        self.clock = pygame.time.Clock()
        self.display_config.fps = pygame.display.get_current_refresh_rate()

        self.ui_manager = pygame_gui.UIManager(
            (self.display_config.screen_width, self.display_config.screen_height),
            "ui_theme.json",
        )

        self.simulation = Simulation(self.display_config, self.sim_config, log)
        self.scene_data = SceneData(ppm=self.sim_config.pixels_per_meter)

        self.floorplan = None
        self.floorplan_filename = "wall.png"
        self.available_floorplans = FloorplanManager.get_available()

        self.ui_panel = UIPanel(
            self.ui_manager,
            self.available_floorplans,
            self.floorplan_filename,
            self.colours,
            state_getter=lambda: self.state,
        )
        self.agent_panel = AgentPanel(
            self.ui_manager,
            self.colours,
            self.sim_config,
            self.scene_data,
            state_getter=lambda: self.state,
        )
        self.sim_window = SimWindow(self.sim_config, self.colours)

        self.background = create_gradient(
            self.display_config.screen_width,
            self.display_config.screen_height,
            self.colours.bg_top,
            self.colours.bg_bottom,
        )

        self.state = AppState.LOADING
        self.tool = "agent"
        self.show_paths = False
        self.roadmap_index = 0
        self.first_load = True

        self.default_agent_type = AgentType.default(self.sim_config)
        self.editing_agent_type = self.default_agent_type
        self.last_selected_agent_index = None

    def run(self):
        self.set_state(AppState.LOADING)

        while True:
            dt = self.clock.get_time() / 1000.0

            self.handle_events()
            self.update(dt)
            self.render(dt)

            pygame.display.update()
            self.clock.tick(self.display_config.fps)

    def handle_events(self):
        for event in pygame.event.get():
            if event.type == QUIT:
                pygame.quit()
                sys.exit()

            if event.type == KEYDOWN:
                self.on_keydown(event)

            elif event.type == pygame_gui.UI_DROP_DOWN_MENU_CHANGED:
                self.on_floorplan_changed(event)

            elif event.type == pygame_gui.UI_BUTTON_PRESSED:
                self.on_button_pressed(event)

            elif event.type == pygame_gui.UI_TEXT_ENTRY_FINISHED:
                self.agent_panel.handle_text_entry_finished(event.ui_element)

            elif event.type == MOUSEBUTTONUP and self.state == AppState.EDITING:
                self.on_editing_click(event)

            elif event.type == MOUSEBUTTONDOWN:
                self.on_mouse_down(event)

            self.ui_manager.process_events(event)

    def on_keydown(self, event):
        if event.key == K_p:
            self.show_paths = not self.show_paths
            log(f"Path visibility: {'ON' if self.show_paths else 'OFF'}", "D")

        elif event.key in (K_RIGHTBRACKET, K_LEFTBRACKET):
            n = len(self.simulation.roadmaps)
            if n > 0:
                d = 1 if event.key == K_RIGHTBRACKET else -1
                self.roadmap_index = (self.roadmap_index + d) % n
                radius = list(self.simulation.roadmaps.keys())[self.roadmap_index]
                log(f"Showing roadmap {self.roadmap_index + 1}/{n} (radius {radius}px)", "D")

    def on_floorplan_changed(self, event):
        if event.ui_element != self.ui_panel.floorplan_picker:
            return
        if event.text != self.floorplan_filename:
            self.floorplan_filename = event.text
            self.set_state(AppState.LOADING)

    def on_button_pressed(self, event):
        buttons = self.ui_panel.buttons

        if event.ui_element == buttons["clear"]:
            self.scene_data.clear()

        elif event.ui_element == buttons["tool_agent"]:
            self.select_tool("agent")

        elif event.ui_element == buttons["tool_exit"]:
            self.select_tool("exit")

        elif event.ui_element == buttons["load"]:
            self.load_state()

        elif event.ui_element == buttons["save"]:
            self.save_state()

        elif event.ui_element == buttons["start"]:
            self.set_state(AppState.RUNNING)

        elif event.ui_element == buttons["pause_resume"]:
            paused = self.simulation.toggle_pause()
            buttons["pause_resume"].set_text("Resume" if paused else "Pause")

        elif event.ui_element == buttons["stop"]:
            self.set_state(AppState.EDITING)

    def select_tool(self, tool_name):
        buttons = self.ui_panel.buttons

        if tool_name == "agent":
            self.tool = "agent"
            buttons["tool_agent"].disable()
            buttons["tool_exit"].enable()
            # Restore previously selected agent card
            idx = self.last_selected_agent_index if self.last_selected_agent_index is not None else 0
            self.agent_panel.focused_index = idx
            self.editing_agent_type = self.agent_panel.cards[idx].agent_type
        else:
            self.tool = "exit"
            buttons["tool_exit"].disable()
            buttons["tool_agent"].enable()
            self.last_selected_agent_index = self.agent_panel.focused_index
            self.agent_panel.focused_index = None

    def on_mouse_down(self, event):
        if self.state == AppState.EDITING:
            if self.agent_panel.handle_click(event.pos):
                idx = self.agent_panel.focused_index
                if idx is not None and idx < len(self.agent_panel.cards):
                    self.editing_agent_type = self.agent_panel.cards[idx].agent_type

                # Auto-switch back to agent tool if user clicks an agent card while in exit mode
                if self.tool == "exit":
                    self.select_tool("agent")

    def on_editing_click(self, event):
        if self.tool != "exit":
            return
        mx, my = event.pos
        if not self.sim_window.is_within_bounds(mx, my):
            return
        if event.button == 1:
            self.scene_data.add_exit(mx, my, self.sim_config)
        elif event.button == 3:
            self.scene_data.remove_exit_at(mx, my)

    def handle_agent_placement(self):
        mx, my = pygame.mouse.get_pos()
        if not self.sim_window.is_within_bounds(mx, my):
            return
        left, _, right = pygame.mouse.get_pressed()
        if left:
            self.scene_data.add_agent(mx, my, self.editing_agent_type)
        elif right:
            self.scene_data.remove_agent_at(mx, my)

    def set_state(self, new_state):
        self.state = new_state
        log(f"State → {new_state.name}", "D")

        self.ui_panel.hide_all_buttons()

        if new_state == AppState.LOADING:
            self.scene_data.clear()
            self.load_floorplan()
            self.set_state(AppState.EDITING)
            # Startup animations
            if self.first_load:
                self.sim_window.enter(delay=0.15)
                self.ui_panel.enter(delay=0.25)
                self.agent_panel.enter(delay=0.35)
                self.agent_panel.add_agent_type(self.default_agent_type)
                self.first_load = False


        elif new_state == AppState.EDITING:
            self.simulation.reset()
            self.tool = "agent"
            self.agent_panel.focused_index = 0
            self.editing_agent_type = self.default_agent_type
            self.ui_panel.show_editing_buttons()

        elif new_state == AppState.RUNNING:
            self.copy_scene_to_simulation()
            self.simulation.start()
            self.ui_panel.show_running_buttons()
            self.last_selected_agent_index = self.agent_panel.focused_index
            self.agent_panel.focused_index = None

        elif new_state == AppState.COMPLETED:
            self.ui_panel.show_completed_buttons()
            self.last_selected_agent_index = self.agent_panel.focused_index
            self.agent_panel.focused_index = None
            log(f"All agents evacuated in {self.simulation.time:.3f}s")

    def copy_scene_to_simulation(self):
        self.simulation.agents.empty()
        self.simulation.exits.empty()
        for agent in self.scene_data.agents:
            self.simulation.agents.add(agent.copy())
        for exit_obj in self.scene_data.exits:
            self.simulation.exits.add(exit_obj.copy())

    def load_floorplan(self):
        if self.floorplan_filename not in self.available_floorplans:
            self.floorplan_filename = self.available_floorplans[0]

        # Apply per-floorplan PPM
        old_ppm = self.sim_config.pixels_per_meter
        self.sim_config.pixels_per_meter = FloorplanManager.get_pixels_per_meter(
            self.floorplan_filename, self.sim_config.pixels_per_meter,
        )
        if self.sim_config.pixels_per_meter != old_ppm:
            self.scene_data.update_ppm(self.sim_config.pixels_per_meter)
            self.agent_panel.pixels_per_meter = self.sim_config.pixels_per_meter

        # Initialise RVO and pass floorplan for extracting geometry
        self.simulation.initialize_rvo()
        self.floorplan = Floorplan(
            self.floorplan_filename, self.display_config, self.sim_config, self.colours,
        )
        self.floorplan.load(self.simulation.rvo_sim)
        self.simulation.rvo_sim.process_obstacles()

        self.simulation.set_floorplan(self.floorplan)
        self.sim_window.update_floorplan(self.floorplan)
        self.scene_data.set_floorplan(self.floorplan)

        log(f"Loaded floorplan: {self.floorplan_filename}")

    def state_filename(self):
        base = self.floorplan_filename.rsplit(".", 1)[0]
        return os.path.join("floorplans", f"{base}-state.json")

    def load_state(self):
        state_loading.load_to_scene(
            self.scene_data, self.state_filename(),
            self.sim_config, log,
        )
        self.agent_panel.sync_from_scene(self.scene_data, self.default_agent_type)

        # Update default type & select the first card
        self.editing_agent_type = self.default_agent_type = self.agent_panel.cards[0].agent_type
        self.select_tool("agent")

    def save_state(self):
        state_loading.save_from_scene(
            self.scene_data, self.state_filename(),
            self.sim_config.pixels_per_meter, self.floorplan_filename, log,
        )

    def update(self, dt):
        self.ui_manager.update(dt)

        if self.state == AppState.EDITING:
            if self.tool == "agent":
                self.handle_agent_placement()

        elif self.state == AppState.RUNNING:
            mouse_override = None
            if pygame.mouse.get_pressed()[0]:
                mouse_override = self.sim_window.get_mouse_override(pygame.mouse.get_pos())

            if self.simulation.update(dt, mouse_override):
                self.set_state(AppState.COMPLETED)

    def render(self, dt):
        self.screen.blit(self.background, (0, 0))

        if self.state == AppState.EDITING:
            num_agents = len(self.scene_data.agents)
            evacuated = 0
        else:
            num_agents = self.simulation.agent_count + self.simulation.evacuated_count
            evacuated = self.simulation.evacuated_count

        self.ui_panel.draw(
            self.screen,
            self.state.name,
            self.clock.get_fps(),
            dt,
            self.simulation.time,
            self.simulation.simulation_time,
            num_agents,
            evacuated,
        )
        self.agent_panel.draw(self.screen, dt)

        show_crosshair = (
            self.state == AppState.EDITING
            and (pygame.mouse.get_pressed()[0] or pygame.mouse.get_pressed()[2])
        )
        mouse_pos = pygame.mouse.get_pos() if show_crosshair else None

        scene = self.scene_data if self.state == AppState.EDITING else None
        self.sim_window.draw(
            self.screen,
            self.simulation,
            dt,
            scene_data=scene,
            show_paths=self.show_paths,
            show_crosshair=show_crosshair,
            mouse_pos=mouse_pos,
            tool=self.tool,
            roadmap_index=self.roadmap_index,
        )

        self.ui_manager.draw_ui(self.screen)


if __name__ == "__main__":
    app = EvacuationSimulator()
    app.run()
