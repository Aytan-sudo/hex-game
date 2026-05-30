"""
Règles de combat (engine/combat.py).

Inclut la régression du correctif AUDIT §2.5 : la contre-attaque ne doit avoir
lieu que si l'attaquant est à portée du défenseur.
"""

import pytest

from engine.unit import Unit, UnitType, UnitStats
from engine.combat import CombatSystem


class DummyUnit(Unit):
    """Unité concrète minimale : attaque/défense = stats brutes."""

    def get_attack_power(self) -> int:
        return self.stats.attack

    def get_defense_power(self) -> int:
        return self.stats.defense


def make_unit(attack=10, defense=4, hp=20, movement=3, rng=1, player_id=0):
    return DummyUnit(
        name="u",
        unit_type=UnitType.INFANTRY,
        stats=UnitStats(max_hp=hp, current_hp=hp, attack=attack,
                        defense=defense, movement=movement, range=rng),
        player_id=player_id,
    )


@pytest.fixture
def combat():
    """Système de combat déterministe (sans aléa)."""
    return CombatSystem(random_factor=0.0)


def test_damage_formula(combat):
    """base = attack - defense // 2 (sans aléa)."""
    assert combat._calculate_attack_damage(10, 4) == 8     # 10 - 2
    assert combat._calculate_attack_damage(15, 6) == 12    # 15 - 3


def test_damage_minimum_is_one(combat):
    """Les dégâts ne descendent jamais sous 1, même face à une défense énorme."""
    assert combat._calculate_attack_damage(2, 100) == 1


def test_attacker_marked_acted(combat):
    a, d = make_unit(player_id=0), make_unit(player_id=1)
    assert not a.has_acted
    combat.resolve_combat(a, d, distance=1)
    assert a.has_acted


def test_counter_attack_when_in_range(combat):
    """À distance 1, un défenseur survivant riposte (dégâts à l'attaquant > 0)."""
    attacker = make_unit(attack=6, defense=4, hp=20, player_id=0)
    defender = make_unit(attack=12, defense=4, hp=50, rng=1, player_id=1)
    result = combat.resolve_combat(attacker, defender, distance=1)
    assert result.defender_survived          # def survit -> riposte possible
    assert result.attacker_damage > 0


def test_no_counter_when_out_of_defender_range(combat):
    """
    Régression §2.5 : un archer (portée 2) frappant à distance 2 un défenseur
    de mêlée (portée 1) ne doit PAS subir de contre-attaque.
    """
    archer = make_unit(attack=10, defense=3, hp=20, rng=2, player_id=0)
    melee = make_unit(attack=12, defense=4, hp=50, rng=1, player_id=1)
    result = combat.resolve_combat(archer, melee, distance=2)
    assert result.defender_survived
    assert result.attacker_damage == 0       # pas de riposte hors de portée


def test_terrain_defense_reduces_damage(combat):
    """Le bonus défensif de terrain du défenseur réduit les dégâts reçus."""
    from engine.hex_grid import HexCoord
    from engine.tile import Tile
    from game.terrain import TerrainType

    attacker = make_unit(attack=10, defense=4, player_id=0)
    defender = make_unit(attack=5, defense=4, hp=50, player_id=1)

    plain = Tile(position=HexCoord(0, 0), base_terrain=TerrainType.PLAINS)
    mountain = Tile(position=HexCoord(1, 0), base_terrain=TerrainType.MOUNTAIN)

    dmg_plain = combat._calculate_attack_damage(
        attacker.get_attack_power(), defender.get_defense_power() + plain.defense_bonus
    )
    dmg_mountain = combat._calculate_attack_damage(
        attacker.get_attack_power(), defender.get_defense_power() + mountain.defense_bonus
    )
    assert mountain.defense_bonus > plain.defense_bonus
    assert dmg_mountain < dmg_plain
