"""Invariants du système de coordonnées hexagonales (engine/hex_grid.py)."""

import pytest

from engine.hex_grid import HexCoord, HexGrid, HEX_DIRECTIONS


def test_cube_constraint():
    """q + r + s == 0 pour toute coordonnée."""
    for coord in (HexCoord(0, 0), HexCoord(3, -1), HexCoord(-2, 5)):
        assert coord.q + coord.r + coord.s == 0


def test_six_neighbors_at_distance_one():
    """Une case a exactement 6 voisins, tous à distance 1."""
    c = HexCoord(2, -3)
    neighbors = c.neighbors()
    assert len(neighbors) == 6
    assert len(set(neighbors)) == 6  # tous distincts
    assert all(c.distance_to(n) == 1 for n in neighbors)


def test_directions_are_unit_vectors():
    assert len(HEX_DIRECTIONS) == 6
    assert all(HexCoord(0, 0).distance_to(d) == 1 for d in HEX_DIRECTIONS)


@pytest.mark.parametrize("q,r", [(0, 0), (1, 0), (0, 1), (5, -3), (-4, 2), (7, 7)])
def test_pixel_hex_roundtrip(q, r):
    """hex_to_pixel puis pixel_to_hex doit retrouver la case d'origine."""
    grid = HexGrid(hex_size=30.0, pointy_top=True)
    coord = HexCoord(q, r)
    px, py = grid.hex_to_pixel(coord)
    back = grid.pixel_to_hex(px, py)
    assert back == coord


def test_pixel_hex_roundtrip_with_offset():
    grid = HexGrid(hex_size=24.0, pointy_top=True)
    coord = HexCoord(3, -2)
    offset = (120.0, -45.0)
    px, py = grid.hex_to_pixel(coord, offset)
    assert grid.pixel_to_hex(px, py, offset) == coord


def test_distance_symmetry():
    a, b = HexCoord(1, 2), HexCoord(-3, 4)
    assert a.distance_to(b) == b.distance_to(a)
