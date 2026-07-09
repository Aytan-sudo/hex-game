"""
BattleResolver (Phase 1) : le combat est appelable sans ouvrir de fenêtre.

- L'auto-résolution (mode AUTO) termine, retourne un rapport cohérent et
  répercute les pertes sur les armées d'origine.
- Même seed → même issue (reproductibilité du champ de bataille et du combat).
- Le mode TACTICAL exige les dépendances de vue (screen, couleurs).
"""

import pytest

from engine.unit import Army
from game.units import create_lancer, create_archer, create_cavalry
from game.ai import AIPersonality
from game.terrain import TerrainType
from game.battle_resolver import BattleResolver, BattleMode


def _make_armies():
    attacker = Army("Att", player_id=0)
    for u in (create_lancer(8), create_archer(4)):
        attacker.add_unit(u)
    defender = Army("Def", player_id=1)
    for u in (create_cavalry(6), create_lancer(5)):
        defender.add_unit(u)
    return attacker, defender


def _army_size(army: Army) -> int:
    return sum(u.count for u in army.units)


def test_auto_resolution_completes_and_reports():
    attacker, defender = _make_armies()
    report = BattleResolver().resolve(
        attacker, defender, TerrainType.PLAINS, seed=123
    )
    assert report is not None
    assert report.attacker_name == "Att"
    assert report.defender_name == "Def"
    assert report.rounds >= 1
    # Une bataille agressive des deux côtés fait forcément des pertes.
    assert report.attacker_losses + report.defender_losses > 0


def test_auto_resolution_updates_original_armies():
    attacker, defender = _make_armies()
    att_before, def_before = _army_size(attacker), _army_size(defender)

    report = BattleResolver().resolve(
        attacker, defender, TerrainType.FOREST, seed=7
    )

    # Les pertes du rapport se reflètent sur les armées stratégiques.
    assert _army_size(attacker) == att_before - report.attacker_losses
    assert _army_size(defender) == def_before - report.defender_losses


def test_auto_resolution_is_reproducible_by_seed():
    def outcome(seed):
        attacker, defender = _make_armies()
        r = BattleResolver().resolve(
            attacker, defender, TerrainType.HILLS, seed=seed,
            ai_players={0: AIPersonality.AGGRESSIVE, 1: AIPersonality.DEFENSIVE},
        )
        return (r.attacker_won, r.rounds, r.attacker_losses, r.defender_losses)

    assert outcome(42) == outcome(42)


def test_tactical_mode_requires_view_dependencies():
    attacker, defender = _make_armies()
    with pytest.raises(ValueError):
        BattleResolver().resolve(
            attacker, defender, mode=BattleMode.TACTICAL
        )
