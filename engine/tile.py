"""
Tile system for the hex grid.

Each tile represents a single hexagon on the map with its terrain,
overlay (construction), movement costs, and other properties.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Optional, TYPE_CHECKING, Tuple

from .hex_grid import HexCoord

if TYPE_CHECKING:
    from .unit import Unit
    from game.terrain import TerrainType, OverlayType


@dataclass
class Tile:
    """
    Represents a single hexagonal tile on the map.

    Attributes:
        position: Axial hex coordinate of this tile
        base_terrain: Base terrain type (TerrainType enum value)
        overlay: Optional overlay/construction type (OverlayType enum value)
        unit: Unit currently occupying this tile (if any)
        is_visible: Whether tile is visible to current player
        is_explored: Whether tile has been explored (fog of war)
    """
    position: HexCoord
    base_terrain: "TerrainType"
    overlay: Optional["OverlayType"] = None
    unit: Optional["Unit"] = None
    is_visible: bool = True
    is_explored: bool = True

    @property
    def is_passable(self) -> bool:
        """Check if units can move through this tile."""
        return self.get_movement_cost() > 0

    @property
    def is_occupied(self) -> bool:
        """Check if a unit is on this tile."""
        return self.unit is not None

    @property
    def display_color(self) -> Tuple[int, int, int]:
        """Get the display color for this tile."""
        from game.terrain import get_display_color
        return get_display_color(self.base_terrain, self.overlay)

    @property
    def display_name(self) -> str:
        """Get the display name for this tile."""
        from game.terrain import get_display_name
        return get_display_name(self.base_terrain, self.overlay)

    @property
    def defense_bonus(self) -> int:
        """Get the combined defense bonus for this tile."""
        from game.terrain import calculate_combined_defense_bonus
        return calculate_combined_defense_bonus(self.base_terrain, self.overlay)

    def can_enter(self, unit: Optional["Unit"] = None) -> bool:
        """
        Check if a unit can enter this tile.

        Args:
            unit: The unit trying to enter (for future unit-specific rules)

        Returns:
            True if tile is passable and unoccupied
        """
        return self.is_passable and not self.is_occupied

    def get_movement_cost(self, unit: Optional["Unit"] = None) -> int:
        """
        Get the movement cost to enter this tile.

        Args:
            unit: The unit moving (for future unit-specific modifiers)

        Returns:
            Movement cost, or -1 if impassable
        """
        from game.terrain import calculate_combined_movement_cost
        return calculate_combined_movement_cost(self.base_terrain, self.overlay)

    def place_unit(self, unit: "Unit") -> bool:
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

    def remove_unit(self) -> Optional["Unit"]:
        """
        Remove and return the unit from this tile.

        Returns:
            The removed unit, or None if no unit was present
        """
        unit = self.unit
        self.unit = None
        return unit
