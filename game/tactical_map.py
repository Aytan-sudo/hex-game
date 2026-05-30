"""
Tactical battle map for the hex strategy game.

Opens when two armies meet on the strategic map.
Handles individual unit combat on a smaller battlefield.
"""

from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, List, Optional, Set, Tuple
import random

import pygame

from engine.hex_grid import HexCoord, HexGrid
from engine.tile import Tile
from engine.unit import Army, ArmyUnit, Hero, UnitStats, UnitType
from engine.combat import CombatSystem, CombatResult
from engine.camera import Camera
from engine.input_handler import CameraController
from engine.pathfinding import calculate_valid_moves, calculate_path_cost
from game.terrain import TerrainType, get_terrain_config
from game.map_generator import MapConfig, MapGenerator
from game.config import UI, INPUT, BATTLE, PLAYER_COLORS, AI, PROGRESSION
from game.ai import TacticalAI, TacticalAction, AIPersonality


# =============================================================================
# DATA CLASSES
# =============================================================================

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
    source_army_unit: Optional[ArmyUnit] = None
    source_hero: Optional[Hero] = None  # Set when this tactical unit is a deployed hero

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


# =============================================================================
# TACTICAL MAP GENERATION
# =============================================================================

def _create_tactical_map_config(
    terrain: TerrainType,
    width: int,
    height: int,
    seed: int
) -> MapConfig:
    """Create map configuration based on strategic terrain type."""
    base_config = {
        'width': width,
        'height': height,
        'seed': seed,
        'add_river': False,
        'add_lakes': False,
        'swamp_near_water': False,
        'add_cities': False,
        'add_roads': False,
        'add_bridges': False,
        'add_ruins': False,
    }

    terrain_configs = {
        TerrainType.PLAINS: {
            'forest_density': 0.15,
            'hills_density': 0.10,
            'mountain_density': 0.02,
            'mountain_cluster_size': 2,
        },
        TerrainType.HILLS: {
            'forest_density': 0.10,
            'hills_density': 0.45,
            'mountain_density': 0.10,
            'mountain_cluster_size': 2,
        },
        TerrainType.FOREST: {
            'forest_density': 0.55,
            'hills_density': 0.05,
            'mountain_density': 0.0,
            'swamp_near_water': True,
        },
        TerrainType.MOUNTAIN: {
            'forest_density': 0.10,
            'hills_density': 0.20,
            'mountain_density': 0.35,
            'mountain_cluster_size': 4,
        },
        TerrainType.SWAMP: {
            'forest_density': 0.15,
            'hills_density': 0.0,
            'mountain_density': 0.0,
            'add_lakes': True,
            'lake_count': 3,
            'swamp_near_water': True,
        },
        TerrainType.DESERT: {
            'forest_density': 0.0,
            'hills_density': 0.20,
            'mountain_density': 0.15,
            'mountain_cluster_size': 2,
        },
        # Note: ROAD is now an OverlayType, not a TerrainType.
        # Battles on roads use the base terrain config (e.g., PLAINS).
    }

    # Get terrain-specific config or use default
    specific_config = terrain_configs.get(terrain, {
        'forest_density': 0.20,
        'mountain_density': 0.05,
        'mountain_cluster_size': 2,
        'add_lakes': True,
        'lake_count': 1,
        'swamp_near_water': True,
    })

    return MapConfig(**{**base_config, **specific_config})


def _generate_tactical_map(
    width: int,
    height: int,
    strategic_terrain: TerrainType,
    seed: int
) -> Dict[Tuple[int, int], Tile]:
    """Generate a tactical battlefield based on the strategic terrain."""
    config = _create_tactical_map_config(strategic_terrain, width, height, seed)
    generator = MapGenerator(config)
    tiles = generator.generate()

    # Post-processing for specific terrain types
    if strategic_terrain == TerrainType.DESERT:
        tiles = _convert_plains_to_desert(tiles)
    # Note: ROAD overlay handling removed - roads are now overlays on base terrain

    return tiles


def _convert_plains_to_desert(tiles: Dict[Tuple[int, int], Tile]) -> Dict[Tuple[int, int], Tile]:
    """Convert plains tiles to desert for desert battles."""
    for tile in tiles.values():
        if tile.base_terrain == TerrainType.PLAINS:
            tile.base_terrain = TerrainType.DESERT
    return tiles


def _add_tactical_road(
    tiles: Dict[Tuple[int, int], Tile],
    width: int,
    height: int
) -> Dict[Tuple[int, int], Tile]:
    """Add a road crossing the tactical battlefield."""
    from game.terrain import OverlayType
    mid_r = height // 2
    for q in range(width):
        r = mid_r + (q % 3 - 1)
        if (q, r) in tiles and tiles[(q, r)].is_passable:
            tiles[(q, r)].overlay = OverlayType.ROAD
    return tiles


# =============================================================================
# TACTICAL BATTLE CLASS
# =============================================================================

class TacticalBattle:
    """
    Manages a tactical battle between two armies.

    Creates a small battlefield and places units from both armies.
    Combat is resolved turn by turn until one side is eliminated.
    """

    def __init__(
        self,
        attacker: Army,
        defender: Army,
        screen: pygame.Surface,
        strategic_terrain: TerrainType = TerrainType.PLAINS,
        seed: Optional[int] = None,
        ai_players: Optional[Dict[int, AIPersonality]] = None
    ):
        self.attacker = attacker
        self.defender = defender
        self.screen = screen
        self.strategic_terrain = strategic_terrain
        self.seed = seed or random.randint(0, 999999)

        self.screen_width = screen.get_width()
        self.screen_height = screen.get_height()

        # Generate tactical map
        self.tiles = _generate_tactical_map(
            BATTLE.map_width,
            BATTLE.map_height,
            strategic_terrain,
            self.seed
        )

        # Create tactical units from armies
        self.attacker_units: List[TacticalUnit] = []
        self.defender_units: List[TacticalUnit] = []
        # Stable references to deployed hero units (kept even after death,
        # when the unit is dropped from the lists above).
        self.attacker_hero_unit: Optional[TacticalUnit] = None
        self.defender_hero_unit: Optional[TacticalUnit] = None
        self._deploy_units()

        # Combat system
        self.combat_system = CombatSystem(random_factor=0.2)

        # Turn management
        self.current_player_id = attacker.player_id
        self.turn_number = 1

        # Selection state
        self.selected_unit: Optional[TacticalUnit] = None
        self.valid_moves: Set[Tuple[int, int]] = set()
        self.valid_attacks: Set[Tuple[int, int]] = set()

        # Battle state
        self.battle_over = False
        self.battle_report: Optional[BattleReport] = None
        self.combat_log: List[str] = []

        # AI controllers
        self.ai_players: Dict[int, TacticalAI] = {}
        if ai_players:
            for player_id, personality in ai_players.items():
                self.ai_players[player_id] = TacticalAI(player_id, personality)

        # AI turn state
        self._ai_action_timer: int = 0
        self._pending_ai_action: Optional[TacticalAction] = None
        # Hex sur lequel la caméra doit se recentrer pendant le tour IA
        # (l'unité en train d'agir), pour que le joueur suive l'action.
        self.ai_focus: Optional[HexCoord] = None

        # Camera
        self.camera = Camera(self.screen_width, self.screen_height)
        self.camera.zoom_index = 6  # 48px - comfortable for tactical view
        self._center_camera()

    def _center_camera(self):
        """Center camera on the tactical map."""
        center_x = BATTLE.map_width * self.camera.hex_size * 1.5
        center_y = BATTLE.map_height * self.camera.hex_size * 1.3
        self.camera.set_offset(
            self.screen_width / 2 - center_x / 2,
            self.screen_height / 2 - center_y / 2
        )

    def _deploy_units(self):
        """Deploy units from both armies onto the battlefield."""
        left_tiles = [
            (q, r) for (q, r), tile in self.tiles.items()
            if q < BATTLE.map_width // 3 and tile.is_passable
        ]
        right_tiles = [
            (q, r) for (q, r), tile in self.tiles.items()
            if q > 2 * BATTLE.map_width // 3 and tile.is_passable
        ]

        random.seed(self.seed)
        random.shuffle(left_tiles)
        random.shuffle(right_tiles)

        self._deploy_army_units(self.attacker, left_tiles, self.attacker_units)
        self._deploy_army_units(self.defender, right_tiles, self.defender_units)

        self.attacker_hero_unit = next(
            (u for u in self.attacker_units if u.source_hero is not None), None
        )
        self.defender_hero_unit = next(
            (u for u in self.defender_units if u.source_hero is not None), None
        )

    def _deploy_army_units(
        self,
        army: Army,
        positions: List[Tuple[int, int]],
        target_list: List[TacticalUnit]
    ):
        """Deploy units from an army to given positions."""
        deploy_idx = 0
        for army_unit in army.units:
            for i in range(army_unit.count):
                if deploy_idx >= len(positions):
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
                    player_id=army.player_id,
                    position=HexCoord(*positions[deploy_idx]),
                    movement_remaining=army_unit.base_stats.movement,
                    source_army_unit=army_unit,
                )
                self.tiles[positions[deploy_idx]].unit = tactical_unit
                target_list.append(tactical_unit)
                deploy_idx += 1

        # Deploy the commanding hero as its own combatant, if any.
        if army.hero is not None and deploy_idx < len(positions):
            hero = army.hero
            hero_unit = TacticalUnit(
                name=hero.name,
                unit_type=UnitType.HERO,
                stats=UnitStats(
                    max_hp=hero.stats.max_hp,
                    current_hp=hero.stats.current_hp,
                    attack=hero.stats.attack,
                    defense=hero.stats.defense,
                    movement=hero.stats.movement,
                    range=hero.stats.range,
                ),
                player_id=army.player_id,
                position=HexCoord(*positions[deploy_idx]),
                movement_remaining=hero.stats.movement,
                source_hero=hero,
            )
            self.tiles[positions[deploy_idx]].unit = hero_unit
            target_list.append(hero_unit)
            deploy_idx += 1

    def get_units_for_player(self, player_id: int) -> List[TacticalUnit]:
        """Get all living units for a player."""
        if player_id == self.attacker.player_id:
            return [u for u in self.attacker_units if u.is_alive]
        return [u for u in self.defender_units if u.is_alive]

    def get_enemy_units(self, player_id: int) -> List[TacticalUnit]:
        """Get enemy units."""
        if player_id == self.attacker.player_id:
            return [u for u in self.defender_units if u.is_alive]
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

        if unit.movement_remaining > 0:
            self.valid_moves = self._calculate_valid_moves(unit)

        if not unit.has_acted:
            self.valid_attacks = self._calculate_valid_attacks(unit)

    def _calculate_valid_moves(self, unit: TacticalUnit) -> Set[Tuple[int, int]]:
        """Calculate valid move destinations using pathfinding module."""
        start = unit.position.to_tuple()

        def can_move_to(tile: Tile, pos: Tuple[int, int]) -> bool:
            return tile.unit is None

        return calculate_valid_moves(
            start,
            unit.movement_remaining,
            self.tiles,
            can_move_to
        )

    def _calculate_valid_attacks(self, unit: TacticalUnit) -> Set[Tuple[int, int]]:
        """Calculate valid attack targets."""
        valid = set()
        position = unit.position
        attack_range = unit.stats.range

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

        source_tuple = self.selected_unit.position.to_tuple()
        path_cost = calculate_path_cost(source_tuple, target_tuple, self.tiles)

        if path_cost > self.selected_unit.movement_remaining:
            return False

        # Execute move
        self.tiles[source_tuple].unit = None
        self.tiles[target_tuple].unit = self.selected_unit
        self.selected_unit.position = target
        self.selected_unit.movement_remaining -= path_cost

        self.select_unit(self.selected_unit)
        return True

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
        distance = attacker.position.distance_to(defender.position)

        # Resolve combat
        result = self.combat_system.resolve_combat(
            attacker, defender,
            attacker_tile, target_tile,
            distance=distance
        )

        # Une attaque consomme l'action de l'unité pour ce tour.
        attacker.has_acted = True

        # Log combat
        self._log_combat(attacker, defender, result)

        # Handle deaths
        self._handle_deaths(attacker, defender, attacker_tile, target_tile)

        # Check for battle end
        self._check_battle_end()

        if self.selected_unit:
            self.select_unit(self.selected_unit)

        return result

    def _log_combat(self, attacker: TacticalUnit, defender: TacticalUnit, result: CombatResult):
        """Log combat result."""
        log_msg = f"{attacker.name} attacks {defender.name}: "
        if result.defender_survived:
            log_msg += f"-{result.defender_damage} HP"
            if result.attacker_damage > 0:
                log_msg += f" (counter: -{result.attacker_damage})"
        else:
            log_msg += "KILLED!"
        self.combat_log.append(log_msg)

    def _handle_deaths(
        self,
        attacker: TacticalUnit,
        defender: TacticalUnit,
        attacker_tile: Tile,
        target_tile: Tile
    ):
        """Handle unit deaths after combat."""
        if not defender.is_alive:
            target_tile.unit = None
            self._remove_unit(defender)

        if not attacker.is_alive:
            if attacker_tile:
                attacker_tile.unit = None
            self._remove_unit(attacker)
            self.selected_unit = None

    def _remove_unit(self, unit: TacticalUnit):
        """Remove a unit from its list."""
        if unit in self.defender_units:
            self.defender_units.remove(unit)
        elif unit in self.attacker_units:
            self.attacker_units.remove(unit)

    def end_turn(self):
        """End current player's turn."""
        if self.current_player_id == self.attacker.player_id:
            self.current_player_id = self.defender.player_id
        else:
            self.current_player_id = self.attacker.player_id
            self.turn_number += 1

        for unit in self.get_units_for_player(self.current_player_id):
            unit.start_turn()

        self.selected_unit = None
        self.valid_moves.clear()
        self.valid_attacks.clear()

        if self.turn_number > BATTLE.max_turns:
            self._end_battle(is_draw=True)

    def is_ai_turn(self) -> bool:
        """Check if it's an AI player's turn."""
        return self.current_player_id in self.ai_players

    def current_player_has_actions(self) -> bool:
        """
        Indique si le joueur courant peut encore faire quelque chose ce tour-ci.

        Vrai si au moins une de ses unités vivantes peut se déplacer (case
        atteignable) ou attaquer (cible à portée). Sert à enclencher
        automatiquement la fin de tour quand il n'y a plus rien à faire.
        """
        for unit in self.get_units_for_player(self.current_player_id):
            if not unit.is_alive:
                continue
            if unit.movement_remaining > 0 and self._calculate_valid_moves(unit):
                return True
            if not unit.has_acted and self._calculate_valid_attacks(unit):
                return True
        return False

    def update_ai_turn(self, dt_ms: int = 0) -> bool:
        """
        Update AI turn logic. Returns True if AI is still acting.

        Call this every frame during AI turns. The AI will execute actions
        avec des délais pour la lisibilité. La cadence est pilotée par ``dt_ms``
        (temps écoulé depuis la frame précédente), pas par l'horloge murale
        (AUDIT §2.3 / reco 11) : ``_ai_action_timer`` est un compte à rebours.
        """
        if not self.is_ai_turn() or self.battle_over:
            return False

        # Wait for action delay (compte à rebours alimenté par dt_ms)
        self._ai_action_timer -= dt_ms
        if self._ai_action_timer > 0:
            return True

        ai = self.ai_players[self.current_player_id]

        # Execute pending action if any
        if self._pending_ai_action:
            self._execute_ai_action(self._pending_ai_action)
            self._pending_ai_action = None
            self._ai_action_timer = AI.action_delay_ms
            return True

        # Get next action from AI
        action = ai.play_turn(self)

        if action:
            self._pending_ai_action = action
            # Recentre la caméra sur l'unité qui va agir : le joueur voit ainsi
            # ce que fait l'ennemi pendant le tour adverse.
            if action.unit and action.unit.position:
                self.ai_focus = action.unit.position
            self._ai_action_timer = AI.action_delay_ms // 2
            return True
        else:
            # AI turn complete, end turn
            self.end_turn()
            self._ai_action_timer = AI.turn_start_delay_ms
            return True

    def _execute_ai_action(self, action: TacticalAction):
        """Execute a tactical AI action."""
        unit = action.unit

        if action.action_type == "attack":
            # Direct attack
            self.select_unit(unit)
            if action.attack_target and action.attack_target.position:
                self.try_attack(action.attack_target.position)

        elif action.action_type == "move":
            # Just move
            self.select_unit(unit)
            if action.target_pos:
                target_coord = HexCoord(*action.target_pos)
                self.try_move(target_coord)

        elif action.action_type == "move_and_attack":
            # Move first
            self.select_unit(unit)
            if action.target_pos:
                target_coord = HexCoord(*action.target_pos)
                self.try_move(target_coord)

            # Then attack
            if action.attack_target and action.attack_target.position:
                self.select_unit(unit)  # Re-select to update valid attacks
                self.try_attack(action.attack_target.position)

        # Une activation par unité et par tour : on marque l'unité comme ayant
        # agi même pour un simple déplacement, sinon elle est re-sélectionnée en
        # boucle et le tour IA traîne en longueur.
        if unit.is_alive:
            unit.has_acted = True

        # Clear selection after action
        self.select_unit(None)

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

        attacker_survivors = self._count_survivors(self.attacker_units, self.attacker)
        defender_survivors = self._count_survivors(self.defender_units, self.defender)

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

    def _count_survivors(
        self,
        units: List[TacticalUnit],
        army: Army
    ) -> Dict[str, List[int]]:
        """Count surviving units by type."""
        survivors = {}
        for unit in units:
            if unit.is_alive and unit.source_army_unit:
                name = unit.source_army_unit.name
                if name not in survivors:
                    survivors[name] = [0, unit.source_army_unit.count]
                survivors[name][0] += 1
        return survivors

    def update_armies_after_battle(self):
        """Update the original armies with battle results."""
        self._update_army(self.attacker, self.attacker_units)
        self._update_army(self.defender, self.defender_units)
        self._resolve_hero_outcomes()

    def _resolve_hero_outcomes(self):
        """
        Propagate each commanding hero's fate back to the strategic layer.

        A hero that fell in battle is detached from its army and removed from
        play; a survivor gains experience proportional to the enemy units it
        helped destroy.
        """
        report = self.battle_report
        # Units each side lost are the units the *other* side destroyed.
        attacker_kills = report.defender_losses if report else 0
        defender_kills = report.attacker_losses if report else 0

        self._resolve_hero(self.attacker, self.attacker_hero_unit, attacker_kills)
        self._resolve_hero(self.defender, self.defender_hero_unit, defender_kills)

    def _resolve_hero(
        self,
        army: Army,
        hero_unit: Optional[TacticalUnit],
        enemy_kills: int
    ):
        """Apply a single hero's battle outcome to the original army/hero."""
        hero = army.hero
        if hero is None or hero_unit is None:
            return

        if not hero_unit.is_alive:
            # Hero killed: drop from the army and pull it off the map.
            hero.stats.current_hp = 0
            army.detach_hero()
            hero.position = None
            return

        # Survivor: award XP. Stats are not persisted between battles (units
        # redeploy at full strength), so we only level the hero up here.
        if enemy_kills > 0:
            hero.gain_experience(enemy_kills * PROGRESSION.xp_per_kill)

    def _update_army(self, army: Army, tactical_units: List[TacticalUnit]):
        """Update an army's unit counts based on survivors."""
        for army_unit in army.units[:]:
            survivors = sum(
                1 for u in tactical_units
                if u.is_alive and u.source_army_unit == army_unit
            )
            if survivors == 0:
                army.units.remove(army_unit)
            else:
                army_unit.count = survivors

        army._recalculate_stats()


# =============================================================================
# TACTICAL RENDERER
# =============================================================================

class TacticalRenderer:
    """Handles all rendering for tactical battles."""

    def __init__(self, screen: pygame.Surface, font: pygame.font.Font, title_font: pygame.font.Font):
        self.screen = screen
        self.font = font
        self.title_font = title_font
        self.screen_width = screen.get_width()
        self.screen_height = screen.get_height()

    def render_frame(
        self,
        battle: TacticalBattle,
        hex_grid: HexGrid,
        player_colors: Dict[int, Tuple[int, int, int]],
        show_report: bool
    ):
        """Render a complete frame."""
        self.screen.fill(UI.screen_bg_color)

        self._render_tiles(battle, hex_grid)
        self._render_units(battle, hex_grid, player_colors)
        self._render_top_panel(battle, player_colors)
        self._render_bottom_panel(battle)
        self._render_combat_log(battle)

        if show_report and battle.battle_report:
            self._render_battle_report(battle.battle_report)

    def _render_tiles(self, battle: TacticalBattle, hex_grid: HexGrid):
        """Render battlefield tiles."""
        for coord_tuple, tile in battle.tiles.items():
            coord = HexCoord(*coord_tuple)
            center = hex_grid.hex_to_pixel(coord, battle.camera.offset)

            # Culling
            if not self._is_on_screen(center, battle.camera.hex_size):
                continue

            vertices = hex_grid.get_hex_corners(coord, battle.camera.offset)
            color = self._get_tile_color(tile, coord_tuple, battle)

            pygame.draw.polygon(self.screen, color, vertices)
            pygame.draw.polygon(self.screen, (50, 50, 60), vertices, 1)

    def _get_tile_color(
        self,
        tile: Tile,
        coord_tuple: Tuple[int, int],
        battle: TacticalBattle
    ) -> Tuple[int, int, int]:
        """Get tile color with highlights."""
        color = tile.display_color

        if coord_tuple in battle.valid_moves:
            color = tuple(min(255, c + 40) for c in color)
        elif coord_tuple in battle.valid_attacks:
            color = UI.attack_highlight_color

        return color

    def _render_units(
        self,
        battle: TacticalBattle,
        hex_grid: HexGrid,
        player_colors: Dict[int, Tuple[int, int, int]]
    ):
        """Render all units on the battlefield."""
        all_units = battle.attacker_units + battle.defender_units
        for unit in all_units:
            if not unit.is_alive or unit.position is None:
                continue

            center = hex_grid.hex_to_pixel(unit.position, battle.camera.offset)
            x, y = int(center[0]), int(center[1])
            color = player_colors.get(unit.player_id, (200, 200, 200))
            radius = int(battle.camera.hex_size * 0.4)

            # Unit circle
            pygame.draw.circle(self.screen, color, (x, y), radius)
            pygame.draw.circle(self.screen, (255, 255, 255), (x, y), radius, 2)

            # Selected highlight
            if unit == battle.selected_unit:
                pygame.draw.circle(self.screen, UI.selection_color, (x, y), radius + 4, 3)

            # Unit type letter
            letter = unit.name[0].upper()
            text = self.font.render(letter, True, UI.text_color)
            text_rect = text.get_rect(center=(x, y))
            self.screen.blit(text, text_rect)

            # HP bar
            self._render_hp_bar(x, y, radius, unit, battle.camera.hex_size)

    def _render_hp_bar(self, x: int, y: int, radius: int, unit: TacticalUnit, hex_size: int):
        """Render HP bar under a unit."""
        hp_width = int(hex_size * 0.8)
        hp_height = 4
        hp_x = x - hp_width // 2
        hp_y = y + radius + 5

        pygame.draw.rect(self.screen, (60, 60, 60), (hp_x, hp_y, hp_width, hp_height))

        hp_pct = unit.stats.current_hp / unit.stats.max_hp
        if hp_pct > 0.5:
            hp_color = (100, 200, 100)
        elif hp_pct > 0.25:
            hp_color = (200, 200, 100)
        else:
            hp_color = (200, 100, 100)

        pygame.draw.rect(self.screen, hp_color, (hp_x, hp_y, int(hp_width * hp_pct), hp_height))

    def _render_top_panel(
        self,
        battle: TacticalBattle,
        player_colors: Dict[int, Tuple[int, int, int]]
    ):
        """Render top UI panel."""
        panel_height = 60
        pygame.draw.rect(self.screen, UI.panel_bg_color, (0, 0, self.screen_width, panel_height))

        # Title
        title = self.title_font.render("TACTICAL BATTLE", True, UI.text_color)
        self.screen.blit(title, (self.screen_width // 2 - title.get_width() // 2, 5))

        # Turn info
        current_name = (battle.attacker.name if battle.current_player_id == battle.attacker.player_id
                       else battle.defender.name)
        current_color = player_colors.get(battle.current_player_id, (200, 200, 200))
        turn_text = self.font.render(f"Turn {battle.turn_number} - {current_name}", True, current_color)
        self.screen.blit(turn_text, (10, 35))

        # Controls hint
        hint = self.font.render("Space: End Turn | ESC: Retreat", True, UI.hint_color)
        self.screen.blit(hint, (self.screen_width - 250, 35))

        # Unit counts
        attacker_count = len([u for u in battle.attacker_units if u.is_alive])
        defender_count = len([u for u in battle.defender_units if u.is_alive])

        att_color = player_colors.get(battle.attacker.player_id, (100, 100, 255))
        def_color = player_colors.get(battle.defender.player_id, (255, 100, 100))

        att_text = self.font.render(f"{battle.attacker.name}: {attacker_count} units", True, att_color)
        def_text = self.font.render(f"{battle.defender.name}: {defender_count} units", True, def_color)
        self.screen.blit(att_text, (10, 8))
        self.screen.blit(def_text, (250, 8))

    def _render_bottom_panel(self, battle: TacticalBattle):
        """Render bottom UI panel with selected unit info."""
        panel_height = 50
        pygame.draw.rect(
            self.screen,
            UI.panel_bg_color,
            (0, self.screen_height - panel_height, self.screen_width, panel_height)
        )

        if battle.selected_unit:
            unit = battle.selected_unit
            info = (f"{unit.name} | HP: {unit.stats.current_hp}/{unit.stats.max_hp} | "
                   f"ATK: {unit.stats.attack} | DEF: {unit.stats.defense} | "
                   f"Move: {unit.movement_remaining}/{unit.stats.movement} | Range: {unit.stats.range}")
            info_text = self.font.render(info, True, (255, 200, 100))
            self.screen.blit(info_text, (10, self.screen_height - 35))

    def _render_combat_log(self, battle: TacticalBattle):
        """Render last 3 combat log entries."""
        if battle.combat_log:
            for i, log in enumerate(battle.combat_log[-3:]):
                log_text = self.font.render(log, True, (180, 180, 180))
                self.screen.blit(log_text, (10, 70 + i * 20))

    def _render_battle_report(self, report: BattleReport):
        """Render battle report overlay."""
        # Semi-transparent overlay
        overlay = pygame.Surface((self.screen_width, self.screen_height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        self.screen.blit(overlay, (0, 0))

        # Report box
        box_w, box_h = 500, 400
        box_x = self.screen_width // 2 - box_w // 2
        box_y = self.screen_height // 2 - box_h // 2

        pygame.draw.rect(self.screen, (50, 50, 60), (box_x, box_y, box_w, box_h), border_radius=10)
        pygame.draw.rect(self.screen, (100, 100, 120), (box_x, box_y, box_w, box_h), 3, border_radius=10)

        # Title
        result_text = "VICTORY!" if report.attacker_won else "DEFEAT!"
        result_color = (100, 255, 100) if report.attacker_won else (255, 100, 100)
        title = self.title_font.render(f"BATTLE REPORT - {result_text}", True, result_color)
        self.screen.blit(title, (self.screen_width // 2 - title.get_width() // 2, box_y + 20))

        y = box_y + 70

        # Battle info
        info = self.font.render(f"{report.attacker_name} vs {report.defender_name}", True, (200, 200, 200))
        self.screen.blit(info, (self.screen_width // 2 - info.get_width() // 2, y))
        y += 30

        rounds = self.font.render(f"Battle lasted {report.rounds} rounds", True, (180, 180, 180))
        self.screen.blit(rounds, (self.screen_width // 2 - rounds.get_width() // 2, y))
        y += 40

        # Survivors sections
        y = self._render_survivors_section(
            box_x, y,
            f"{report.attacker_name} survivors:",
            report.attacker_survivors,
            (100, 100, 255),
            (150, 150, 200)
        )
        y += 20
        self._render_survivors_section(
            box_x, y,
            f"{report.defender_name} survivors:",
            report.defender_survivors,
            (255, 100, 100),
            (200, 150, 150)
        )

        # Continue prompt
        prompt = self.font.render("Press any key to continue...", True, (200, 200, 200))
        self.screen.blit(prompt, (self.screen_width // 2 - prompt.get_width() // 2, box_y + box_h - 40))

    def _render_survivors_section(
        self,
        box_x: int,
        y: int,
        title: str,
        survivors: List[Tuple[str, int, int]],
        title_color: Tuple[int, int, int],
        text_color: Tuple[int, int, int]
    ) -> int:
        """Render a survivors section and return new y position."""
        title_text = self.font.render(title, True, title_color)
        self.screen.blit(title_text, (box_x + 30, y))
        y += 25

        if survivors:
            for name, remaining, original in survivors:
                surv = self.font.render(f"  {name}: {remaining}/{original}", True, text_color)
                self.screen.blit(surv, (box_x + 30, y))
                y += 20
        else:
            none = self.font.render("  All units lost!", True, (255, 100, 100))
            self.screen.blit(none, (box_x + 30, y))
            y += 20

        return y

    def _is_on_screen(self, center: Tuple[float, float], hex_size: int) -> bool:
        """Check if a hex is visible on screen."""
        margin = hex_size * 2
        return (-margin < center[0] < self.screen_width + margin and
                -margin < center[1] < self.screen_height + margin)


# =============================================================================
# MAIN GAME LOOP
# =============================================================================

def run_tactical_battle(
    screen: pygame.Surface,
    attacker: Army,
    defender: Army,
    player_colors: Dict[int, Tuple[int, int, int]],
    strategic_terrain: TerrainType = TerrainType.PLAINS,
    ai_players: Optional[Dict[int, AIPersonality]] = None
) -> BattleReport:
    """
    Run a tactical battle between two armies.

    Args:
        screen: Pygame display surface
        attacker: The attacking army
        defender: The defending army
        player_colors: Color mapping for player IDs
        strategic_terrain: The terrain type from the strategic map
        ai_players: Optional dict mapping player_id to AIPersonality for AI-controlled players

    Returns the battle report when complete.
    """
    battle = TacticalBattle(attacker, defender, screen, strategic_terrain, ai_players=ai_players)
    camera_controller = CameraController(
        battle.camera, INPUT.drag_threshold, INPUT.scroll_speed, INPUT.fast_scroll_multiplier
    )

    font = pygame.font.Font(None, 24)
    title_font = pygame.font.Font(None, 36)
    renderer = TacticalRenderer(screen, font, title_font)
    clock = pygame.time.Clock()

    running = True
    show_report = False
    dt_ms = 0  # temps écoulé sur la frame précédente (ms)

    while running:
        mouse_pos = pygame.mouse.get_pos()
        is_ai_turn = battle.is_ai_turn()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if not battle.battle_over:
                    battle._end_battle(is_draw=True)
                running = False

            elif event.type == pygame.KEYDOWN:
                if show_report:
                    running = False
                elif event.key == pygame.K_ESCAPE:
                    battle._end_battle(attacker_won=False)
                elif event.key == pygame.K_SPACE and not is_ai_turn:
                    battle.end_turn()
                else:
                    camera_controller.handle_event(event, mouse_pos)

            elif event.type == pygame.MOUSEBUTTONDOWN and not show_report and not is_ai_turn:
                if event.button == 1:
                    _handle_left_click(battle, camera_controller.hex_grid, mouse_pos)
                else:
                    camera_controller.handle_event(event, mouse_pos)

            elif event.type == pygame.MOUSEBUTTONUP:
                if not camera_controller.handle_event(event, mouse_pos):
                    # Right-click was not a drag - deselect
                    if event.button == 3 and not is_ai_turn:
                        battle.select_unit(None)

            elif event.type == pygame.MOUSEMOTION:
                camera_controller.handle_event(event, mouse_pos)

            elif event.type == pygame.MOUSEWHEEL:
                camera_controller.handle_event(event, mouse_pos)

        # Update AI turn
        if is_ai_turn and not battle.battle_over:
            battle.update_ai_turn(dt_ms)
            # Suit l'unité IA en cours d'action (glissement fluide de la caméra).
            if battle.ai_focus is not None:
                battle.camera.center_on(
                    battle.ai_focus, camera_controller.hex_grid, smoothing=0.2
                )
        elif not battle.battle_over and not show_report:
            # Tour humain : si plus aucune action possible, on termine le tour
            # automatiquement (inutile d'attendre un appui sur Espace).
            if not battle.current_player_has_actions():
                battle.end_turn()

        camera_controller.handle_continuous_input()

        if battle.battle_over and not show_report:
            show_report = True

        renderer.render_frame(battle, camera_controller.hex_grid, player_colors, show_report)
        pygame.display.flip()
        dt_ms = clock.tick(60)

    battle.update_armies_after_battle()
    return battle.battle_report


def _handle_left_click(
    battle: TacticalBattle,
    hex_grid: HexGrid,
    mouse_pos: Tuple[int, int]
):
    """Handle left click on tactical map."""
    clicked_hex = hex_grid.pixel_to_hex(mouse_pos[0], mouse_pos[1], battle.camera.offset)
    clicked_tuple = clicked_hex.to_tuple()

    if clicked_tuple not in battle.tiles:
        return

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
