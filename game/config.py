"""
Game configuration and constants.

Centralizes all magic numbers and configurable values.
"""

from dataclasses import dataclass
from typing import Tuple


@dataclass
class InputSettings:
    """Input handling configuration."""
    drag_threshold: int = 5
    scroll_speed: int = 10
    fast_scroll_multiplier: int = 5  # Shift+arrows scroll this many times faster


@dataclass
class UISettings:
    """UI layout and styling configuration."""
    # Colors
    panel_bg_color: Tuple[int, int, int] = (40, 40, 50)
    screen_bg_color: Tuple[int, int, int] = (25, 25, 35)
    text_color: Tuple[int, int, int] = (255, 255, 255)
    hint_color: Tuple[int, int, int] = (150, 150, 150)
    selection_color: Tuple[int, int, int] = (255, 255, 100)
    move_highlight_color: Tuple[int, int, int] = (100, 200, 100)
    attack_highlight_color: Tuple[int, int, int] = (255, 150, 150)
    hero_gold_color: Tuple[int, int, int] = (255, 215, 0)

    # Panel dimensions
    top_panel_height: int = 50
    bottom_panel_height: int = 60

    # Button dimensions
    button_width: int = 120
    button_height: int = 35
    button_margin: int = 10


@dataclass
class GameSpeed:
    """Vitesse de lecture des tours IA et des animations.

    Le facteur multiplie tous les délais : plus il est petit, plus le jeu est
    rapide. ``Normal`` (1.0) correspond aux délais de base d'origine.
    """
    # (libellé, facteur). Pas une dataclass field (non annoté) → variable de classe.
    LEVELS = (
        ("Lent", 1.6),
        ("Normal", 1.0),
        ("Rapide", 0.45),
        ("Très rapide", 0.2),
    )
    index: int = 1  # "Normal" par défaut

    @property
    def factor(self) -> float:
        """Facteur multiplicatif appliqué aux délais."""
        return self.LEVELS[self.index][1]

    @property
    def name(self) -> str:
        """Libellé de la vitesse courante."""
        return self.LEVELS[self.index][0]

    @classmethod
    def names(cls) -> list:
        """Liste des libellés (pour les menus)."""
        return [name for name, _ in cls.LEVELS]

    def set_by_name(self, name: str) -> None:
        """Sélectionne une vitesse par son libellé (ignore si inconnu)."""
        for i, (n, _) in enumerate(self.LEVELS):
            if n == name:
                self.index = i
                return

    def cycle(self, direction: int = 1) -> None:
        """Passe à la vitesse suivante/précédente (cyclique)."""
        self.index = (self.index + direction) % len(self.LEVELS)


@dataclass
class AnimationSettings:
    """Animation configuration."""
    base_move_step_delay_ms: int = 80  # Délai de base entre deux pas (avant vitesse)
    enabled: bool = True

    @property
    def move_step_delay_ms(self) -> int:
        """Délai effectif entre deux pas, ajusté par la vitesse de jeu."""
        return max(1, int(self.base_move_step_delay_ms * SPEED.factor))


@dataclass
class BattleSettings:
    """Tactical battle configuration."""
    map_width: int = 20
    map_height: int = 20
    max_turns: int = 20
    message_display_time: float = 3.0
    victory_message_time: float = 5.0


@dataclass
class ProgressionSettings:
    """Character progression configuration."""
    xp_per_level_multiplier: int = 100  # XP needed = level * this value
    xp_per_kill: int = 25  # XP a surviving hero gains per enemy unit destroyed in battle

    # Stat gains per level
    hp_per_level: int = 5
    attack_per_level: int = 2
    defense_per_level: int = 1
    leadership_per_level: int = 2


@dataclass
class AISettings:
    """AI behavior configuration.

    Les délais sont exprimés à vitesse ``Normal`` ; ils sont automatiquement
    réduits/augmentés selon ``SPEED`` (voir :class:`GameSpeed`).
    """
    base_action_delay_ms: int = 400        # Délai de base entre deux actions IA
    base_turn_start_delay_ms: int = 300    # Délai de base au début d'un tour IA
    enabled: bool = True                   # Master switch for AI

    @property
    def action_delay_ms(self) -> int:
        """Délai effectif entre deux actions, ajusté par la vitesse de jeu."""
        return max(1, int(self.base_action_delay_ms * SPEED.factor))

    @property
    def turn_start_delay_ms(self) -> int:
        """Délai effectif au début d'un tour IA, ajusté par la vitesse de jeu."""
        return max(1, int(self.base_turn_start_delay_ms * SPEED.factor))


@dataclass
class PlayerColors:
    """Player color configuration."""
    player1: Tuple[int, int, int] = (100, 100, 255)
    player2: Tuple[int, int, int] = (255, 100, 100)

    def get(self, player_id: int) -> Tuple[int, int, int]:
        """Get color for a player ID."""
        if player_id == 0:
            return self.player1
        elif player_id == 1:
            return self.player2
        return (200, 200, 200)

    def as_dict(self) -> dict:
        """Return as dictionary for compatibility."""
        return {
            0: self.player1,
            1: self.player2,
        }


# Global configuration instances
# SPEED doit exister avant ANIMATION/AI car leurs propriétés le référencent.
SPEED = GameSpeed()
INPUT = InputSettings()
UI = UISettings()
ANIMATION = AnimationSettings()
BATTLE = BattleSettings()
PROGRESSION = ProgressionSettings()
AI = AISettings()
PLAYER_COLORS = PlayerColors()


# Default game configuration (for menu)
DEFAULT_GAME_CONFIG = {
    'mode': 'Campagne',   # 'Campagne' (pivot, PROJET.md) | 'Wargame' (couche historique)
    'map_width': 100,
    'map_height': 100,
    'player1_armies': 3,
    'player2_armies': 3,
    'add_river': True,
    'game_speed': 'Normal',
}
