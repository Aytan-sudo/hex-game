"""
Camera system for the hex strategy game.

Handles zoom levels and viewport management.
"""

from typing import Tuple


class Camera:
    """
    Manages zoom and viewport for the hex grid.

    Uses discrete zoom levels (hex sizes in pixels) for clean rendering.
    Zoom is centered on the screen center.
    """

    # Zoom levels: hex_size in pixels (center to corner)
    # Added smaller sizes (6, 8, 12, 18) for viewing large maps
    ZOOM_LEVELS = [6, 8, 12, 18, 24, 36, 48, 72, 96]
    DEFAULT_ZOOM_INDEX = 6  # 48px by default

    def __init__(self, screen_width: int, screen_height: int):
        """
        Initialize the camera.

        Args:
            screen_width: Width of the screen in pixels
            screen_height: Height of the screen in pixels
        """
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.zoom_index = self.DEFAULT_ZOOM_INDEX
        self.offset_x = 100.0
        self.offset_y = 100.0

    @property
    def hex_size(self) -> int:
        """Current hex size in pixels."""
        return self.ZOOM_LEVELS[self.zoom_index]

    @property
    def offset(self) -> Tuple[float, float]:
        """Current offset as tuple."""
        return (self.offset_x, self.offset_y)

    def set_offset(self, x: float, y: float):
        """Set the rendering offset."""
        self.offset_x = x
        self.offset_y = y

    def move_offset(self, dx: float, dy: float):
        """Move the rendering offset by a delta."""
        self.offset_x += dx
        self.offset_y += dy

    def zoom_in(self) -> bool:
        """
        Zoom in (increase hex size), centered on screen center.

        Returns:
            True if zoom changed, False if already at max zoom
        """
        if self.zoom_index >= len(self.ZOOM_LEVELS) - 1:
            return False

        self._zoom_to_index(self.zoom_index + 1)
        return True

    def zoom_out(self) -> bool:
        """
        Zoom out (decrease hex size), centered on screen center.

        Returns:
            True if zoom changed, False if already at min zoom
        """
        if self.zoom_index <= 0:
            return False

        self._zoom_to_index(self.zoom_index - 1)
        return True

    def _zoom_to_index(self, new_index: int):
        """
        Change zoom level while keeping the screen center stable.

        The key insight: when we zoom, we want the world point at the
        screen center to stay at the screen center.

        World point at screen center = screen_center - offset
        After zoom, we need: new_offset = screen_center - (world_point * scale_ratio)
        """
        old_hex_size = self.hex_size
        self.zoom_index = new_index
        new_hex_size = self.hex_size

        # Scale ratio
        scale = new_hex_size / old_hex_size

        # Screen center
        center_x = self.screen_width / 2
        center_y = self.screen_height / 2

        # World point currently at screen center
        world_x = center_x - self.offset_x
        world_y = center_y - self.offset_y

        # Scale the world point and compute new offset
        self.offset_x = center_x - (world_x * scale)
        self.offset_y = center_y - (world_y * scale)

    def can_zoom_in(self) -> bool:
        """Check if zoom in is possible."""
        return self.zoom_index < len(self.ZOOM_LEVELS) - 1

    def can_zoom_out(self) -> bool:
        """Check if zoom out is possible."""
        return self.zoom_index > 0

    @property
    def zoom_level_name(self) -> str:
        """Human-readable zoom level."""
        return f"{self.hex_size}px ({self.zoom_index + 1}/{len(self.ZOOM_LEVELS)})"

    def update_screen_size(self, width: int, height: int):
        """Update screen dimensions (e.g., after window resize)."""
        self.screen_width = width
        self.screen_height = height
