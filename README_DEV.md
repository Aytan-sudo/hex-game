# Guide de Développement - Hex Strategy Game

Guide pour modifier le projet (~7000 lignes de code).

## Architecture

```
hex-game/
├── engine/             # Moteur générique réutilisable
│   ├── hex_grid.py        # HexCoord, HexGrid (conversions pixel/hex)
│   ├── tile.py            # Tile (terrain + overlay + unité)
│   ├── unit.py            # Unit, ArmyUnit, Army, Hero
│   ├── camera.py          # Zoom multi-niveaux
│   ├── combat.py          # CombatSystem (dégâts, contre-attaque)
│   ├── pathfinding.py     # BFS (valid_moves), Dijkstra (find_path)
│   ├── input_handler.py   # CameraController (drag, zoom)
│   └── renderer.py        # Rendu Pygame de base
│
├── game/               # Implémentation du jeu
│   ├── config.py          # Constantes (INPUT, UI, ANIMATION, BATTLE, AI)
│   ├── terrain.py         # TerrainType, OverlayType + configs
│   ├── units.py           # create_lancer(), create_archer()...
│   ├── heroes.py          # create_hero(), HERO_CLASSES
│   ├── ai.py              # AIPlayer (stratégique), TacticalAI (combat)
│   ├── map_generator.py   # MapGenerator, MapConfig
│   ├── strategic_map.py   # StrategicGameState, StrategicRenderer
│   ├── tactical_map.py    # TacticalBattle, TacticalRenderer
│   └── main.py            # Point d'entrée, MainMenu
```

## Flux d'exécution

```
main.py → MainMenu.run()
  └── run_strategic_game()
        ├── StrategicGameState (tours, sélection, animations, IA stratégique)
        └── [bataille] → run_tactical_battle()
              └── TacticalBattle (combat tour par tour, IA tactique)
```

---

## Classes clés

### Terrain (`game/terrain.py`)

```python
class TerrainType(Enum):    # PLAINS, HILLS, FOREST, MOUNTAIN, WATER, DESERT, SWAMP
class OverlayType(Enum):    # ROAD, CITY, BRIDGE, RUINS
TERRAIN_CONFIGS = {...}     # movement_cost, defense_bonus, color
OVERLAY_CONFIGS = {...}     # modifie movement et defense
```

### Tile (`engine/tile.py`)

```python
class Tile:
    position: HexCoord
    base_terrain: TerrainType
    overlay: Optional[OverlayType]
    unit: Optional[Unit]

    # Propriétés calculées (base + overlay)
    defense_bonus: int
    get_movement_cost() -> int
    is_passable -> bool
```

### Unités (`engine/unit.py`)

```python
class UnitStats:    # max_hp, current_hp, attack, defense, movement, range
class Unit:         # Base (name, unit_type, stats, player_id, position)
class ArmyUnit:     # Unité avec count (ex: 5 archers)
class Army:         # Stack d'unités, peut avoir un Hero
class Hero:         # hero_class, level, xp, is_independent
```

### IA (`game/ai.py`)

```python
class AIPersonality(Enum):  # AGGRESSIVE, DEFENSIVE, MOBILE, PASSIVE
class AIConfig:             # attack_weight, defense_weight, movement_weight, hold_weight
class AIPlayer:             # IA stratégique - plan_turn(), _evaluate_best_action()
class TacticalAI:           # IA combat - play_turn(), _score_attack(), _score_position()
```

---

## Configuration (`game/config.py`)

```python
INPUT = InputSettings(drag_threshold=5, scroll_speed=10)
UI = UISettings(panel_bg_color, text_color, selection_color)
ANIMATION = AnimationSettings(move_step_delay_ms=80)
BATTLE = BattleSettings(map_width=20, map_height=20, max_turns=20)
AI = AISettings(action_delay_ms=400, turn_start_delay_ms=300)
PLAYER_COLORS = PlayerColors(player1=(100,100,255), player2=(255,100,100))
```

---

## Guide par fonctionnalité

### Ajouter un terrain

1. `game/terrain.py` : ajouter à `TerrainType`, config dans `TERRAIN_CONFIGS`
2. `game/map_generator.py` : ajouter génération si nécessaire
3. `game/tactical_map.py` : config dans `_create_tactical_map_config()` si spécifique

### Ajouter une unité

1. `game/units.py` : créer `create_xxx()` avec stats
2. `game/main.py` : l'utiliser dans les armées initiales

### Ajouter une personnalité IA

1. `game/ai.py` : ajouter à `AIPersonality` enum
2. `game/ai.py` : config dans `AI_CONFIGS` (poids attack/defense/movement/hold)

### Changer la personnalité du Player 2

`game/strategic_map.py` ligne ~128 : `ai_personality=AIPersonality.XXX`

### Modifier le combat

`engine/combat.py` : `CombatSystem.resolve_combat()`, `_calculate_attack_damage()`

### Modifier le pathfinding

`engine/pathfinding.py` : `calculate_valid_moves()` (BFS), `find_path()` (Dijkstra)

---

## Fichiers à modifier par type de changement

| Changement | Fichier principal | Secondaires |
|------------|-------------------|-------------|
| Terrain | `terrain.py` | `map_generator.py`, `tactical_map.py` |
| Unité | `units.py` | `main.py` |
| Héros | `heroes.py` | `main.py` |
| Combat | `combat.py` | `tactical_map.py` |
| IA stratégique | `ai.py` | `strategic_map.py` |
| IA tactique | `ai.py` | `tactical_map.py` |
| UI stratégique | `strategic_map.py` | `config.py` |
| UI tactique | `tactical_map.py` | `config.py` |
| Mouvement | `pathfinding.py` | `strategic_map.py` |
| Animation | `strategic_map.py` | `config.py` |

---

## Points d'attention

1. **Coordonnées** : `HexCoord` pour calculs, `tuple (q,r)` pour clés de dict
2. **Terrain + overlay** : toujours via `tile.get_movement_cost()` et `tile.defense_bonus`
3. **Unités sur tiles** : `tile.unit` = `Army` ou `None` (Hero indépendants pas sur tiles)
4. **Animation** : bloquer inputs si `game_state.current_animation is not None`
5. **Import circulaire** : `tile.py` importe `terrain.py` via lazy import

---

## Tests rapides

```bash
source .venv/bin/activate

# Imports
python -c "from game.terrain import TerrainType; print('OK')"
python -c "from game.ai import AIPlayer, TacticalAI; print('OK')"

# Génération carte
python -c "from game.map_generator import generate_map; print(len(generate_map(20,20)), 'tiles')"

# Jeu complet
python game/main.py
```

---

## Conventions

- Classes : `PascalCase`
- Fonctions : `snake_case`
- Privées : `_snake_case`
- Constantes : `UPPER_SNAKE_CASE`
- Enums : `PascalCase` (enum), `UPPER_SNAKE_CASE` (valeurs)
