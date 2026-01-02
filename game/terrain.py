"""
Terrain types for the hex strategy game.

Defines base terrain types and overlay/construction types.
Each tile has a base terrain and optionally an overlay (city, road, bridge, ruins).
The combined modifiers are calculated from both base terrain and overlay.
"""

from enum import Enum
from dataclasses import dataclass
from typing import Optional, Tuple


@dataclass
class TerrainConfig:
    """Configuration for a terrain type."""
    name: str
    movement_cost: int  # 1 = normal, 2 = difficult, -1 = impassable
    defense_bonus: int  # Bonus to defense when unit is on this terrain
    color: Tuple[int, int, int]  # RGB color for rendering


@dataclass
class OverlayConfig:
    """Configuration for an overlay/construction type."""
    name: str
    movement_cost_modifier: int  # Added to base terrain (negative = faster, -999 = set to 1)
    defense_bonus_modifier: int  # Added to base terrain defense
    color: Tuple[int, int, int]  # RGB color for rendering (overrides base terrain)
    makes_passable: bool = False  # If True, makes impassable terrain passable (bridges)


class TerrainType(Enum):
    """Base terrain types."""
    PLAINS = "plains"
    HILLS = "hills"
    FOREST = "forest"
    MOUNTAIN = "mountain"
    WATER = "water"
    DESERT = "desert"
    SWAMP = "swamp"


class OverlayType(Enum):
    """Overlay/construction types that can be placed on base terrain."""
    ROAD = "road"
    CITY = "city"
    BRIDGE = "bridge"
    RUINS = "ruins"


# Base terrain configurations
TERRAIN_CONFIGS: dict[TerrainType, TerrainConfig] = {
    TerrainType.PLAINS: TerrainConfig(
        name="Plains",
        movement_cost=1,
        defense_bonus=0,
        color=(144, 238, 144)  # Light green
    ),

    TerrainType.HILLS: TerrainConfig(
        name="Hills",
        movement_cost=2,
        defense_bonus=2,
        color=(180, 200, 120)  # Yellow-green
    ),

    TerrainType.FOREST: TerrainConfig(
        name="Forest",
        movement_cost=2,
        defense_bonus=2,
        color=(34, 139, 34)  # Forest green
    ),

    TerrainType.MOUNTAIN: TerrainConfig(
        name="Mountain",
        movement_cost=3,
        defense_bonus=4,
        color=(139, 137, 137)  # Gray
    ),

    TerrainType.WATER: TerrainConfig(
        name="Water",
        movement_cost=-1,  # Impassable
        defense_bonus=0,
        color=(65, 105, 225)  # Royal blue
    ),

    TerrainType.DESERT: TerrainConfig(
        name="Desert",
        movement_cost=2,
        defense_bonus=-1,  # Penalty in desert
        color=(238, 221, 130)  # Light goldenrod
    ),

    TerrainType.SWAMP: TerrainConfig(
        name="Swamp",
        movement_cost=3,
        defense_bonus=1,
        color=(85, 107, 47)  # Dark olive green
    ),
}


# Overlay configurations
OVERLAY_CONFIGS: dict[OverlayType, OverlayConfig] = {
    OverlayType.ROAD: OverlayConfig(
        name="Road",
        movement_cost_modifier=-999,  # Roads set movement cost to 1
        defense_bonus_modifier=-1,  # Exposed on roads
        color=(210, 180, 140)  # Tan
    ),

    OverlayType.CITY: OverlayConfig(
        name="City",
        movement_cost_modifier=-999,  # Cities set movement cost to 1
        defense_bonus_modifier=3,  # Good defense in cities
        color=(169, 169, 169)  # Dark gray
    ),

    OverlayType.BRIDGE: OverlayConfig(
        name="Bridge",
        movement_cost_modifier=-999,  # Bridges set movement cost to 1
        defense_bonus_modifier=-2,  # Very exposed on bridges
        color=(139, 90, 43),  # Saddle brown (wooden bridge)
        makes_passable=True  # Makes water passable
    ),

    OverlayType.RUINS: OverlayConfig(
        name="Ruins",
        movement_cost_modifier=0,  # No change to movement
        defense_bonus_modifier=1,  # Slight cover from ruins
        color=(120, 100, 90)  # Brown-gray
    ),
}


def get_terrain_config(terrain_type: TerrainType) -> TerrainConfig:
    """Get the configuration for a terrain type."""
    return TERRAIN_CONFIGS[terrain_type]


def get_overlay_config(overlay_type: OverlayType) -> OverlayConfig:
    """Get the configuration for an overlay type."""
    return OVERLAY_CONFIGS[overlay_type]


def calculate_combined_movement_cost(
    base_terrain: TerrainType,
    overlay: Optional[OverlayType] = None
) -> int:
    """
    Calculate the combined movement cost for a terrain with optional overlay.

    Args:
        base_terrain: The base terrain type
        overlay: Optional overlay on the terrain

    Returns:
        Movement cost (-1 if impassable)
    """
    base_config = TERRAIN_CONFIGS[base_terrain]
    base_cost = base_config.movement_cost

    if overlay is None:
        return base_cost

    overlay_config = OVERLAY_CONFIGS[overlay]

    # Bridge makes water passable
    if overlay_config.makes_passable and base_cost < 0:
        return 1

    # If base terrain is impassable and overlay doesn't make it passable
    if base_cost < 0:
        return base_cost

    # Special modifier -999 means "set to 1"
    if overlay_config.movement_cost_modifier == -999:
        return 1

    # Normal modifier: add to base
    combined = base_cost + overlay_config.movement_cost_modifier
    return max(1, combined)  # Minimum of 1


def calculate_combined_defense_bonus(
    base_terrain: TerrainType,
    overlay: Optional[OverlayType] = None
) -> int:
    """
    Calculate the combined defense bonus for a terrain with optional overlay.

    Args:
        base_terrain: The base terrain type
        overlay: Optional overlay on the terrain

    Returns:
        Defense bonus (can be negative)
    """
    base_config = TERRAIN_CONFIGS[base_terrain]
    base_defense = base_config.defense_bonus

    if overlay is None:
        return base_defense

    overlay_config = OVERLAY_CONFIGS[overlay]
    return base_defense + overlay_config.defense_bonus_modifier


def get_display_color(
    base_terrain: TerrainType,
    overlay: Optional[OverlayType] = None
) -> Tuple[int, int, int]:
    """
    Get the display color for a terrain with optional overlay.
    Overlays override the base terrain color.

    Args:
        base_terrain: The base terrain type
        overlay: Optional overlay on the terrain

    Returns:
        RGB color tuple
    """
    if overlay is not None:
        return OVERLAY_CONFIGS[overlay].color
    return TERRAIN_CONFIGS[base_terrain].color


def get_display_name(
    base_terrain: TerrainType,
    overlay: Optional[OverlayType] = None
) -> str:
    """
    Get the display name for a terrain with optional overlay.

    Args:
        base_terrain: The base terrain type
        overlay: Optional overlay on the terrain

    Returns:
        Display name (e.g., "City (Plains)" or "Plains")
    """
    base_name = TERRAIN_CONFIGS[base_terrain].name

    if overlay is None:
        return base_name

    overlay_name = OVERLAY_CONFIGS[overlay].name
    return f"{overlay_name} ({base_name})"
