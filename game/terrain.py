"""
Terrain types for the hex strategy game.

Defines all available terrain types with their properties.
"""

from enum import Enum
from engine.tile import TerrainConfig


class TerrainType(Enum):
    """Available terrain types in the game."""
    PLAINS = "plains"
    FOREST = "forest"
    MOUNTAIN = "mountain"
    WATER = "water"
    DESERT = "desert"
    SWAMP = "swamp"
    ROAD = "road"


# Terrain configurations with gameplay properties
TERRAIN_CONFIGS: dict[TerrainType, TerrainConfig] = {
    TerrainType.PLAINS: TerrainConfig(
        name="Plains",
        movement_cost=1,
        defense_bonus=0,
        color=(144, 238, 144)  # Light green
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

    TerrainType.ROAD: TerrainConfig(
        name="Road",
        movement_cost=1,  # Fast movement
        defense_bonus=-1,  # Exposed on roads
        color=(210, 180, 140)  # Tan
    ),
}


def get_terrain_config(terrain_type: TerrainType) -> TerrainConfig:
    """Get the configuration for a terrain type."""
    return TERRAIN_CONFIGS[terrain_type]
