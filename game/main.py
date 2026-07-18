"""
Main entry point for the hex strategy game.

Includes main menu, game configuration, and game loop.
Now uses separate strategic and tactical map layers.
"""

import sys
import pygame

# Add project root to path for imports
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from engine.hex_grid import HexCoord
from engine.tile import Tile
from engine.unit import Army, Hero
from game.units import create_lancer, create_archer, create_cavalry, create_mage
from game.heroes import create_hero
from game.map_generator import MapConfig, MapGenerator
from game.campaign_map import run_campaign
from game.strategic_map import run_strategic_game
from game.config import DEFAULT_GAME_CONFIG, UI, GameSpeed


def generate_test_map(width: int, height: int, add_river: bool = True, seed: int = None) -> dict[tuple[int, int], Tile]:
    """
    Generate a map using the layered terrain generator.

    Args:
        width: Map width in hexes
        height: Map height in hexes
        add_river: Whether to add a river
        seed: Random seed for reproducibility (None = random)

    Returns:
        Dictionary mapping (q, r) to Tile objects
    """
    config = MapConfig(
        width=width,
        height=height,
        seed=seed,
        add_river=add_river,
        river_count=max(1, width // 50),       # More rivers for bigger maps
        river_min_width=1,
        river_max_width=3,
        forest_density=0.30,
        mountain_density=0.08,
        mountain_cluster_size=12,              # ~10-12 hex clusters
        add_lakes=True,
        lake_count=max(2, width // 40),
        swamp_near_water=True,
        add_cities=True,
        add_roads=True,
        add_bridges=True,
    )

    generator = MapGenerator(config)
    return generator.generate()


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
        if coord[0] < mid_q - 1 and tiles[coord].get_movement_cost() > 0
    ]

    # Player 2 positions (right side)
    player2_positions = [
        coord for coord in tile_list
        if coord[0] > mid_q + 1 and tiles[coord].get_movement_cost() > 0
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


def create_test_heroes(tiles: dict, armies: list) -> list[Hero]:
    """Create test heroes for both players."""
    heroes = []
    tile_list = list(tiles.keys())

    # Get map bounds
    min_q = min(c[0] for c in tile_list)
    max_q = max(c[0] for c in tile_list)
    mid_q = (min_q + max_q) // 2

    # Find passable positions for heroes
    player1_positions = [
        coord for coord in tile_list
        if coord[0] < mid_q - 5 and tiles[coord].get_movement_cost() > 0
        and tiles[coord].unit is None
    ]
    player2_positions = [
        coord for coord in tile_list
        if coord[0] > mid_q + 5 and tiles[coord].get_movement_cost() > 0
        and tiles[coord].unit is None
    ]

    # Create Player 1 heroes
    hero_configs = [
        ("Sir Roland", "Paladin", 0, 3),
        ("Elena", "Scout", 0, 2),
    ]

    for i, (name, hero_class, player_id, level) in enumerate(hero_configs):
        if i < len(player1_positions):
            hero = create_hero(name, hero_class, player_id, level)
            pos = player1_positions[i * len(player1_positions) // max(len(hero_configs), 1)]
            hero.position = HexCoord(*pos)
            heroes.append(hero)

    # Create Player 2 heroes
    hero_configs_p2 = [
        ("Lord Vexar", "Commander", 1, 3),
        ("Shadow", "Scout", 1, 2),
    ]

    for i, (name, hero_class, player_id, level) in enumerate(hero_configs_p2):
        if i < len(player2_positions):
            hero = create_hero(name, hero_class, player_id, level)
            pos = player2_positions[i * len(player2_positions) // max(len(hero_configs_p2), 1)]
            hero.position = HexCoord(*pos)
            heroes.append(hero)

    return heroes


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
        self.config = DEFAULT_GAME_CONFIG.copy()

        # UI state
        self.selected_option = 0
        self.options = [
            ('mode', 'Mode', ['Campagne', 'Wargame']),
            ('map_width', 'Map Width', [50, 75, 100, 150, 200]),
            ('map_height', 'Map Height', [50, 75, 100, 150, 200]),
            ('player1_armies', 'Player 1 Armies', [1, 2, 3, 4, 5, 6]),
            ('player2_armies', 'Player 2 Armies', [1, 2, 3, 4, 5, 6]),
            ('add_river', 'Add River', [True, False]),
            ('game_speed', 'Game Speed', GameSpeed.names()),
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
        self.screen.fill(UI.screen_bg_color)

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
    """
    Run the main game loop.

    Mode 'Campagne' (the pivot): character campaign on a generated WorldState.
    Mode 'Wargame': the historical strategic map with tactical battles.
    """
    if config.get('mode') == 'Campagne':
        return run_campaign(screen, config)

    # Generate strategic map
    tiles = generate_test_map(
        config['map_width'],
        config['map_height'],
        config['add_river']
    )

    # Create armies
    armies = create_test_units(
        tiles,
        config['player1_armies'],
        config['player2_armies']
    )

    # Create heroes
    heroes = create_test_heroes(tiles, armies)

    # Run strategic game (handles tactical battles internally)
    return run_strategic_game(screen, tiles, armies, config, heroes)


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
