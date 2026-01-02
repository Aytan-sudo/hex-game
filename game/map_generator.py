"""
Procedural map generator for the hex strategy game.

Uses a layered approach:
1. Base terrain (plains, hills, forests) using noise
2. Mountain ranges (clustered massifs)
3. Water features (rivers with variable width)
4. Contextual terrain (swamps near water)
5. Infrastructure (cities, roads, bridges) as overlays
"""

import random
import math
from typing import Optional
from dataclasses import dataclass

from engine.hex_grid import HexCoord
from engine.tile import Tile
from game.terrain import TerrainType, OverlayType


@dataclass
class MapConfig:
    """Configuration for map generation."""
    width: int = 200
    height: int = 200
    seed: Optional[int] = None

    # Terrain distribution
    forest_density: float = 0.30     # 0.0 to 1.0
    hills_density: float = 0.15      # 0.0 to 1.0
    mountain_density: float = 0.08   # 0.0 to 1.0 (will form clusters)

    # Mountain clusters
    mountain_cluster_size: int = 10  # Approximate size of mountain massifs
    mountain_cluster_count: int = 0  # 0 = auto-calculate based on density

    # Water features
    add_river: bool = True
    river_count: int = 3             # Number of rivers
    river_min_width: int = 1         # Minimum river width
    river_max_width: int = 3         # Maximum river width

    # Lakes
    add_lakes: bool = True
    lake_count: int = 5

    # Contextual terrain
    swamp_near_water: bool = True

    # Infrastructure (overlays)
    add_cities: bool = True
    city_count: int = 0              # 0 = auto-calculate based on map size
    add_roads: bool = True
    add_bridges: bool = True
    add_ruins: bool = True
    ruins_count: int = 0             # 0 = auto-calculate


class SimplexNoise:
    """
    Simplified noise generator for terrain variation.
    Uses a basic approach suitable for hex grids.
    """

    def __init__(self, seed: int = 0):
        self.seed = seed
        random.seed(seed)
        # Permutation table
        self.perm = list(range(256))
        random.shuffle(self.perm)
        self.perm = self.perm + self.perm  # Double it for overflow

    def _grad(self, hash_val: int, x: float, y: float) -> float:
        """Compute gradient."""
        h = hash_val & 7
        u = x if h < 4 else y
        v = y if h < 4 else x
        return (u if (h & 1) == 0 else -u) + (v if (h & 2) == 0 else -v)

    def _fade(self, t: float) -> float:
        """Fade function for smooth interpolation."""
        return t * t * t * (t * (t * 6 - 15) + 10)

    def _lerp(self, a: float, b: float, t: float) -> float:
        """Linear interpolation."""
        return a + t * (b - a)

    def noise2d(self, x: float, y: float) -> float:
        """Generate 2D noise value between -1 and 1."""
        xi = int(math.floor(x)) & 255
        yi = int(math.floor(y)) & 255

        xf = x - math.floor(x)
        yf = y - math.floor(y)

        u = self._fade(xf)
        v = self._fade(yf)

        aa = self.perm[self.perm[xi] + yi]
        ab = self.perm[self.perm[xi] + yi + 1]
        ba = self.perm[self.perm[xi + 1] + yi]
        bb = self.perm[self.perm[xi + 1] + yi + 1]

        x1 = self._lerp(self._grad(aa, xf, yf), self._grad(ba, xf - 1, yf), u)
        x2 = self._lerp(self._grad(ab, xf, yf - 1), self._grad(bb, xf - 1, yf - 1), u)

        return self._lerp(x1, x2, v)

    def octave_noise(self, x: float, y: float, octaves: int = 4, persistence: float = 0.5) -> float:
        """Generate multi-octave noise for more natural terrain."""
        total = 0.0
        frequency = 1.0
        amplitude = 1.0
        max_value = 0.0

        for _ in range(octaves):
            total += self.noise2d(x * frequency, y * frequency) * amplitude
            max_value += amplitude
            amplitude *= persistence
            frequency *= 2

        return total / max_value


class MapGenerator:
    """
    Generates hex maps using a layered approach.
    """

    def __init__(self, config: MapConfig):
        self.config = config
        self.seed = config.seed if config.seed is not None else random.randint(0, 999999)
        self.noise = SimplexNoise(self.seed)
        self.tiles: dict[tuple[int, int], Tile] = {}

        # Track special positions
        self.water_tiles: set[tuple[int, int]] = set()
        self.mountain_tiles: set[tuple[int, int]] = set()
        self.hills_tiles: set[tuple[int, int]] = set()
        self.city_positions: list[tuple[int, int]] = []
        self.river_paths: list[list[tuple[int, int]]] = []

    def generate(self) -> dict[tuple[int, int], Tile]:
        """
        Generate a complete map using layered approach.

        Returns:
            Dictionary mapping (q, r) to Tile objects
        """
        random.seed(self.seed)

        # Layer 1: Base terrain (plains, hills, and forests)
        self._generate_base_terrain()

        # Layer 2: Mountain ranges (clustered)
        self._generate_mountain_clusters()

        # Layer 3: Water features
        if self.config.add_river:
            self._generate_rivers()
        if self.config.add_lakes:
            self._generate_lakes()

        # Layer 4: Contextual terrain
        if self.config.swamp_near_water:
            self._add_swamps_near_water()

        # Layer 5: Infrastructure (overlays)
        if self.config.add_cities:
            self._generate_cities()
        if self.config.add_roads:
            self._generate_roads()
        if self.config.add_ruins:
            self._generate_ruins()

        return self.tiles

    def _generate_base_terrain(self):
        """
        Layer 1: Generate base terrain (plains, hills, and forests) using noise.
        Mountains are handled separately in clusters.
        """
        forest_scale = 0.08  # Larger features for big maps
        hills_scale = 0.06   # Different scale for hills

        # Collect all coordinates and their noise values
        coords_data: list[tuple[tuple[int, int], float, float]] = []

        for row in range(self.config.height):
            for col in range(self.config.width):
                q = col - (row // 2)
                r = row

                forest_noise = self.noise.octave_noise(
                    q * forest_scale + 50,
                    r * forest_scale + 50,
                    octaves=3,
                    persistence=0.5
                )

                hills_noise = self.noise.octave_noise(
                    q * hills_scale + 100,
                    r * hills_scale + 100,
                    octaves=3,
                    persistence=0.6
                )

                coords_data.append(((q, r), forest_noise, hills_noise))

        # Determine thresholds
        forest_values = sorted([d[1] for d in coords_data], reverse=True)
        hills_values = sorted([d[2] for d in coords_data], reverse=True)
        total = len(forest_values)

        forest_count = int(total * self.config.forest_density)
        hills_count = int(total * self.config.hills_density)

        forest_threshold = forest_values[forest_count] if forest_count < total else forest_values[-1]
        hills_threshold = hills_values[hills_count] if hills_count < total else hills_values[-1]

        # Assign terrain
        for (q, r), forest_noise, hills_noise in coords_data:
            coord = HexCoord(q, r)

            # Determine base terrain (priority: hills > forest > plains)
            if hills_noise >= hills_threshold:
                terrain_type = TerrainType.HILLS
                self.hills_tiles.add((q, r))
            elif forest_noise >= forest_threshold:
                terrain_type = TerrainType.FOREST
            else:
                terrain_type = TerrainType.PLAINS

            tile = Tile(position=coord, base_terrain=terrain_type)
            self.tiles[coord.to_tuple()] = tile

    def _generate_mountain_clusters(self):
        """
        Layer 2: Generate mountain ranges as clusters/massifs.
        Uses seed points and grows clusters around them.
        """
        total_tiles = self.config.width * self.config.height
        target_mountain_tiles = int(total_tiles * self.config.mountain_density)

        # Calculate number of clusters
        cluster_count = self.config.mountain_cluster_count
        if cluster_count == 0:
            # Auto-calculate: one cluster per ~cluster_size^2 tiles needed
            tiles_per_cluster = self.config.mountain_cluster_size ** 2
            cluster_count = max(1, target_mountain_tiles // tiles_per_cluster)

        tiles_per_cluster = target_mountain_tiles // max(1, cluster_count)

        # Generate cluster seed points using noise for natural distribution
        cluster_seeds = self._find_cluster_seeds(cluster_count)

        # Grow each cluster
        for seed_coord in cluster_seeds:
            self._grow_mountain_cluster(seed_coord, tiles_per_cluster)

    def _find_cluster_seeds(self, count: int) -> list[tuple[int, int]]:
        """Find good positions for mountain cluster seeds using elevation noise."""
        elevation_scale = 0.05

        # Calculate elevation for sampling points
        candidates: list[tuple[tuple[int, int], float]] = []

        # Sample at intervals to find high elevation areas
        step = max(1, min(self.config.width, self.config.height) // 20)

        for row in range(0, self.config.height, step):
            for col in range(0, self.config.width, step):
                q = col - (row // 2)
                r = row
                coord = (q, r)

                if coord not in self.tiles:
                    continue

                elevation = self.noise.octave_noise(
                    q * elevation_scale,
                    r * elevation_scale,
                    octaves=4,
                    persistence=0.6
                )
                candidates.append((coord, elevation))

        # Sort by elevation and pick top candidates with spacing
        candidates.sort(key=lambda x: x[1], reverse=True)

        seeds = []
        min_distance = self.config.mountain_cluster_size * 2

        for coord, _ in candidates:
            if len(seeds) >= count:
                break

            # Check distance from existing seeds
            too_close = False
            for existing in seeds:
                dist = HexCoord(*coord).distance_to(HexCoord(*existing))
                if dist < min_distance:
                    too_close = True
                    break

            if not too_close:
                seeds.append(coord)

        # If we didn't find enough, add random ones
        all_coords = list(self.tiles.keys())
        while len(seeds) < count and all_coords:
            coord = random.choice(all_coords)
            all_coords.remove(coord)

            too_close = False
            for existing in seeds:
                dist = HexCoord(*coord).distance_to(HexCoord(*existing))
                if dist < min_distance // 2:
                    too_close = True
                    break

            if not too_close:
                seeds.append(coord)

        return seeds

    def _grow_mountain_cluster(self, seed: tuple[int, int], target_size: int):
        """Grow a mountain cluster from a seed point."""
        cluster = {seed}
        frontier = [seed]

        while len(cluster) < target_size and frontier:
            # Pick from frontier with preference for closer to seed
            current = frontier.pop(0)
            neighbors = HexCoord(*current).neighbors()
            random.shuffle(neighbors)

            for neighbor in neighbors:
                coord = neighbor.to_tuple()

                if coord not in self.tiles:
                    continue
                if coord in cluster:
                    continue
                if coord in self.mountain_tiles:
                    continue

                # Higher chance to expand if we haven't reached target
                expand_chance = 0.7 if len(cluster) < target_size * 0.8 else 0.3

                if random.random() < expand_chance:
                    cluster.add(coord)
                    frontier.append(coord)

                    if len(cluster) >= target_size:
                        break

        # Apply mountain terrain
        for coord in cluster:
            self.tiles[coord] = Tile(
                position=HexCoord(*coord),
                base_terrain=TerrainType.MOUNTAIN
            )
            self.mountain_tiles.add(coord)
            # Remove from hills if it was there
            self.hills_tiles.discard(coord)

    def _generate_rivers(self):
        """
        Layer 3a: Generate rivers with variable width.
        Rivers flow from mountains/edges toward the map center or edges.
        """
        for river_idx in range(self.config.river_count):
            # Alternate starting edge
            if river_idx % 2 == 0:
                # Start from top
                start_col = random.randint(self.config.width // 6, 5 * self.config.width // 6)
                start_row = 0
            else:
                # Start from side
                start_col = 0 if random.random() < 0.5 else self.config.width - 1
                start_row = random.randint(self.config.height // 6, 5 * self.config.height // 6)

            self._generate_single_river(start_col, start_row, river_idx)

    def _generate_single_river(self, start_col: int, start_row: int, river_idx: int):
        """Generate a single river with variable width."""
        river_path: list[tuple[int, int]] = []

        current_col = start_col
        current_row = start_row
        direction = 0  # Accumulated direction bias

        # Determine flow direction
        flow_vertical = start_row == 0 or start_row == self.config.height - 1

        max_steps = max(self.config.width, self.config.height) * 2

        for step in range(max_steps):
            q = current_col - (current_row // 2)
            r = current_row
            coord = (q, r)

            if coord not in self.tiles:
                break

            # Check if we've crossed another river (stop or continue)
            if coord in self.water_tiles and len(river_path) > 10:
                river_path.append(coord)
                break

            river_path.append(coord)

            # Calculate width for this segment (varies along the river)
            progress = step / max_steps
            base_width = self.config.river_min_width
            if progress > 0.3:
                # River gets wider downstream
                width_range = self.config.river_max_width - self.config.river_min_width
                base_width += int(width_range * min(1.0, (progress - 0.3) / 0.5))

            # Add some width variation
            current_width = base_width + random.randint(-1, 1)
            current_width = max(self.config.river_min_width, min(self.config.river_max_width, current_width))

            # Store width info for later
            river_path[-1] = (coord, current_width)

            # Move to next position
            if flow_vertical:
                # Primarily vertical flow
                current_row += 1

                # Meander
                direction += random.choice([-1, -1, 0, 0, 0, 0, 1, 1])
                direction = max(-3, min(3, direction))

                if abs(direction) >= 2:
                    current_col += 1 if direction > 0 else -1
                    direction = direction // 2
            else:
                # Primarily horizontal flow
                if start_col == 0:
                    current_col += 1
                else:
                    current_col -= 1

                # Meander
                direction += random.choice([-1, 0, 0, 0, 0, 1])
                direction = max(-2, min(2, direction))

                if abs(direction) >= 2:
                    current_row += 1 if direction > 0 else -1
                    direction = 0

            # Bounds check
            current_col = max(0, min(self.config.width - 1, current_col))
            current_row = max(0, min(self.config.height - 1, current_row))

            # Stop if we reach edge
            if flow_vertical and current_row >= self.config.height - 1:
                break
            if not flow_vertical and (current_col <= 0 or current_col >= self.config.width - 1):
                break

        # Apply water tiles with width
        actual_path = []
        for item in river_path:
            if isinstance(item, tuple) and len(item) == 2 and isinstance(item[0], tuple):
                coord, width = item
            else:
                coord = item
                width = 1

            actual_path.append(coord)
            self._apply_water_tile(coord)

            # Add width
            if width > 1:
                q, r = coord
                neighbors = HexCoord(q, r).neighbors()
                added = 0
                for neighbor in neighbors:
                    if added >= width - 1:
                        break
                    ncoord = neighbor.to_tuple()
                    if ncoord in self.tiles and ncoord not in self.water_tiles:
                        # Don't widen through mountains
                        if ncoord not in self.mountain_tiles:
                            self._apply_water_tile(ncoord)
                            added += 1

        self.river_paths.append(actual_path)

    def _apply_water_tile(self, coord: tuple[int, int]):
        """Apply water terrain to a tile."""
        if coord in self.tiles:
            self.tiles[coord] = Tile(
                position=HexCoord(*coord),
                base_terrain=TerrainType.WATER
            )
            self.water_tiles.add(coord)
            # Remove from other sets
            self.mountain_tiles.discard(coord)
            self.hills_tiles.discard(coord)

    def _generate_lakes(self):
        """Layer 3b: Generate lakes."""
        for _ in range(self.config.lake_count):
            # Find a spot not too close to existing water
            attempts = 50
            best_coord = None

            for _ in range(attempts):
                row = random.randint(self.config.height // 4, 3 * self.config.height // 4)
                col = random.randint(self.config.width // 4, 3 * self.config.width // 4)
                q = col - (row // 2)
                coord = (q, row)

                if coord not in self.tiles or coord in self.water_tiles:
                    continue
                if coord in self.mountain_tiles:
                    continue

                # Check distance from water
                min_dist = min(
                    (HexCoord(*coord).distance_to(HexCoord(*w)) for w in self.water_tiles),
                    default=999
                )

                if min_dist > 5:
                    best_coord = coord
                    break

            if best_coord:
                self._create_lake(best_coord, random.randint(3, 8))

    def _create_lake(self, center: tuple[int, int], size: int):
        """Create a lake around a center point."""
        lake_tiles = {center}
        frontier = [center]

        while len(lake_tiles) < size and frontier:
            current = frontier.pop(0)
            neighbors = HexCoord(*current).neighbors()
            random.shuffle(neighbors)

            for neighbor in neighbors:
                coord = neighbor.to_tuple()
                if coord in self.tiles and coord not in lake_tiles:
                    if coord not in self.water_tiles and coord not in self.mountain_tiles:
                        if random.random() < 0.6:
                            lake_tiles.add(coord)
                            frontier.append(coord)

        for coord in lake_tiles:
            self._apply_water_tile(coord)

    def _add_swamps_near_water(self):
        """Layer 4: Add swamps adjacent to water features."""
        swamp_candidates = set()

        for water_coord in self.water_tiles:
            neighbors = HexCoord(*water_coord).neighbors()
            for neighbor in neighbors:
                coord = neighbor.to_tuple()
                if coord in self.tiles and coord not in self.water_tiles:
                    tile = self.tiles[coord]
                    if tile.base_terrain == TerrainType.PLAINS:
                        swamp_candidates.add(coord)

        for coord in swamp_candidates:
            if random.random() < 0.35:
                self.tiles[coord] = Tile(
                    position=HexCoord(*coord),
                    base_terrain=TerrainType.SWAMP
                )

    def _generate_cities(self):
        """
        Layer 5a: Generate cities at strategic locations.
        Cities are placed as overlays on suitable base terrain.
        """
        city_count = self.config.city_count
        if city_count == 0:
            # Auto-calculate: roughly 1 city per 1000 tiles
            city_count = max(3, (self.config.width * self.config.height) // 1000)

        min_city_distance = max(15, min(self.config.width, self.config.height) // 10)

        for _ in range(city_count):
            best_coord = None
            best_score = -999

            attempts = 100
            for _ in range(attempts):
                row = random.randint(5, self.config.height - 5)
                col = random.randint(5, self.config.width - 5)
                q = col - (row // 2)
                coord = (q, row)

                if coord not in self.tiles:
                    continue
                if coord in self.water_tiles or coord in self.mountain_tiles:
                    continue

                # Check distance from other cities
                too_close = False
                for city in self.city_positions:
                    if HexCoord(*coord).distance_to(HexCoord(*city)) < min_city_distance:
                        too_close = True
                        break

                if too_close:
                    continue

                # Score based on proximity to water (good) and flatness
                score = 0

                # Near water is good
                min_water_dist = min(
                    (HexCoord(*coord).distance_to(HexCoord(*w)) for w in self.water_tiles),
                    default=999
                )
                if min_water_dist <= 3:
                    score += 10 - min_water_dist * 2
                elif min_water_dist <= 6:
                    score += 3

                # On plains is best, hills is okay
                tile = self.tiles[coord]
                if tile.base_terrain == TerrainType.PLAINS:
                    score += 5
                elif tile.base_terrain == TerrainType.HILLS:
                    score += 2

                # Not surrounded by mountains
                neighbors = HexCoord(*coord).neighbors()
                mountain_neighbors = sum(1 for n in neighbors if n.to_tuple() in self.mountain_tiles)
                score -= mountain_neighbors * 2

                if score > best_score:
                    best_score = score
                    best_coord = coord

            if best_coord:
                # Add city as overlay on existing terrain
                tile = self.tiles[best_coord]
                tile.overlay = OverlayType.CITY
                self.city_positions.append(best_coord)

    def _generate_roads(self):
        """
        Layer 5b: Generate roads connecting cities.
        Also generates bridges where roads cross water.
        """
        if len(self.city_positions) < 2:
            return

        # Connect each city to nearest unconnected city (minimum spanning tree approach)
        connected = {self.city_positions[0]}
        unconnected = set(self.city_positions[1:])

        while unconnected:
            best_pair = None
            best_distance = float('inf')

            for c1 in connected:
                for c2 in unconnected:
                    dist = HexCoord(*c1).distance_to(HexCoord(*c2))
                    if dist < best_distance:
                        best_distance = dist
                        best_pair = (c1, c2)

            if best_pair:
                self._build_road(best_pair[0], best_pair[1])
                connected.add(best_pair[1])
                unconnected.remove(best_pair[1])

    def _build_road(self, start: tuple[int, int], end: tuple[int, int]):
        """Build a road between two points, adding bridges over water."""
        # Use A* or simple line for path
        path = self._find_path(start, end)

        for coord in path:
            if coord == start or coord == end:
                continue  # Don't overwrite cities

            tile = self.tiles.get(coord)
            if not tile:
                continue

            if coord in self.water_tiles:
                # Build bridge as overlay on water
                if self.config.add_bridges:
                    tile.overlay = OverlayType.BRIDGE
            elif coord not in self.mountain_tiles:
                # Build road as overlay (not through mountains)
                if tile.base_terrain in [TerrainType.PLAINS, TerrainType.FOREST,
                                          TerrainType.SWAMP, TerrainType.HILLS,
                                          TerrainType.DESERT]:
                    tile.overlay = OverlayType.ROAD

    def _generate_ruins(self):
        """Layer 5c: Generate ruins scattered across the map."""
        ruins_count = self.config.ruins_count
        if ruins_count == 0:
            # Auto-calculate: roughly 1 ruin per 2000 tiles
            ruins_count = max(2, (self.config.width * self.config.height) // 2000)

        min_ruin_distance = 10

        placed = 0
        attempts = ruins_count * 20

        for _ in range(attempts):
            if placed >= ruins_count:
                break

            row = random.randint(3, self.config.height - 3)
            col = random.randint(3, self.config.width - 3)
            q = col - (row // 2)
            coord = (q, row)

            if coord not in self.tiles:
                continue

            tile = self.tiles[coord]

            # Don't place on water, mountains, or tiles with overlays
            if coord in self.water_tiles or coord in self.mountain_tiles:
                continue
            if tile.overlay is not None:
                continue

            # Check distance from cities and other ruins
            too_close = False
            for city in self.city_positions:
                if HexCoord(*coord).distance_to(HexCoord(*city)) < min_ruin_distance:
                    too_close = True
                    break

            if too_close:
                continue

            # Place ruin as overlay
            tile.overlay = OverlayType.RUINS
            placed += 1

    def _find_path(self, start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
        """Find a path between two points (simple A* implementation)."""
        from heapq import heappush, heappop

        def heuristic(a, b):
            return HexCoord(*a).distance_to(HexCoord(*b))

        def get_cost(coord):
            if coord in self.mountain_tiles:
                return 10  # Very expensive to cross mountains
            if coord in self.water_tiles:
                return 3 if self.config.add_bridges else 100
            return 1

        open_set = [(0, start)]
        came_from = {}
        g_score = {start: 0}

        while open_set:
            _, current = heappop(open_set)

            if current == end:
                # Reconstruct path
                path = [current]
                while current in came_from:
                    current = came_from[current]
                    path.append(current)
                return list(reversed(path))

            neighbors = HexCoord(*current).neighbors()
            for neighbor in neighbors:
                ncoord = neighbor.to_tuple()

                if ncoord not in self.tiles:
                    continue

                tentative_g = g_score[current] + get_cost(ncoord)

                if ncoord not in g_score or tentative_g < g_score[ncoord]:
                    came_from[ncoord] = current
                    g_score[ncoord] = tentative_g
                    f_score = tentative_g + heuristic(ncoord, end)
                    heappush(open_set, (f_score, ncoord))

        # No path found, return direct line
        return self._get_hex_line(start, end)

    def _get_hex_line(self, start: tuple[int, int], end: tuple[int, int]) -> list[tuple[int, int]]:
        """Get hexes along a line between two points."""
        start_hex = HexCoord(*start)
        end_hex = HexCoord(*end)
        n = start_hex.distance_to(end_hex)

        if n == 0:
            return [start]

        results = []
        for i in range(n + 1):
            t = i / n
            q = start_hex.q + (end_hex.q - start_hex.q) * t
            r = start_hex.r + (end_hex.r - start_hex.r) * t

            # Round to nearest hex
            rq, rr = round(q), round(r)
            results.append((rq, rr))

        return results


def generate_map(
    width: int = 200,
    height: int = 200,
    seed: Optional[int] = None,
    add_river: bool = True,
    forest_density: float = 0.30,
    hills_density: float = 0.15,
    mountain_density: float = 0.08
) -> dict[tuple[int, int], Tile]:
    """
    Convenience function to generate a map with common options.
    """
    config = MapConfig(
        width=width,
        height=height,
        seed=seed,
        add_river=add_river,
        forest_density=forest_density,
        hills_density=hills_density,
        mountain_density=mountain_density,
    )

    generator = MapGenerator(config)
    return generator.generate()
