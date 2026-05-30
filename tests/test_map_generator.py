"""
Génération de carte (game/map_generator.py).

On verrouille surtout le **déterminisme par seed** (AUDIT §2.11 note que l'ordre
des appels random global peut influer ; ``generate()`` ré-amorce ``random.seed``,
ce test garantit que deux générateurs de même seed produisent la même carte).
"""

import random

from engine.tile import Tile
from game.map_generator import MapConfig, MapGenerator
from game.terrain import TerrainType


def _generate(seed, width=24, height=24):
    return MapGenerator(MapConfig(width=width, height=height, seed=seed)).generate()


def test_generate_returns_tiles():
    tiles = _generate(seed=1)
    assert len(tiles) > 0
    assert all(isinstance(t, Tile) for t in tiles.values())
    assert all(isinstance(t.base_terrain, TerrainType) for t in tiles.values())


def test_same_seed_is_deterministic():
    a = _generate(seed=42)
    b = _generate(seed=42)
    assert a.keys() == b.keys()
    assert {p: t.base_terrain for p, t in a.items()} == \
           {p: t.base_terrain for p, t in b.items()}


def test_same_seed_deterministic_despite_global_random_state():
    """Le ré-amorçage interne protège du bruit du random global."""
    random.seed(1)
    a = _generate(seed=7)
    random.seed(999)
    [random.random() for _ in range(50)]  # pollue l'état global
    b = _generate(seed=7)
    assert {p: t.base_terrain for p, t in a.items()} == \
           {p: t.base_terrain for p, t in b.items()}


def test_different_seeds_differ():
    a = _generate(seed=1)
    b = _generate(seed=2)
    terrains_a = {p: t.base_terrain for p, t in a.items()}
    terrains_b = {p: t.base_terrain for p, t in b.items()}
    assert terrains_a != terrains_b
