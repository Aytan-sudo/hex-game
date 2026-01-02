"""
Strategic map for the hex strategy game.

Handles army movement on the large-scale map (up to 200x200).
Triggers tactical battles when armies meet.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum

import pygame

from engine.hex_grid import HexCoord, HexGrid
from engine.tile import Tile
from engine.unit import Army, Hero
from engine.camera import Camera
from engine.renderer import HexRenderer
from game.map_generator import MapConfig, MapGenerator
from game.tactical_map import run_tactical_battle, BattleReport
from game.terrain import TerrainType

# Type alias for units that can be selected on strategic map
StrategicUnit = Army | Hero


def _get_terrain_type(tile: Tile) -> TerrainType:
    """Get the TerrainType enum from a tile's terrain config."""
    name_to_type = {
        "Plains": TerrainType.PLAINS,
        "Forest": TerrainType.FOREST,
        "Mountain": TerrainType.MOUNTAIN,
        "Water": TerrainType.WATER,
        "Desert": TerrainType.DESERT,
        "Swamp": TerrainType.SWAMP,
        "Road": TerrainType.ROAD,
        "City": TerrainType.CITY,
        "Bridge": TerrainType.BRIDGE,
    }
    return name_to_type.get(tile.terrain.name, TerrainType.PLAINS)


def _get_hero_at(
    heroes: List[Hero],
    position: Tuple[int, int],
    player_id: int = None
) -> Optional[Hero]:
    """
    Get an independent hero at a specific position.

    Args:
        heroes: List of all heroes
        position: Position to check (q, r) tuple
        player_id: If specified, only return hero belonging to this player

    Returns:
        Hero at position, or None
    """
    for hero in heroes:
        if not hero.is_independent:
            continue
        if hero.position is None:
            continue
        if hero.position.to_tuple() == position:
            if player_id is None or hero.player_id == player_id:
                return hero
    return None


class StrategicGamePhase(Enum):
    """Current phase of the strategic game."""
    PLAYER_TURN = "player_turn"
    TACTICAL_BATTLE = "tactical_battle"
    GAME_OVER = "game_over"


@dataclass
class Player:
    """Represents a player in the game."""
    id: int
    name: str
    color: Tuple[int, int, int]
    is_human: bool = True


class StrategicGameState:
    """
    Manages the strategic layer of the game.

    Handles army and hero movement, city control, and triggers tactical battles.
    """

    def __init__(self, players: List[Player] = None):
        """Initialize strategic game state."""
        self.players = players or [
            Player(id=0, name="Player 1", color=(100, 100, 255), is_human=True),
            Player(id=1, name="Player 2", color=(255, 100, 100), is_human=False),
        ]

        self.turn_number = 1
        self.current_player_index = 0
        self.phase = StrategicGamePhase.PLAYER_TURN

        # Selection state - can be Army or Hero
        self.selected_unit: Optional[StrategicUnit] = None
        self.valid_moves: Set[Tuple[int, int]] = set()

        # Pending battle
        self.pending_battle: Optional[Tuple[Army, Army]] = None
        self.last_battle_report: Optional[BattleReport] = None

        # Track which units have moved this turn
        self.units_moved: Set[int] = set()

    @property
    def current_player(self) -> Player:
        """Get the current player."""
        return self.players[self.current_player_index]

    @property
    def selected_army(self) -> Optional[Army]:
        """Get selected army (for compatibility)."""
        if isinstance(self.selected_unit, Army):
            return self.selected_unit
        return None

    def start_turn(self, armies: List[Army], heroes: List[Hero] = None):
        """Start a new turn for the current player."""
        self.units_moved.clear()
        self.selected_unit = None
        self.valid_moves.clear()

        # Reset movement for current player's armies
        for army in armies:
            if army.player_id == self.current_player.id:
                army.start_turn()

        # Reset movement for current player's independent heroes
        if heroes:
            for hero in heroes:
                if hero.player_id == self.current_player.id and hero.is_independent:
                    hero.start_turn()

    def end_turn(self, armies: List[Army], heroes: List[Hero] = None):
        """End the current player's turn."""
        self.current_player_index = (self.current_player_index + 1) % len(self.players)

        if self.current_player_index == 0:
            self.turn_number += 1

        self.start_turn(armies, heroes)

    def select_unit(
        self,
        unit: Optional[StrategicUnit],
        tiles: Dict[Tuple[int, int], Tile],
        heroes: List[Hero] = None
    ):
        """Select a unit (army or hero) and calculate valid moves."""
        self.selected_unit = unit
        self.valid_moves.clear()

        if unit is None:
            return

        # Get position based on unit type
        if isinstance(unit, Hero):
            if not unit.is_independent:
                # Hero is attached to army, can't select independently
                self.selected_unit = None
                return
            position = unit.position
        else:
            position = getattr(unit, 'position', None)

        if position is None:
            self.selected_unit = None
            return

        # Only allow selecting own units
        if unit.player_id != self.current_player.id:
            self.selected_unit = None
            return

        # Calculate valid moves if unit can still move
        if unit.movement_remaining > 0:
            self.valid_moves = self._calculate_valid_moves(unit, tiles, heroes)

    def select_army(self, army: Optional[Army], tiles: Dict[Tuple[int, int], Tile]):
        """Select an army (compatibility wrapper)."""
        self.select_unit(army, tiles)

    def _calculate_valid_moves(
        self,
        unit: StrategicUnit,
        tiles: Dict[Tuple[int, int], Tile],
        heroes: List[Hero] = None
    ) -> Set[Tuple[int, int]]:
        """Calculate all valid move destinations using BFS."""
        valid = set()

        # Get starting position
        if isinstance(unit, Hero):
            start = unit.position.to_tuple()
        else:
            start = unit.position.to_tuple()

        queue = [(start, unit.movement_remaining)]
        visited = {start: unit.movement_remaining}

        is_hero = isinstance(unit, Hero)

        while queue:
            current_pos, remaining = queue.pop(0)
            current_coord = HexCoord(*current_pos)

            for neighbor in current_coord.neighbors():
                neighbor_tuple = neighbor.to_tuple()

                if neighbor_tuple not in tiles:
                    continue

                tile = tiles[neighbor_tuple]

                if not tile.is_passable:
                    continue

                move_cost = tile.get_movement_cost()
                new_remaining = remaining - move_cost

                if new_remaining < 0:
                    continue

                if neighbor_tuple in visited and visited[neighbor_tuple] >= new_remaining:
                    continue

                visited[neighbor_tuple] = new_remaining

                if is_hero:
                    # Heroes can move to empty tiles or tiles with friendly armies (to join)
                    if tile.unit is None:
                        valid.add(neighbor_tuple)
                    elif tile.unit.player_id == unit.player_id and isinstance(tile.unit, Army):
                        # Can join friendly army
                        valid.add(neighbor_tuple)
                else:
                    # Armies can move to empty tiles or enemy tiles (battle)
                    if tile.unit is None:
                        valid.add(neighbor_tuple)
                    elif tile.unit.player_id != unit.player_id:
                        valid.add(neighbor_tuple)

                # Continue exploring from empty tiles
                if tile.unit is None:
                    queue.append((neighbor_tuple, new_remaining))

        return valid

    def try_move_army(
        self,
        target: HexCoord,
        tiles: Dict[Tuple[int, int], Tile]
    ) -> Optional[Tuple[Army, Army]]:
        """
        Try to move the selected army to target position.

        Returns:
            Tuple of (attacker, defender) if battle triggered, None otherwise
        """
        if self.selected_army is None:
            return None

        target_tuple = target.to_tuple()

        if target_tuple not in self.valid_moves:
            return None

        source_tuple = self.selected_army.position.to_tuple()
        source_tile = tiles.get(source_tuple)
        target_tile = tiles.get(target_tuple)

        if source_tile is None or target_tile is None:
            return None

        # Calculate movement cost
        move_cost = self._calculate_path_cost(source_tuple, target_tuple, tiles)

        if not self.selected_army.use_movement(move_cost):
            return None

        # Check if there's an enemy army at target
        if target_tile.unit and target_tile.unit.player_id != self.selected_army.player_id:
            # Battle will be triggered
            attacker = self.selected_army
            defender = target_tile.unit

            # Move attacker to adjacent hex (battle happens at defender's position)
            # For now, keep attacker at source position until battle resolves
            return (attacker, defender)

        # Normal move (no battle)
        source_tile.unit = None
        target_tile.unit = self.selected_army
        self.selected_army.position = target

        # Update valid moves
        if self.selected_army.movement_remaining > 0:
            self.valid_moves = self._calculate_valid_moves(self.selected_army, tiles)
        else:
            self.valid_moves.clear()

        return None

    def try_move_hero(
        self,
        hero: Hero,
        target: HexCoord,
        tiles: Dict[Tuple[int, int], Tile]
    ) -> Optional[str]:
        """
        Try to move a hero to target position.

        Returns:
            Action taken: "moved", "joined_army", or None if failed
        """
        if not hero.is_independent:
            return None

        target_tuple = target.to_tuple()

        if target_tuple not in self.valid_moves:
            return None

        source_tuple = hero.position.to_tuple()
        target_tile = tiles.get(target_tuple)

        if target_tile is None:
            return None

        # Calculate movement cost
        move_cost = self._calculate_path_cost(source_tuple, target_tuple, tiles)

        if not hero.use_movement(move_cost):
            return None

        # Check if there's a friendly army at target
        if target_tile.unit and isinstance(target_tile.unit, Army):
            if target_tile.unit.player_id == hero.player_id:
                # Join the army
                if hero.join_army(target_tile.unit):
                    self.selected_unit = None
                    self.valid_moves.clear()
                    return "joined_army"
                return None

        # Normal move to empty tile
        hero.position = target

        # Update valid moves
        if hero.movement_remaining > 0:
            self.valid_moves = self._calculate_valid_moves(hero, tiles)
        else:
            self.valid_moves.clear()

        return "moved"

    def resolve_battle_aftermath(
        self,
        attacker: Army,
        defender: Army,
        report: BattleReport,
        tiles: Dict[Tuple[int, int], Tile],
        armies: List[Army]
    ):
        """Handle the aftermath of a tactical battle on the strategic map."""
        self.last_battle_report = report

        attacker_tile = tiles.get(attacker.position.to_tuple())
        defender_tile = tiles.get(defender.position.to_tuple())

        # Check if armies were eliminated
        attacker_dead = len(attacker.units) == 0
        defender_dead = len(defender.units) == 0

        if attacker_dead:
            if attacker_tile:
                attacker_tile.unit = None
            if attacker in armies:
                armies.remove(attacker)
            self.selected_army = None

        if defender_dead:
            if defender_tile:
                defender_tile.unit = None
            if defender in armies:
                armies.remove(defender)

            # If attacker won and survived, move to defender's position
            if not attacker_dead:
                if attacker_tile:
                    attacker_tile.unit = None
                defender_tile.unit = attacker
                attacker.position = HexCoord(*defender_tile.position.to_tuple())

        # Clear selection and moves
        self.selected_army = None
        self.valid_moves.clear()

    def _calculate_path_cost(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        tiles: Dict[Tuple[int, int], Tile]
    ) -> int:
        """Calculate minimum movement cost using Dijkstra."""
        import heapq

        distances = {start: 0}
        pq = [(0, start)]

        while pq:
            current_dist, current = heapq.heappop(pq)

            if current == end:
                return current_dist

            if current_dist > distances.get(current, float('inf')):
                continue

            current_coord = HexCoord(*current)

            for neighbor in current_coord.neighbors():
                neighbor_tuple = neighbor.to_tuple()

                if neighbor_tuple not in tiles:
                    continue

                tile = tiles[neighbor_tuple]
                if not tile.is_passable:
                    continue

                new_dist = current_dist + tile.get_movement_cost()

                if new_dist < distances.get(neighbor_tuple, float('inf')):
                    distances[neighbor_tuple] = new_dist
                    heapq.heappush(pq, (new_dist, neighbor_tuple))

        return 999

    def check_victory(self, armies: List[Army]) -> Optional[int]:
        """
        Check if a player has won.

        Returns:
            Player ID of winner, or None if game continues
        """
        player_armies = {}
        for army in armies:
            if army.player_id not in player_armies:
                player_armies[army.player_id] = 0
            player_armies[army.player_id] += 1

        # A player wins if they're the only one with armies
        alive_players = [pid for pid, count in player_armies.items() if count > 0]

        if len(alive_players) == 1:
            return alive_players[0]

        if len(alive_players) == 0:
            # Draw - shouldn't happen
            return None

        return None


def run_strategic_game(
    screen: pygame.Surface,
    tiles: Dict[Tuple[int, int], Tile],
    armies: List[Army],
    config: dict,
    heroes: List[Hero] = None
) -> bool:
    """
    Run the strategic game loop.

    Args:
        screen: Pygame display surface
        tiles: Map tiles
        armies: List of armies
        config: Game configuration
        heroes: List of independent heroes (optional)

    Returns:
        True to return to menu, False to quit entirely
    """
    heroes = heroes or []

    screen_width = screen.get_width()
    screen_height = screen.get_height()

    # Create camera
    camera = Camera(screen_width, screen_height)

    # Create hex grid
    hex_grid = HexGrid(hex_size=camera.hex_size, pointy_top=True)

    # Initialize game state
    game_state = StrategicGameState()
    game_state.start_turn(armies, heroes)

    player_colors = {
        0: (100, 100, 255),
        1: (255, 100, 100),
    }

    font = pygame.font.Font(None, 24)
    clock = pygame.time.Clock()

    # Button
    end_turn_button_rect = pygame.Rect(screen_width - 130, 10, 120, 35)

    # Drag state
    is_dragging = False
    drag_start_pos = (0, 0)
    drag_start_offset = (0.0, 0.0)
    drag_button = None
    drag_threshold = 5

    # State
    running = True
    show_coordinates = False
    scroll_speed = 10
    hover_hex = None
    selected_hex = None

    # Battle message timer
    battle_message = ""
    battle_message_timer = 0
    dt = 0

    while running:
        mouse_pos = pygame.mouse.get_pos()
        end_turn_hovered = end_turn_button_rect.collidepoint(mouse_pos)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return True
                elif event.key == pygame.K_c:
                    show_coordinates = not show_coordinates
                elif event.key == pygame.K_SPACE:
                    game_state.end_turn(armies, heroes)
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    if camera.zoom_in():
                        hex_grid = HexGrid(hex_size=camera.hex_size, pointy_top=True)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    if camera.zoom_out():
                        hex_grid = HexGrid(hex_size=camera.hex_size, pointy_top=True)

            elif event.type == pygame.MOUSEBUTTONDOWN:
                if event.button == 1:
                    if end_turn_hovered:
                        game_state.end_turn(armies, heroes)
                        continue

                    clicked_hex = hex_grid.pixel_to_hex(mouse_pos[0], mouse_pos[1], camera.offset)

                    if clicked_hex.to_tuple() not in tiles:
                        continue

                    tile = tiles[clicked_hex.to_tuple()]
                    clicked_tuple = clicked_hex.to_tuple()

                    # Check if moving selected unit to valid destination
                    if game_state.selected_unit and clicked_tuple in game_state.valid_moves:
                        # Handle hero movement
                        if isinstance(game_state.selected_unit, Hero):
                            hero = game_state.selected_unit
                            result = game_state.try_move_hero(hero, clicked_hex, tiles)
                            if result == "joined_army":
                                battle_message = f"{hero.name} joined {tile.unit.name}!"
                                battle_message_timer = 3.0
                            selected_hex = clicked_hex if result else selected_hex

                        # Handle army movement
                        elif game_state.selected_army:
                            battle_result = game_state.try_move_army(clicked_hex, tiles)

                            if battle_result:
                                # Trigger tactical battle
                                attacker, defender = battle_result
                                # Get terrain where battle takes place (defender's position)
                                defender_tile = tiles.get(defender.position.to_tuple())
                                battle_terrain = _get_terrain_type(defender_tile) if defender_tile else TerrainType.PLAINS
                                report = run_tactical_battle(
                                    screen, attacker, defender, player_colors,
                                    strategic_terrain=battle_terrain
                                )

                                # Handle aftermath
                                game_state.resolve_battle_aftermath(attacker, defender, report, tiles, armies)

                                # Show battle result message
                                if report.attacker_won:
                                    battle_message = f"{report.attacker_name} wins! Losses: {report.attacker_losses} vs {report.defender_losses}"
                                else:
                                    battle_message = f"{report.defender_name} wins! Losses: {report.defender_losses} vs {report.attacker_losses}"
                                battle_message_timer = 5.0

                                # Rebuild hex_grid after battle (zoom may have changed)
                                hex_grid = HexGrid(hex_size=camera.hex_size, pointy_top=True)

                                # Check victory
                                winner = game_state.check_victory(armies)
                                if winner is not None:
                                    _show_victory_screen(screen, game_state.players[winner], font)
                                    return True
                            else:
                                selected_hex = clicked_hex
                                game_state.select_unit(game_state.selected_army, tiles, heroes)

                    # Check for hero at clicked position
                    elif _get_hero_at(heroes, clicked_tuple, game_state.current_player.id):
                        hero = _get_hero_at(heroes, clicked_tuple, game_state.current_player.id)
                        game_state.select_unit(hero, tiles, heroes)
                        selected_hex = clicked_hex

                    # Select army
                    elif tile.unit and tile.unit.player_id == game_state.current_player.id:
                        game_state.select_unit(tile.unit, tiles, heroes)
                        selected_hex = clicked_hex

                    else:
                        game_state.select_unit(None, tiles, heroes)
                        selected_hex = clicked_hex

                elif event.button == 3:
                    is_dragging = True
                    drag_button = 3
                    drag_start_pos = mouse_pos
                    drag_start_offset = camera.offset

                elif event.button == 2:
                    is_dragging = True
                    drag_button = 2
                    drag_start_pos = mouse_pos
                    drag_start_offset = camera.offset

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button in (2, 3) and drag_button == event.button:
                    dx = abs(mouse_pos[0] - drag_start_pos[0])
                    dy = abs(mouse_pos[1] - drag_start_pos[1])
                    was_drag = dx > drag_threshold or dy > drag_threshold

                    if event.button == 3 and not was_drag:
                        game_state.select_unit(None, tiles, heroes)
                        selected_hex = None

                    is_dragging = False
                    drag_button = None

            elif event.type == pygame.MOUSEMOTION:
                if is_dragging:
                    dx = mouse_pos[0] - drag_start_pos[0]
                    dy = mouse_pos[1] - drag_start_pos[1]
                    camera.set_offset(
                        drag_start_offset[0] + dx,
                        drag_start_offset[1] + dy
                    )

            elif event.type == pygame.MOUSEWHEEL:
                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_CTRL:
                    if event.y > 0:
                        if camera.zoom_in():
                            hex_grid = HexGrid(hex_size=camera.hex_size, pointy_top=True)
                    elif event.y < 0:
                        if camera.zoom_out():
                            hex_grid = HexGrid(hex_size=camera.hex_size, pointy_top=True)

        # Keyboard scrolling
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            camera.move_offset(scroll_speed, 0)
        if keys[pygame.K_RIGHT]:
            camera.move_offset(-scroll_speed, 0)
        if keys[pygame.K_UP]:
            camera.move_offset(0, scroll_speed)
        if keys[pygame.K_DOWN]:
            camera.move_offset(0, -scroll_speed)

        # Update hover
        hovered = hex_grid.pixel_to_hex(mouse_pos[0], mouse_pos[1], camera.offset)
        if hovered.to_tuple() in tiles:
            hover_hex = hovered
        else:
            hover_hex = None

        # Render
        screen.fill((25, 25, 35))

        # Draw tiles
        for coord_tuple, tile in tiles.items():
            coord = HexCoord(*coord_tuple)
            center = hex_grid.hex_to_pixel(coord, camera.offset)

            # Culling
            if (center[0] < -camera.hex_size * 2 or
                center[0] > screen_width + camera.hex_size * 2 or
                center[1] < -camera.hex_size * 2 or
                center[1] > screen_height + camera.hex_size * 2):
                continue

            vertices = hex_grid.get_hex_corners(coord, camera.offset)
            color = tile.terrain.color

            # Highlights
            if coord_tuple in game_state.valid_moves:
                target_tile = tiles[coord_tuple]
                if target_tile.unit and target_tile.unit.player_id != game_state.current_player.id:
                    # Enemy - attack highlight
                    color = (255, 150, 150)
                else:
                    # Move highlight
                    color = tuple(min(255, c + 40) for c in color)

            if selected_hex and coord_tuple == selected_hex.to_tuple():
                color = (255, 255, 150)

            if hover_hex and coord_tuple == hover_hex.to_tuple():
                color = tuple(min(255, c + 20) for c in color)

            pygame.draw.polygon(screen, color, vertices)
            pygame.draw.polygon(screen, (50, 50, 60), vertices, 1)

            # Draw coordinates if enabled
            if show_coordinates and camera.hex_size >= 24:
                coord_text = font.render(f"{coord.q},{coord.r}", True, (80, 80, 80))
                text_rect = coord_text.get_rect(center=center)
                screen.blit(coord_text, text_rect)

        # Draw armies
        for army in armies:
            if not hasattr(army, 'position'):
                continue

            center = hex_grid.hex_to_pixel(army.position, camera.offset)
            x, y = int(center[0]), int(center[1])

            color = player_colors.get(army.player_id, (200, 200, 200))

            # Army marker
            radius = int(camera.hex_size * 0.5)
            pygame.draw.circle(screen, color, (x, y), radius)
            pygame.draw.circle(screen, (255, 255, 255), (x, y), radius, 2)

            # Selected highlight
            if army == game_state.selected_army:
                pygame.draw.circle(screen, (255, 255, 100), (x, y), radius + 4, 3)

            # Army letter
            letter = army.name[0].upper()
            text = font.render(letter, True, (255, 255, 255))
            text_rect = text.get_rect(center=(x, y))
            screen.blit(text, text_rect)

            # Unit count
            if camera.hex_size >= 18:
                count = army.total_unit_count
                count_text = font.render(str(count), True, (255, 255, 255))
                screen.blit(count_text, (x + radius - 5, y + radius - 5))

            # Hero indicator if army has one
            if army.hero is not None:
                hero_radius = int(camera.hex_size * 0.2)
                hero_x = x + radius - 3
                hero_y = y - radius + 3
                pygame.draw.circle(screen, (255, 215, 0), (hero_x, hero_y), hero_radius)
                pygame.draw.circle(screen, (255, 255, 255), (hero_x, hero_y), hero_radius, 1)

        # Draw independent heroes
        for hero in heroes:
            if not hero.is_independent:
                continue
            if hero.position is None:
                continue

            center = hex_grid.hex_to_pixel(hero.position, camera.offset)
            x, y = int(center[0]), int(center[1])

            # Culling
            if (x < -camera.hex_size * 2 or x > screen_width + camera.hex_size * 2 or
                y < -camera.hex_size * 2 or y > screen_height + camera.hex_size * 2):
                continue

            color = player_colors.get(hero.player_id, (200, 200, 200))

            # Hero marker (diamond shape)
            radius = int(camera.hex_size * 0.35)
            points = [
                (x, y - radius),      # top
                (x + radius, y),      # right
                (x, y + radius),      # bottom
                (x - radius, y),      # left
            ]
            pygame.draw.polygon(screen, color, points)
            pygame.draw.polygon(screen, (255, 215, 0), points, 2)  # Gold border

            # Selected highlight
            if hero == game_state.selected_unit:
                outer_radius = radius + 4
                outer_points = [
                    (x, y - outer_radius),
                    (x + outer_radius, y),
                    (x, y + outer_radius),
                    (x - outer_radius, y),
                ]
                pygame.draw.polygon(screen, (255, 255, 100), outer_points, 3)

            # Hero letter
            letter = hero.portrait_letter
            text = font.render(letter, True, (255, 255, 255))
            text_rect = text.get_rect(center=(x, y))
            screen.blit(text, text_rect)

        # UI Panels
        pygame.draw.rect(screen, (40, 40, 50), (0, 0, screen_width, 50))

        turn_text = f"Tour {game_state.turn_number}"
        player_text = game_state.current_player.name
        turn_surf = font.render(turn_text, True, (255, 255, 255))
        player_surf = font.render(player_text, True, game_state.current_player.color)
        screen.blit(turn_surf, (10, 8))
        screen.blit(player_surf, (10, 28))

        hint = font.render("Arrows/Drag: Pan | +/-: Zoom | C: Coords | Space: End Turn", True, (150, 150, 150))
        screen.blit(hint, (200, 18))

        zoom_text = font.render(f"Zoom: {camera.zoom_level_name}", True, (150, 150, 150))
        screen.blit(zoom_text, (screen_width - 280, 8))

        # End turn button
        btn_color = (80, 120, 80) if end_turn_hovered else (60, 100, 60)
        pygame.draw.rect(screen, btn_color, end_turn_button_rect, border_radius=5)
        pygame.draw.rect(screen, (100, 150, 100), end_turn_button_rect, 2, border_radius=5)
        btn_text = font.render("End Turn", True, (255, 255, 255))
        btn_rect = btn_text.get_rect(center=end_turn_button_rect.center)
        screen.blit(btn_text, btn_rect)

        # Bottom panel
        pygame.draw.rect(screen, (40, 40, 50), (0, screen_height - 60, screen_width, 60))

        if selected_hex and selected_hex.to_tuple() in tiles:
            tile = tiles[selected_hex.to_tuple()]
            info = f"Terrain: {tile.terrain.name} | Move cost: {tile.terrain.movement_cost} | Def bonus: +{tile.terrain.defense_bonus}"
            info_surf = font.render(info, True, (200, 200, 200))
            screen.blit(info_surf, (10, screen_height - 52))

            if tile.unit:
                unit = tile.unit
                unit_info = f"Army: {unit.name} | Units: {unit.total_unit_count} | Move: {unit.movement_remaining}/{unit.stats.movement}"
                if hasattr(unit, 'hero') and unit.hero:
                    unit_info += f" | Hero: {unit.hero.name} (Lv.{unit.hero.level})"
                unit_surf = font.render(unit_info, True, (255, 200, 100))
                screen.blit(unit_surf, (10, screen_height - 30))

            # Check for hero at selected position
            hero_at_pos = _get_hero_at(heroes, selected_hex.to_tuple())
            if hero_at_pos:
                hero_info = f"Hero: {hero_at_pos.name} | Class: {hero_at_pos.hero_class} | Lv.{hero_at_pos.level} | Move: {hero_at_pos.movement_remaining}/{hero_at_pos.stats.movement}"
                hero_surf = font.render(hero_info, True, (255, 215, 100))
                screen.blit(hero_surf, (10, screen_height - 30 if not tile.unit else screen_height - 10))

        if hover_hex and hover_hex.to_tuple() in tiles:
            tile = tiles[hover_hex.to_tuple()]
            hover_text = f"({hover_hex.q}, {hover_hex.r}) - {tile.terrain.name}"
            hover_surf = font.render(hover_text, True, (150, 150, 150))
            screen.blit(hover_surf, (screen_width - 250, screen_height - 52))

        # Battle message
        if battle_message_timer > 0:
            msg_surf = font.render(battle_message, True, (255, 200, 100))
            msg_rect = msg_surf.get_rect(center=(screen_width // 2, 70))
            pygame.draw.rect(screen, (40, 40, 50), msg_rect.inflate(20, 10))
            screen.blit(msg_surf, msg_rect)
            battle_message_timer -= dt

        pygame.display.flip()
        dt = clock.tick(60) / 1000.0

    return False


def _show_victory_screen(screen: pygame.Surface, winner: Player, font: pygame.font.Font):
    """Show victory screen."""
    sw, sh = screen.get_width(), screen.get_height()
    title_font = pygame.font.Font(None, 72)

    running = True
    clock = pygame.time.Clock()

    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                running = False
            elif event.type == pygame.MOUSEBUTTONDOWN:
                running = False

        screen.fill((20, 20, 30))

        # Victory text
        title = title_font.render("VICTORY!", True, winner.color)
        screen.blit(title, (sw // 2 - title.get_width() // 2, sh // 2 - 100))

        winner_text = title_font.render(f"{winner.name} wins!", True, (255, 255, 255))
        screen.blit(winner_text, (sw // 2 - winner_text.get_width() // 2, sh // 2))

        prompt = font.render("Press any key to continue...", True, (150, 150, 150))
        screen.blit(prompt, (sw // 2 - prompt.get_width() // 2, sh // 2 + 100))

        pygame.display.flip()
        clock.tick(60)
