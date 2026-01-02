"""
Hero definitions for the hex strategy game.

Defines hero classes and factory functions to create heroes.
"""

from engine.unit import Hero, UnitStats


# Hero class definitions with base stats
HERO_CLASSES = {
    "Warrior": {
        "description": "Frontline fighter, high HP and attack",
        "base_stats": UnitStats(
            max_hp=50,
            current_hp=50,
            attack=15,
            defense=12,
            movement=4,
            range=1
        ),
        "leadership": 12,
        "magic": 0,
    },
    "Mage": {
        "description": "Powerful ranged attacks, fragile",
        "base_stats": UnitStats(
            max_hp=30,
            current_hp=30,
            attack=20,
            defense=5,
            movement=3,
            range=3
        ),
        "leadership": 8,
        "magic": 15,
    },
    "Scout": {
        "description": "Fast movement, good for reconnaissance",
        "base_stats": UnitStats(
            max_hp=35,
            current_hp=35,
            attack=10,
            defense=8,
            movement=6,
            range=1
        ),
        "leadership": 6,
        "magic": 0,
    },
    "Commander": {
        "description": "High leadership, boosts army significantly",
        "base_stats": UnitStats(
            max_hp=40,
            current_hp=40,
            attack=12,
            defense=10,
            movement=4,
            range=1
        ),
        "leadership": 20,
        "magic": 0,
    },
    "Paladin": {
        "description": "Balanced warrior with some magic",
        "base_stats": UnitStats(
            max_hp=45,
            current_hp=45,
            attack=14,
            defense=14,
            movement=4,
            range=1
        ),
        "leadership": 10,
        "magic": 5,
    },
}


def create_hero(
    name: str,
    hero_class: str = "Warrior",
    player_id: int = 0,
    level: int = 1
) -> Hero:
    """
    Create a hero of a specific class.

    Args:
        name: Hero's unique name
        hero_class: One of the HERO_CLASSES keys
        player_id: Owner player ID
        level: Starting level (affects stats)

    Returns:
        A new Hero instance
    """
    if hero_class not in HERO_CLASSES:
        hero_class = "Warrior"

    class_info = HERO_CLASSES[hero_class]
    base = class_info["base_stats"]

    # Copy stats to avoid modifying the template
    stats = UnitStats(
        max_hp=base.max_hp,
        current_hp=base.current_hp,
        attack=base.attack,
        defense=base.defense,
        movement=base.movement,
        range=base.range
    )

    hero = Hero(
        name=name,
        stats=stats,
        player_id=player_id,
        level=1,
        experience=0,
        hero_class=hero_class
    )

    hero.leadership = class_info["leadership"]
    hero.magic = class_info["magic"]

    # Apply level-ups if starting above level 1
    for _ in range(level - 1):
        hero._on_level_up()
        hero.level += 1

    return hero


# Pre-defined named heroes for campaigns/scenarios
def create_named_heroes() -> dict:
    """Create a dictionary of named heroes for both players."""
    return {
        # Player 1 heroes
        "Sir Roland": create_hero("Sir Roland", "Paladin", player_id=0, level=3),
        "Elena the Swift": create_hero("Elena the Swift", "Scout", player_id=0, level=2),
        "Archmage Theron": create_hero("Archmage Theron", "Mage", player_id=0, level=4),

        # Player 2 heroes
        "Lord Vexar": create_hero("Lord Vexar", "Commander", player_id=1, level=3),
        "Grimjaw": create_hero("Grimjaw", "Warrior", player_id=1, level=2),
        "Shadow": create_hero("Shadow", "Scout", player_id=1, level=2),
    }
