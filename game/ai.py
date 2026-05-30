"""
AI player logic for the hex strategy game.

Handles automated decision-making for non-human players.
Each AI has a personality that influences its behavior.
"""

from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Dict, List, Optional, Tuple
import random

from engine.hex_grid import HexCoord
from engine.pathfinding import find_path, calculate_path_cost

if TYPE_CHECKING:
    from engine.tile import Tile
    from engine.unit import Army
    from game.strategic_map import StrategicGameState


class AIPersonality(Enum):
    """Personality types that influence AI behavior."""
    AGGRESSIVE = "aggressive"      # Seeks combat, prioritizes attacking
    DEFENSIVE = "defensive"        # Avoids combat unless advantageous, seeks terrain bonuses
    MOBILE = "mobile"              # Prioritizes movement and exploration
    PASSIVE = "passive"            # Minimal movement, holds position


@dataclass
class AIConfig:
    """Configuration parameters for AI behavior by personality."""
    # Probability weights (0.0 to 1.0)
    attack_weight: float          # How much the AI values attacking
    defense_weight: float         # How much the AI values defensive positions
    movement_weight: float        # How much the AI values moving
    hold_weight: float            # How much the AI values staying in place

    # Thresholds
    min_strength_ratio_to_attack: float  # Minimum own/enemy strength ratio to consider attack
    preferred_terrain_bonus: int         # Minimum terrain defense bonus to seek


# Personality configurations
AI_CONFIGS: Dict[AIPersonality, AIConfig] = {
    AIPersonality.AGGRESSIVE: AIConfig(
        attack_weight=0.8,
        defense_weight=0.1,
        movement_weight=0.5,
        hold_weight=0.1,
        min_strength_ratio_to_attack=0.5,  # Will attack even when weaker
        preferred_terrain_bonus=0,
    ),
    AIPersonality.DEFENSIVE: AIConfig(
        attack_weight=0.3,
        defense_weight=0.8,
        movement_weight=0.3,
        hold_weight=0.5,
        min_strength_ratio_to_attack=1.5,  # Only attacks when clearly stronger
        preferred_terrain_bonus=2,
    ),
    AIPersonality.MOBILE: AIConfig(
        attack_weight=0.4,
        defense_weight=0.2,
        movement_weight=0.9,
        hold_weight=0.1,
        min_strength_ratio_to_attack=0.8,
        preferred_terrain_bonus=0,
    ),
    AIPersonality.PASSIVE: AIConfig(
        attack_weight=0.1,
        defense_weight=0.5,
        movement_weight=0.1,
        hold_weight=0.9,
        min_strength_ratio_to_attack=2.0,  # Very reluctant to attack
        preferred_terrain_bonus=1,
    ),
}


@dataclass
class AIAction:
    """Represents a single action the AI wants to take."""
    army: Army
    target_pos: Tuple[int, int]
    is_attack: bool = False
    priority: float = 0.0


class AIPlayer:
    """
    AI controller for a non-human player.

    Evaluates the game state and decides actions for all armies
    belonging to the AI player.
    """

    def __init__(self, player_id: int, personality: AIPersonality = AIPersonality.AGGRESSIVE):
        self.player_id = player_id
        self.personality = personality
        self.config = AI_CONFIGS[personality]

    def plan_turn(
        self,
        tiles: Dict[Tuple[int, int], Tile],
        armies: List[Army],
        game_state: StrategicGameState
    ) -> List[AIAction]:
        """
        Plan all actions for this AI's turn.

        Returns a list of actions sorted by priority (highest first).
        """
        my_armies = [a for a in armies if a.player_id == self.player_id]
        enemy_armies = [a for a in armies if a.player_id != self.player_id]

        actions: List[AIAction] = []

        for army in my_armies:
            if army.movement_remaining <= 0:
                continue

            action = self._evaluate_best_action(army, tiles, enemy_armies, game_state)
            if action:
                actions.append(action)

        # Sort by priority (highest first)
        actions.sort(key=lambda a: a.priority, reverse=True)
        return actions

    def _evaluate_best_action(
        self,
        army: Army,
        tiles: Dict[Tuple[int, int], Tile],
        enemy_armies: List[Army],
        game_state: StrategicGameState
    ) -> Optional[AIAction]:
        """Evaluate and return the best action for a single army."""
        current_pos = army.position.to_tuple()
        current_tile = tiles.get(current_pos)

        if current_tile is None:
            return None

        # Calculate valid moves for this army
        valid_moves = self._calculate_valid_moves(army, tiles)

        if not valid_moves:
            return None

        best_action: Optional[AIAction] = None
        best_score = -float('inf')

        for target_pos in valid_moves:
            target_tile = tiles.get(target_pos)
            if target_tile is None:
                continue

            score = self._score_move(army, target_pos, target_tile, enemy_armies, tiles)

            if score > best_score:
                best_score = score
                is_attack = (
                    target_tile.unit is not None and
                    target_tile.unit.player_id != self.player_id
                )
                best_action = AIAction(
                    army=army,
                    target_pos=target_pos,
                    is_attack=is_attack,
                    priority=score
                )

        # Consider holding position
        hold_score = self._score_hold(army, current_tile, enemy_armies)
        if hold_score > best_score:
            return None  # Don't move

        return best_action

    def _calculate_valid_moves(
        self,
        army: Army,
        tiles: Dict[Tuple[int, int], Tile]
    ) -> List[Tuple[int, int]]:
        """Calculate valid move destinations using BFS."""
        valid = []
        start = army.position.to_tuple()

        queue = [(start, army.movement_remaining)]
        visited = {start: army.movement_remaining}

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

                # Can move to empty tiles or enemy tiles (battle)
                if tile.unit is None:
                    valid.append(neighbor_tuple)
                elif tile.unit.player_id != army.player_id:
                    valid.append(neighbor_tuple)

                # Continue exploring from empty tiles
                if tile.unit is None:
                    queue.append((neighbor_tuple, new_remaining))

        return valid

    def _score_move(
        self,
        army: Army,
        target_pos: Tuple[int, int],
        target_tile: Tile,
        enemy_armies: List[Army],
        tiles: Dict[Tuple[int, int], Tile]
    ) -> float:
        """Score a potential move based on AI personality."""
        score = 0.0
        cfg = self.config

        # Attack scoring
        if target_tile.unit and target_tile.unit.player_id != self.player_id:
            enemy = target_tile.unit
            strength_ratio = army.total_unit_count / max(1, enemy.total_unit_count)

            if strength_ratio >= cfg.min_strength_ratio_to_attack:
                # Bonus for favorable matchups
                score += cfg.attack_weight * 100 * strength_ratio
            else:
                # Penalty for attacking when weak
                score -= cfg.attack_weight * 50

        # Terrain defense scoring
        terrain_bonus = target_tile.defense_bonus
        if terrain_bonus >= cfg.preferred_terrain_bonus:
            score += cfg.defense_weight * terrain_bonus * 20

        # Distance to nearest enemy (for aggressive/mobile)
        min_enemy_dist = self._distance_to_nearest_enemy(target_pos, enemy_armies)
        if cfg.attack_weight > 0.5:
            # Aggressive: prefer being close to enemies
            score += cfg.attack_weight * (10 - min(10, min_enemy_dist)) * 5
        elif cfg.defense_weight > 0.5:
            # Defensive: prefer being far from enemies (unless on good terrain)
            if terrain_bonus < cfg.preferred_terrain_bonus:
                score += cfg.defense_weight * min(10, min_enemy_dist) * 3

        # Movement value (mobile personalities like to use movement)
        move_cost = calculate_path_cost(army.position.to_tuple(), target_pos, tiles)
        score += cfg.movement_weight * move_cost * 2

        # Add small random factor for variety
        score += random.uniform(0, 5)

        return score

    def _score_hold(
        self,
        army: Army,
        current_tile: Tile,
        enemy_armies: List[Army]
    ) -> float:
        """Score staying in current position."""
        cfg = self.config
        score = cfg.hold_weight * 50

        # Bonus for good defensive terrain
        score += cfg.defense_weight * current_tile.defense_bonus * 15

        # Passive AI gets extra hold bonus
        if self.personality == AIPersonality.PASSIVE:
            score += 30

        return score

    def _distance_to_nearest_enemy(
        self,
        pos: Tuple[int, int],
        enemy_armies: List[Army]
    ) -> int:
        """Calculate distance to the nearest enemy army."""
        if not enemy_armies:
            return 999

        coord = HexCoord(*pos)
        min_dist = 999

        for enemy in enemy_armies:
            if enemy.position:
                dist = coord.distance_to(enemy.position)
                min_dist = min(min_dist, dist)

        return min_dist


# =============================================================================
# TACTICAL AI
# =============================================================================

@dataclass
class TacticalAction:
    """Represents an action for a tactical unit."""
    unit: any  # TacticalUnit
    action_type: str  # "move", "attack", "move_and_attack"
    target_pos: Optional[Tuple[int, int]] = None
    attack_target: Optional[any] = None  # TacticalUnit
    priority: float = 0.0


class TacticalAI:
    """
    AI controller for tactical battles.

    Uses the same personality system as strategic AI to make
    decisions about unit movement and attacks.
    """

    def __init__(self, player_id: int, personality: AIPersonality = AIPersonality.AGGRESSIVE):
        self.player_id = player_id
        self.personality = personality
        self.config = AI_CONFIGS[personality]

    def play_turn(
        self,
        battle: any  # TacticalBattle
    ) -> Optional[TacticalAction]:
        """
        Decide and return the next action for AI turn.

        Returns None when AI turn is complete (all units acted).
        """
        my_units = battle.get_units_for_player(self.player_id)
        enemies = battle.get_enemy_units(self.player_id)

        if not my_units or not enemies:
            return None

        # Find units that can still act.
        # Une unité agit une seule fois par tour (déplacement + attaque éventuelle
        # résolus en une activation). On se base donc sur ``has_acted``, qui est
        # positionné après chaque action dans TacticalBattle._execute_ai_action.
        # Sans cela, une unité qui ne fait que se déplacer restait « disponible »
        # et était re-sélectionnée en boucle, multipliant les délais de tour.
        available_units = [
            u for u in my_units
            if u.is_alive and not u.has_acted
        ]

        if not available_units:
            return None

        # Evaluate best action for each available unit
        best_action: Optional[TacticalAction] = None
        best_score = -float('inf')

        for unit in available_units:
            action = self._evaluate_unit_action(unit, battle, enemies)
            if action and action.priority > best_score:
                best_score = action.priority
                best_action = action

        return best_action

    def _evaluate_unit_action(
        self,
        unit: any,  # TacticalUnit
        battle: any,  # TacticalBattle
        enemies: List[any]
    ) -> Optional[TacticalAction]:
        """Evaluate and return best action for a single unit."""
        cfg = self.config

        # Select this unit to get valid moves/attacks
        battle.select_unit(unit)

        best_action: Optional[TacticalAction] = None
        best_score = -float('inf')

        # Evaluate direct attacks from current position
        if battle.valid_attacks and not unit.has_acted:
            for attack_pos in battle.valid_attacks:
                target_tile = battle.tiles.get(attack_pos)
                if target_tile and target_tile.unit:
                    score = self._score_attack(unit, target_tile.unit, battle)
                    if score > best_score:
                        best_score = score
                        best_action = TacticalAction(
                            unit=unit,
                            action_type="attack",
                            attack_target=target_tile.unit,
                            target_pos=attack_pos,
                            priority=score
                        )

        # Evaluate moves (and potential attacks after moving)
        if battle.valid_moves and unit.movement_remaining > 0:
            for move_pos in battle.valid_moves:
                move_tile = battle.tiles.get(move_pos)
                if not move_tile:
                    continue

                # Score move position
                move_score = self._score_position(move_pos, move_tile, enemies, battle)

                # Check if we can attack after moving
                attack_target = self._find_attack_target_from(move_pos, unit, battle, enemies)

                if attack_target and not unit.has_acted:
                    # Move + attack is very valuable
                    attack_score = self._score_attack(unit, attack_target, battle)
                    total_score = move_score + attack_score * 1.5

                    if total_score > best_score:
                        best_score = total_score
                        best_action = TacticalAction(
                            unit=unit,
                            action_type="move_and_attack",
                            target_pos=move_pos,
                            attack_target=attack_target,
                            priority=total_score
                        )
                else:
                    # Just move
                    if move_score > best_score:
                        best_score = move_score
                        best_action = TacticalAction(
                            unit=unit,
                            action_type="move",
                            target_pos=move_pos,
                            priority=move_score
                        )

        # Consider holding position (especially for defensive AI)
        hold_score = cfg.hold_weight * 30 + cfg.defense_weight * unit.position.distance_to(HexCoord(0, 0)) * 0.1
        if hold_score > best_score and unit.has_acted:
            return None  # Don't move, end unit's turn

        return best_action

    def _score_attack(
        self,
        attacker: any,  # TacticalUnit
        target: any,  # TacticalUnit
        battle: any
    ) -> float:
        """Score an attack action."""
        cfg = self.config
        score = cfg.attack_weight * 100

        # Prioritize low HP targets (can kill)
        if target.stats.current_hp <= attacker.stats.attack:
            score += 50  # Kill bonus

        # Prioritize high-value targets
        score += target.stats.attack * 2  # Removing high attack units is valuable

        # Consider our survivability
        if attacker.stats.current_hp < target.stats.attack:
            score -= cfg.defense_weight * 30  # Risk penalty

        # Ranged units are safer attackers
        if attacker.stats.range > 1:
            score += 20

        return score

    def _score_position(
        self,
        pos: Tuple[int, int],
        tile: any,  # Tile
        enemies: List[any],
        battle: any
    ) -> float:
        """Score a position for movement."""
        cfg = self.config
        score = cfg.movement_weight * 10

        # Terrain defense bonus
        score += cfg.defense_weight * tile.defense_bonus * 15

        # Distance to nearest enemy
        min_dist = self._distance_to_nearest_unit(pos, enemies)

        if cfg.attack_weight > 0.5:
            # Aggressive: prefer being close
            score += cfg.attack_weight * (10 - min(10, min_dist)) * 8
        elif cfg.defense_weight > 0.5:
            # Defensive: prefer distance unless on good terrain
            if tile.defense_bonus < cfg.preferred_terrain_bonus:
                score += cfg.defense_weight * min(10, min_dist) * 5

        # Add small randomness
        score += random.uniform(0, 3)

        return score

    def _find_attack_target_from(
        self,
        pos: Tuple[int, int],
        unit: any,  # TacticalUnit
        battle: any,
        enemies: List[any]
    ) -> Optional[any]:
        """Find best attack target from a given position."""
        attack_range = unit.stats.range
        pos_coord = HexCoord(*pos)

        best_target = None
        best_score = -float('inf')

        for enemy in enemies:
            if not enemy.is_alive or enemy.position is None:
                continue

            dist = pos_coord.distance_to(enemy.position)
            if dist <= attack_range:
                # Score this target
                score = self._score_attack(unit, enemy, battle)
                if score > best_score:
                    best_score = score
                    best_target = enemy

        return best_target

    def _distance_to_nearest_unit(
        self,
        pos: Tuple[int, int],
        units: List[any]
    ) -> int:
        """Calculate distance to nearest unit."""
        if not units:
            return 999

        coord = HexCoord(*pos)
        min_dist = 999

        for unit in units:
            if unit.position:
                dist = coord.distance_to(unit.position)
                min_dist = min(min_dist, dist)

        return min_dist
