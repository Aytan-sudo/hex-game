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
class AnimationSettings:
    """Animation configuration."""
    move_step_delay_ms: int = 80  # Delay between each step in milliseconds
    enabled: bool = True


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

    # Stat gains per level
    hp_per_level: int = 5
    attack_per_level: int = 2
    defense_per_level: int = 1
    leadership_per_level: int = 2


@dataclass
class AISettings:
    """AI behavior configuration."""
    action_delay_ms: int = 400        # Delay between AI actions for visibility
    turn_start_delay_ms: int = 300    # Delay at start of AI turn
    enabled: bool = True              # Master switch for AI


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
INPUT = InputSettings()
UI = UISettings()
ANIMATION = AnimationSettings()
BATTLE = BattleSettings()
PROGRESSION = ProgressionSettings()
AI = AISettings()
PLAYER_COLORS = PlayerColors()


# Default game configuration (for menu)
DEFAULT_GAME_CONFIG = {
    'map_width': 100,
    'map_height': 100,
    'player1_armies': 3,
    'player2_armies': 3,
    'add_river': True,
}
