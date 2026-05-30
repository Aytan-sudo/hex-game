"""
Sémantique des destinations valides après dédup du BFS (Workstream B).

``StrategicGameState._calculate_valid_moves`` et ``AIPlayer._calculate_valid_moves``
délèguent désormais au BFS canonique ; ces tests verrouillent le prédicat
« peut s'arrêter ici » propre à chaque type d'unité.
"""

from engine.hex_grid import HexCoord
from engine.unit import Army
from game.strategic_map import StrategicGameState
from game.ai import AIPlayer
from game.heroes import create_hero


def _army(player_id, pos):
    a = Army(f"A{player_id}", player_id=player_id)
    a.position = HexCoord(*pos)
    return a


def test_army_can_stop_on_enemy_not_on_ally(make_grid):
    tiles = make_grid(radius=2)
    mover = _army(0, (0, 0))
    mover.movement_remaining = 3

    enemy = _army(1, (1, 0))
    ally = _army(0, (0, 1))
    tiles[(1, 0)].unit = enemy
    tiles[(0, 1)].unit = ally

    gs = StrategicGameState()
    valid = gs._calculate_valid_moves(mover, tiles)

    assert (1, 0) in valid        # ennemi = case d'arrêt (bataille)
    assert (0, 1) not in valid    # allié = interdit


def test_hero_can_join_ally_army_not_enemy(make_grid):
    tiles = make_grid(radius=2)
    hero = create_hero("H", "Scout", player_id=0, level=1)
    hero.position = HexCoord(0, 0)
    hero.movement_remaining = 3

    ally = _army(0, (1, 0))
    enemy = _army(1, (0, 1))
    tiles[(1, 0)].unit = ally
    tiles[(0, 1)].unit = enemy

    gs = StrategicGameState()
    valid = gs._calculate_valid_moves(hero, tiles)

    assert (1, 0) in valid        # armée alliée = jonction possible
    assert (0, 1) not in valid    # ennemi = interdit pour un héros


def test_ai_army_matches_strategic_for_armies(make_grid):
    """L'IA et le moteur stratégique calculent les mêmes destinations pour une armée."""
    tiles = make_grid(radius=3)
    mover = _army(0, (0, 0))
    mover.movement_remaining = 3
    tiles[(1, 0)].unit = _army(1, (1, 0))  # ennemi

    gs = StrategicGameState()
    ai = AIPlayer(player_id=0)

    strat = set(gs._calculate_valid_moves(mover, tiles))
    ai_moves = set(ai._calculate_valid_moves(mover, tiles))
    assert strat == ai_moves
