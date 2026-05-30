"""
Configuration et fixtures partagées pour la suite de tests.

On force le driver vidéo SDL en mode « dummy » avant tout import de pygame :
les composants logiques (ex. ``TacticalBattle``) exigent un ``screen`` mais on
ne veut pas ouvrir de fenêtre. Voir AUDIT §2.3 (couplage logique ↔ Pygame) :
tant que ce couplage existe, les tests gameplay passent par cette fixture.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import pygame
import pytest

from engine.hex_grid import HexCoord
from engine.tile import Tile
from game.terrain import TerrainType


@pytest.fixture(scope="session", autouse=True)
def _pygame_session():
    """Initialise pygame en mode headless pour toute la session de tests."""
    pygame.init()
    pygame.display.set_mode((320, 240))
    yield
    pygame.quit()


@pytest.fixture
def screen():
    """Surface d'affichage headless (pour les objets qui exigent un screen)."""
    return pygame.display.get_surface()


@pytest.fixture
def make_grid():
    """
    Fabrique une grille hexagonale (zone de rayon ``radius``) d'un terrain donné.

    Retourne un dict ``(q, r) -> Tile`` directement utilisable par les fonctions
    de ``engine.pathfinding``.
    """
    def _make(radius: int = 3, terrain: TerrainType = TerrainType.PLAINS):
        tiles = {}
        for q in range(-radius, radius + 1):
            for r in range(max(-radius, -q - radius), min(radius, -q + radius) + 1):
                tiles[(q, r)] = Tile(position=HexCoord(q, r), base_terrain=terrain)
        return tiles

    return _make
