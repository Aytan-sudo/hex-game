"""
Pygame renderer for the hex strategy game.

Handles all visual rendering of the hex grid, tiles, and units.
"""

from __future__ import annotations
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING
import math
import pygame

from .hex_grid import HexGrid, HexCoord
from .tile import Tile

if TYPE_CHECKING:
    from .camera import Camera


class HexRenderer:
    """
    Renders the hex grid and game elements using Pygame.

    Uses pointy-top hexagons by default.
    """

    # Default colors
    BACKGROUND_COLOR = (30, 30, 40)
    GRID_LINE_COLOR = (60, 60, 80)
    SELECTED_COLOR = (255, 255, 100)
    HOVER_COLOR = (200, 200, 255)

    def __init__(
        self,
        screen_width: int = 1280,
        screen_height: int = 720,
        hex_size: float = 30.0,
        title: str = "Hex Strategy Game",
        camera: Optional[Camera] = None
    ):
        """
        Initialize the renderer.

        Args:
            screen_width: Window width in pixels
            screen_height: Window height in pixels
            hex_size: Size of hexagons (center to corner) - ignored if camera provided
            title: Window title
            camera: Optional Camera instance for zoom control
        """
        self.screen_width = screen_width
        self.screen_height = screen_height
        self.title = title

        # Camera for zoom and offset management
        self._camera = camera
        self._base_hex_size = hex_size  # Fallback if no camera

        # Grid offset for centering/scrolling (used only if no camera)
        self._offset = (100.0, 100.0)

        # Initialize Pygame
        pygame.init()
        self.screen = pygame.display.set_mode((screen_width, screen_height))
        pygame.display.set_caption(title)
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 24)

        # Create hex grid helper
        self.hex_grid = HexGrid(hex_size=self.hex_size, pointy_top=True)

        # Selection state
        self.selected_hex: Optional[HexCoord] = None
        self.hover_hex: Optional[HexCoord] = None

    @property
    def hex_size(self) -> float:
        """Current hex size (from camera if available)."""
        if self._camera:
            return self._camera.hex_size
        return self._base_hex_size

    @property
    def offset(self) -> Tuple[float, float]:
        """Current offset (from camera if available)."""
        if self._camera:
            return self._camera.offset
        return self._offset

    @offset.setter
    def offset(self, value: Tuple[float, float]):
        """Set offset (on camera if available)."""
        if self._camera:
            self._camera.set_offset(value[0], value[1])
        else:
            self._offset = value

    @property
    def camera(self) -> Optional[Camera]:
        """Get the camera instance."""
        return self._camera

    def set_camera(self, camera: Camera):
        """Set or update the camera and rebuild hex_grid."""
        self._camera = camera
        self._rebuild_hex_grid()

    def _rebuild_hex_grid(self):
        """Rebuild hex_grid with current hex_size."""
        self.hex_grid = HexGrid(hex_size=self.hex_size, pointy_top=True)

    def clear(self):
        """Clear the screen with background color."""
        self.screen.fill(self.BACKGROUND_COLOR)

    def draw_hex(
        self,
        coord: HexCoord,
        fill_color: Tuple[int, int, int],
        border_color: Optional[Tuple[int, int, int]] = None,
        border_width: int = 1
    ):
        """
        Draw a single hexagon.

        Args:
            coord: Hex coordinate to draw
            fill_color: RGB fill color
            border_color: RGB border color (None for no border)
            border_width: Border line width
        """
        corners = self.hex_grid.get_hex_corners(coord, self.offset)

        # Draw filled hexagon
        pygame.draw.polygon(self.screen, fill_color, corners)

        # Draw border
        if border_color:
            pygame.draw.polygon(self.screen, border_color, corners, border_width)

    def draw_tile(self, tile: Tile):
        """
        Draw a tile with its terrain color.

        Args:
            tile: The tile to draw
        """
        # Get terrain color
        fill_color = tile.display_color

        # Determine border color based on selection state
        border_color = self.GRID_LINE_COLOR
        border_width = 1

        if tile.position == self.selected_hex:
            border_color = self.SELECTED_COLOR
            border_width = 3
        elif tile.position == self.hover_hex:
            border_color = self.HOVER_COLOR
            border_width = 2

        self.draw_hex(tile.position, fill_color, border_color, border_width)

    def draw_grid(self, tiles: Dict[Tuple[int, int], Tile]):
        """
        Draw the entire grid of tiles.

        Args:
            tiles: Dictionary mapping (q, r) tuples to Tile objects
        """
        for coord_tuple, tile in tiles.items():
            self.draw_tile(tile)

    def draw_hex_coordinates(self, coord: HexCoord, color: Tuple[int, int, int] = (200, 200, 200)):
        """
        Draw coordinate labels on a hex (for debugging).

        Args:
            coord: Hex coordinate
            color: Text color
        """
        center = self.hex_grid.hex_to_pixel(coord, self.offset)
        text = f"{coord.q},{coord.r}"
        text_surface = self.font.render(text, True, color)
        text_rect = text_surface.get_rect(center=center)
        self.screen.blit(text_surface, text_rect)

    def draw_unit_marker(
        self,
        coord: HexCoord,
        color: Tuple[int, int, int] = (255, 0, 0),
        size: float = 0.5,
        letter: str = "",
        is_selected: bool = False
    ):
        """
        Draw a unit marker as a smaller hexagon with a letter.

        Args:
            coord: Hex coordinate
            color: Marker color
            size: Size relative to hex (0.0 to 1.0)
            letter: Letter to display in center
            is_selected: Whether this unit is selected
        """
        center = self.hex_grid.hex_to_pixel(coord, self.offset)
        unit_hex_size = self.hex_size * size

        # Calculate hexagon corners for unit marker
        corners = []
        for i in range(6):
            angle = math.pi / 180 * (60 * i - 30)  # Pointy-top
            corner_x = center[0] + unit_hex_size * math.cos(angle)
            corner_y = center[1] + unit_hex_size * math.sin(angle)
            corners.append((corner_x, corner_y))

        # Draw selection highlight if selected
        if is_selected:
            highlight_size = unit_hex_size * 1.15
            highlight_corners = []
            for i in range(6):
                angle = math.pi / 180 * (60 * i - 30)
                corner_x = center[0] + highlight_size * math.cos(angle)
                corner_y = center[1] + highlight_size * math.sin(angle)
                highlight_corners.append((corner_x, corner_y))
            pygame.draw.polygon(self.screen, (255, 255, 100), highlight_corners)
            pygame.draw.polygon(self.screen, (255, 255, 200), highlight_corners, 3)

        # Draw filled hexagon
        pygame.draw.polygon(self.screen, color, corners)

        # Draw border
        border_color = (
            min(255, color[0] + 60),
            min(255, color[1] + 60),
            min(255, color[2] + 60)
        )
        pygame.draw.polygon(self.screen, border_color, corners, 3)

        # Draw darker inner border for depth
        inner_border = (
            max(0, color[0] - 40),
            max(0, color[1] - 40),
            max(0, color[2] - 40)
        )
        pygame.draw.polygon(self.screen, inner_border, corners, 1)

        # Draw letter in center
        if letter:
            # Use larger font for the letter
            letter_font = pygame.font.Font(None, int(unit_hex_size * 1.2))
            text_surface = letter_font.render(letter, True, (255, 255, 255))
            text_rect = text_surface.get_rect(center=(int(center[0]), int(center[1])))
            self.screen.blit(text_surface, text_rect)

            # Draw text shadow for better visibility
            shadow_surface = letter_font.render(letter, True, (0, 0, 0))
            shadow_rect = shadow_surface.get_rect(center=(int(center[0]) + 2, int(center[1]) + 2))
            self.screen.blit(shadow_surface, shadow_rect)
            self.screen.blit(text_surface, text_rect)

    def get_hex_at_pixel(self, x: int, y: int) -> HexCoord:
        """
        Get the hex coordinate at a pixel position.

        Args:
            x, y: Pixel coordinates (e.g., mouse position)

        Returns:
            HexCoord at that position
        """
        return self.hex_grid.pixel_to_hex(x, y, self.offset)

    def set_offset(self, x: float, y: float):
        """Set the rendering offset (for scrolling/panning)."""
        if self._camera:
            self._camera.set_offset(x, y)
        else:
            self._offset = (x, y)

    def move_offset(self, dx: float, dy: float):
        """Move the rendering offset by a delta."""
        if self._camera:
            self._camera.move_offset(dx, dy)
        else:
            self._offset = (self._offset[0] + dx, self._offset[1] + dy)

    def zoom_in(self) -> bool:
        """Zoom in if camera is available."""
        if self._camera and self._camera.zoom_in():
            self._rebuild_hex_grid()
            return True
        return False

    def zoom_out(self) -> bool:
        """Zoom out if camera is available."""
        if self._camera and self._camera.zoom_out():
            self._rebuild_hex_grid()
            return True
        return False

    def update_display(self):
        """Update the display (call after drawing)."""
        pygame.display.flip()

    def tick(self, fps: int = 60) -> float:
        """
        Limit frame rate and return delta time.

        Args:
            fps: Target frames per second

        Returns:
            Time since last frame in seconds
        """
        return self.clock.tick(fps) / 1000.0

    def quit(self):
        """Clean up Pygame resources."""
        pygame.quit()

    def draw_text(
        self,
        text: str,
        position: Tuple[int, int],
        color: Tuple[int, int, int] = (255, 255, 255),
        center: bool = False
    ):
        """
        Draw text on the screen.

        Args:
            text: Text to draw
            position: (x, y) position
            color: Text color
            center: If True, center text on position
        """
        text_surface = self.font.render(text, True, color)
        if center:
            text_rect = text_surface.get_rect(center=position)
        else:
            text_rect = text_surface.get_rect(topleft=position)
        self.screen.blit(text_surface, text_rect)

    def draw_valid_attacks(self, valid_attacks: set, color: Tuple[int, int, int] = (255, 80, 80)):
        """
        Draw indicators for valid attack targets.

        Args:
            valid_attacks: Set of (q, r) tuples representing valid attack targets
            color: Color for the attack indicators
        """
        for coord_tuple in valid_attacks:
            coord = HexCoord(*coord_tuple)
            corners = self.hex_grid.get_hex_corners(coord, self.offset)

            # Draw semi-transparent red overlay
            surface = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
            pygame.draw.polygon(surface, (*color, 100), corners)
            self.screen.blit(surface, (0, 0))

            # Draw thick red border
            pygame.draw.polygon(self.screen, color, corners, 3)

            # Draw crosshair/target indicator
            center = self.hex_grid.hex_to_pixel(coord, self.offset)
            cx, cy = int(center[0]), int(center[1])
            size = int(self.hex_size * 0.3)
            pygame.draw.line(self.screen, (255, 255, 255), (cx - size, cy), (cx + size, cy), 2)
            pygame.draw.line(self.screen, (255, 255, 255), (cx, cy - size), (cx, cy + size), 2)
            pygame.draw.circle(self.screen, (255, 255, 255), (cx, cy), size // 2, 2)

    def draw_combat_message(
        self,
        message: str,
        position: Tuple[int, int] = None,
        color: Tuple[int, int, int] = (255, 255, 100)
    ):
        """
        Draw a combat message in a visible box.

        Args:
            message: The message to display
            position: (x, y) position, or None for center screen
            color: Text color
        """
        if not message:
            return

        # Use larger font for combat messages
        combat_font = pygame.font.Font(None, 32)
        text_surface = combat_font.render(message, True, color)
        text_rect = text_surface.get_rect()

        if position is None:
            position = (self.screen_width // 2, 100)

        text_rect.center = position

        # Draw background box
        padding = 15
        bg_rect = text_rect.inflate(padding * 2, padding * 2)

        # Semi-transparent background
        bg_surface = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        bg_surface.fill((0, 0, 0, 200))
        self.screen.blit(bg_surface, bg_rect.topleft)

        # Border
        pygame.draw.rect(self.screen, color, bg_rect, 2, border_radius=5)

        # Text
        self.screen.blit(text_surface, text_rect)

    def highlight_hexes(
        self,
        hexes: List[HexCoord],
        color: Tuple[int, int, int, int] = (100, 100, 255, 100)
    ):
        """
        Highlight a list of hexes (e.g., for movement range).

        Args:
            hexes: List of hex coordinates to highlight
            color: RGBA color for highlight
        """
        # Create a transparent surface for the highlight
        for hex_coord in hexes:
            corners = self.hex_grid.get_hex_corners(hex_coord, self.offset)
            # Draw semi-transparent overlay
            surface = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
            pygame.draw.polygon(surface, color, corners)
            self.screen.blit(surface, (0, 0))

    def draw_valid_moves(self, valid_moves: set, color: Tuple[int, int, int] = (100, 200, 100)):
        """
        Draw indicators for valid move destinations.

        Args:
            valid_moves: Set of (q, r) tuples representing valid moves
            color: Color for the move indicators
        """
        for coord_tuple in valid_moves:
            coord = HexCoord(*coord_tuple)
            corners = self.hex_grid.get_hex_corners(coord, self.offset)

            # Draw semi-transparent green overlay
            surface = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
            pygame.draw.polygon(surface, (*color, 80), corners)
            self.screen.blit(surface, (0, 0))

            # Draw border
            pygame.draw.polygon(self.screen, color, corners, 2)

    def draw_button(
        self,
        text: str,
        rect: Tuple[int, int, int, int],
        color: Tuple[int, int, int] = (80, 80, 120),
        hover_color: Tuple[int, int, int] = (100, 100, 150),
        text_color: Tuple[int, int, int] = (255, 255, 255),
        is_hovered: bool = False
    ) -> pygame.Rect:
        """
        Draw a UI button.

        Args:
            text: Button text
            rect: (x, y, width, height)
            color: Normal button color
            hover_color: Color when hovered
            text_color: Text color
            is_hovered: Whether mouse is over button

        Returns:
            pygame.Rect of the button for click detection
        """
        button_rect = pygame.Rect(rect)
        current_color = hover_color if is_hovered else color

        pygame.draw.rect(self.screen, current_color, button_rect, border_radius=5)
        pygame.draw.rect(self.screen, (150, 150, 180), button_rect, 2, border_radius=5)

        text_surface = self.font.render(text, True, text_color)
        text_rect = text_surface.get_rect(center=button_rect.center)
        self.screen.blit(text_surface, text_rect)

        return button_rect

    def draw_panel(
        self,
        rect: Tuple[int, int, int, int],
        color: Tuple[int, int, int] = (40, 40, 60),
        alpha: int = 220
    ):
        """
        Draw a semi-transparent UI panel.

        Args:
            rect: (x, y, width, height)
            color: Panel color
            alpha: Transparency (0-255)
        """
        panel = pygame.Surface((rect[2], rect[3]), pygame.SRCALPHA)
        panel.fill((*color, alpha))
        self.screen.blit(panel, (rect[0], rect[1]))
        pygame.draw.rect(self.screen, (80, 80, 100), rect, 2, border_radius=3)

    def draw_movement_path(
        self,
        start: HexCoord,
        end: HexCoord,
        valid_moves: set,
        color: Tuple[int, int, int] = (255, 255, 100),
        invalid_color: Tuple[int, int, int] = (255, 100, 100)
    ):
        """
        Draw a path line from start to end hex, showing movement preview.

        The line is drawn only up to the last valid hex on the path.
        If the destination is not reachable, shows a red indicator.

        Args:
            start: Starting hex coordinate
            end: Target hex coordinate (mouse hover position)
            valid_moves: Set of valid move destinations
            color: Color for valid path
            invalid_color: Color for invalid destination indicator
        """
        if start == end:
            return

        # Get the hex line from start to end
        path = self.hex_grid.get_line(start, end)

        if len(path) < 2:
            return

        # Find the last valid hex on the path
        last_valid_index = 0
        for i, hex_coord in enumerate(path[1:], 1):  # Skip start
            if hex_coord.to_tuple() in valid_moves:
                last_valid_index = i
            else:
                break

        # Draw the valid portion of the path
        if last_valid_index > 0:
            # Get pixel positions for path
            points = []
            for i in range(last_valid_index + 1):
                center = self.hex_grid.hex_to_pixel(path[i], self.offset)
                points.append((int(center[0]), int(center[1])))

            # Draw thick line for valid path
            if len(points) >= 2:
                pygame.draw.lines(self.screen, color, False, points, 4)

                # Draw circles at each hex center
                for point in points:
                    pygame.draw.circle(self.screen, color, point, 6)
                    pygame.draw.circle(self.screen, (255, 255, 255), point, 6, 2)

        # If end is not reachable (not in valid moves), show indicator
        end_tuple = end.to_tuple()
        if end_tuple not in valid_moves and last_valid_index < len(path) - 1:
            # Draw a dashed/faded line from last valid to hover
            if last_valid_index > 0:
                last_valid_center = self.hex_grid.hex_to_pixel(path[last_valid_index], self.offset)
                end_center = self.hex_grid.hex_to_pixel(end, self.offset)

                # Draw dashed line to unreachable destination
                pygame.draw.line(
                    self.screen,
                    (*invalid_color, 150),
                    (int(last_valid_center[0]), int(last_valid_center[1])),
                    (int(end_center[0]), int(end_center[1])),
                    2
                )

            # Draw X at unreachable destination
            end_center = self.hex_grid.hex_to_pixel(end, self.offset)
            x, y = int(end_center[0]), int(end_center[1])
            size = 8
            pygame.draw.line(self.screen, invalid_color, (x - size, y - size), (x + size, y + size), 3)
            pygame.draw.line(self.screen, invalid_color, (x - size, y + size), (x + size, y - size), 3)
