"""
Tactical battle map for the hex strategy game.

Opens when two armies meet on the strategic map.
Handles individual unit combat on a smaller battlefield.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from enum import Enum
import random

import pygame

from engine.hex_grid import HexCoord, HexGrid
from engine.tile import Tile
from engine.unit import Unit, Army, ArmyUnit, UnitStats, UnitType
from engine.combat import CombatSystem, CombatResult
from engine.camera import Camera
from game.terrain import TerrainType, TERRAIN_CONFIGS
from game.map_generator import MapConfig, MapGenerator


@dataclass
class TacticalUnit:
    """A single unit on the tactical battlefield."""
    name: str
    unit_type: UnitType
    stats: UnitStats
    player_id: int
    position: Optional[HexCoord] = None
    movement_remaining: int = 0
    has_acted: bool = False
    source_army_unit: Optional[ArmyUnit] = None  # Reference to original army unit

    @property
    def is_alive(self) -> bool:
        return self.stats.current_hp > 0

    def start_turn(self):
        """Reset unit state at the start of a turn."""
        self.movement_remaining = self.stats.movement
        self.has_acted = False

    def get_attack_power(self) -> int:
        return self.stats.attack

    def get_defense_power(self) -> int:
        return self.stats.defense

    def can_attack(self) -> bool:
        return not self.has_acted and self.is_alive


@dataclass
class BattleReport:
    """Report of the battle outcome."""
    attacker_name: str
    defender_name: str
    attacker_won: bool
    attacker_survivors: List[Tuple[str, int, int]]  # (name, remaining, original)
    defender_survivors: List[Tuple[str, int, int]]
    attacker_losses: int
    defender_losses: int
    rounds: int

    @property
    def is_draw(self) -> bool:
        """A draw if both sides still have units."""
        return len(self.attacker_survivors) > 0 and len(self.defender_survivors) > 0


class TacticalBattle:
    """
    Manages a tactical battle between two armies.

    Creates a small battlefield (20x20) and places units from both armies.
    Combat is resolved turn by turn until one side is eliminated.
    """

    MAP_WIDTH = 20
    MAP_HEIGHT = 20

    def __init__(
        self,
        attacker: Army,
        defender: Army,
        screen: pygame.Surface,
        strategic_terrain: TerrainType = TerrainType.PLAINS,
        seed: Optional[int] = None
    ):
        self.attacker = attacker
        self.defender = defender
        self.screen = screen
        self.strategic_terrain = strategic_terrain
        self.seed = seed or random.randint(0, 999999)

        self.screen_width = screen.get_width()
        self.screen_height = screen.get_height()

        # Generate tactical map based on strategic terrain
        self.tiles = self._generate_tactical_map()

        # Create tactical units from armies
        self.attacker_units: List[TacticalUnit] = []
        self.defender_units: List[TacticalUnit] = []
        self._deploy_units()

        # Combat system
        self.combat_system = CombatSystem(random_factor=0.2)

        # Turn management
        self.current_player_id = attacker.player_id
        self.turn_number = 1
        self.max_turns = 20  # Auto-draw after 20 turns

        # Selection state
        self.selected_unit: Optional[TacticalUnit] = None
        self.valid_moves: Set[Tuple[int, int]] = set()
        self.valid_attacks: Set[Tuple[int, int]] = set()

        # Battle state
        self.battle_over = False
        self.battle_report: Optional[BattleReport] = None
        self.combat_log: List[str] = []

        # Camera for tactical view
        self.camera = Camera(self.screen_width, self.screen_height)
        # Start at a comfortable zoom for 20x20
        self.camera.zoom_index = 6  # 48px

        # Center camera on map
        center_x = self.MAP_WIDTH * self.camera.hex_size * 1.5
        center_y = self.MAP_HEIGHT * self.camera.hex_size * 1.3
        self.camera.set_offset(
            self.screen_width / 2 - center_x / 2,
            self.screen_height / 2 - center_y / 2
        )

    def _generate_tactical_map(self) -> Dict[Tuple[int, int], Tile]:
        """
        Generate a tactical battlefield based on the strategic terrain.

        Different strategic terrains produce different tactical maps:
        - Plains: Open field with scattered forests
        - Forest: Dense forest with clearings
        - Mountain: Mountain passes and plateaus
        - Swamp: Marshy terrain with water pools
        - Desert: Sandy terrain with rocky outcrops
        - Road: Open terrain with a road crossing
        """
        terrain = self.strategic_terrain

        # Configure generation based on strategic terrain
        if terrain == TerrainType.PLAINS:
            config = MapConfig(
                width=self.MAP_WIDTH,
                height=self.MAP_HEIGHT,
                seed=self.seed,
                forest_density=0.15,
                mountain_density=0.02,
                mountain_cluster_size=2,
                add_river=False,
                add_lakes=False,
                swamp_near_water=False,
                add_cities=False,
                add_roads=False,
                add_bridges=False,
            )

        elif terrain == TerrainType.FOREST:
            config = MapConfig(
                width=self.MAP_WIDTH,
                height=self.MAP_HEIGHT,
                seed=self.seed,
                forest_density=0.55,  # Dense forest
                mountain_density=0.0,
                add_river=False,
                add_lakes=False,
                swamp_near_water=True,
                add_cities=False,
                add_roads=False,
                add_bridges=False,
            )

        elif terrain == TerrainType.MOUNTAIN:
            config = MapConfig(
                width=self.MAP_WIDTH,
                height=self.MAP_HEIGHT,
                seed=self.seed,
                forest_density=0.10,
                mountain_density=0.35,  # Lots of mountains
                mountain_cluster_size=4,
                add_river=False,
                add_lakes=False,
                swamp_near_water=False,
                add_cities=False,
                add_roads=False,
                add_bridges=False,
            )

        elif terrain == TerrainType.SWAMP:
            config = MapConfig(
                width=self.MAP_WIDTH,
                height=self.MAP_HEIGHT,
                seed=self.seed,
                forest_density=0.15,
                mountain_density=0.0,
                add_river=False,
                add_lakes=True,
                lake_count=3,  # Multiple water pools
                swamp_near_water=True,
                add_cities=False,
                add_roads=False,
                add_bridges=False,
            )

        elif terrain == TerrainType.DESERT:
            config = MapConfig(
                width=self.MAP_WIDTH,
                height=self.MAP_HEIGHT,
                seed=self.seed,
                forest_density=0.0,  # No forests in desert
                mountain_density=0.15,  # Rocky outcrops
                mountain_cluster_size=2,
                add_river=False,
                add_lakes=False,
                swamp_near_water=False,
                add_cities=False,
                add_roads=False,
                add_bridges=False,
            )

        elif terrain == TerrainType.ROAD:
            # Road battle - mostly open with a road
            config = MapConfig(
                width=self.MAP_WIDTH,
                height=self.MAP_HEIGHT,
                seed=self.seed,
                forest_density=0.20,
                mountain_density=0.0,
                add_river=False,
                add_lakes=False,
                swamp_near_water=False,
                add_cities=False,
                add_roads=False,  # We'll add a road manually
                add_bridges=False,
            )

        else:
            # Default/fallback (City, Bridge, Water, etc.)
            config = MapConfig(
                width=self.MAP_WIDTH,
                height=self.MAP_HEIGHT,
                seed=self.seed,
                forest_density=0.20,
                mountain_density=0.05,
                mountain_cluster_size=2,
                add_river=False,
                add_lakes=True,
                lake_count=1,
                swamp_near_water=True,
                add_cities=False,
                add_roads=False,
                add_bridges=False,
            )

        generator = MapGenerator(config)
        tiles = generator.generate()

        # Post-processing for specific terrain types
        if terrain == TerrainType.DESERT:
            # Convert plains to desert
            tiles = self._convert_plains_to_desert(tiles)

        elif terrain == TerrainType.ROAD:
            # Add a road crossing the battlefield
            tiles = self._add_tactical_road(tiles)

        return tiles

    def _convert_plains_to_desert(self, tiles: Dict[Tuple[int, int], Tile]) -> Dict[Tuple[int, int], Tile]:
        """Convert plains tiles to desert for desert battles."""
        from game.terrain import get_terrain_config
        desert_config = get_terrain_config(TerrainType.DESERT)

        for tile in tiles.values():
            if tile.terrain.name == "Plains":
                tile.terrain = desert_config

        return tiles

    def _add_tactical_road(self, tiles: Dict[Tuple[int, int], Tile]) -> Dict[Tuple[int, int], Tile]:
        """Add a road crossing the tactical battlefield."""
        from game.terrain import get_terrain_config
        road_config = get_terrain_config(TerrainType.ROAD)

        # Road from left to right through the middle
        mid_r = self.MAP_HEIGHT // 2
        for q in range(self.MAP_WIDTH):
            # Slight curve using offset
            r = mid_r + (q % 3 - 1)
            if (q, r) in tiles and tiles[(q, r)].is_passable:
                tiles[(q, r)].terrain = road_config

        return tiles

    def _deploy_units(self):
        """Deploy units from both armies onto the battlefield."""
        # Get passable tiles on each side
        left_tiles = [
            (q, r) for (q, r), tile in self.tiles.items()
            if q < self.MAP_WIDTH // 3 and tile.is_passable
        ]
        right_tiles = [
            (q, r) for (q, r), tile in self.tiles.items()
            if q > 2 * self.MAP_WIDTH // 3 and tile.is_passable
        ]

        random.seed(self.seed)
        random.shuffle(left_tiles)
        random.shuffle(right_tiles)

        # Deploy attacker units (left side)
        deploy_idx = 0
        for army_unit in self.attacker.units:
            for i in range(army_unit.count):
                if deploy_idx >= len(left_tiles):
                    break

                tactical_unit = TacticalUnit(
                    name=f"{army_unit.name} {i+1}",
                    unit_type=army_unit.unit_type,
                    stats=UnitStats(
                        max_hp=army_unit.base_stats.max_hp,
                        current_hp=army_unit.base_stats.current_hp,
                        attack=army_unit.base_stats.attack,
                        defense=army_unit.base_stats.defense,
                        movement=army_unit.base_stats.movement,
                        range=army_unit.base_stats.range,
                    ),
                    player_id=self.attacker.player_id,
                    position=HexCoord(*left_tiles[deploy_idx]),
                    movement_remaining=army_unit.base_stats.movement,
                    source_army_unit=army_unit,
                )
                self.tiles[left_tiles[deploy_idx]].unit = tactical_unit
                self.attacker_units.append(tactical_unit)
                deploy_idx += 1

        # Deploy defender units (right side)
        deploy_idx = 0
        for army_unit in self.defender.units:
            for i in range(army_unit.count):
                if deploy_idx >= len(right_tiles):
                    break

                tactical_unit = TacticalUnit(
                    name=f"{army_unit.name} {i+1}",
                    unit_type=army_unit.unit_type,
                    stats=UnitStats(
                        max_hp=army_unit.base_stats.max_hp,
                        current_hp=army_unit.base_stats.current_hp,
                        attack=army_unit.base_stats.attack,
                        defense=army_unit.base_stats.defense,
                        movement=army_unit.base_stats.movement,
                        range=army_unit.base_stats.range,
                    ),
                    player_id=self.defender.player_id,
                    position=HexCoord(*right_tiles[deploy_idx]),
                    movement_remaining=army_unit.base_stats.movement,
                    source_army_unit=army_unit,
                )
                self.tiles[right_tiles[deploy_idx]].unit = tactical_unit
                self.defender_units.append(tactical_unit)
                deploy_idx += 1

    def get_units_for_player(self, player_id: int) -> List[TacticalUnit]:
        """Get all living units for a player."""
        if player_id == self.attacker.player_id:
            return [u for u in self.attacker_units if u.is_alive]
        else:
            return [u for u in self.defender_units if u.is_alive]

    def get_enemy_units(self, player_id: int) -> List[TacticalUnit]:
        """Get enemy units."""
        if player_id == self.attacker.player_id:
            return [u for u in self.defender_units if u.is_alive]
        else:
            return [u for u in self.attacker_units if u.is_alive]

    def select_unit(self, unit: Optional[TacticalUnit]):
        """Select a unit and calculate valid moves/attacks."""
        self.selected_unit = unit
        self.valid_moves.clear()
        self.valid_attacks.clear()

        if unit is None or not unit.is_alive:
            return

        if unit.player_id != self.current_player_id:
            self.selected_unit = None
            return

        # Calculate valid moves
        if unit.movement_remaining > 0:
            self.valid_moves = self._calculate_valid_moves(unit)

        # Calculate valid attacks
        if not unit.has_acted:
            self.valid_attacks = self._calculate_valid_attacks(unit)

    def _calculate_valid_moves(self, unit: TacticalUnit) -> Set[Tuple[int, int]]:
        """Calculate valid move destinations using BFS."""
        valid = set()
        start = unit.position.to_tuple()

        queue = [(start, unit.movement_remaining)]
        visited = {start: unit.movement_remaining}

        while queue:
            current_pos, remaining = queue.pop(0)
            current_coord = HexCoord(*current_pos)

            for neighbor in current_coord.neighbors():
                neighbor_tuple = neighbor.to_tuple()

                if neighbor_tuple not in self.tiles:
                    continue

                tile = self.tiles[neighbor_tuple]

                if not tile.is_passable:
                    continue

                move_cost = tile.get_movement_cost()
                new_remaining = remaining - move_cost

                if new_remaining < 0:
                    continue

                if neighbor_tuple in visited and visited[neighbor_tuple] >= new_remaining:
                    continue

                visited[neighbor_tuple] = new_remaining

                if tile.unit is None:
                    valid.add(neighbor_tuple)

                queue.append((neighbor_tuple, new_remaining))

        return valid

    def _calculate_valid_attacks(self, unit: TacticalUnit) -> Set[Tuple[int, int]]:
        """Calculate valid attack targets."""
        valid = set()
        position = unit.position
        attack_range = unit.stats.range

        # Check all hexes within range
        for q in range(-attack_range, attack_range + 1):
            for r in range(max(-attack_range, -q - attack_range),
                          min(attack_range, -q + attack_range) + 1):
                target = HexCoord(position.q + q, position.r + r)
                target_tuple = target.to_tuple()

                if target_tuple == position.to_tuple():
                    continue

                if target_tuple not in self.tiles:
                    continue

                tile = self.tiles[target_tuple]
                if tile.unit and tile.unit.player_id != unit.player_id:
                    distance = position.distance_to(target)
                    if distance <= attack_range:
                        valid.add(target_tuple)

        return valid

    def try_move(self, target: HexCoord) -> bool:
        """Try to move selected unit to target."""
        if self.selected_unit is None:
            return False

        target_tuple = target.to_tuple()
        if target_tuple not in self.valid_moves:
            return False

        # Calculate path cost
        source_tuple = self.selected_unit.position.to_tuple()
        path_cost = self._calculate_path_cost(source_tuple, target_tuple)

        if path_cost > self.selected_unit.movement_remaining:
            return False

        # Move the unit
        self.tiles[source_tuple].unit = None
        self.tiles[target_tuple].unit = self.selected_unit
        self.selected_unit.position = target
        self.selected_unit.movement_remaining -= path_cost

        # Update valid moves/attacks
        self.select_unit(self.selected_unit)

        return True

    def _calculate_path_cost(self, start: Tuple[int, int], end: Tuple[int, int]) -> int:
        """Calculate minimum movement cost using Dijkstra."""
        import heapq

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

                if neighbor_tuple not in self.tiles:
                    continue

                tile = self.tiles[neighbor_tuple]
                if not tile.is_passable:
                    continue

                new_dist = current_dist + tile.get_movement_cost()

                if new_dist < distances.get(neighbor_tuple, float('inf')):
                    distances[neighbor_tuple] = new_dist
                    heapq.heappush(pq, (new_dist, neighbor_tuple))

        return 999

    def try_attack(self, target: HexCoord) -> Optional[CombatResult]:
        """Try to attack enemy at target position."""
        if self.selected_unit is None or self.selected_unit.has_acted:
            return None

        target_tuple = target.to_tuple()
        if target_tuple not in self.valid_attacks:
            return None

        target_tile = self.tiles.get(target_tuple)
        if target_tile is None or target_tile.unit is None:
            return None

        attacker = self.selected_unit
        defender = target_tile.unit

        attacker_tile = self.tiles.get(attacker.position.to_tuple())

        # Resolve combat
        result = self.combat_system.resolve_combat(
            attacker, defender,
            attacker_tile, target_tile
        )

        # Log combat
        log_msg = f"{attacker.name} attacks {defender.name}: "
        if result.defender_survived:
            log_msg += f"-{result.defender_damage} HP"
            if result.attacker_damage > 0:
                log_msg += f" (counter: -{result.attacker_damage})"
        else:
            log_msg += "KILLED!"
        self.combat_log.append(log_msg)

        # Handle deaths
        if not defender.is_alive:
            target_tile.unit = None
            if defender in self.defender_units:
                self.defender_units.remove(defender)
            elif defender in self.attacker_units:
                self.attacker_units.remove(defender)

        if not attacker.is_alive:
            attacker_tile = self.tiles.get(attacker.position.to_tuple())
            if attacker_tile:
                attacker_tile.unit = None
            if attacker in self.attacker_units:
                self.attacker_units.remove(attacker)
            elif attacker in self.defender_units:
                self.defender_units.remove(attacker)
            self.selected_unit = None

        # Check for battle end
        self._check_battle_end()

        # Update selection
        if self.selected_unit:
            self.select_unit(self.selected_unit)

        return result

    def end_turn(self):
        """End current player's turn."""
        # Switch player
        if self.current_player_id == self.attacker.player_id:
            self.current_player_id = self.defender.player_id
        else:
            self.current_player_id = self.attacker.player_id
            self.turn_number += 1

        # Reset units for current player
        for unit in self.get_units_for_player(self.current_player_id):
            unit.start_turn()

        self.selected_unit = None
        self.valid_moves.clear()
        self.valid_attacks.clear()

        # Check for auto-draw
        if self.turn_number > self.max_turns:
            self._end_battle(is_draw=True)

    def _check_battle_end(self):
        """Check if battle should end."""
        attacker_alive = [u for u in self.attacker_units if u.is_alive]
        defender_alive = [u for u in self.defender_units if u.is_alive]

        if len(attacker_alive) == 0:
            self._end_battle(attacker_won=False)
        elif len(defender_alive) == 0:
            self._end_battle(attacker_won=True)

    def _end_battle(self, attacker_won: bool = None, is_draw: bool = False):
        """End the battle and create report."""
        self.battle_over = True

        # Count survivors by unit type
        attacker_survivors = {}
        for unit in self.attacker_units:
            if unit.is_alive and unit.source_army_unit:
                name = unit.source_army_unit.name
                if name not in attacker_survivors:
                    attacker_survivors[name] = [0, unit.source_army_unit.count]
                attacker_survivors[name][0] += 1

        defender_survivors = {}
        for unit in self.defender_units:
            if unit.is_alive and unit.source_army_unit:
                name = unit.source_army_unit.name
                if name not in defender_survivors:
                    defender_survivors[name] = [0, unit.source_army_unit.count]
                defender_survivors[name][0] += 1

        # Calculate losses
        attacker_original = sum(au.count for au in self.attacker.units)
        defender_original = sum(du.count for du in self.defender.units)
        attacker_remaining = sum(s[0] for s in attacker_survivors.values())
        defender_remaining = sum(s[0] for s in defender_survivors.values())

        if is_draw:
            attacker_won = attacker_remaining >= defender_remaining

        self.battle_report = BattleReport(
            attacker_name=self.attacker.name,
            defender_name=self.defender.name,
            attacker_won=attacker_won,
            attacker_survivors=[(k, v[0], v[1]) for k, v in attacker_survivors.items()],
            defender_survivors=[(k, v[0], v[1]) for k, v in defender_survivors.items()],
            attacker_losses=attacker_original - attacker_remaining,
            defender_losses=defender_original - defender_remaining,
            rounds=self.turn_number,
        )

    def update_armies_after_battle(self):
        """Update the original armies with battle results."""
        # Update attacker army
        for army_unit in self.attacker.units[:]:  # Copy list to modify
            survivors = sum(
                1 for u in self.attacker_units
                if u.is_alive and u.source_army_unit == army_unit
            )
            if survivors == 0:
                self.attacker.units.remove(army_unit)
            else:
                army_unit.count = survivors

        # Update defender army
        for army_unit in self.defender.units[:]:
            survivors = sum(
                1 for u in self.defender_units
                if u.is_alive and u.source_army_unit == army_unit
            )
            if survivors == 0:
                self.defender.units.remove(army_unit)
            else:
                army_unit.count = survivors

        # Recalculate army stats
        self.attacker._recalculate_stats()
        self.defender._recalculate_stats()


def run_tactical_battle(
    screen: pygame.Surface,
    attacker: Army,
    defender: Army,
    player_colors: Dict[int, Tuple[int, int, int]],
    strategic_terrain: TerrainType = TerrainType.PLAINS
) -> BattleReport:
    """
    Run a tactical battle between two armies.

    Args:
        screen: Pygame display surface
        attacker: The attacking army
        defender: The defending army
        player_colors: Color mapping for player IDs
        strategic_terrain: The terrain type from the strategic map where battle occurs

    Returns the battle report when complete.
    """
    battle = TacticalBattle(attacker, defender, screen, strategic_terrain)

    # Create hex grid for rendering
    hex_grid = HexGrid(hex_size=battle.camera.hex_size, pointy_top=True)

    font = pygame.font.Font(None, 24)
    title_font = pygame.font.Font(None, 36)
    clock = pygame.time.Clock()

    # Drag state
    is_dragging = False
    drag_start_pos = (0, 0)
    drag_start_offset = (0.0, 0.0)
    drag_button = None
    drag_threshold = 5

    running = True
    show_report = False

    while running:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                # Force end battle
                if not battle.battle_over:
                    battle._end_battle(is_draw=True)
                running = False

            elif event.type == pygame.KEYDOWN:
                if show_report:
                    # Any key closes report
                    running = False
                elif event.key == pygame.K_ESCAPE:
                    # ESC to retreat (auto-lose for attacker)
                    battle._end_battle(attacker_won=False)
                elif event.key == pygame.K_SPACE:
                    battle.end_turn()
                elif event.key in (pygame.K_PLUS, pygame.K_EQUALS, pygame.K_KP_PLUS):
                    if battle.camera.zoom_in():
                        hex_grid = HexGrid(hex_size=battle.camera.hex_size, pointy_top=True)
                elif event.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    if battle.camera.zoom_out():
                        hex_grid = HexGrid(hex_size=battle.camera.hex_size, pointy_top=True)

            elif event.type == pygame.MOUSEBUTTONDOWN and not show_report:
                if event.button == 1:  # Left click
                    clicked_hex = hex_grid.pixel_to_hex(mouse_pos[0], mouse_pos[1], battle.camera.offset)
                    clicked_tuple = clicked_hex.to_tuple()

                    if clicked_tuple not in battle.tiles:
                        continue

                    tile = battle.tiles[clicked_tuple]

                    # Check attack
                    if battle.selected_unit and clicked_tuple in battle.valid_attacks:
                        battle.try_attack(clicked_hex)

                    # Check move
                    elif battle.selected_unit and clicked_tuple in battle.valid_moves:
                        battle.try_move(clicked_hex)

                    # Select unit
                    elif tile.unit and tile.unit.player_id == battle.current_player_id:
                        battle.select_unit(tile.unit)

                    else:
                        battle.select_unit(None)

                elif event.button == 3:
                    is_dragging = True
                    drag_button = 3
                    drag_start_pos = mouse_pos
                    drag_start_offset = battle.camera.offset

                elif event.button == 2:
                    is_dragging = True
                    drag_button = 2
                    drag_start_pos = mouse_pos
                    drag_start_offset = battle.camera.offset

            elif event.type == pygame.MOUSEBUTTONUP:
                if event.button in (2, 3) and drag_button == event.button:
                    dx = abs(mouse_pos[0] - drag_start_pos[0])
                    dy = abs(mouse_pos[1] - drag_start_pos[1])
                    was_drag = dx > drag_threshold or dy > drag_threshold

                    if event.button == 3 and not was_drag:
                        battle.select_unit(None)

                    is_dragging = False
                    drag_button = None

            elif event.type == pygame.MOUSEMOTION:
                if is_dragging:
                    dx = mouse_pos[0] - drag_start_pos[0]
                    dy = mouse_pos[1] - drag_start_pos[1]
                    battle.camera.set_offset(
                        drag_start_offset[0] + dx,
                        drag_start_offset[1] + dy
                    )

            elif event.type == pygame.MOUSEWHEEL:
                mods = pygame.key.get_mods()
                if mods & pygame.KMOD_CTRL:
                    if event.y > 0:
                        if battle.camera.zoom_in():
                            hex_grid = HexGrid(hex_size=battle.camera.hex_size, pointy_top=True)
                    elif event.y < 0:
                        if battle.camera.zoom_out():
                            hex_grid = HexGrid(hex_size=battle.camera.hex_size, pointy_top=True)

        # Keyboard scrolling
        keys = pygame.key.get_pressed()
        scroll_speed = 10
        if keys[pygame.K_LEFT]:
            battle.camera.move_offset(scroll_speed, 0)
        if keys[pygame.K_RIGHT]:
            battle.camera.move_offset(-scroll_speed, 0)
        if keys[pygame.K_UP]:
            battle.camera.move_offset(0, scroll_speed)
        if keys[pygame.K_DOWN]:
            battle.camera.move_offset(0, -scroll_speed)

        # Check if battle ended
        if battle.battle_over and not show_report:
            show_report = True

        # Render
        screen.fill((30, 30, 40))

        # Draw tiles
        for coord_tuple, tile in battle.tiles.items():
            coord = HexCoord(*coord_tuple)
            center = hex_grid.hex_to_pixel(coord, battle.camera.offset)

            # Check if on screen
            if (center[0] < -battle.camera.hex_size * 2 or
                center[0] > battle.screen_width + battle.camera.hex_size * 2 or
                center[1] < -battle.camera.hex_size * 2 or
                center[1] > battle.screen_height + battle.camera.hex_size * 2):
                continue

            vertices = hex_grid.get_hex_corners(coord, battle.camera.offset)

            # Base terrain color
            color = tile.terrain.color

            # Highlight valid moves
            if coord_tuple in battle.valid_moves:
                color = tuple(min(255, c + 40) for c in color)

            # Highlight valid attacks
            if coord_tuple in battle.valid_attacks:
                color = (255, 100, 100)

            # Draw hex
            pygame.draw.polygon(screen, color, vertices)
            pygame.draw.polygon(screen, (50, 50, 60), vertices, 1)

        # Draw units
        all_units = battle.attacker_units + battle.defender_units
        for unit in all_units:
            if not unit.is_alive or unit.position is None:
                continue

            center = hex_grid.hex_to_pixel(unit.position, battle.camera.offset)
            x, y = int(center[0]), int(center[1])

            # Unit color
            color = player_colors.get(unit.player_id, (200, 200, 200))

            # Draw circle
            radius = int(battle.camera.hex_size * 0.4)
            pygame.draw.circle(screen, color, (x, y), radius)
            pygame.draw.circle(screen, (255, 255, 255), (x, y), radius, 2)

            # Selected highlight
            if unit == battle.selected_unit:
                pygame.draw.circle(screen, (255, 255, 100), (x, y), radius + 4, 3)

            # Unit type letter
            letter = unit.name[0].upper()
            text = font.render(letter, True, (255, 255, 255))
            text_rect = text.get_rect(center=(x, y))
            screen.blit(text, text_rect)

            # HP bar
            hp_width = int(battle.camera.hex_size * 0.8)
            hp_height = 4
            hp_x = x - hp_width // 2
            hp_y = y + radius + 5

            # Background
            pygame.draw.rect(screen, (60, 60, 60), (hp_x, hp_y, hp_width, hp_height))
            # HP fill
            hp_pct = unit.stats.current_hp / unit.stats.max_hp
            hp_color = (100, 200, 100) if hp_pct > 0.5 else (200, 200, 100) if hp_pct > 0.25 else (200, 100, 100)
            pygame.draw.rect(screen, hp_color, (hp_x, hp_y, int(hp_width * hp_pct), hp_height))

        # UI Panel - Top
        pygame.draw.rect(screen, (40, 40, 50), (0, 0, battle.screen_width, 60))

        title = title_font.render("TACTICAL BATTLE", True, (255, 255, 255))
        screen.blit(title, (battle.screen_width // 2 - title.get_width() // 2, 5))

        # Turn info
        current_name = attacker.name if battle.current_player_id == attacker.player_id else defender.name
        current_color = player_colors.get(battle.current_player_id, (200, 200, 200))
        turn_text = font.render(f"Turn {battle.turn_number} - {current_name}", True, current_color)
        screen.blit(turn_text, (10, 35))

        # Controls hint
        hint = font.render("Space: End Turn | ESC: Retreat", True, (150, 150, 150))
        screen.blit(hint, (battle.screen_width - 250, 35))

        # Unit counts
        attacker_count = len([u for u in battle.attacker_units if u.is_alive])
        defender_count = len([u for u in battle.defender_units if u.is_alive])

        att_text = font.render(f"{attacker.name}: {attacker_count} units", True, player_colors.get(attacker.player_id, (100, 100, 255)))
        def_text = font.render(f"{defender.name}: {defender_count} units", True, player_colors.get(defender.player_id, (255, 100, 100)))
        screen.blit(att_text, (10, 8))
        screen.blit(def_text, (250, 8))

        # Bottom panel - selected unit info
        pygame.draw.rect(screen, (40, 40, 50), (0, battle.screen_height - 50, battle.screen_width, 50))

        if battle.selected_unit:
            unit = battle.selected_unit
            info = f"{unit.name} | HP: {unit.stats.current_hp}/{unit.stats.max_hp} | ATK: {unit.stats.attack} | DEF: {unit.stats.defense} | Move: {unit.movement_remaining}/{unit.stats.movement} | Range: {unit.stats.range}"
            info_text = font.render(info, True, (255, 200, 100))
            screen.blit(info_text, (10, battle.screen_height - 35))

        # Combat log (last 3 entries)
        if battle.combat_log:
            for i, log in enumerate(battle.combat_log[-3:]):
                log_text = font.render(log, True, (180, 180, 180))
                screen.blit(log_text, (10, 70 + i * 20))

        # Battle report overlay
        if show_report and battle.battle_report:
            _draw_battle_report(screen, battle.battle_report, font, title_font)

        pygame.display.flip()
        clock.tick(60)

    battle.update_armies_after_battle()
    return battle.battle_report


def _draw_battle_report(
    screen: pygame.Surface,
    report: BattleReport,
    font: pygame.font.Font,
    title_font: pygame.font.Font
):
    """Draw battle report overlay."""
    sw, sh = screen.get_width(), screen.get_height()

    # Semi-transparent overlay
    overlay = pygame.Surface((sw, sh), pygame.SRCALPHA)
    overlay.fill((0, 0, 0, 180))
    screen.blit(overlay, (0, 0))

    # Report box
    box_w, box_h = 500, 400
    box_x = sw // 2 - box_w // 2
    box_y = sh // 2 - box_h // 2

    pygame.draw.rect(screen, (50, 50, 60), (box_x, box_y, box_w, box_h), border_radius=10)
    pygame.draw.rect(screen, (100, 100, 120), (box_x, box_y, box_w, box_h), 3, border_radius=10)

    # Title
    result_text = "VICTORY!" if report.attacker_won else "DEFEAT!"
    result_color = (100, 255, 100) if report.attacker_won else (255, 100, 100)
    title = title_font.render(f"BATTLE REPORT - {result_text}", True, result_color)
    screen.blit(title, (sw // 2 - title.get_width() // 2, box_y + 20))

    y = box_y + 70

    # Battle info
    info = font.render(f"{report.attacker_name} vs {report.defender_name}", True, (200, 200, 200))
    screen.blit(info, (sw // 2 - info.get_width() // 2, y))
    y += 30

    rounds = font.render(f"Battle lasted {report.rounds} rounds", True, (180, 180, 180))
    screen.blit(rounds, (sw // 2 - rounds.get_width() // 2, y))
    y += 40

    # Attacker survivors
    att_title = font.render(f"{report.attacker_name} survivors:", True, (100, 100, 255))
    screen.blit(att_title, (box_x + 30, y))
    y += 25

    if report.attacker_survivors:
        for name, remaining, original in report.attacker_survivors:
            surv = font.render(f"  {name}: {remaining}/{original}", True, (150, 150, 200))
            screen.blit(surv, (box_x + 30, y))
            y += 20
    else:
        none = font.render("  All units lost!", True, (255, 100, 100))
        screen.blit(none, (box_x + 30, y))
        y += 20

    y += 20

    # Defender survivors
    def_title = font.render(f"{report.defender_name} survivors:", True, (255, 100, 100))
    screen.blit(def_title, (box_x + 30, y))
    y += 25

    if report.defender_survivors:
        for name, remaining, original in report.defender_survivors:
            surv = font.render(f"  {name}: {remaining}/{original}", True, (200, 150, 150))
            screen.blit(surv, (box_x + 30, y))
            y += 20
    else:
        none = font.render("  All units lost!", True, (255, 100, 100))
        screen.blit(none, (box_x + 30, y))
        y += 20

    # Continue prompt
    prompt = font.render("Press any key to continue...", True, (200, 200, 200))
    screen.blit(prompt, (sw // 2 - prompt.get_width() // 2, box_y + box_h - 40))
