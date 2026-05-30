"""
Régressions sur le déroulement des tours (session 2026-05-30).

- Tour IA tactique **borné** : une unité = une activation (fix ``has_acted``).
  Sans le correctif, une unité qui ne faisait que se déplacer était rejouée en
  boucle.
- Détection « plus rien à faire » pour la fin de tour automatique
  (stratégique et tactique).
"""

from engine.unit import Army
from game.units import create_lancer, create_archer, create_cavalry
from game.ai import AIPersonality
from game.terrain import TerrainType
from game.tactical_map import TacticalBattle


def _make_battle(screen):
    attacker = Army("Att", player_id=0)
    for u in (create_lancer(8), create_archer(4)):
        attacker.add_unit(u)
    defender = Army("Def", player_id=1)
    for u in (create_cavalry(6), create_lancer(5)):
        defender.add_unit(u)
    return TacticalBattle(
        attacker, defender, screen,
        strategic_terrain=TerrainType.PLAINS,
        ai_players={0: AIPersonality.AGGRESSIVE, 1: AIPersonality.DEFENSIVE},
    )


def test_tactical_ai_turn_is_bounded(screen):
    """Le nombre d'actions IA d'un tour ne dépasse pas le nombre d'unités."""
    battle = _make_battle(screen)
    ai = battle.ai_players[battle.current_player_id]
    n_units = len(battle.get_units_for_player(battle.current_player_id))

    actions = 0
    while True:
        action = ai.play_turn(battle)
        if action is None:
            break
        battle._execute_ai_action(action)
        actions += 1
        assert actions <= n_units, "boucle non bornée : régression du fix has_acted"

    # Toutes les unités vivantes du joueur ont agi en fin de tour IA.
    assert all(
        u.has_acted for u in battle.get_units_for_player(battle.current_player_id)
        if u.is_alive
    )


def test_attack_marks_unit_acted(screen):
    """try_attack pose has_acted (corrige le multi-attaque côté humain)."""
    battle = _make_battle(screen)
    # Place deux ennemis adjacents pour garantir une attaque possible.
    units_p0 = battle.get_units_for_player(0)
    enemies = battle.get_enemy_units(0)
    attacker = units_p0[0]
    target = enemies[0]
    # Déplace la cible juste à côté de l'attaquant.
    from engine.hex_grid import HEX_DIRECTIONS
    neighbor = attacker.position + HEX_DIRECTIONS[0]
    battle.tiles[target.position.to_tuple()].unit = None
    target.position = neighbor
    battle.tiles[neighbor.to_tuple()].unit = target

    battle.current_player_id = 0
    battle.select_unit(attacker)
    assert not attacker.has_acted
    battle.try_attack(neighbor)
    assert attacker.has_acted


def test_tactical_has_actions_true_at_start(screen):
    battle = _make_battle(screen)
    assert battle.current_player_has_actions() is True


def test_tactical_ai_is_dt_driven(screen):
    """
    C1 : la cadence IA dépend de ``dt_ms`` injecté, pas de l'horloge murale.
    Tant que le délai n'est pas écoulé (dt=0), l'action reste en attente.
    """
    battle = _make_battle(screen)
    # 1er appel : le timer démarre à 0 -> l'IA choisit une action en attente.
    battle.update_ai_turn(dt_ms=0)
    assert battle._pending_ai_action is not None
    # dt=0 : délai non écoulé, l'action ne s'exécute pas encore.
    battle.update_ai_turn(dt_ms=0)
    assert battle._pending_ai_action is not None
    # dt large : délai écoulé, l'action est exécutée.
    battle.update_ai_turn(dt_ms=10_000)
    assert battle._pending_ai_action is None


def test_tactical_ai_turn_completes_via_dt(screen):
    """En pompant ``update_ai_turn`` avec du dt, le tour IA se termine (sans horloge)."""
    battle = _make_battle(screen)
    start = battle.current_player_id
    for _ in range(300):
        battle.update_ai_turn(dt_ms=10_000)
        if battle.battle_over or battle.current_player_id != start:
            break
    assert battle.battle_over or battle.current_player_id != start


def test_strategic_animation_is_dt_driven(make_grid):
    """L'animation stratégique avance selon ``dt_ms`` (accumulateur), pas l'horloge."""
    from game.strategic_map import StrategicGameState, MoveAnimation
    from game.config import ANIMATION
    from engine.unit import Army
    from engine.hex_grid import HexCoord

    tiles = make_grid(radius=3)
    army = Army("a", player_id=0)
    army.position = HexCoord(0, 0)

    gs = StrategicGameState()
    gs.current_animation = MoveAnimation(unit=army, path=[(0, 0), (1, 0), (2, 0)])

    delay = ANIMATION.move_step_delay_ms
    # dt insuffisant -> aucun pas
    gs.update_animation(tiles, dt_ms=delay - 1)
    assert army.position.to_tuple() == (0, 0)
    # le cumul dépasse le délai -> un pas effectué
    gs.update_animation(tiles, dt_ms=delay)
    assert army.position.to_tuple() == (1, 0)


def test_strategic_auto_end_detection():
    """current_player_has_moves : vrai au départ, faux une fois le mouvement épuisé."""
    from game.main import generate_test_map, create_test_units
    from game.strategic_map import StrategicGameState

    tiles = generate_test_map(40, 40, add_river=False, seed=1)
    armies = create_test_units(tiles, 2, 2)
    gs = StrategicGameState()
    gs.set_tiles_reference(tiles)
    gs.start_turn(armies, [])

    assert gs.current_player_has_moves(armies, [], tiles) is True

    for a in armies:
        if a.player_id == gs.current_player.id:
            a.movement_remaining = 0
    assert gs.current_player_has_moves(armies, [], tiles) is False
