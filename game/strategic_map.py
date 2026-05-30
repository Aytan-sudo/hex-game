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
from engine.input_handler import CameraController
from engine.pathfinding import calculate_path_cost, find_path, calculate_valid_moves
from game.tactical_map import run_tactical_battle, BattleReport
from game.terrain import TerrainType
from game.config import UI, INPUT, PLAYER_COLORS, ANIMATION, AI, SPEED
from game.ai import AIPlayer, AIPersonality

# Type alias for units that can be selected on strategic map
StrategicUnit = Army | Hero


# =============================================================================
# Helper Functions
# =============================================================================

def _get_terrain_type(tile: Tile) -> TerrainType:
    """Get the TerrainType enum from a tile's base terrain."""
    return tile.base_terrain


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


# =============================================================================
# Data Classes
# =============================================================================

class StrategicGamePhase(Enum):
    """Current phase of the strategic game."""
    PLAYER_TURN = "player_turn"
    AI_TURN = "ai_turn"
    TACTICAL_BATTLE = "tactical_battle"
    GAME_OVER = "game_over"


@dataclass
class Player:
    """Represents a player in the game."""
    id: int
    name: str
    color: Tuple[int, int, int]
    is_human: bool = True
    ai_personality: Optional[AIPersonality] = None  # Only used if is_human=False


@dataclass
class MoveAnimation:
    """Tracks an ongoing movement animation.

    Le rythme est piloté par un accumulateur ``elapsed_ms`` alimenté par le
    ``dt_ms`` de la boucle (voir ``update_animation``) : la logique ne lit pas
    l'horloge murale directement (AUDIT §2.3 / reco 11).
    """
    unit: StrategicUnit
    path: List[Tuple[int, int]]  # Full path from start to end
    current_step: int = 0  # Current position in path
    elapsed_ms: float = 0.0  # Temps accumulé depuis le dernier pas
    on_complete: Optional[str] = None  # Action to perform after: "join_army", etc.

    @property
    def is_complete(self) -> bool:
        return self.current_step >= len(self.path) - 1

    @property
    def current_pos(self) -> Tuple[int, int]:
        return self.path[self.current_step]

    @property
    def target_pos(self) -> Tuple[int, int]:
        return self.path[-1]

    def advance(self) -> Tuple[int, int]:
        """Advance to next step and return new position."""
        self.current_step += 1
        self.elapsed_ms = 0.0
        return self.current_pos


# =============================================================================
# Game State
# =============================================================================

class StrategicGameState:
    """
    Manages the strategic layer of the game.

    Handles army and hero movement, city control, and triggers tactical battles.
    """

    def __init__(self, players: List[Player] = None):
        """Initialize strategic game state."""
        self.players = players or [
            Player(id=0, name="Player 1", color=PLAYER_COLORS.player1, is_human=True),
            Player(id=1, name="Player 2", color=PLAYER_COLORS.player2, is_human=False,
                   ai_personality=AIPersonality.AGGRESSIVE),
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

        # Current animation (if any)
        self.current_animation: Optional[MoveAnimation] = None

        # AI controllers for non-human players
        self.ai_controllers: Dict[int, AIPlayer] = {}
        for player in self.players:
            if not player.is_human and player.ai_personality:
                self.ai_controllers[player.id] = AIPlayer(player.id, player.ai_personality)

        # AI turn state
        self._pending_ai_actions: List = []
        self._ai_action_timer: int = 0
        self._tiles_ref: Dict[Tuple[int, int], Tile] = {}

    @property
    def current_player(self) -> Player:
        """Get the current player."""
        return self.players[self.current_player_index]

    @property
    def selected_army(self) -> Optional[Army]:
        """Get selected army if one is selected."""
        if isinstance(self.selected_unit, Army):
            return self.selected_unit
        return None

    def get_ai_players_for_tactical(self) -> Dict[int, AIPersonality]:
        """Get AI personality dict for tactical battles."""
        return {
            player.id: player.ai_personality
            for player in self.players
            if not player.is_human and player.ai_personality
        }

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

        # Set phase based on player type
        if self.current_player.is_human:
            self.phase = StrategicGamePhase.PLAYER_TURN
        else:
            self.phase = StrategicGamePhase.AI_TURN
            # Plan AI actions at start of turn
            self._pending_ai_actions = []
            self._ai_action_timer = AI.turn_start_delay_ms
            if self.current_player.id in self.ai_controllers:
                ai = self.ai_controllers[self.current_player.id]
                self._pending_ai_actions = ai.plan_turn(self._tiles_ref, armies, self)

    def set_tiles_reference(self, tiles: Dict[Tuple[int, int], Tile]):
        """Set reference to tiles for AI planning."""
        self._tiles_ref = tiles

    def update_ai_turn(self, tiles: Dict[Tuple[int, int], Tile], dt_ms: int) -> Optional[Tuple[str, any]]:
        """
        Update AI turn logic.

        Args:
            tiles: Game tiles
            dt_ms: Delta time in milliseconds

        Returns:
            Tuple of (action, data) or None:
            - ("battle", (attacker, defender, original_pos)): Battle triggered
            - ("end_turn", None): AI finished its turn
            - None: Still processing
        """
        if self.phase != StrategicGamePhase.AI_TURN:
            return None

        # Wait during animation
        if self.current_animation is not None:
            return None

        # Delay timer between actions
        self._ai_action_timer -= dt_ms
        if self._ai_action_timer > 0:
            return None

        # No more actions - end turn
        if not self._pending_ai_actions:
            return ("end_turn", None)

        # Execute next action
        action = self._pending_ai_actions.pop(0)
        self._ai_action_timer = AI.action_delay_ms

        # Get the army and verify it can still act
        army = action.army
        if army.movement_remaining <= 0:
            return None  # Skip, army already moved

        target_pos = action.target_pos
        target_tile = tiles.get(target_pos)
        if target_tile is None:
            return None

        # Store original position for battle retreat
        original_pos = army.position.to_tuple()

        # Select the army and calculate valid moves
        self.select_unit(army, tiles)

        # Check if target is still valid
        if target_pos not in self.valid_moves:
            self.select_unit(None, tiles)
            return None

        # Execute the move
        target_coord = HexCoord(*target_pos)
        battle_result = self.try_move_army(target_coord, tiles)

        if battle_result:
            attacker, defender = battle_result
            return ("battle", (attacker, defender, original_pos))

        return None

    def current_player_has_moves(
        self,
        armies: List[Army],
        heroes: List[Hero],
        tiles: Dict[Tuple[int, int], Tile]
    ) -> bool:
        """
        Indique si le joueur courant peut encore bouger une unité ce tour-ci.

        Vrai si au moins une armée (ou un héros indépendant) lui appartenant
        dispose de points de mouvement ET d'au moins une destination atteignable.
        Sert à enclencher automatiquement la fin de tour quand il n'y a plus
        rien à faire.
        """
        for army in armies:
            if army.player_id != self.current_player.id:
                continue
            if army.movement_remaining > 0 and self._calculate_valid_moves(army, tiles, heroes):
                return True

        if heroes:
            for hero in heroes:
                if hero.player_id != self.current_player.id or not hero.is_independent:
                    continue
                if hero.movement_remaining > 0 and self._calculate_valid_moves(hero, tiles, heroes):
                    return True

        return False

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

    def _calculate_valid_moves(
        self,
        unit: StrategicUnit,
        tiles: Dict[Tuple[int, int], Tile],
        heroes: List[Hero] = None
    ) -> Set[Tuple[int, int]]:
        """
        Calculate all valid move destinations.

        Délègue au BFS canonique d'``engine.pathfinding``. La traversée n'est
        autorisée que sur les cases vides (``can_pass_through`` par défaut) ;
        seul le prédicat d'arrêt change selon le type d'unité :

        - héros : case vide, ou armée alliée (pour la rejoindre) ;
        - armée : case vide, ou case ennemie (déclenche une bataille).

        ``heroes`` est conservé pour compatibilité d'appel mais inutilisé ici.
        """
        if isinstance(unit, Hero):
            def can_stop(tile, pos):
                return tile.unit is None or (
                    tile.unit.player_id == unit.player_id and isinstance(tile.unit, Army)
                )
        else:
            def can_stop(tile, pos):
                return tile.unit is None or tile.unit.player_id != unit.player_id

        return calculate_valid_moves(
            unit.position.to_tuple(), unit.movement_remaining, tiles, can_stop
        )

    def try_move_army(
        self,
        target: HexCoord,
        tiles: Dict[Tuple[int, int], Tile]
    ) -> Optional[Tuple[Army, Army]]:
        """
        Try to move the selected army to target position.

        If animation is enabled, starts an animation. Otherwise moves directly.

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
        move_cost = calculate_path_cost(source_tuple, target_tuple, tiles)

        if not self.selected_army.use_movement(move_cost):
            return None

        # Check if there's an enemy army at target - battle triggered
        if target_tile.unit and target_tile.unit.player_id != self.selected_army.player_id:
            # Start animation to move towards enemy (stop before reaching)
            if ANIMATION.enabled:
                path = find_path(source_tuple, target_tuple, tiles)
                if path and len(path) > 1:
                    # Animate up to the tile before enemy
                    path_to_enemy = path[:-1]
                    if len(path_to_enemy) > 1:
                        self.current_animation = MoveAnimation(
                            unit=self.selected_army,
                            path=path_to_enemy,
                        )
            return (self.selected_army, target_tile.unit)

        # Normal move (no battle) - start animation
        if ANIMATION.enabled:
            path = find_path(source_tuple, target_tuple, tiles)
            if path and len(path) > 1:
                self.current_animation = MoveAnimation(
                    unit=self.selected_army,
                    path=path,
                )
                # Clear source tile, unit position will be updated during animation
                source_tile.unit = None
                self.valid_moves.clear()
                return None

        # No animation - move directly
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
            Action taken: "moved", "joined_army", "animating", or None if failed
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
        move_cost = calculate_path_cost(source_tuple, target_tuple, tiles)

        if not hero.use_movement(move_cost):
            return None

        # Check if there's a friendly army at target
        if target_tile.unit and isinstance(target_tile.unit, Army):
            if target_tile.unit.player_id == hero.player_id:
                # Animate movement to army before joining
                if ANIMATION.enabled:
                    path = find_path(source_tuple, target_tuple, tiles)
                    if path and len(path) > 1:
                        self.current_animation = MoveAnimation(
                            unit=hero,
                            path=path,
                            on_complete="join_army"
                        )
                        self.valid_moves.clear()
                        return "animating_join"

                if hero.join_army(target_tile.unit):
                    self.selected_unit = None
                    self.valid_moves.clear()
                    return "joined_army"
                return None

        # Normal move to empty tile - start animation
        if ANIMATION.enabled:
            path = find_path(source_tuple, target_tuple, tiles)
            if path and len(path) > 1:
                self.current_animation = MoveAnimation(
                    unit=hero,
                    path=path,
                )
                self.valid_moves.clear()
                return "animating"

        # No animation - move directly
        hero.position = target

        # Update valid moves
        if hero.movement_remaining > 0:
            self.valid_moves = self._calculate_valid_moves(hero, tiles)
        else:
            self.valid_moves.clear()

        return "moved"

    def update_animation(
        self,
        tiles: Dict[Tuple[int, int], Tile],
        dt_ms: int = 0
    ) -> Optional[str]:
        """
        Update the current animation.

        Args:
            tiles: Map tiles.
            dt_ms: Temps écoulé depuis la frame précédente (ms). La cadence des
                pas est pilotée par ce delta, pas par l'horloge murale.

        Returns:
            - "continue" if animation is still running
            - "complete" if animation just finished normally
            - "hero_joined" if hero joined an army after animation
            - None if no animation
        """
        if self.current_animation is None:
            return None

        anim = self.current_animation
        anim.elapsed_ms += dt_ms

        # Check if it's time for next step
        if anim.elapsed_ms < ANIMATION.move_step_delay_ms:
            return "continue"

        # Advance animation (advance() remet l'accumulateur à zéro)
        if not anim.is_complete:
            new_pos = anim.advance()
            anim.unit.position = HexCoord(*new_pos)
            return "continue"

        # Animation complete - finalize position
        final_pos = anim.target_pos
        final_tile = tiles.get(final_pos)
        on_complete = anim.on_complete

        if final_tile:
            # Handle special on_complete actions
            if on_complete == "join_army" and isinstance(anim.unit, Hero):
                # Hero joins the army at target
                if final_tile.unit and isinstance(final_tile.unit, Army):
                    anim.unit.join_army(final_tile.unit)
                    self.selected_unit = None
                    self.current_animation = None
                    return "hero_joined"

            # Normal completion - place unit on tile
            if isinstance(anim.unit, Army):
                final_tile.unit = anim.unit

            # Update valid moves if unit has movement remaining
            if isinstance(anim.unit, Army) and anim.unit.movement_remaining > 0:
                self.valid_moves = self._calculate_valid_moves(anim.unit, tiles)
            elif isinstance(anim.unit, Hero) and anim.unit.movement_remaining > 0:
                self.valid_moves = self._calculate_valid_moves(anim.unit, tiles)

        self.current_animation = None
        return "complete"

    def resolve_battle_aftermath(
        self,
        attacker: Army,
        defender: Army,
        report: BattleReport,
        tiles: Dict[Tuple[int, int], Tile],
        armies: List[Army],
        attacker_original_pos: Tuple[int, int]
    ):
        """
        Handle the aftermath of a tactical battle on the strategic map.

        Battle outcomes:
        - Attacker wins (defender destroyed): attacker moves to defender's position
        - Defender wins (attacker destroyed): attacker removed, defender stays
        - Draw/Both survive: attacker retreats to original position
        """
        self.last_battle_report = report

        attacker_pos = attacker.position.to_tuple()
        defender_pos = defender.position.to_tuple()
        attacker_tile = tiles.get(attacker_pos)
        defender_tile = tiles.get(defender_pos)

        attacker_dead = len(attacker.units) == 0
        defender_dead = len(defender.units) == 0

        # Case 1: Attacker destroyed
        if attacker_dead:
            if attacker_tile:
                attacker_tile.unit = None
            if attacker in armies:
                armies.remove(attacker)

        # Case 2: Defender destroyed - attacker takes position
        if defender_dead:
            if defender_tile:
                defender_tile.unit = None
            if defender in armies:
                armies.remove(defender)

            if not attacker_dead:
                # Move attacker to defender's position
                if attacker_tile:
                    attacker_tile.unit = None
                defender_tile.unit = attacker
                attacker.position = HexCoord(*defender_pos)

        # Case 3: Both survive (draw) - attacker retreats to original position
        if not attacker_dead and not defender_dead:
            # Attacker needs to retreat
            if attacker_pos != attacker_original_pos:
                # Move attacker back to original position
                if attacker_tile:
                    attacker_tile.unit = None
                original_tile = tiles.get(attacker_original_pos)
                if original_tile:
                    original_tile.unit = attacker
                    attacker.position = HexCoord(*attacker_original_pos)

        # Clear selection and moves
        self.selected_unit = None
        self.valid_moves.clear()

    def check_victory(self, armies: List[Army]) -> Optional[int]:
        """Check if a player has won. Returns player ID or None."""
        player_armies = {}
        for army in armies:
            if army.player_id not in player_armies:
                player_armies[army.player_id] = 0
            player_armies[army.player_id] += 1

        alive_players = [pid for pid, count in player_armies.items() if count > 0]

        if len(alive_players) == 1:
            return alive_players[0]

        return None


# =============================================================================
# Renderer
# =============================================================================

class StrategicRenderer:
    """Handles all rendering for the strategic map."""

    def __init__(self, screen: pygame.Surface, font: pygame.font.Font):
        self.screen = screen
        self.font = font
        self.screen_width = screen.get_width()
        self.screen_height = screen.get_height()

        # UI elements
        self.end_turn_button_rect = pygame.Rect(
            self.screen_width - UI.button_width - UI.button_margin,
            UI.button_margin,
            UI.button_width,
            UI.button_height
        )

    def render_frame(
        self,
        tiles: Dict[Tuple[int, int], Tile],
        armies: List[Army],
        heroes: List[Hero],
        game_state: StrategicGameState,
        camera: Camera,
        hex_grid: HexGrid,
        hover_hex: Optional[HexCoord],
        selected_hex: Optional[HexCoord],
        show_coordinates: bool,
        battle_message: str,
        battle_message_timer: float
    ):
        """Render a complete frame."""
        self.screen.fill(UI.screen_bg_color)

        self._render_tiles(tiles, game_state, camera, hex_grid, hover_hex, selected_hex, show_coordinates)
        self._render_armies(armies, game_state, camera, hex_grid)
        self._render_heroes(heroes, game_state, camera, hex_grid)
        self._render_top_panel(game_state, camera)
        self._render_bottom_panel(tiles, heroes, selected_hex, hover_hex)
        self._render_battle_message(battle_message, battle_message_timer)

        pygame.display.flip()

    def _render_tiles(
        self,
        tiles: Dict[Tuple[int, int], Tile],
        game_state: StrategicGameState,
        camera: Camera,
        hex_grid: HexGrid,
        hover_hex: Optional[HexCoord],
        selected_hex: Optional[HexCoord],
        show_coordinates: bool
    ):
        """Render all visible tiles."""
        for coord_tuple, tile in tiles.items():
            coord = HexCoord(*coord_tuple)
            center = hex_grid.hex_to_pixel(coord, camera.offset)

            # Culling
            if not self._is_on_screen(center, camera.hex_size):
                continue

            vertices = hex_grid.get_hex_corners(coord, camera.offset)
            color = self._get_tile_color(tile, coord_tuple, game_state, hover_hex, selected_hex)

            pygame.draw.polygon(self.screen, color, vertices)
            pygame.draw.polygon(self.screen, (50, 50, 60), vertices, 1)

            # Draw coordinates if enabled
            if show_coordinates and camera.hex_size >= 24:
                coord_text = self.font.render(f"{coord.q},{coord.r}", True, (80, 80, 80))
                text_rect = coord_text.get_rect(center=center)
                self.screen.blit(coord_text, text_rect)

    def _get_tile_color(
        self,
        tile: Tile,
        coord_tuple: Tuple[int, int],
        game_state: StrategicGameState,
        hover_hex: Optional[HexCoord],
        selected_hex: Optional[HexCoord]
    ) -> Tuple[int, int, int]:
        """Determine the color for a tile based on state."""
        color = tile.display_color

        # Valid move highlight
        if coord_tuple in game_state.valid_moves:
            if tile.unit and tile.unit.player_id != game_state.current_player.id:
                color = UI.attack_highlight_color
            else:
                color = tuple(min(255, c + 40) for c in color)

        # Selected hex
        if selected_hex and coord_tuple == selected_hex.to_tuple():
            color = UI.selection_color

        # Hover
        if hover_hex and coord_tuple == hover_hex.to_tuple():
            color = tuple(min(255, c + 20) for c in color)

        return color

    def _render_armies(
        self,
        armies: List[Army],
        game_state: StrategicGameState,
        camera: Camera,
        hex_grid: HexGrid
    ):
        """Render all armies on the map."""
        for army in armies:
            if not hasattr(army, 'position'):
                continue

            center = hex_grid.hex_to_pixel(army.position, camera.offset)
            x, y = int(center[0]), int(center[1])

            if not self._is_on_screen((x, y), camera.hex_size):
                continue

            color = PLAYER_COLORS.get(army.player_id)
            radius = int(camera.hex_size * 0.5)

            # Army circle
            pygame.draw.circle(self.screen, color, (x, y), radius)
            pygame.draw.circle(self.screen, (255, 255, 255), (x, y), radius, 2)

            # Selected highlight
            if army == game_state.selected_army:
                pygame.draw.circle(self.screen, UI.selection_color, (x, y), radius + 4, 3)

            # Army letter
            letter = army.name[0].upper()
            text = self.font.render(letter, True, UI.text_color)
            text_rect = text.get_rect(center=(x, y))
            self.screen.blit(text, text_rect)

            # Unit count
            if camera.hex_size >= 18:
                count_text = self.font.render(str(army.total_unit_count), True, UI.text_color)
                self.screen.blit(count_text, (x + radius - 5, y + radius - 5))

            # Hero indicator
            if army.hero is not None:
                hero_radius = int(camera.hex_size * 0.2)
                hero_x = x + radius - 3
                hero_y = y - radius + 3
                pygame.draw.circle(self.screen, UI.hero_gold_color, (hero_x, hero_y), hero_radius)
                pygame.draw.circle(self.screen, UI.text_color, (hero_x, hero_y), hero_radius, 1)

    def _render_heroes(
        self,
        heroes: List[Hero],
        game_state: StrategicGameState,
        camera: Camera,
        hex_grid: HexGrid
    ):
        """Render all independent heroes on the map."""
        for hero in heroes:
            if not hero.is_independent or hero.position is None:
                continue

            center = hex_grid.hex_to_pixel(hero.position, camera.offset)
            x, y = int(center[0]), int(center[1])

            if not self._is_on_screen((x, y), camera.hex_size):
                continue

            color = PLAYER_COLORS.get(hero.player_id)
            radius = int(camera.hex_size * 0.35)

            # Diamond shape
            points = [
                (x, y - radius),
                (x + radius, y),
                (x, y + radius),
                (x - radius, y),
            ]
            pygame.draw.polygon(self.screen, color, points)
            pygame.draw.polygon(self.screen, UI.hero_gold_color, points, 2)

            # Selected highlight
            if hero == game_state.selected_unit:
                outer_radius = radius + 4
                outer_points = [
                    (x, y - outer_radius),
                    (x + outer_radius, y),
                    (x, y + outer_radius),
                    (x - outer_radius, y),
                ]
                pygame.draw.polygon(self.screen, UI.selection_color, outer_points, 3)

            # Hero letter
            text = self.font.render(hero.portrait_letter, True, UI.text_color)
            text_rect = text.get_rect(center=(x, y))
            self.screen.blit(text, text_rect)

    def _render_top_panel(self, game_state: StrategicGameState, camera: Camera):
        """Render the top UI panel."""
        pygame.draw.rect(self.screen, UI.panel_bg_color, (0, 0, self.screen_width, UI.top_panel_height))

        # Turn info
        turn_surf = self.font.render(f"Tour {game_state.turn_number}", True, UI.text_color)
        player_surf = self.font.render(game_state.current_player.name, True, game_state.current_player.color)
        self.screen.blit(turn_surf, (10, 8))
        self.screen.blit(player_surf, (10, 28))

        # Hints
        hint = self.font.render("Arrows/Drag: Pan | +/-: Zoom | C: Coords | Space: End Turn", True, UI.hint_color)
        self.screen.blit(hint, (200, 18))

        # Zoom level
        zoom_text = self.font.render(f"Zoom: {camera.zoom_level_name}", True, UI.hint_color)
        self.screen.blit(zoom_text, (self.screen_width - 280, 8))

        # End turn button
        self._render_end_turn_button()

    def _render_end_turn_button(self):
        """Render the end turn button."""
        mouse_pos = pygame.mouse.get_pos()
        hovered = self.end_turn_button_rect.collidepoint(mouse_pos)

        btn_color = (80, 120, 80) if hovered else (60, 100, 60)
        pygame.draw.rect(self.screen, btn_color, self.end_turn_button_rect, border_radius=5)
        pygame.draw.rect(self.screen, (100, 150, 100), self.end_turn_button_rect, 2, border_radius=5)

        btn_text = self.font.render("End Turn", True, UI.text_color)
        btn_rect = btn_text.get_rect(center=self.end_turn_button_rect.center)
        self.screen.blit(btn_text, btn_rect)

    def _render_bottom_panel(
        self,
        tiles: Dict[Tuple[int, int], Tile],
        heroes: List[Hero],
        selected_hex: Optional[HexCoord],
        hover_hex: Optional[HexCoord]
    ):
        """Render the bottom UI panel."""
        pygame.draw.rect(
            self.screen, UI.panel_bg_color,
            (0, self.screen_height - UI.bottom_panel_height, self.screen_width, UI.bottom_panel_height)
        )

        if selected_hex and selected_hex.to_tuple() in tiles:
            tile = tiles[selected_hex.to_tuple()]
            info = f"Terrain: {tile.display_name} | Move cost: {tile.get_movement_cost()} | Def bonus: +{tile.defense_bonus}"
            info_surf = self.font.render(info, True, (200, 200, 200))
            self.screen.blit(info_surf, (10, self.screen_height - 52))

            if tile.unit:
                unit = tile.unit
                unit_info = f"Army: {unit.name} | Units: {unit.total_unit_count} | Move: {unit.movement_remaining}/{unit.stats.movement}"
                if hasattr(unit, 'hero') and unit.hero:
                    unit_info += f" | Hero: {unit.hero.name} (Lv.{unit.hero.level})"
                unit_surf = self.font.render(unit_info, True, (255, 200, 100))
                self.screen.blit(unit_surf, (10, self.screen_height - 30))

            # Hero at position
            hero_at_pos = _get_hero_at(heroes, selected_hex.to_tuple())
            if hero_at_pos:
                hero_info = f"Hero: {hero_at_pos.name} | Class: {hero_at_pos.hero_class} | Lv.{hero_at_pos.level} | Move: {hero_at_pos.movement_remaining}/{hero_at_pos.stats.movement}"
                hero_surf = self.font.render(hero_info, True, (255, 215, 100))
                y_pos = self.screen_height - 30 if not tile.unit else self.screen_height - 10
                self.screen.blit(hero_surf, (10, y_pos))

        if hover_hex and hover_hex.to_tuple() in tiles:
            tile = tiles[hover_hex.to_tuple()]
            hover_text = f"({hover_hex.q}, {hover_hex.r}) - {tile.display_name}"
            hover_surf = self.font.render(hover_text, True, UI.hint_color)
            self.screen.blit(hover_surf, (self.screen_width - 250, self.screen_height - 52))

    def _render_battle_message(self, message: str, timer: float):
        """Render the battle result message."""
        if timer > 0 and message:
            msg_surf = self.font.render(message, True, (255, 200, 100))
            msg_rect = msg_surf.get_rect(center=(self.screen_width // 2, 70))
            pygame.draw.rect(self.screen, UI.panel_bg_color, msg_rect.inflate(20, 10))
            self.screen.blit(msg_surf, msg_rect)

    def _is_on_screen(self, center: Tuple[float, float], hex_size: int) -> bool:
        """Check if a position is visible on screen."""
        margin = hex_size * 2
        return (
            -margin < center[0] < self.screen_width + margin and
            -margin < center[1] < self.screen_height + margin
        )

    def is_end_turn_clicked(self, pos: Tuple[int, int]) -> bool:
        """Check if the end turn button was clicked."""
        return self.end_turn_button_rect.collidepoint(pos)


# =============================================================================
# Main Game Loop
# =============================================================================

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

    # Applique la vitesse de jeu choisie dans le menu (IA + animations).
    SPEED.set_by_name(config.get('game_speed', 'Normal'))

    screen_width = screen.get_width()
    screen_height = screen.get_height()

    # Create components
    camera = Camera(screen_width, screen_height)
    camera_controller = CameraController(
        camera, INPUT.drag_threshold, INPUT.scroll_speed, INPUT.fast_scroll_multiplier
    )
    font = pygame.font.Font(None, 24)
    renderer = StrategicRenderer(screen, font)

    # Initialize game state
    game_state = StrategicGameState()
    game_state.set_tiles_reference(tiles)
    game_state.start_turn(armies, heroes)

    clock = pygame.time.Clock()

    # State
    show_coordinates = False
    hover_hex = None
    selected_hex = None
    battle_message = ""
    battle_message_timer = 0.0
    dt = 0.0

    # Pending battle to trigger after animation
    pending_battle_data = None

    while True:
        mouse_pos = pygame.mouse.get_pos()

        # Update animation (cadence pilotée par le dt de la frame précédente)
        anim_result = game_state.update_animation(tiles, int(dt * 1000))
        is_animating = anim_result in ("continue",)

        # Event handling (block game inputs during animation, allow camera)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            # Réglage de la vitesse IA/animation, accessible à tout moment
            # (y compris pendant le tour de l'ennemi) : '<' ralentit, '>' accélère.
            if event.type == pygame.KEYDOWN and event.key in (pygame.K_COMMA, pygame.K_PERIOD):
                SPEED.cycle(1 if event.key == pygame.K_PERIOD else -1)
                battle_message = f"Speed: {SPEED.name}"
                battle_message_timer = 1.5
                continue

            # Always allow camera control
            if camera_controller.handle_event(event, mouse_pos):
                if event.type == pygame.MOUSEBUTTONUP and event.button == 3:
                    if not is_animating and camera_controller.was_right_click_not_drag(event, mouse_pos):
                        game_state.select_unit(None, tiles, heroes)
                        selected_hex = None
                continue

            # Block other inputs during animation or AI turn
            if is_animating or game_state.phase == StrategicGamePhase.AI_TURN:
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return True
                elif event.key == pygame.K_c:
                    show_coordinates = not show_coordinates
                elif event.key == pygame.K_SPACE:
                    game_state.end_turn(armies, heroes)

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                result = _handle_left_click(
                    mouse_pos, tiles, armies, heroes, game_state,
                    camera_controller.hex_grid, camera, renderer, screen
                )
                if result:
                    action, data = result
                    if action == "end_turn":
                        game_state.end_turn(armies, heroes)
                    elif action == "select":
                        selected_hex = data
                    elif action == "battle":
                        battle_message, battle_message_timer = data
                        # Check victory
                        winner = game_state.check_victory(armies)
                        if winner is not None:
                            _show_victory_screen(screen, game_state.players[winner], font)
                            return True
                    elif action == "pending_battle":
                        # Battle will be triggered after animation
                        pending_battle_data = data

        # Handle animation completion
        if anim_result == "hero_joined":
            battle_message = "Hero joined the army!"
            battle_message_timer = 2.0

        elif anim_result == "complete" and pending_battle_data:
            attacker, defender, attacker_original_pos = pending_battle_data
            defender_tile = tiles.get(defender.position.to_tuple())
            battle_terrain = _get_terrain_type(defender_tile) if defender_tile else TerrainType.PLAINS

            report = run_tactical_battle(
                screen, attacker, defender,
                PLAYER_COLORS.as_dict(),
                strategic_terrain=battle_terrain,
                ai_players=game_state.get_ai_players_for_tactical()
            )

            game_state.resolve_battle_aftermath(
                attacker, defender, report, tiles, armies, attacker_original_pos
            )

            if report.attacker_won:
                battle_message = f"{report.attacker_name} wins! Losses: {report.attacker_losses} vs {report.defender_losses}"
            else:
                battle_message = f"{report.defender_name} wins! Losses: {report.defender_losses} vs {report.attacker_losses}"
            battle_message_timer = 5.0

            pending_battle_data = None

            # Check victory
            winner = game_state.check_victory(armies)
            if winner is not None:
                _show_victory_screen(screen, game_state.players[winner], font)
                return True

        # Handle AI turn
        if game_state.phase == StrategicGamePhase.AI_TURN and not is_animating:
            dt_ms = int(dt * 1000)
            ai_result = game_state.update_ai_turn(tiles, dt_ms)

            if ai_result:
                action, data = ai_result
                if action == "end_turn":
                    game_state.end_turn(armies, heroes)
                elif action == "battle":
                    attacker, defender, attacker_original_pos = data

                    # If animation is running, defer battle
                    if game_state.current_animation:
                        pending_battle_data = (attacker, defender, attacker_original_pos)
                    else:
                        # Run battle immediately
                        defender_tile = tiles.get(defender.position.to_tuple())
                        battle_terrain = _get_terrain_type(defender_tile) if defender_tile else TerrainType.PLAINS

                        report = run_tactical_battle(
                            screen, attacker, defender,
                            PLAYER_COLORS.as_dict(),
                            strategic_terrain=battle_terrain,
                            ai_players=game_state.get_ai_players_for_tactical()
                        )

                        game_state.resolve_battle_aftermath(
                            attacker, defender, report, tiles, armies, attacker_original_pos
                        )

                        if report.attacker_won:
                            battle_message = f"{report.attacker_name} wins! Losses: {report.attacker_losses} vs {report.defender_losses}"
                        else:
                            battle_message = f"{report.defender_name} wins! Losses: {report.defender_losses} vs {report.attacker_losses}"
                        battle_message_timer = 5.0

                        # Check victory
                        winner = game_state.check_victory(armies)
                        if winner is not None:
                            _show_victory_screen(screen, game_state.players[winner], font)
                            return True

        # Pendant le tour de l'IA, la caméra suit l'unité ennemie en mouvement
        # (glissement fluide) afin que le joueur voie ce que fait l'adversaire.
        if (game_state.phase == StrategicGamePhase.AI_TURN
                and game_state.current_animation is not None):
            camera.center_on(
                game_state.current_animation.unit.position,
                camera_controller.hex_grid,
                smoothing=0.18,
            )

        # Fin de tour automatique côté joueur humain : dès qu'aucune unité ne
        # peut plus se déplacer, on enchaîne le tour suivant sans attendre.
        if (game_state.phase == StrategicGamePhase.PLAYER_TURN
                and game_state.current_animation is None
                and pending_battle_data is None
                and not game_state.current_player_has_moves(armies, heroes, tiles)):
            game_state.end_turn(armies, heroes)

        # Continuous input
        camera_controller.handle_continuous_input()

        # Update hover
        hex_grid = camera_controller.hex_grid
        hovered = hex_grid.pixel_to_hex(mouse_pos[0], mouse_pos[1], camera.offset)
        hover_hex = hovered if hovered.to_tuple() in tiles else None

        # Update message timer
        if battle_message_timer > 0:
            battle_message_timer -= dt

        # Render
        renderer.render_frame(
            tiles, armies, heroes, game_state, camera, hex_grid,
            hover_hex, selected_hex, show_coordinates,
            battle_message, battle_message_timer
        )

        pygame.display.flip()
        dt = clock.tick(60) / 1000.0

    return False


def _handle_left_click(
    mouse_pos: Tuple[int, int],
    tiles: Dict[Tuple[int, int], Tile],
    armies: List[Army],
    heroes: List[Hero],
    game_state: StrategicGameState,
    hex_grid: HexGrid,
    camera: Camera,
    renderer: StrategicRenderer,
    screen: pygame.Surface
) -> Optional[Tuple[str, any]]:
    """
    Handle left click events.

    Returns:
        Tuple of (action, data) or None
    """
    # Check end turn button
    if renderer.is_end_turn_clicked(mouse_pos):
        return ("end_turn", None)

    clicked_hex = hex_grid.pixel_to_hex(mouse_pos[0], mouse_pos[1], camera.offset)
    clicked_tuple = clicked_hex.to_tuple()

    if clicked_tuple not in tiles:
        return None

    tile = tiles[clicked_tuple]

    # Check if moving selected unit to valid destination
    if game_state.selected_unit and clicked_tuple in game_state.valid_moves:
        # Handle hero movement
        if isinstance(game_state.selected_unit, Hero):
            hero = game_state.selected_unit
            result = game_state.try_move_hero(hero, clicked_hex, tiles)
            if result == "joined_army":
                return ("battle", (f"{hero.name} joined {tile.unit.name}!", 3.0))
            elif result == "animating_join":
                # Hero is animating toward army, will join after
                return ("select", clicked_hex)
            elif result == "animating":
                # Hero is animating movement
                return ("select", clicked_hex)
            return ("select", clicked_hex) if result else None

        # Handle army movement
        elif game_state.selected_army:
            # Save original position before attempting move (for retreat if battle is a draw)
            attacker_original_pos = game_state.selected_army.position.to_tuple()

            battle_result = game_state.try_move_army(clicked_hex, tiles)

            if battle_result:
                attacker, defender = battle_result

                # If animation is running, defer battle until animation completes
                if game_state.current_animation:
                    return ("pending_battle", (attacker, defender, attacker_original_pos))

                # No animation - run battle immediately
                defender_tile = tiles.get(defender.position.to_tuple())
                battle_terrain = _get_terrain_type(defender_tile) if defender_tile else TerrainType.PLAINS

                report = run_tactical_battle(
                    screen, attacker, defender,
                    PLAYER_COLORS.as_dict(),
                    strategic_terrain=battle_terrain,
                    ai_players=game_state.get_ai_players_for_tactical()
                )

                game_state.resolve_battle_aftermath(
                    attacker, defender, report, tiles, armies, attacker_original_pos
                )

                if report.attacker_won:
                    msg = f"{report.attacker_name} wins! Losses: {report.attacker_losses} vs {report.defender_losses}"
                else:
                    msg = f"{report.defender_name} wins! Losses: {report.defender_losses} vs {report.attacker_losses}"

                return ("battle", (msg, 5.0))
            else:
                # Normal move (possibly animating)
                if not game_state.current_animation:
                    game_state.select_unit(game_state.selected_army, tiles, heroes)
                return ("select", clicked_hex)

    # Check for hero at clicked position
    hero = _get_hero_at(heroes, clicked_tuple, game_state.current_player.id)
    if hero:
        game_state.select_unit(hero, tiles, heroes)
        return ("select", clicked_hex)

    # Select army
    if tile.unit and tile.unit.player_id == game_state.current_player.id:
        game_state.select_unit(tile.unit, tiles, heroes)
        return ("select", clicked_hex)

    # Deselect
    game_state.select_unit(None, tiles, heroes)
    return ("select", clicked_hex)


def _show_victory_screen(screen: pygame.Surface, winner: Player, font: pygame.font.Font):
    """Show victory screen."""
    sw, sh = screen.get_width(), screen.get_height()
    title_font = pygame.font.Font(None, 72)
    clock = pygame.time.Clock()

    running = True
    while running:
        for event in pygame.event.get():
            if event.type in (pygame.QUIT, pygame.KEYDOWN, pygame.MOUSEBUTTONDOWN):
                running = False

        screen.fill((20, 20, 30))

        title = title_font.render("VICTORY!", True, winner.color)
        screen.blit(title, (sw // 2 - title.get_width() // 2, sh // 2 - 100))

        winner_text = title_font.render(f"{winner.name} wins!", True, (255, 255, 255))
        screen.blit(winner_text, (sw // 2 - winner_text.get_width() // 2, sh // 2))

        prompt = font.render("Press any key to continue...", True, (150, 150, 150))
        screen.blit(prompt, (sw // 2 - prompt.get_width() // 2, sh // 2 + 100))

        pygame.display.flip()
        clock.tick(60)
