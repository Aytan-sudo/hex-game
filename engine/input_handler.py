"""
Input handling utilities for camera control and user interactions.

Provides unified drag, zoom, and scroll handling.
"""

from dataclasses import dataclass
from typing import Optional, Tuple

import pygame

from engine.camera import Camera
from engine.hex_grid import HexGrid


@dataclass
class DragState:
    """Tracks mouse drag state."""
    is_dragging: bool = False
    button: Optional[int] = None
    start_pos: Tuple[int, int] = (0, 0)
    start_offset: Tuple[float, float] = (0.0, 0.0)


class CameraController:
    """
    Handles camera movement via drag, scroll, and zoom.

    Supports:
    - Middle mouse button drag
    - Right mouse button drag (trackpad friendly)
    - Keyboard arrow scrolling (Shift for faster)
    - Zoom with +/- keys or Ctrl+mousewheel
    """

    def __init__(
        self,
        camera: Camera,
        drag_threshold: int = 5,
        scroll_speed: int = 10,
        fast_scroll_multiplier: int = 5
    ):
        self.camera = camera
        self.drag_threshold = drag_threshold
        self.scroll_speed = scroll_speed
        self.fast_scroll_multiplier = fast_scroll_multiplier
        self.drag = DragState()
        self._hex_grid: Optional[HexGrid] = None

    @property
    def hex_grid(self) -> HexGrid:
        """Get or create HexGrid matching current camera zoom."""
        if self._hex_grid is None or self._hex_grid.hex_size != self.camera.hex_size:
            self._hex_grid = HexGrid(hex_size=self.camera.hex_size, pointy_top=True)
        return self._hex_grid

    def handle_event(self, event: pygame.event.Event, mouse_pos: Tuple[int, int]) -> bool:
        """
        Handle a pygame event for camera control.

        Args:
            event: Pygame event
            mouse_pos: Current mouse position

        Returns:
            True if event was consumed (camera action), False otherwise
        """
        if event.type == pygame.MOUSEBUTTONDOWN:
            if event.button in (2, 3):  # Middle or right click
                self.drag.is_dragging = True
                self.drag.button = event.button
                self.drag.start_pos = mouse_pos
                self.drag.start_offset = self.camera.offset
                return True

        elif event.type == pygame.MOUSEBUTTONUP:
            if event.button in (2, 3) and self.drag.button == event.button:
                was_drag = self._was_significant_drag(mouse_pos)
                self.drag.is_dragging = False
                self.drag.button = None

                # Return whether this was a drag (vs a click)
                # If right-click wasn't a drag, caller may want to deselect
                if event.button == 3 and not was_drag:
                    return False  # Let caller handle right-click
                return True

        elif event.type == pygame.MOUSEMOTION:
            if self.drag.is_dragging:
                dx = mouse_pos[0] - self.drag.start_pos[0]
                dy = mouse_pos[1] - self.drag.start_pos[1]
                self.camera.set_offset(
                    self.drag.start_offset[0] + dx,
                    self.drag.start_offset[1] + dy
                )
                return True

        elif event.type == pygame.MOUSEWHEEL:
            mods = pygame.key.get_mods()
            if mods & pygame.KMOD_CTRL:
                if event.y > 0:
                    self.camera.zoom_in()
                elif event.y < 0:
                    self.camera.zoom_out()
                return True

        elif event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                self.camera.zoom_in()
                return True
            elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                self.camera.zoom_out()
                return True

        return False

    def handle_continuous_input(self):
        """Handle continuous keyboard input for scrolling. Shift for faster movement."""
        keys = pygame.key.get_pressed()
        mods = pygame.key.get_mods()

        # Use faster scroll speed when Shift is held
        speed = self.scroll_speed
        if mods & pygame.KMOD_SHIFT:
            speed *= self.fast_scroll_multiplier

        if keys[pygame.K_LEFT]:
            self.camera.move_offset(speed, 0)
        if keys[pygame.K_RIGHT]:
            self.camera.move_offset(-speed, 0)
        if keys[pygame.K_UP]:
            self.camera.move_offset(0, speed)
        if keys[pygame.K_DOWN]:
            self.camera.move_offset(0, -speed)

    def _was_significant_drag(self, current_pos: Tuple[int, int]) -> bool:
        """Check if mouse moved enough to count as a drag."""
        dx = abs(current_pos[0] - self.drag.start_pos[0])
        dy = abs(current_pos[1] - self.drag.start_pos[1])
        return dx > self.drag_threshold or dy > self.drag_threshold

    def was_right_click_not_drag(self, event: pygame.event.Event, mouse_pos: Tuple[int, int]) -> bool:
        """Check if a right mouse button up event was a click (not a drag)."""
        if event.type != pygame.MOUSEBUTTONUP or event.button != 3:
            return False
        return not self._was_significant_drag(mouse_pos)
