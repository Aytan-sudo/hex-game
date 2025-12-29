"""
Hex Grid System using axial coordinates (q, r).

Axial coordinates are a standard way to represent hexagonal grids.
- q: column (increases going right)
- r: row (increases going down-right for pointy-top hexagons)

Reference: https://www.redblobgames.com/grids/hexagons/
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import List, Tuple, Optional
import math


@dataclass(frozen=True)
class HexCoord:
    """
    Immutable axial coordinate for a hexagon.
    Uses (q, r) system where q + r + s = 0 (s is implicit: s = -q - r)
    """
    q: int
    r: int

    @property
    def s(self) -> int:
        """Third cube coordinate (implicit from q and r)."""
        return -self.q - self.r

    def __add__(self, other: HexCoord) -> HexCoord:
        return HexCoord(self.q + other.q, self.r + other.r)

    def __sub__(self, other: HexCoord) -> HexCoord:
        return HexCoord(self.q - other.q, self.r - other.r)

    def distance_to(self, other: HexCoord) -> int:
        """
        Calculate the distance between two hexagons.
        Uses cube coordinate distance formula.
        """
        return (abs(self.q - other.q) + abs(self.r - other.r) + abs(self.s - other.s)) // 2

    def neighbors(self) -> List[HexCoord]:
        """Return all 6 neighboring hex coordinates."""
        return [self + direction for direction in HEX_DIRECTIONS]

    def to_tuple(self) -> Tuple[int, int]:
        """Convert to tuple for use as dictionary key."""
        return (self.q, self.r)


# The 6 directions in axial coordinates (for pointy-top hexagons)
HEX_DIRECTIONS = [
    HexCoord(1, 0),   # East
    HexCoord(1, -1),  # Northeast
    HexCoord(0, -1),  # Northwest
    HexCoord(-1, 0),  # West
    HexCoord(-1, 1),  # Southwest
    HexCoord(0, 1),   # Southeast
]


class HexGrid:
    """
    Manages a hexagonal grid with axial coordinates.
    Handles coordinate conversions and grid operations.
    """

    def __init__(self, hex_size: float = 30.0, pointy_top: bool = True):
        """
        Initialize the hex grid.

        Args:
            hex_size: Distance from center to corner of hexagon (in pixels)
            pointy_top: If True, hexagons have a point at top (vs flat top)
        """
        self.hex_size = hex_size
        self.pointy_top = pointy_top

        # Precompute conversion constants
        if pointy_top:
            # Pointy-top hexagon dimensions
            self.width = math.sqrt(3) * hex_size
            self.height = 2 * hex_size
        else:
            # Flat-top hexagon dimensions
            self.width = 2 * hex_size
            self.height = math.sqrt(3) * hex_size

    def hex_to_pixel(self, coord: HexCoord, offset: Tuple[float, float] = (0, 0)) -> Tuple[float, float]:
        """
        Convert axial hex coordinates to pixel coordinates (center of hex).

        Args:
            coord: Hex coordinate to convert
            offset: Pixel offset to add (for screen positioning)

        Returns:
            (x, y) pixel coordinates of hex center
        """
        if self.pointy_top:
            x = self.hex_size * (math.sqrt(3) * coord.q + math.sqrt(3) / 2 * coord.r)
            y = self.hex_size * (3 / 2 * coord.r)
        else:
            x = self.hex_size * (3 / 2 * coord.q)
            y = self.hex_size * (math.sqrt(3) / 2 * coord.q + math.sqrt(3) * coord.r)

        return (x + offset[0], y + offset[1])

    def pixel_to_hex(self, x: float, y: float, offset: Tuple[float, float] = (0, 0)) -> HexCoord:
        """
        Convert pixel coordinates to the nearest hex coordinate.

        Args:
            x, y: Pixel coordinates
            offset: Pixel offset that was used (for screen positioning)

        Returns:
            Nearest HexCoord
        """
        # Remove offset
        px = x - offset[0]
        py = y - offset[1]

        if self.pointy_top:
            q = (math.sqrt(3) / 3 * px - 1 / 3 * py) / self.hex_size
            r = (2 / 3 * py) / self.hex_size
        else:
            q = (2 / 3 * px) / self.hex_size
            r = (-1 / 3 * px + math.sqrt(3) / 3 * py) / self.hex_size

        return self._round_hex(q, r)

    def _round_hex(self, q: float, r: float) -> HexCoord:
        """
        Round fractional hex coordinates to nearest integer hex.
        Uses cube coordinate rounding for accuracy.
        """
        s = -q - r

        rq = round(q)
        rr = round(r)
        rs = round(s)

        # Fix rounding errors by adjusting the largest diff
        q_diff = abs(rq - q)
        r_diff = abs(rr - r)
        s_diff = abs(rs - s)

        if q_diff > r_diff and q_diff > s_diff:
            rq = -rr - rs
        elif r_diff > s_diff:
            rr = -rq - rs
        # else: rs = -rq - rr (not needed since we only use q, r)

        return HexCoord(int(rq), int(rr))

    def get_hex_corners(self, coord: HexCoord, offset: Tuple[float, float] = (0, 0)) -> List[Tuple[float, float]]:
        """
        Get the 6 corner points of a hexagon for drawing.

        Args:
            coord: Hex coordinate
            offset: Pixel offset for screen positioning

        Returns:
            List of 6 (x, y) tuples for the corners
        """
        center = self.hex_to_pixel(coord, offset)
        corners = []

        for i in range(6):
            if self.pointy_top:
                angle = math.pi / 180 * (60 * i - 30)
            else:
                angle = math.pi / 180 * (60 * i)

            corner_x = center[0] + self.hex_size * math.cos(angle)
            corner_y = center[1] + self.hex_size * math.sin(angle)
            corners.append((corner_x, corner_y))

        return corners

    def get_hexes_in_range(self, center: HexCoord, range_: int) -> List[HexCoord]:
        """
        Get all hexes within a given range of a center hex.

        Args:
            center: Center hex coordinate
            range_: Maximum distance from center

        Returns:
            List of all hex coordinates within range
        """
        results = []
        for q in range(-range_, range_ + 1):
            for r in range(max(-range_, -q - range_), min(range_, -q + range_) + 1):
                results.append(center + HexCoord(q, r))
        return results

    def get_line(self, start: HexCoord, end: HexCoord) -> List[HexCoord]:
        """
        Get all hexes along a line between two hexes.

        Args:
            start: Starting hex
            end: Ending hex

        Returns:
            List of hexes along the line (including start and end)
        """
        n = start.distance_to(end)
        if n == 0:
            return [start]

        results = []
        for i in range(n + 1):
            t = i / n
            # Linear interpolation in cube coordinates
            q = start.q + (end.q - start.q) * t
            r = start.r + (end.r - start.r) * t
            results.append(self._round_hex(q, r))

        return results
