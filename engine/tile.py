"""
Tile system for the hex grid.

Each tile represents a single hexagon on the map with its terrain,
movement costs, and other properties.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from enum import Enum

from .hex_grid import HexCoord

if TYPE_CHECKING:
    from .unit import Unit


@dataclass
class TerrainConfig:
    """Configuration for a terrain type."""
    name: str
    movement_cost: int  # 1 = normal, 2 = difficult, -1 = impassable
    defense_bonus: int  # Bonus to defense when unit is on this terrain
    color: tuple[int, int, int]  # RGB color for rendering


@dataclass
class Tile:
    """
    Represents a single hexagonal tile on the map.

    Attributes:
        position: Axial hex coordinate of this tile
        terrain: Terrain configuration for this tile
        unit: Unit currently occupying this tile (if any)
        is_visible: Whether tile is visible to current player
        is_explored: Whether tile has been explored (fog of war)
    """
    position: HexCoord
    terrain: TerrainConfig
    unit: Optional[Unit] = None
    is_visible: bool = True
    is_explored: bool = True

    @property
    def is_passable(self) -> bool:
        """Check if units can move through this tile."""
        return self.terrain.movement_cost > 0

    @property
    def is_occupied(self) -> bool:
        """Check if a unit is on this tile."""
        return self.unit is not None

    def can_enter(self, unit: Optional[Unit] = None) -> bool:
        """
        Check if a unit can enter this tile.

        Args:
            unit: The unit trying to enter (for future unit-specific rules)

        Returns:
            True if tile is passable and unoccupied
        """
        return self.is_passable and not self.is_occupied

    def get_movement_cost(self, unit: Optional[Unit] = None) -> int:
        """
        Get the movement cost to enter this tile.

        Args:
            unit: The unit moving (for future unit-specific modifiers)

        Returns:
            Movement cost, or -1 if impassable
        """
        return self.terrain.movement_cost

    def place_unit(self, unit: Unit) -> bool:
        """
        Place a unit on this tile.

        Args:
            unit: Unit to place

        Returns:
            True if successful, False if tile already occupied
        """
        if self.is_occupied:
            return False
        self.unit = unit
        return True

    def remove_unit(self) -> Optional[Unit]:
        """
        Remove and return the unit from this tile.

        Returns:
            The removed unit, or None if no unit was present
        """
        unit = self.unit
        self.unit = None
        return unit
