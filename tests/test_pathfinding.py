"""Invariants du pathfinding (engine/pathfinding.py)."""

from engine.hex_grid import HexCoord
from engine.pathfinding import calculate_valid_moves, calculate_path_cost, find_path
from game.terrain import TerrainType


# Prédicat « peut s'arrêter ici » : case vide.
EMPTY = lambda tile, pos: tile.unit is None


def test_valid_moves_budget_on_plains(make_grid):
    """
    Sur plaines (coût 1/case), un budget de 2 atteint exactement les anneaux à
    distance 1 et 2, soit 6 + 12 = 18 cases (le départ exclu).
    """
    tiles = make_grid(radius=3, terrain=TerrainType.PLAINS)
    valid = calculate_valid_moves((0, 0), 2, tiles, EMPTY)
    assert (0, 0) not in valid
    assert len(valid) == 18
    assert all(HexCoord(0, 0).distance_to(HexCoord(*p)) <= 2 for p in valid)


def test_valid_moves_respects_budget_zero(make_grid):
    tiles = make_grid(radius=2, terrain=TerrainType.PLAINS)
    assert calculate_valid_moves((0, 0), 0, tiles, EMPTY) == set()


def test_expensive_terrain_limits_reach(make_grid):
    """Montagne = coût 3 : un budget de 2 ne permet aucun déplacement."""
    tiles = make_grid(radius=2, terrain=TerrainType.MOUNTAIN)
    assert calculate_valid_moves((0, 0), 2, tiles, EMPTY) == set()


def test_impassable_water_is_excluded_and_blocks(make_grid):
    """Une case d'eau est infranchissable : ni atteignable, ni traversable."""
    tiles = make_grid(radius=3, terrain=TerrainType.PLAINS)
    water_pos = (1, 0)
    tiles[water_pos].base_terrain = TerrainType.WATER
    assert not tiles[water_pos].is_passable

    valid = calculate_valid_moves((0, 0), 3, tiles, EMPTY)
    assert water_pos not in valid


def test_occupied_tile_not_a_valid_stop(make_grid):
    """Une case occupée n'est pas une destination valide pour le prédicat EMPTY."""
    tiles = make_grid(radius=2, terrain=TerrainType.PLAINS)
    tiles[(1, 0)].unit = object()  # occupant factice
    valid = calculate_valid_moves((0, 0), 2, tiles, EMPTY)
    assert (1, 0) not in valid


def test_path_cost_straight_line_on_plains(make_grid):
    tiles = make_grid(radius=4, terrain=TerrainType.PLAINS)
    # 3 cases vers l'est, coût 1 chacune
    assert calculate_path_cost((0, 0), (3, 0), tiles) == 3


def test_path_cost_no_path_returns_sentinel(make_grid):
    tiles = make_grid(radius=2, terrain=TerrainType.PLAINS)
    # Cible hors de la grille -> pas de chemin
    assert calculate_path_cost((0, 0), (99, 99), tiles) == 999


def test_find_path_is_contiguous(make_grid):
    tiles = make_grid(radius=4, terrain=TerrainType.PLAINS)
    path = find_path((0, 0), (3, -1), tiles)
    assert path is not None
    assert path[0] == (0, 0)
    assert path[-1] == (3, -1)
    # chaque pas relie deux cases adjacentes
    for a, b in zip(path, path[1:]):
        assert HexCoord(*a).distance_to(HexCoord(*b)) == 1


def test_find_path_none_when_unreachable(make_grid):
    tiles = make_grid(radius=2, terrain=TerrainType.PLAINS)
    assert find_path((0, 0), (50, 50), tiles) is None
