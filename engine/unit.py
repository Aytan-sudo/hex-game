"""
Unit system for the hex strategy game.

Provides base classes for units, armies, and heroes.
"""

from __future__ import annotations
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class UnitType(Enum):
    """Base unit types."""
    INFANTRY = "infantry"
    RANGED = "ranged"
    CAVALRY = "cavalry"
    SIEGE = "siege"
    HERO = "hero"


@dataclass
class UnitStats:
    """Stats for a unit or army."""
    max_hp: int
    current_hp: int
    attack: int
    defense: int
    movement: int  # Movement points per turn
    range: int = 1  # Attack range (1 = melee)

    def __post_init__(self):
        """Ensure current HP doesn't exceed max."""
        self.current_hp = min(self.current_hp, self.max_hp)

    @property
    def is_alive(self) -> bool:
        return self.current_hp > 0

    @property
    def hp_percentage(self) -> float:
        return self.current_hp / self.max_hp if self.max_hp > 0 else 0

    def take_damage(self, amount: int) -> int:
        """
        Apply damage to unit.

        Returns:
            Actual damage dealt (may be less if unit dies)
        """
        actual_damage = min(amount, self.current_hp)
        self.current_hp -= actual_damage
        return actual_damage

    def heal(self, amount: int) -> int:
        """
        Heal the unit.

        Returns:
            Actual amount healed
        """
        heal_amount = min(amount, self.max_hp - self.current_hp)
        self.current_hp += heal_amount
        return heal_amount


class Unit(ABC):
    """
    Abstract base class for all units.

    Units are entities that can move on the hex grid and participate in combat.
    """

    def __init__(
        self,
        name: str,
        unit_type: UnitType,
        stats: UnitStats,
        player_id: int = 0
    ):
        self.name = name
        self.unit_type = unit_type
        self.stats = stats
        self.player_id = player_id
        self.movement_remaining = stats.movement
        self.has_acted = False  # True if unit has attacked this turn

    @property
    def is_alive(self) -> bool:
        return self.stats.is_alive

    @abstractmethod
    def get_attack_power(self) -> int:
        """Calculate total attack power for combat."""
        pass

    @abstractmethod
    def get_defense_power(self) -> int:
        """Calculate total defense power for combat."""
        pass

    def start_turn(self):
        """Reset unit state at the start of a turn."""
        self.movement_remaining = self.stats.movement
        self.has_acted = False

    def end_turn(self):
        """Called when the unit's turn ends."""
        pass

    def can_move(self) -> bool:
        """Check if unit can still move this turn."""
        return self.movement_remaining > 0

    def can_attack(self) -> bool:
        """Check if unit can still attack this turn."""
        return not self.has_acted and self.is_alive

    def use_movement(self, cost: int) -> bool:
        """
        Spend movement points.

        Returns:
            True if successful, False if not enough movement
        """
        if cost > self.movement_remaining:
            return False
        self.movement_remaining -= cost
        return True


@dataclass
class ArmyUnit:
    """A single unit type within an army stack."""
    name: str
    unit_type: UnitType
    count: int  # Number of this unit in the stack
    base_stats: UnitStats  # Stats per individual unit

    @property
    def total_hp(self) -> int:
        """Total HP for all units of this type."""
        return self.base_stats.current_hp * self.count

    @property
    def total_attack(self) -> int:
        """Total attack for all units of this type."""
        return self.base_stats.attack * self.count

    @property
    def total_defense(self) -> int:
        """Total defense for all units of this type."""
        return self.base_stats.defense * self.count


class Army(Unit):
    """
    An army is a stack of multiple unit types that move together.

    Armies can contain different types of soldiers (infantry, archers, etc.)
    and optionally be led by a Hero.
    """

    def __init__(
        self,
        name: str,
        player_id: int = 0,
        units: Optional[List[ArmyUnit]] = None
    ):
        # Calculate aggregate stats from units
        base_stats = self._calculate_army_stats(units or [])

        super().__init__(
            name=name,
            unit_type=UnitType.INFANTRY,  # Default type
            stats=base_stats,
            player_id=player_id
        )

        self.units: List[ArmyUnit] = units or []
        self.hero: Optional[Hero] = None

    def _calculate_army_stats(self, units: List[ArmyUnit]) -> UnitStats:
        """Calculate aggregate stats from all units in the army."""
        if not units:
            return UnitStats(
                max_hp=0, current_hp=0,
                attack=0, defense=0,
                movement=0, range=1
            )

        total_hp = sum(u.total_hp for u in units)
        total_attack = sum(u.total_attack for u in units)
        total_defense = sum(u.total_defense for u in units)
        # Army moves at speed of slowest unit
        min_movement = min(u.base_stats.movement for u in units)
        # Army range is that of longest-range unit
        max_range = max(u.base_stats.range for u in units)

        return UnitStats(
            max_hp=total_hp,
            current_hp=total_hp,
            attack=total_attack,
            defense=total_defense,
            movement=min_movement,
            range=max_range
        )

    def get_attack_power(self) -> int:
        """Calculate total attack including hero bonus."""
        base_attack = sum(u.total_attack for u in self.units)
        hero_bonus = self.hero.get_attack_bonus() if self.hero else 0
        return base_attack + hero_bonus

    def get_defense_power(self) -> int:
        """Calculate total defense including hero bonus."""
        base_defense = sum(u.total_defense for u in self.units)
        hero_bonus = self.hero.get_defense_bonus() if self.hero else 0
        return base_defense + hero_bonus

    def add_unit(self, unit: ArmyUnit):
        """Add a unit type to the army."""
        # Check if we already have this unit type
        for existing in self.units:
            if existing.name == unit.name:
                existing.count += unit.count
                self._recalculate_stats()
                return

        self.units.append(unit)
        self._recalculate_stats()

    def attach_hero(self, hero: Hero):
        """Attach a hero to lead this army."""
        self.hero = hero
        hero.army = self

    def detach_hero(self) -> Optional[Hero]:
        """Detach and return the hero from this army."""
        hero = self.hero
        if hero:
            hero.army = None
        self.hero = None
        return hero

    def _recalculate_stats(self):
        """Recalculate aggregate stats after army composition changes."""
        new_stats = self._calculate_army_stats(self.units)
        self.stats = new_stats
        self.movement_remaining = min(self.movement_remaining, new_stats.movement)

    @property
    def total_unit_count(self) -> int:
        """Total number of individual soldiers in the army."""
        return sum(u.count for u in self.units)


class Hero(Unit):
    """
    A hero is a unique, powerful unit that can lead armies.

    Heroes have individual stats, can level up, and provide bonuses to armies.
    On the strategic map, heroes can:
    - Move independently on their own tile
    - Attach to an army to provide bonuses
    - Stack with other heroes on the same tile
    """

    def __init__(
        self,
        name: str,
        stats: UnitStats,
        player_id: int = 0,
        level: int = 1,
        experience: int = 0,
        hero_class: str = "Warrior"
    ):
        super().__init__(
            name=name,
            unit_type=UnitType.HERO,
            stats=stats,
            player_id=player_id
        )

        self.level = level
        self.experience = experience
        self.hero_class = hero_class  # Warrior, Mage, Scout, etc.
        self.army: Optional[Army] = None  # Army this hero is leading
        self.position: Optional[HexCoord] = None  # Position on strategic map (when not in army)

        # Hero-specific bonus stats
        self.leadership = 10  # Bonus to army under command
        self.magic = 0  # For future spell system

        # Visual
        self.portrait_letter = name[0].upper()  # First letter for display

    def get_attack_power(self) -> int:
        """Hero's personal attack power."""
        return self.stats.attack

    def get_defense_power(self) -> int:
        """Hero's personal defense power."""
        return self.stats.defense

    def get_attack_bonus(self) -> int:
        """Bonus attack provided to commanded army."""
        return self.leadership // 2

    def get_defense_bonus(self) -> int:
        """Bonus defense provided to commanded army."""
        return self.leadership // 3

    def gain_experience(self, amount: int):
        """
        Add experience points, potentially leveling up.

        Returns:
            Number of levels gained
        """
        self.experience += amount
        levels_gained = 0

        # Simple leveling: 100 XP per level
        xp_for_next = self.level * 100
        while self.experience >= xp_for_next:
            self.experience -= xp_for_next
            self.level += 1
            levels_gained += 1
            self._on_level_up()
            xp_for_next = self.level * 100

        return levels_gained

    def _on_level_up(self):
        """Apply stat increases on level up."""
        self.stats.max_hp += 5
        self.stats.current_hp += 5
        self.stats.attack += 2
        self.stats.defense += 1
        self.leadership += 2

    def join_army(self, army: 'Army') -> bool:
        """
        Join an army as its commander.

        Args:
            army: The army to join

        Returns:
            True if successful, False if army already has a hero
        """
        if army.hero is not None:
            return False

        self.army = army
        army.hero = self
        # Hero's position is now the army's position
        self.position = None
        return True

    def leave_army(self) -> bool:
        """
        Leave the current army.

        Returns:
            True if successful, False if not in an army
        """
        if self.army is None:
            return False

        # Take army's position as hero's position
        if hasattr(self.army, 'position'):
            self.position = self.army.position

        self.army.hero = None
        self.army = None
        return True

    @property
    def is_independent(self) -> bool:
        """Check if hero is moving independently (not attached to army)."""
        return self.army is None

    @property
    def effective_position(self) -> Optional[HexCoord]:
        """Get hero's position (own position if independent, army's if attached)."""
        if self.army is not None and hasattr(self.army, 'position'):
            return self.army.position
        return self.position
