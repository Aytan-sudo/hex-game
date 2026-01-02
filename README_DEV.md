# Guide de Développement - Hex Strategy Game

Ce document contient toutes les informations nécessaires pour modifier et améliorer le projet sans avoir à lire l'intégralité du code source (~6500 lignes).

## Architecture Globale

```
hex-game/
├── engine/          # Moteur générique réutilisable (2400 lignes)
│   ├── hex_grid.py     # Coordonnées hexagonales, conversions pixel/hex
│   ├── tile.py         # Classe Tile (terrain + overlay + unité)
│   ├── unit.py         # Unit, Army, Hero, UnitStats
│   ├── camera.py       # Zoom multi-niveaux et offset
│   ├── combat.py       # Système de combat (dégâts, contre-attaque)
│   ├── pathfinding.py  # BFS (valid_moves) et Dijkstra (find_path)
│   ├── input_handler.py # CameraController (drag, zoom, scroll)
│   ├── renderer.py     # Rendu Pygame générique
│   └── game_state.py   # Base class GameState (non utilisé actuellement)
│
├── game/            # Implémentation concrète du jeu (4100 lignes)
│   ├── config.py       # Toutes les constantes de configuration
│   ├── terrain.py      # TerrainType, OverlayType, configs
│   ├── units.py        # Factory functions pour les unités
│   ├── heroes.py       # Factory functions pour les héros
│   ├── cities.py       # Classe City (placeholder)
│   ├── map_generator.py # Génération procédurale
│   ├── strategic_map.py # Carte stratégique + game loop
│   ├── tactical_map.py  # Batailles tactiques + game loop
│   └── main.py         # Point d'entrée, menu, création unités
```

## Flux d'Exécution Principal

```
main.py
  └── MainMenu.run()
        └── run_strategic_game()
              ├── StrategicGameState (gère tours, sélection, animations)
              ├── StrategicRenderer (rendu carte stratégique)
              └── [Si bataille] → run_tactical_battle()
                    ├── TacticalBattle (gère combat tour par tour)
                    └── TacticalRenderer (rendu carte tactique)
```

---

## Classes Principales

### Système de Terrain (game/terrain.py)

```python
# Terrains de base
class TerrainType(Enum):
    PLAINS, HILLS, FOREST, MOUNTAIN, WATER, DESERT, SWAMP

# Constructions (overlays sur terrain de base)
class OverlayType(Enum):
    ROAD, CITY, BRIDGE, RUINS

# Configs stockées dans TERRAIN_CONFIGS et OVERLAY_CONFIGS
# Fonctions utilitaires : calculate_combined_movement_cost(), calculate_combined_defense_bonus()
```

### Tile (engine/tile.py)

```python
@dataclass
class Tile:
    position: HexCoord
    base_terrain: TerrainType
    overlay: Optional[OverlayType] = None
    unit: Optional[Unit] = None

    # Propriétés calculées (combinent base + overlay)
    display_color: Tuple[int, int, int]
    display_name: str
    defense_bonus: int
    def get_movement_cost() -> int
    def is_passable -> bool
```

### Unités (engine/unit.py)

```python
@dataclass
class UnitStats:
    hp, max_hp, attack, defense, movement, range

class Unit:  # Base class
    name, unit_type, stats, player_id, position
    movement_remaining, has_acted

class ArmyUnit(Unit):  # Unité dans une armée
    count  # Nombre d'unités de ce type

class Army(Unit):  # Armée sur carte stratégique
    units: List[ArmyUnit]
    hero: Optional[Hero]

class Hero(Unit):  # Héros (peut être indépendant ou dans armée)
    hero_class, level, xp
    is_independent, army  # Si dans une armée
```

### Coordonnées Hexagonales (engine/hex_grid.py)

```python
@dataclass
class HexCoord:
    q, r  # Coordonnées axiales
    def neighbors() -> List[HexCoord]
    def distance_to(other) -> int
    def to_tuple() -> Tuple[int, int]

class HexGrid:
    hex_size: float
    def hex_to_pixel(coord, offset) -> Tuple[float, float]
    def pixel_to_hex(x, y, offset) -> HexCoord
    def get_hex_corners(coord, offset) -> List[Tuple[float, float]]
```

---

## Configuration (game/config.py)

Toutes les constantes sont centralisées ici :

```python
INPUT = InputSettings(drag_threshold=5, scroll_speed=10, fast_scroll_multiplier=5)
UI = UISettings(panel_bg_color, text_color, selection_color, ...)
ANIMATION = AnimationSettings(move_step_delay_ms=80, enabled=True)
BATTLE = BattleSettings(map_width=20, map_height=20, max_turns=20)
PROGRESSION = ProgressionSettings(xp_per_level_multiplier=100, ...)
PLAYER_COLORS = PlayerColors(player1=(100,100,255), player2=(255,100,100))
```

---

## Guide par Fonctionnalité

### Ajouter un nouveau terrain de base

1. **Fichier** : `game/terrain.py`
2. Ajouter à `TerrainType` enum
3. Ajouter config dans `TERRAIN_CONFIGS`
4. Si génération spéciale : modifier `game/map_generator.py`
5. Si carte tactique spéciale : modifier `_create_tactical_map_config()` dans `game/tactical_map.py`

### Ajouter une nouvelle construction (overlay)

1. **Fichier** : `game/terrain.py`
2. Ajouter à `OverlayType` enum
3. Ajouter config dans `OVERLAY_CONFIGS`
4. Modifier génération dans `game/map_generator.py` (méthode appropriée)

### Ajouter un nouveau type d'unité

1. **Fichiers** : `engine/unit.py` (si nouveau type), `game/units.py` (factory function)
2. Ajouter le type dans `UnitType` enum si nécessaire
3. Créer factory function `create_xxx()` dans `game/units.py`
4. L'utiliser dans `game/main.py` pour les armées initiales

### Ajouter une nouvelle classe de héros

1. **Fichier** : `game/heroes.py`
2. Ajouter à `HERO_CLASSES` dict
3. Modifier `create_hero()` si stats spéciales

### Modifier le système de combat

1. **Fichier** : `engine/combat.py`
2. Classe `CombatSystem` - méthodes `resolve_combat()` et `_calculate_attack_damage()`
3. Pour bonus terrain : modifier `game/terrain.py` (defense_bonus)

### Modifier la génération de carte

1. **Fichier** : `game/map_generator.py`
2. Classe `MapGenerator` - méthodes `_generate_*` pour chaque layer
3. Config via `MapConfig` dataclass
4. Ordre des layers : base terrain → mountains → water → swamps → cities → roads → ruins

### Ajouter une fonctionnalité UI

1. **Carte stratégique** : `game/strategic_map.py` - classe `StrategicRenderer`
2. **Carte tactique** : `game/tactical_map.py` - classe `TacticalRenderer`
3. **Menu** : `game/main.py` - classe `MainMenu`
4. **Constantes couleurs/tailles** : `game/config.py`

### Modifier le pathfinding

1. **Fichier** : `engine/pathfinding.py`
2. `calculate_valid_moves()` - BFS pour cases accessibles
3. `find_path()` - Dijkstra pour chemin optimal
4. `calculate_path_cost()` - coût d'un chemin donné

### Ajouter une animation

1. **Fichier** : `game/strategic_map.py`
2. Dataclass `MoveAnimation` pour tracking
3. Méthode `update_animation()` dans `StrategicGameState`
4. Config vitesse : `ANIMATION.move_step_delay_ms` dans `game/config.py`

---

## Dépendances entre Fichiers

```
game/main.py
  ├── game/config.py
  ├── game/strategic_map.py
  │     ├── engine/pathfinding.py
  │     ├── game/tactical_map.py
  │     │     ├── engine/combat.py
  │     │     ├── game/map_generator.py
  │     │     └── game/terrain.py
  │     └── game/terrain.py
  ├── game/map_generator.py
  │     └── game/terrain.py
  ├── game/units.py
  │     └── engine/unit.py
  └── game/heroes.py
        └── engine/unit.py

engine/tile.py
  ├── engine/hex_grid.py
  └── game/terrain.py (import circulaire évité via lazy import)
```

---

## Patterns de Code Utilisés

### Dataclasses pour les données

```python
@dataclass
class MoveAnimation:
    unit: StrategicUnit
    path: List[Tuple[int, int]]
    current_step: int = 0
```

### Enums pour les types

```python
class TerrainType(Enum):
    PLAINS = "plains"
```

### Factory functions pour création d'objets

```python
def create_lancer(count: int = 1) -> ArmyUnit:
    return ArmyUnit(name="Lancer", unit_type=UnitType.INFANTRY, ...)
```

### Game loop pattern

```python
while True:
    for event in pygame.event.get():
        # Handle events
    # Update state
    # Render
    pygame.display.flip()
    clock.tick(60)
```

---

## Tests Rapides

```bash
# Activer l'environnement
source .venv/bin/activate

# Test import terrain
python -c "from game.terrain import TerrainType, OverlayType; print('OK')"

# Test génération de carte
python -c "from game.map_generator import generate_map; t = generate_map(20,20); print(len(t), 'tiles')"

# Test complet création armées
python -c "
from game.map_generator import generate_map
from game.main import create_test_units, create_test_heroes
tiles = generate_map(30, 30, seed=42)
armies = create_test_units(tiles, 2, 2)
heroes = create_test_heroes(tiles, armies)
print(f'{len(tiles)} tiles, {len(armies)} armies, {len(heroes)} heroes')
"
```

---

## Fichiers à Modifier par Type de Changement

| Changement | Fichiers principaux | Fichiers secondaires |
|------------|---------------------|---------------------|
| Nouveau terrain | `terrain.py` | `map_generator.py`, `tactical_map.py` |
| Nouvelle unité | `units.py` | `main.py` |
| Nouveau héros | `heroes.py` | `main.py` |
| UI stratégique | `strategic_map.py` | `config.py` |
| UI tactique | `tactical_map.py` | `config.py` |
| Combat | `combat.py` | `tactical_map.py` |
| Mouvement | `pathfinding.py` | `strategic_map.py` |
| Génération carte | `map_generator.py` | - |
| Animation | `strategic_map.py` | `config.py` |
| Constantes | `config.py` | - |

---

## Points d'Attention

1. **Imports circulaires** : `tile.py` importe `terrain.py` via lazy imports dans les méthodes
2. **Coordonnées** : Toujours utiliser `HexCoord` pour les calculs, `tuple (q,r)` pour les clés de dict
3. **Unités sur tiles** : `tile.unit` peut être `Army` ou `None`, les `Hero` indépendants ne sont PAS sur les tiles
4. **Animation** : Bloquer les inputs utilisateur pendant `game_state.current_animation is not None`
5. **Overlays** : Toujours accéder aux stats terrain via `tile.get_movement_cost()` et `tile.defense_bonus`, pas directement via le terrain

---

## Conventions de Nommage

- Classes : `PascalCase` (ex: `StrategicGameState`)
- Fonctions : `snake_case` (ex: `calculate_valid_moves`)
- Fonctions privées : `_snake_case` (ex: `_generate_base_terrain`)
- Constantes : `UPPER_SNAKE_CASE` (ex: `TERRAIN_CONFIGS`)
- Enums : `PascalCase` pour l'enum, `UPPER_SNAKE_CASE` pour les valeurs
