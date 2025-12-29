"""
Main entry point for the hex strategy game.

Includes main menu, game configuration, and game loop.
"""

import sys
import random
import pygame

# Add project root to path for imports
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.hex_grid import HexCoord
from engine.tile import Tile
from engine.renderer import HexRenderer
from engine.unit import Army, Hero, UnitStats
from engine.game_state import GameState
from game.terrain import TerrainType, TERRAIN_CONFIGS
from game.units import create_lancer, create_archer, create_cavalry, create_mage


# Game configuration defaults
DEFAULT_CONFIG = {
    'map_width': 15,
    'map_height': 10,
    'player1_armies': 2,
    'player2_armies': 2,
    'add_river': True,
}

# Hex size (50% larger than original 35)
HEX_SIZE = 52.0


def generate_test_map(width: int, height: int, add_river: bool = True) -> dict[tuple[int, int], Tile]:
    """Generate a test map with varied terrain."""
    tiles = {}

    terrain_weights = [
        (TerrainType.PLAINS, 40),
        (TerrainType.FOREST, 25),
        (TerrainType.MOUNTAIN, 10),
        (TerrainType.WATER, 10),
        (TerrainType.DESERT, 10),
        (TerrainType.SWAMP, 5),
    ]

    def weighted_random_terrain() -> TerrainType:
        total = sum(w for _, w in terrain_weights)
        r = random.randint(1, total)
        cumulative = 0
        for terrain, weight in terrain_weights:
            cumulative += weight
            if r <= cumulative:
                return terrain
        return TerrainType.PLAINS

    for row in range(height):
        for col in range(width):
            q = col - (row // 2)
            r = row
            coord = HexCoord(q, r)
            terrain_type = weighted_random_terrain()
            tile = Tile(position=coord, terrain=TERRAIN_CONFIGS[terrain_type])
            tiles[coord.to_tuple()] = tile

    if add_river:
        _add_water_feature(tiles, width, height)

    return tiles


def create_test_units(tiles: dict, p1_count: int, p2_count: int) -> list[Army]:
    """Create test armies based on configuration."""
    armies = []
    tile_list = list(tiles.keys())

    # Get map bounds
    min_q = min(c[0] for c in tile_list)
    max_q = max(c[0] for c in tile_list)
    mid_q = (min_q + max_q) // 2

    # Player 1 positions (left side)
    player1_positions = [
        coord for coord in tile_list
        if coord[0] < mid_q - 1 and tiles[coord].terrain.movement_cost > 0
    ]

    # Player 2 positions (right side)
    player2_positions = [
        coord for coord in tile_list
        if coord[0] > mid_q + 1 and tiles[coord].terrain.movement_cost > 0
    ]

    # Create Player 1 armies
    unit_types = [
        ("Infantry", lambda: (create_lancer(10), create_archer(5))),
        ("Cavalry", lambda: (create_cavalry(8),)),
        ("Mixed", lambda: (create_lancer(5), create_archer(3), create_mage(2))),
    ]

    for i in range(min(p1_count, len(player1_positions))):
        name = f"Army {i+1}"
        army = Army(name, player_id=0)
        units = unit_types[i % len(unit_types)][1]()
        for unit in units:
            army.add_unit(unit)

        pos = player1_positions[i * len(player1_positions) // max(p1_count, 1)]
        tiles[pos].unit = army
        army.position = HexCoord(*pos)
        armies.append(army)

    # Create Player 2 armies
    for i in range(min(p2_count, len(player2_positions))):
        name = f"Enemy {i+1}"
        army = Army(name, player_id=1)
        units = unit_types[i % len(unit_types)][1]()
        for unit in units:
            army.add_unit(unit)

        pos = player2_positions[i * len(player2_positions) // max(p2_count, 1)]
        tiles[pos].unit = army
        army.position = HexCoord(*pos)
        armies.append(army)

    return armies


def _add_water_feature(tiles: dict, width: int, height: int):
    """Add a river to the map."""
    current_col = width // 4
    for row in range(height):
        q = current_col - (row // 2)
        r = row
        coord = (q, r)
        if coord in tiles:
            tiles[coord] = Tile(
                position=HexCoord(q, r),
                terrain=TERRAIN_CONFIGS[TerrainType.WATER]
            )
        current_col += random.choice([-1, 0, 0, 1])
        current_col = max(0, min(width - 1, current_col))


class MainMenu:
    """Main menu screen with game configuration."""

    def __init__(self, screen: pygame.Surface, font: pygame.font.Font):
        self.screen = screen
        self.font = font
        self.title_font = pygame.font.Font(None, 72)
        self.subtitle_font = pygame.font.Font(None, 36)

        self.screen_width = screen.get_width()
        self.screen_height = screen.get_height()

        # Configuration values
        self.config = DEFAULT_CONFIG.copy()

        # UI state
        self.selected_option = 0
        self.options = [
            ('map_width', 'Map Width', [8, 10, 12, 15, 20, 25, 30]),
            ('map_height', 'Map Height', [6, 8, 10, 12, 15, 20]),
            ('player1_armies', 'Player 1 Armies', [1, 2, 3, 4, 5]),
            ('player2_armies', 'Player 2 Armies', [1, 2, 3, 4, 5]),
            ('add_river', 'Add River', [True, False]),
        ]

    def run(self) -> dict | None:
        """Run the menu loop. Returns config dict or None if quit."""
        clock = pygame.time.Clock()

        while True:
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        return None
                    elif event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                        return self.config
                    elif event.key == pygame.K_UP:
                        self.selected_option = (self.selected_option - 1) % len(self.options)
                    elif event.key == pygame.K_DOWN:
                        self.selected_option = (self.selected_option + 1) % len(self.options)
                    elif event.key == pygame.K_LEFT:
                        self._change_value(-1)
                    elif event.key == pygame.K_RIGHT:
                        self._change_value(1)

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        # Check start button
                        start_rect = self._get_start_button_rect()
                        if start_rect.collidepoint(mouse_pos):
                            return self.config

                        # Check option clicks
                        for i, (key, label, values) in enumerate(self.options):
                            left_rect, right_rect = self._get_arrow_rects(i)
                            if left_rect.collidepoint(mouse_pos):
                                self.selected_option = i
                                self._change_value(-1)
                            elif right_rect.collidepoint(mouse_pos):
                                self.selected_option = i
                                self._change_value(1)

            self._draw(mouse_pos)
            pygame.display.flip()
            clock.tick(60)

    def _change_value(self, direction: int):
        """Change the current option value."""
        key, label, values = self.options[self.selected_option]
        current = self.config[key]
        try:
            idx = values.index(current)
            new_idx = (idx + direction) % len(values)
            self.config[key] = values[new_idx]
        except ValueError:
            self.config[key] = values[0]

    def _get_start_button_rect(self) -> pygame.Rect:
        return pygame.Rect(
            self.screen_width // 2 - 100,
            self.screen_height - 120,
            200, 50
        )

    def _get_arrow_rects(self, option_idx: int) -> tuple[pygame.Rect, pygame.Rect]:
        y = 280 + option_idx * 50
        center_x = self.screen_width // 2
        left = pygame.Rect(center_x + 50, y - 15, 30, 30)
        right = pygame.Rect(center_x + 180, y - 15, 30, 30)
        return left, right

    def _draw(self, mouse_pos: tuple[int, int]):
        # Background
        self.screen.fill((20, 20, 35))

        # Title
        title = self.title_font.render("Hex Strategy Game", True, (255, 255, 255))
        title_rect = title.get_rect(center=(self.screen_width // 2, 80))
        self.screen.blit(title, title_rect)

        # Subtitle
        subtitle = self.subtitle_font.render("Game Configuration", True, (180, 180, 200))
        subtitle_rect = subtitle.get_rect(center=(self.screen_width // 2, 140))
        self.screen.blit(subtitle, subtitle_rect)

        # Options
        for i, (key, label, values) in enumerate(self.options):
            y = 280 + i * 50
            is_selected = i == self.selected_option
            color = (255, 255, 100) if is_selected else (200, 200, 200)

            # Label
            label_surf = self.font.render(f"{label}:", True, color)
            self.screen.blit(label_surf, (self.screen_width // 2 - 150, y - 10))

            # Value
            value = self.config[key]
            if isinstance(value, bool):
                value_str = "Yes" if value else "No"
            else:
                value_str = str(value)

            value_surf = self.font.render(value_str, True, (255, 255, 255))
            value_rect = value_surf.get_rect(center=(self.screen_width // 2 + 130, y))
            self.screen.blit(value_surf, value_rect)

            # Arrows
            left_rect, right_rect = self._get_arrow_rects(i)
            arrow_color = (150, 150, 200)
            if left_rect.collidepoint(mouse_pos):
                arrow_color = (200, 200, 255)
            pygame.draw.polygon(self.screen, arrow_color, [
                (left_rect.right - 5, left_rect.centery),
                (left_rect.left + 5, left_rect.top + 5),
                (left_rect.left + 5, left_rect.bottom - 5),
            ])

            arrow_color = (150, 150, 200)
            if right_rect.collidepoint(mouse_pos):
                arrow_color = (200, 200, 255)
            pygame.draw.polygon(self.screen, arrow_color, [
                (right_rect.left + 5, right_rect.centery),
                (right_rect.right - 5, right_rect.top + 5),
                (right_rect.right - 5, right_rect.bottom - 5),
            ])

        # Start button
        start_rect = self._get_start_button_rect()
        btn_color = (80, 120, 80) if start_rect.collidepoint(mouse_pos) else (60, 100, 60)
        pygame.draw.rect(self.screen, btn_color, start_rect, border_radius=8)
        pygame.draw.rect(self.screen, (100, 150, 100), start_rect, 2, border_radius=8)

        start_text = self.subtitle_font.render("Start Game", True, (255, 255, 255))
        start_text_rect = start_text.get_rect(center=start_rect.center)
        self.screen.blit(start_text, start_text_rect)

        # Instructions
        instructions = self.font.render(
            "Arrow keys to navigate | Enter to start | ESC to quit",
            True, (120, 120, 140)
        )
        inst_rect = instructions.get_rect(center=(self.screen_width // 2, self.screen_height - 40))
        self.screen.blit(instructions, inst_rect)


def run_game(screen: pygame.Surface, config: dict):
    """Run the main game loop."""
    screen_width = screen.get_width()
    screen_height = screen.get_height()

    # Create renderer using existing screen
    renderer = HexRenderer.__new__(HexRenderer)
    renderer.screen_width = screen_width
    renderer.screen_height = screen_height
    renderer.hex_size = HEX_SIZE
    renderer.title = "Hex Strategy Game"
    renderer.offset = (100.0, 100.0)
    renderer.screen = screen
    renderer.clock = pygame.time.Clock()
    renderer.font = pygame.font.Font(None, 24)
    renderer.hex_grid = __import__('engine.hex_grid', fromlist=['HexGrid']).HexGrid(
        hex_size=HEX_SIZE, pointy_top=True
    )
    renderer.selected_hex = None
    renderer.hover_hex = None

    # Generate map and units
    tiles = generate_test_map(
        config['map_width'],
        config['map_height'],
        config['add_river']
    )
    armies = create_test_units(
        tiles,
        config['player1_armies'],
        config['player2_armies']
    )

    # Initialize game state
    game_state = GameState()
    game_state.start_turn(armies)

    player_colors = {
        0: (100, 100, 255),
        1: (255, 100, 100),
    }

    # Adjust button position for fullscreen
    end_turn_button_rect = (screen_width - 130, 10, 120, 35)

    running = True
    show_coordinates = False
    scroll_speed = 10

    # Track delta time for combat message timer
    dt = 0

    while running:
        mouse_pos = pygame.mouse.get_pos()
        end_turn_hovered = pygame.Rect(end_turn_button_rect).collidepoint(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False  # Quit game entirely

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return True  # Return to menu
                elif event.key == pygame.K_c:
                    show_coordinates = not show_coordinates
                elif event.key == pygame.K_SPACE:
                    game_state.end_turn(armies)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if end_turn_hovered:
                        game_state.end_turn(armies)
                        continue

                    clicked_hex = renderer.get_hex_at_pixel(*mouse_pos)

                    if clicked_hex.to_tuple() not in tiles:
                        continue

                    tile = tiles[clicked_hex.to_tuple()]

                    # Check if clicking on valid attack target
                    if game_state.selected_unit and clicked_hex.to_tuple() in game_state.valid_attacks:
                        result = game_state.try_attack(clicked_hex, tiles, armies)
                        if result:
                            # Recalculate valid attacks after combat
                            game_state.select_unit(game_state.selected_unit, tiles)

                    # Check if clicking on valid move destination
                    elif game_state.selected_unit and clicked_hex.to_tuple() in game_state.valid_moves:
                        if game_state.try_move_unit(clicked_hex, tiles):
                            renderer.selected_hex = clicked_hex
                            # Recalculate valid attacks after move
                            game_state.select_unit(game_state.selected_unit, tiles)

                    elif tile.unit and tile.unit.player_id == game_state.current_player.id:
                        game_state.select_unit(tile.unit, tiles)
                        renderer.selected_hex = clicked_hex

                    else:
                        game_state.select_unit(None, tiles)
                        renderer.selected_hex = clicked_hex

                elif event.button == 3:
                    game_state.select_unit(None, tiles)
                    renderer.selected_hex = None

        # Scrolling
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            renderer.move_offset(scroll_speed, 0)
        if keys[pygame.K_RIGHT]:
            renderer.move_offset(-scroll_speed, 0)
        if keys[pygame.K_UP]:
            renderer.move_offset(0, scroll_speed)
        if keys[pygame.K_DOWN]:
            renderer.move_offset(0, -scroll_speed)

        # Update hover
        hover_hex = renderer.get_hex_at_pixel(*mouse_pos)
        if hover_hex.to_tuple() in tiles:
            renderer.hover_hex = hover_hex
        else:
            renderer.hover_hex = None

        # Render
        renderer.clear()
        renderer.draw_grid(tiles)

        if game_state.valid_moves:
            renderer.draw_valid_moves(game_state.valid_moves)
            if game_state.selected_unit and renderer.hover_hex:
                renderer.draw_movement_path(
                    game_state.selected_unit.position,
                    renderer.hover_hex,
                    game_state.valid_moves
                )

        # Draw valid attack targets
        if game_state.valid_attacks:
            renderer.draw_valid_attacks(game_state.valid_attacks)

        for army in armies:
            if hasattr(army, 'position'):
                color = player_colors.get(army.player_id, (200, 200, 200))
                # Get first letter of army name for display
                letter = army.name[0].upper() if army.name else "?"
                is_selected = army == game_state.selected_unit
                renderer.draw_unit_marker(
                    army.position,
                    color=color,
                    size=0.8,
                    letter=letter,
                    is_selected=is_selected
                )

        if show_coordinates:
            for coord_tuple, tile in tiles.items():
                renderer.draw_hex_coordinates(tile.position, color=(50, 50, 50))

        # UI panels
        renderer.draw_panel((0, 0, screen_width, 50))

        turn_text = f"Tour {game_state.turn_number}"
        player_text = game_state.current_player.name
        renderer.draw_text(turn_text, (10, 8), color=(255, 255, 255))
        renderer.draw_text(player_text, (10, 28), color=game_state.current_player.color)

        renderer.draw_text(
            "Arrows: Pan | C: Coords | Space: End Turn | ESC: Menu",
            (200, 18), color=(150, 150, 150)
        )

        renderer.draw_button("End Turn", end_turn_button_rect, is_hovered=end_turn_hovered)

        renderer.draw_panel((0, screen_height - 60, screen_width, 60))

        if renderer.selected_hex and renderer.selected_hex.to_tuple() in tiles:
            tile = tiles[renderer.selected_hex.to_tuple()]
            info_text = f"Terrain: {tile.terrain.name} | Move cost: {tile.terrain.movement_cost} | Def bonus: +{tile.terrain.defense_bonus}"
            renderer.draw_text(info_text, (10, screen_height - 52), color=(200, 200, 200))

            if tile.unit:
                unit = tile.unit
                unit_info = f"Unit: {unit.name} | HP: {unit.stats.current_hp}/{unit.stats.max_hp} | ATK: {unit.get_attack_power()} | DEF: {unit.get_defense_power()} | Move: {unit.movement_remaining}/{unit.stats.movement}"
                renderer.draw_text(unit_info, (10, screen_height - 30), color=(255, 200, 100))

        if renderer.hover_hex and renderer.hover_hex.to_tuple() in tiles:
            tile = tiles[renderer.hover_hex.to_tuple()]
            hover_text = f"({renderer.hover_hex.q}, {renderer.hover_hex.r}) - {tile.terrain.name}"
            renderer.draw_text(hover_text, (screen_width - 250, screen_height - 52), color=(150, 150, 150))

        # Draw combat message if active
        if game_state.combat_message_timer > 0:
            renderer.draw_combat_message(game_state.combat_message)
            game_state.combat_message_timer -= dt

        renderer.update_display()
        dt = renderer.tick(60)

    return False


def main():
    """Main entry point."""
    pygame.init()

    # Get display info for fullscreen
    display_info = pygame.display.Info()
    screen_width = display_info.current_w
    screen_height = display_info.current_h

    # Create fullscreen window
    screen = pygame.display.set_mode((screen_width, screen_height), pygame.FULLSCREEN)
    pygame.display.set_caption("Hex Strategy Game")

    font = pygame.font.Font(None, 24)

    running = True
    while running:
        # Show main menu
        menu = MainMenu(screen, font)
        config = menu.run()

        if config is None:
            # User quit from menu
            break

        # Run game with config
        return_to_menu = run_game(screen, config)

        if not return_to_menu:
            # User quit from game
            break

    pygame.quit()


if __name__ == "__main__":
    main()
