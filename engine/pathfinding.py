"""
Pathfinding utilities for hex grid navigation.

Provides BFS for valid moves calculation and Dijkstra for path cost.
"""

import heapq
from typing import Callable, Dict, Optional, Set, Tuple

from engine.hex_grid import HexCoord
from engine.tile import Tile


def calculate_valid_moves(
    start: Tuple[int, int],
    movement_remaining: int,
    tiles: Dict[Tuple[int, int], Tile],
    can_move_to: Callable[[Tile, Tuple[int, int]], bool],
    can_pass_through: Callable[[Tile], bool] = None
) -> Set[Tuple[int, int]]:
    """
    Calculate all valid move destinations using BFS.

    Args:
        start: Starting position (q, r)
        movement_remaining: Movement points available
        tiles: Map tiles dictionary
        can_move_to: Function(tile, pos) -> bool, determines if unit can stop here
        can_pass_through: Function(tile) -> bool, determines if unit can pass through
                         (defaults to checking if tile is empty)

    Returns:
        Set of valid destination positions
    """
    if can_pass_through is None:
        can_pass_through = lambda tile: tile.unit is None

    valid = set()
    queue = [(start, movement_remaining)]
    visited = {start: movement_remaining}

    while queue:
        current_pos, remaining = queue.pop(0)
        current_coord = HexCoord(*current_pos)

        for neighbor in current_coord.neighbors():
            neighbor_tuple = neighbor.to_tuple()

            if neighbor_tuple not in tiles:
                continue

            tile = tiles[neighbor_tuple]

            if not tile.is_passable:
                continue

            move_cost = tile.get_movement_cost()
            new_remaining = remaining - move_cost

            if new_remaining < 0:
                continue

            if neighbor_tuple in visited and visited[neighbor_tuple] >= new_remaining:
                continue

            visited[neighbor_tuple] = new_remaining

            # Check if this is a valid destination
            if can_move_to(tile, neighbor_tuple):
                valid.add(neighbor_tuple)

            # Continue exploring from passable tiles
            if can_pass_through(tile):
                queue.append((neighbor_tuple, new_remaining))

    return valid


def calculate_path_cost(
    start: Tuple[int, int],
    end: Tuple[int, int],
    tiles: Dict[Tuple[int, int], Tile]
) -> int:
    """
    Calculate minimum movement cost between two positions using Dijkstra.

    Args:
        start: Starting position (q, r)
        end: Target position (q, r)
        tiles: Map tiles dictionary

    Returns:
        Minimum movement cost, or 999 if no path exists
    """
    distances = {start: 0}
    pq = [(0, start)]

    while pq:
        current_dist, current = heapq.heappop(pq)

        if current == end:
            return current_dist

        if current_dist > distances.get(current, float('inf')):
            continue

        current_coord = HexCoord(*current)

        for neighbor in current_coord.neighbors():
            neighbor_tuple = neighbor.to_tuple()

            if neighbor_tuple not in tiles:
                continue

            tile = tiles[neighbor_tuple]
            if not tile.is_passable:
                continue

            new_dist = current_dist + tile.get_movement_cost()

            if new_dist < distances.get(neighbor_tuple, float('inf')):
                distances[neighbor_tuple] = new_dist
                heapq.heappush(pq, (new_dist, neighbor_tuple))

    return 999


def find_path(
    start: Tuple[int, int],
    end: Tuple[int, int],
    tiles: Dict[Tuple[int, int], Tile]
) -> Optional[list]:
    """
    Find the shortest path between two positions.

    Args:
        start: Starting position (q, r)
        end: Target position (q, r)
        tiles: Map tiles dictionary

    Returns:
        List of positions forming the path, or None if no path exists
    """
    distances = {start: 0}
    previous = {start: None}
    pq = [(0, start)]

    while pq:
        current_dist, current = heapq.heappop(pq)

        if current == end:
            # Reconstruct path
            path = []
            while current is not None:
                path.append(current)
                current = previous[current]
            return list(reversed(path))

        if current_dist > distances.get(current, float('inf')):
            continue

        current_coord = HexCoord(*current)

        for neighbor in current_coord.neighbors():
            neighbor_tuple = neighbor.to_tuple()

            if neighbor_tuple not in tiles:
                continue

            tile = tiles[neighbor_tuple]
            if not tile.is_passable:
                continue

            new_dist = current_dist + tile.get_movement_cost()

            if new_dist < distances.get(neighbor_tuple, float('inf')):
                distances[neighbor_tuple] = new_dist
                previous[neighbor_tuple] = current
                heapq.heappush(pq, (new_dist, neighbor_tuple))

    return None
