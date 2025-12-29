"""
Game state management for the hex strategy game.

Handles turns, player management, and game flow.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum

from .hex_grid import HexCoord
from .tile import Tile
from .unit import Unit, Army
from .combat import CombatSystem, CombatResult


class GamePhase(Enum):
    """Current phase of the game."""
    SETUP = "setup"
    PLAYER_TURN = "player_turn"
    ENEMY_TURN = "enemy_turn"
    COMBAT = "combat"
    GAME_OVER = "game_over"


@dataclass
class Player:
    """Represents a player in the game."""
    id: int
    name: str
    color: Tuple[int, int, int]
    is_human: bool = True


class GameState:
    """
    Manages the overall game state including turns and unit actions.
    """

    def __init__(self, players: List[Player] = None):
        """Initialize game state with players."""
        self.players = players or [
            Player(id=0, name="Player 1", color=(100, 100, 255), is_human=True),
            Player(id=1, name="Player 2", color=(255, 100, 100), is_human=False),
        ]

        self.turn_number = 1
        self.current_player_index = 0
        self.phase = GamePhase.PLAYER_TURN

        # Selection state
        self.selected_unit: Optional[Army] = None
        self.selected_hex: Optional[HexCoord] = None
        self.valid_moves: Set[Tuple[int, int]] = set()
        self.valid_attacks: Set[Tuple[int, int]] = set()  # Enemy units that can be attacked

        # Combat system
        self.combat_system = CombatSystem(random_factor=0.2)
        self.last_combat_result: Optional[CombatResult] = None
        self.combat_message: str = ""
        self.combat_message_timer: float = 0

        # Track which units have moved/acted this turn
        self.units_moved: Set[int] = set()  # Unit ids that moved
        self.units_acted: Set[int] = set()  # Unit ids that attacked

    @property
    def current_player(self) -> Player:
        """Get the current player."""
        return self.players[self.current_player_index]

    def start_turn(self, armies: List[Army]):
        """Start a new turn for the current player."""
        self.units_moved.clear()
        self.units_acted.clear()
        self.selected_unit = None
        self.selected_hex = None
        self.valid_moves.clear()
        self.valid_attacks.clear()

        # Reset movement for all units belonging to current player
        for army in armies:
            if army.player_id == self.current_player.id:
                army.start_turn()

    def end_turn(self, armies: List[Army]):
        """End the current player's turn and switch to next player."""
        self.current_player_index = (self.current_player_index + 1) % len(self.players)

        # If we've gone through all players, increment turn number
        if self.current_player_index == 0:
            self.turn_number += 1

        self.start_turn(armies)

    def select_unit(self, army: Optional[Army], tiles: Dict[Tuple[int, int], Tile]):
        """
        Select a unit and calculate its valid moves.

        Args:
            army: The army to select, or None to deselect
            tiles: The game map tiles
        """
        self.selected_unit = army
        self.valid_moves.clear()

        if army is None or not hasattr(army, 'position'):
            self.selected_hex = None
            return

        # Only allow selecting own units
        if army.player_id != self.current_player.id:
            self.selected_unit = None
            self.selected_hex = None
            return

        self.selected_hex = army.position

        # Calculate valid moves if unit can still move
        if army.movement_remaining > 0:
            self.valid_moves = self._calculate_valid_moves(army, tiles)

        # Calculate valid attacks if unit hasn't acted
        if not army.has_acted:
            self.valid_attacks = self._calculate_valid_attacks(army, tiles)

    def _calculate_valid_moves(
        self,
        army: Army,
        tiles: Dict[Tuple[int, int], Tile]
    ) -> Set[Tuple[int, int]]:
        """
        Calculate all valid move destinations for a unit using BFS.

        Uses movement points and terrain costs.
        """
        valid = set()
        start = army.position.to_tuple()

        # BFS with movement cost tracking
        # (position, remaining_movement)
        queue = [(start, army.movement_remaining)]
        visited = {start: army.movement_remaining}

        while queue:
            current_pos, remaining = queue.pop(0)
            current_coord = HexCoord(*current_pos)

            for neighbor in current_coord.neighbors():
                neighbor_tuple = neighbor.to_tuple()

                # Check if tile exists
                if neighbor_tuple not in tiles:
                    continue

                tile = tiles[neighbor_tuple]

                # Check if passable
                if not tile.is_passable:
                    continue

                # Check movement cost
                move_cost = tile.get_movement_cost()
                new_remaining = remaining - move_cost

                if new_remaining < 0:
                    continue

                # Check if we've found a better path to this tile
                if neighbor_tuple in visited and visited[neighbor_tuple] >= new_remaining:
                    continue

                visited[neighbor_tuple] = new_remaining

                # Can move here if not occupied (or if it's the start)
                if not tile.is_occupied:
                    valid.add(neighbor_tuple)

                # Continue exploring from this tile
                queue.append((neighbor_tuple, new_remaining))

        return valid

    def _calculate_valid_attacks(
        self,
        army: Army,
        tiles: Dict[Tuple[int, int], Tile]
    ) -> Set[Tuple[int, int]]:
        """
        Calculate all valid attack targets for a unit.

        Returns positions of enemy units within attack range.
        """
        valid = set()
        position = army.position

        # Get all hexes within attack range
        attack_range = army.stats.range if hasattr(army.stats, 'range') else 1

        for neighbor in position.neighbors():
            neighbor_tuple = neighbor.to_tuple()

            if neighbor_tuple not in tiles:
                continue

            tile = tiles[neighbor_tuple]

            # Check if there's an enemy unit
            if tile.unit and tile.unit.player_id != army.player_id:
                # Check distance
                distance = position.distance_to(neighbor)
                if distance <= attack_range:
                    valid.add(neighbor_tuple)

        # For ranged units, check further tiles
        if attack_range > 1:
            from .hex_grid import HexCoord
            for q in range(-attack_range, attack_range + 1):
                for r in range(max(-attack_range, -q - attack_range),
                              min(attack_range, -q + attack_range) + 1):
                    target = HexCoord(position.q + q, position.r + r)
                    target_tuple = target.to_tuple()

                    if target_tuple == position.to_tuple():
                        continue

                    if target_tuple not in tiles:
                        continue

                    tile = tiles[target_tuple]
                    if tile.unit and tile.unit.player_id != army.player_id:
                        distance = position.distance_to(target)
                        if distance <= attack_range:
                            valid.add(target_tuple)

        return valid

    def try_attack(
        self,
        target: HexCoord,
        tiles: Dict[Tuple[int, int], Tile],
        armies: List[Army]
    ) -> Optional[CombatResult]:
        """
        Try to attack an enemy unit at the target position.

        Returns:
            CombatResult if attack happened, None otherwise
        """
        if self.selected_unit is None:
            return None

        target_tuple = target.to_tuple()

        if target_tuple not in self.valid_attacks:
            return None

        target_tile = tiles.get(target_tuple)
        if target_tile is None or target_tile.unit is None:
            return None

        defender = target_tile.unit
        attacker = self.selected_unit

        # Get tiles for terrain bonuses
        attacker_tile = tiles.get(attacker.position.to_tuple())

        # Calculate distance
        distance = attacker.position.distance_to(target)

        # Check if attack is valid
        can_attack, reason = self.combat_system.can_attack(
            attacker, defender,
            attacker_tile, target_tile,
            distance
        )

        if not can_attack:
            self.combat_message = reason
            self.combat_message_timer = 2.0
            return None

        # Resolve combat
        result = self.combat_system.resolve_combat(
            attacker, defender,
            attacker_tile, target_tile
        )

        self.last_combat_result = result

        # Build combat message
        if result.defender_survived:
            self.combat_message = f"{attacker.name} attacks {defender.name}! -{result.defender_damage} HP"
            if result.attacker_damage > 0:
                self.combat_message += f" (Counter: -{result.attacker_damage} HP)"
        else:
            self.combat_message = f"{attacker.name} destroys {defender.name}!"

        self.combat_message_timer = 3.0

        # Handle unit death
        if not result.defender_survived:
            target_tile.unit = None
            if defender in armies:
                armies.remove(defender)

        if not result.attacker_survived:
            attacker_tile = tiles.get(attacker.position.to_tuple())
            if attacker_tile:
                attacker_tile.unit = None
            if attacker in armies:
                armies.remove(attacker)
            self.selected_unit = None
            self.valid_moves.clear()
            self.valid_attacks.clear()
        else:
            # Update valid attacks (can't attack again this turn)
            self.valid_attacks.clear()

        return result

    def try_move_unit(
        self,
        target: HexCoord,
        tiles: Dict[Tuple[int, int], Tile]
    ) -> bool:
        """
        Try to move the selected unit to target position.

        Returns:
            True if move was successful
        """
        if self.selected_unit is None:
            return False

        target_tuple = target.to_tuple()

        if target_tuple not in self.valid_moves:
            return False

        # Get source and target tiles
        source_tuple = self.selected_unit.position.to_tuple()
        source_tile = tiles.get(source_tuple)
        target_tile = tiles.get(target_tuple)

        if source_tile is None or target_tile is None:
            return False

        # Calculate movement cost (simplified: direct path cost)
        move_cost = self._calculate_path_cost(source_tuple, target_tuple, tiles)

        if not self.selected_unit.use_movement(move_cost):
            return False

        # Move the unit
        source_tile.unit = None
        target_tile.unit = self.selected_unit
        self.selected_unit.position = target

        # Update valid moves
        self.selected_hex = target
        if self.selected_unit.movement_remaining > 0:
            self.valid_moves = self._calculate_valid_moves(self.selected_unit, tiles)
        else:
            self.valid_moves.clear()

        return True

    def _calculate_path_cost(
        self,
        start: Tuple[int, int],
        end: Tuple[int, int],
        tiles: Dict[Tuple[int, int], Tile]
    ) -> int:
        """
        Calculate the minimum movement cost to reach end from start.
        Uses Dijkstra's algorithm.
        """
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

        return float('inf')

    def can_end_turn(self) -> bool:
        """Check if the current player can end their turn."""
        return True  # Always allow ending turn

    def get_status_text(self) -> str:
        """Get a status string for display."""
        return f"Tour {self.turn_number} - {self.current_player.name}"
