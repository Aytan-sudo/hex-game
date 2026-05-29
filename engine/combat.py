"""
Combat system for the hex strategy game.

Handles combat resolution between units and armies.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, Tuple
import random

from .unit import Unit, Army, Hero
from .tile import Tile


@dataclass
class CombatResult:
    """Result of a combat encounter."""
    attacker_damage: int  # Damage dealt to attacker
    defender_damage: int  # Damage dealt to defender
    attacker_survived: bool
    defender_survived: bool
    attacker_killed: int = 0  # Units killed (for armies)
    defender_killed: int = 0

    @property
    def attacker_won(self) -> bool:
        """Attacker wins if defender is destroyed."""
        return not self.defender_survived

    @property
    def defender_won(self) -> bool:
        """Defender wins if attacker is destroyed."""
        return not self.attacker_survived


class CombatSystem:
    """
    Handles combat calculations and resolution.

    Uses a simple attack vs defense system with randomness.
    """

    def __init__(self, random_factor: float = 0.2):
        """
        Initialize combat system.

        Args:
            random_factor: Amount of randomness in combat (0.0 to 1.0)
                          0.0 = deterministic, 1.0 = highly random
        """
        self.random_factor = random_factor

    def can_attack(
        self,
        attacker: Unit,
        defender: Unit,
        attacker_tile: Optional[Tile] = None,
        defender_tile: Optional[Tile] = None,
        distance: int = 1
    ) -> Tuple[bool, str]:
        """
        Check if an attack is valid.

        Returns:
            (can_attack, reason) tuple
        """
        if not attacker.is_alive:
            return False, "Attacker is dead"

        if not defender.is_alive:
            return False, "Defender is already dead"

        if not attacker.can_attack():
            return False, "Attacker has already acted this turn"

        if attacker.player_id == defender.player_id:
            return False, "Cannot attack friendly units"

        if distance > attacker.stats.range:
            return False, f"Target out of range (range: {attacker.stats.range}, distance: {distance})"

        return True, "Attack valid"

    def resolve_combat(
        self,
        attacker: Unit,
        defender: Unit,
        attacker_tile: Optional[Tile] = None,
        defender_tile: Optional[Tile] = None,
        distance: int = 1
    ) -> CombatResult:
        """
        Resolve combat between two units.

        The attacker strikes first, then the defender counter-attacks
        if still alive and the attacker is within the defender's range.

        Args:
            attacker: The attacking unit
            defender: The defending unit
            attacker_tile: Tile the attacker is on (for terrain bonuses)
            defender_tile: Tile the defender is on (for terrain bonuses)
            distance: Hex distance between attacker and defender. The defender
                only counter-attacks if this is within its own range (e.g. a
                melee unit cannot riposte against an archer firing from afar).

        Returns:
            CombatResult with damage dealt and survival status
        """
        # Calculate terrain bonuses
        attacker_terrain_bonus = 0
        defender_terrain_bonus = 0

        if defender_tile:
            defender_terrain_bonus = defender_tile.defense_bonus

        # Calculate attack damage
        attacker_power = self._calculate_attack_damage(
            attacker.get_attack_power(),
            defender.get_defense_power() + defender_terrain_bonus
        )

        # Apply damage to defender
        defender_damage = defender.stats.take_damage(attacker_power)

        # Counter-attack if defender survives and the attacker is within
        # the defender's range (a melee unit cannot riposte a ranged strike).
        attacker_damage = 0
        if defender.is_alive and distance <= defender.stats.range:
            # Defender's counter-attack is weaker
            counter_power = self._calculate_attack_damage(
                defender.get_attack_power() // 2,
                attacker.get_defense_power() + attacker_terrain_bonus
            )
            attacker_damage = attacker.stats.take_damage(counter_power)

        # Mark attacker as having acted
        attacker.has_acted = True

        return CombatResult(
            attacker_damage=attacker_damage,
            defender_damage=defender_damage,
            attacker_survived=attacker.is_alive,
            defender_survived=defender.is_alive
        )

    def _calculate_attack_damage(self, attack: int, defense: int) -> int:
        """
        Calculate damage from an attack.

        Uses formula: base_damage = attack - defense/2
        Then applies random factor.
        """
        # Base damage calculation
        base_damage = max(1, attack - defense // 2)

        # Apply randomness
        if self.random_factor > 0:
            variance = int(base_damage * self.random_factor)
            base_damage += random.randint(-variance, variance)

        return max(1, base_damage)  # Minimum 1 damage

    def calculate_expected_damage(
        self,
        attacker: Unit,
        defender: Unit,
        defender_tile: Optional[Tile] = None,
        distance: int = 1
    ) -> Tuple[int, int]:
        """
        Calculate expected damage without randomness (for UI preview).

        Returns:
            (damage_to_defender, counter_damage_to_attacker)
        """
        defender_terrain_bonus = 0
        if defender_tile:
            defender_terrain_bonus = defender_tile.defense_bonus

        # Expected damage to defender
        attack_power = attacker.get_attack_power()
        defend_power = defender.get_defense_power() + defender_terrain_bonus
        expected_damage = max(1, attack_power - defend_power // 2)

        # Expected counter-damage (only if attacker is within the defender's range)
        counter_damage = 0
        if distance <= defender.stats.range:
            counter_power = defender.get_attack_power() // 2
            attacker_defense = attacker.get_defense_power()
            counter_damage = max(1, counter_power - attacker_defense // 2)

        return expected_damage, counter_damage
