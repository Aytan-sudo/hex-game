"""
City system for the hex strategy game.

Cities are key locations that can produce units and resources.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict
from enum import Enum

from engine.hex_grid import HexCoord
from engine.unit import Army, ArmyUnit


class BuildingType(Enum):
    """Types of buildings that can be constructed in cities."""
    BARRACKS = "barracks"      # Produces infantry
    ARCHERY_RANGE = "archery"  # Produces archers
    STABLE = "stable"          # Produces cavalry
    MAGE_TOWER = "mage_tower"  # Produces mages
    WALLS = "walls"            # Increases defense
    MARKET = "market"          # Increases income


@dataclass
class Building:
    """A building in a city."""
    building_type: BuildingType
    level: int = 1

    @property
    def name(self) -> str:
        return self.building_type.value.replace("_", " ").title()


@dataclass
class City:
    """
    A city on the hex map.

    Cities can:
    - Produce units
    - Generate resources
    - Be captured by enemies
    """
    name: str
    position: HexCoord
    player_id: int
    population: int = 1000
    buildings: List[Building] = field(default_factory=list)

    # Production queue
    production_queue: List[str] = field(default_factory=list)
    production_progress: int = 0

    # City stats
    defense_bonus: int = 5
    income_per_turn: int = 10

    @property
    def garrison_strength(self) -> int:
        """Calculate defensive strength of the city."""
        base_strength = self.population // 100
        building_bonus = sum(
            b.level * 2 for b in self.buildings
            if b.building_type == BuildingType.WALLS
        )
        return base_strength + building_bonus + self.defense_bonus

    def can_produce(self, unit_type: str) -> bool:
        """Check if city can produce a specific unit type."""
        required_buildings = {
            "Lancer": None,  # Basic unit, no building required
            "Pikeman": None,
            "Archer": BuildingType.ARCHERY_RANGE,
            "Cavalry": BuildingType.STABLE,
            "Mage": BuildingType.MAGE_TOWER,
        }

        required = required_buildings.get(unit_type)
        if required is None:
            return True

        return any(b.building_type == required for b in self.buildings)

    def add_to_queue(self, unit_type: str) -> bool:
        """Add a unit to the production queue."""
        if not self.can_produce(unit_type):
            return False
        self.production_queue.append(unit_type)
        return True

    def process_turn(self) -> Optional[str]:
        """
        Process a turn of production.

        Returns:
            Name of completed unit, or None
        """
        if not self.production_queue:
            return None

        # Simple production: 10 progress per turn, 50 to complete
        self.production_progress += 10

        if self.production_progress >= 50:
            self.production_progress = 0
            return self.production_queue.pop(0)

        return None

    def add_building(self, building_type: BuildingType):
        """Add a building to the city."""
        # Check if building already exists
        for building in self.buildings:
            if building.building_type == building_type:
                building.level += 1
                return

        self.buildings.append(Building(building_type=building_type))

    def capture(self, new_player_id: int):
        """
        City is captured by another player.

        Population decreases on capture.
        """
        self.player_id = new_player_id
        self.population = int(self.population * 0.7)  # 30% loss on capture
        self.production_queue.clear()
        self.production_progress = 0

    def get_color(self) -> tuple[int, int, int]:
        """Get the display color based on player ownership."""
        # Player colors (expandable)
        player_colors = {
            0: (100, 100, 255),  # Blue (Player 1)
            1: (255, 100, 100),  # Red (Player 2)
            2: (100, 255, 100),  # Green (Player 3)
            3: (255, 255, 100),  # Yellow (Player 4)
        }
        return player_colors.get(self.player_id, (200, 200, 200))
