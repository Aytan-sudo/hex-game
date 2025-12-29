"""
Concrete unit types for the hex strategy game.

Defines specific unit classes like Lancers, Archers, etc.
"""

from engine.unit import UnitType, UnitStats, ArmyUnit


def create_lancer(count: int = 10) -> ArmyUnit:
    """
    Create a Lancer unit.

    Lancers are basic infantry with balanced stats.
    """
    return ArmyUnit(
        name="Lancer",
        unit_type=UnitType.INFANTRY,
        count=count,
        base_stats=UnitStats(
            max_hp=10,
            current_hp=10,
            attack=8,
            defense=6,
            movement=3,
            range=1
        )
    )


def create_archer(count: int = 8) -> ArmyUnit:
    """
    Create an Archer unit.

    Archers have lower HP but can attack at range.
    """
    return ArmyUnit(
        name="Archer",
        unit_type=UnitType.RANGED,
        count=count,
        base_stats=UnitStats(
            max_hp=6,
            current_hp=6,
            attack=10,
            defense=3,
            movement=3,
            range=2
        )
    )


def create_cavalry(count: int = 5) -> ArmyUnit:
    """
    Create a Cavalry unit.

    Cavalry has high mobility and attack, but lower defense.
    """
    return ArmyUnit(
        name="Cavalry",
        unit_type=UnitType.CAVALRY,
        count=count,
        base_stats=UnitStats(
            max_hp=12,
            current_hp=12,
            attack=12,
            defense=4,
            movement=5,
            range=1
        )
    )


def create_mage(count: int = 3) -> ArmyUnit:
    """
    Create a Mage unit.

    Mages have powerful ranged attacks but are fragile.
    """
    return ArmyUnit(
        name="Mage",
        unit_type=UnitType.RANGED,
        count=count,
        base_stats=UnitStats(
            max_hp=4,
            current_hp=4,
            attack=15,
            defense=2,
            movement=2,
            range=3
        )
    )


def create_pikeman(count: int = 12) -> ArmyUnit:
    """
    Create a Pikeman unit.

    Pikemen are defensive infantry, strong against cavalry.
    """
    return ArmyUnit(
        name="Pikeman",
        unit_type=UnitType.INFANTRY,
        count=count,
        base_stats=UnitStats(
            max_hp=8,
            current_hp=8,
            attack=6,
            defense=10,
            movement=2,
            range=1
        )
    )


# Shortcut class names for convenience (used in game/__init__.py)
class Lancer:
    """Factory class for Lancer units."""
    @staticmethod
    def create(count: int = 10) -> ArmyUnit:
        return create_lancer(count)


class Archer:
    """Factory class for Archer units."""
    @staticmethod
    def create(count: int = 8) -> ArmyUnit:
        return create_archer(count)


class Cavalry:
    """Factory class for Cavalry units."""
    @staticmethod
    def create(count: int = 5) -> ArmyUnit:
        return create_cavalry(count)


class Mage:
    """Factory class for Mage units."""
    @staticmethod
    def create(count: int = 3) -> ArmyUnit:
        return create_mage(count)
