# Guide de Développement - Hex Strategy Game

Guide pour modifier le projet (~6500 lignes de code).

> 📋 Ce `README_DEV.md` décrit **le code réel d'aujourd'hui** et doit rester synchronisé avec
> lui à chaque changement de structure (cf. `CLAUDE.md`). La **vision cible** et la roadmap
> vivent dans [`PROJET.md`](PROJET.md). Les instantanés datés (ex. audit) sont dans
> [`docs/archive/`](docs/archive/).

---

## ⚠️ Cap : virage vers un jeu de personnages

Le projet **pivote** d'un wargame hexagonal vers un **jeu de gestion de personnages et de
royaumes** (cf. [`PROJET.md`](PROJET.md)). L'atome passe de l'**armée** au **personnage** ; le
combat tactique est **conservé mais rétrogradé** (batailles intermédiaires + finale).

**Architecture cible (3 couches)** — *pas encore en place, les modules ci-dessous n'existent pas
tous* :

```
engine/          # INCHANGÉ : boîte à outils hex générique (grid, tile, camera, pathfinding, combat, input)
world/  (NEW)    # Couche CAMPAGNE = cœur : Character, worldgen, settlement/kingdom, actions, events, world_state
settlement_ui/   # (NEW) écrans d'interaction en ville, dimensionnés par la taille
military/        # l'actuel game/ militaire, RÉTROGRADÉ, derrière un BattleResolver (auto | tactique)
```

**Correspondance actuel → cible** (ce que devient chaque module en migrant) :

| Aujourd'hui (`game/`) | Devient | Note |
|-----------------------|---------|------|
| `strategic_map.py` (armées poussant des tuiles) | **couche militaire** + base de la carte monde | ce n'est **pas** la future couche stratégique |
| `tactical_map.py`, `combat.py` | `military/` derrière `BattleResolver` | conservé, appelé rarement |
| `heroes.py` / `Hero(Unit)` | **`Character`** (composition, pas héritage) | modèle amorcé dans `world/character.py` ; le combat deviendra une facette (rôle Général) |
| `ai.py` `AIPlayer` (IA stratégique symétrique) | **« Metteur en scène de l'Ombre »** | main cachée : traîtres / sbires / escalade |
| `ai.py` `TacticalAI` | conservé | IA des batailles |
| `map_generator.py` | conservé + greffe settlements/royaumes | terrain gardé (bon) |

**Point pivot technique — fait.** Le combat est derrière un **`BattleResolver`**
(`game/battle_resolver.py`) à deux modes : `AUTO` (résolution headless, les deux camps joués
par l'IA tactique, sans fenêtre) et `TACTICAL` (bataille interactive). Prérequis rempli :
`TacticalBattle` est de la logique pure (ni `screen` ni `camera` ; l'état de vue vit dans
`run_tactical_battle` / `TacticalRenderer`). La couche stratégique passe par le resolver
(`strategic_map._fight_battle`, point de passage unique des trois déclencheurs de bataille).
La future couche campagne appellera le même resolver. Voir la roadmap dans `PROJET.md`.

Tant qu'un module cible n'est pas construit, **ce guide continue de décrire le code existant
ci-dessous.** On met à jour au fur et à mesure de la migration.

---

## Architecture (code actuel)

```
hex-game/
├── engine/             # Moteur générique réutilisable
│   ├── hex_grid.py        # HexCoord, HexGrid (conversions pixel/hex)
│   ├── tile.py            # Tile (terrain + overlay + unité)
│   ├── unit.py            # Unit, ArmyUnit, Army, Hero
│   ├── camera.py          # Zoom multi-niveaux + center_on (suivi d'unité)
│   ├── combat.py          # CombatSystem (dégâts, contre-attaque)
│   ├── pathfinding.py     # BFS (valid_moves), Dijkstra (find_path)
│   └── input_handler.py   # CameraController (drag, zoom)
│
├── game/               # Implémentation du jeu
│   ├── config.py          # Constantes (SPEED, INPUT, UI, ANIMATION, BATTLE, AI)
│   ├── terrain.py         # TerrainType, OverlayType + configs
│   ├── units.py           # create_lancer(), create_archer()...
│   ├── heroes.py          # create_hero(), HERO_CLASSES
│   ├── ai.py              # AIPlayer (stratégique), TacticalAI (combat)
│   ├── map_generator.py   # MapGenerator, MapConfig
│   ├── strategic_map.py   # StrategicGameState, StrategicRenderer
│   ├── battle_resolver.py # BattleResolver (AUTO headless | TACTICAL fenêtré)
│   ├── tactical_map.py    # TacticalBattle (logique pure), TacticalRenderer
│   └── main.py            # Point d'entrée, MainMenu
│
└── world/              # Couche campagne (Phase 2+, headless, sans Pygame)
    └── character.py       # Character + couche vrai/connu (HiddenValue, label)
```

## Flux d'exécution

```
main.py → MainMenu.run()
  └── run_strategic_game()
        ├── StrategicGameState (tours, sélection, animations, IA stratégique)
        └── [bataille] → _fight_battle() → BattleResolver.resolve()
              ├── mode TACTICAL → run_tactical_battle() (fenêtre)
              │     └── TacticalBattle (combat tour par tour, IA tactique)
              └── mode AUTO → TacticalBattle pompé en headless (sans rendu)
```

Le stratégique joue toujours en `TACTICAL` ; le mode `AUTO` sert aux tests et à la
future couche campagne (batailles intermédiaires auto-résolues).

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

### Personnage (`world/character.py`) — couche campagne, Phase 2

**Composition, pas héritage** : `Character` n'est pas une unité de combat. Les
caractéristiques sont la source ; aptitudes, points d'action et stats de combat se
**dérivent** (fonctions pures, rien de stocké). Voir PROJET.md §3 / §5.1.

```python
class HiddenValue:   # true_value (0-100, semé) + knowledge_level ; known_interval(), reveal(), collapse()
def label(hv):       # rendu UI ("inconnu" → "semble faible" → "faible à moyen" → …) ; JAMAIS un chiffre
class Trait(Enum):   # 9 caractéristiques : PUISSANCE, VIVACITE, VIGUEUR, INTELLIGENCE,
                     #   PERSPICACITE, VOLONTE, CHARISME, COMMANDEMENT, CHANCE
class Magie(Enum):   # 6 magies : GUERISON, LIEN_DES_BETES, EMPRISE, ESPRIT, SONGE, ANCIENS
class GrandLivre:    # reputation_domaine/_royaume (§5.3), cicatrices, missions
class Position:      # charge accordée (role_id, accordee_par, perimetre)
class FaitsSecrets:  # allegiance (du_mal/revele), est_elu, potentiels magiques (cachés)
class Character:     # 4 couches : identité · caractéristiques · grand livre+positions · secrets
def nouveau_character(id, nom, portrait_id=0, valeurs=None)  # constructeur sans règles
```

- **Couche vrai/connu (§5.1, « Option A »)** : l'intervalle connu **contient toujours**
  la vraie valeur — on ne ment jamais, seule la précision augmente. La divineresse =
  `collapse()` (valeur exacte). `KNOWLEDGE_WIDTHS` règle le resserrement.
- **Hors périmètre volontaire** (à venir) : le **générateur procédural** (profils + budget,
  faits semés — §5.7, règles à co-concevoir), la dérivation d'**aptitude**, l'**adaptateur de
  combat**, les **mécaniques de magie** (§5.4, backlog). Seule la *forme* des données est figée.

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
SPEED = GameSpeed(index=1)   # Lent / Normal / Rapide / Très rapide (facteur ×délais)
INPUT = InputSettings(drag_threshold=5, scroll_speed=10)
UI = UISettings(panel_bg_color, text_color, selection_color)
ANIMATION = AnimationSettings(base_move_step_delay_ms=80)
BATTLE = BattleSettings(map_width=20, map_height=20, max_turns=20)
AI = AISettings(base_action_delay_ms=400, base_turn_start_delay_ms=300)
PLAYER_COLORS = PlayerColors(player1=(100,100,255), player2=(255,100,100))
```

### Vitesse de jeu (`GameSpeed` / `SPEED`)

Les délais qui rythment le tour IA et les animations sont **dérivés** d'une base
via la propriété `factor` de `SPEED` :

- `AI.action_delay_ms` = `base_action_delay_ms × SPEED.factor`
- `AI.turn_start_delay_ms` = `base_turn_start_delay_ms × SPEED.factor`
- `ANIMATION.move_step_delay_ms` = `base_move_step_delay_ms × SPEED.factor`

La durée d'un tour IA est dominée par ces délais (pacing pour la lisibilité),
**pas** par le calcul. Niveaux : `Lent` (×1.6), `Normal` (×1.0), `Rapide`
(×0.45), `Très rapide` (×0.2). Choix dans le menu (`game_speed`), et réglable en
jeu avec `<` / `>` (touches virgule/point), y compris pendant le tour ennemi.

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

- Contre-attaque : conditionnée par la distance (`distance <= defender.stats.range`) — un défenseur corps-à-corps ne riposte pas à un tir hors de portée.
- Héros en bataille : déployés comme `TacticalUnit` (`source_hero`) dans `tactical_map._deploy_army_units()`.
- XP post-bataille : `tactical_map.TacticalBattle._resolve_hero_outcomes()` (XP = pertes ennemies × `PROGRESSION.xp_per_kill`, détache les héros morts).

### Modifier le pathfinding

`engine/pathfinding.py` : `calculate_valid_moves()` (BFS), `find_path()` (Dijkstra)

`calculate_valid_moves()` est la **source unique** du BFS de mouvement : le
tactique, `StrategicGameState._calculate_valid_moves` et
`AIPlayer._calculate_valid_moves` y délèguent tous, en fournissant le prédicat
d'arrêt `can_move_to(tile, pos)` (et optionnellement `can_pass_through(tile)`).
Ne pas réintroduire de BFS faits-main.

### Déroulement / fin de tour

- **Fin de tour automatique** : la boucle stratégique appelle chaque frame
  `StrategicGameState.current_player_has_moves()` ; si le joueur humain n'a plus
  aucune destination atteignable, `end_turn()` est enclenché tout seul. Équivalent
  tactique : `TacticalBattle.current_player_has_actions()` (déplacement *ou*
  attaque possible).
- **Une activation par unité (IA tactique)** : `TacticalAI.play_turn()` filtre sur
  `not has_acted` et `TacticalBattle._execute_ai_action()` pose `has_acted = True`
  après **toute** action (y compris un simple déplacement). Sans ça, une unité qui
  se déplaçait restait « disponible » et était rejouée en boucle, allongeant le
  tour. `try_attack()` pose aussi `has_acted` (une attaque par unité et par tour).
- **Caméra qui suit l'ennemi** : pendant le tour IA, la vue glisse vers l'unité
  active via `Camera.center_on(coord, hex_grid, smoothing)`. Côté stratégique on
  suit `current_animation.unit.position` ; côté tactique on suit `battle.ai_focus`
  (posé dans `update_ai_turn`).

---

## Fichiers à modifier par type de changement

| Changement | Fichier principal | Secondaires |
|------------|-------------------|-------------|
| Terrain | `terrain.py` | `map_generator.py`, `tactical_map.py` |
| Unité | `units.py` | `main.py` |
| Héros | `heroes.py` | `main.py` |
| Combat | `combat.py` | `tactical_map.py` |
| Résolution de bataille | `battle_resolver.py` | `strategic_map.py`, `tactical_map.py` |
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

## Environnement

Le projet utilise **[uv](https://docs.astral.sh/uv/)** (dépendances dans `pyproject.toml`,
verrou dans `uv.lock`, Python épinglé par `.python-version`).

```bash
uv sync          # installe l'environnement (crée .venv)
uv run python game/main.py   # lance le jeu
uv add <paquet>  # ajoute une dépendance
```

## Tests

Suite `pytest` dans `tests/` (config dans `pyproject.toml`, `pythonpath = ["."]`).
Les tests gameplay tournent en **headless** (`SDL_VIDEODRIVER=dummy`, posé par
`tests/conftest.py`) — pas de fenêtre ouverte.

```bash
uv run pytest            # toute la suite
uv run pytest -k combat  # un sous-ensemble
```

Couverture actuelle (invariants, pas de couverture exhaustive) :

| Fichier | Vérifie |
|---------|---------|
| `test_hex_grid.py` | round-trip pixel↔hex, `q+r+s=0`, 6 voisins, distance |
| `test_pathfinding.py` | budget de mouvement, cases infranchissables, chemins contigus |
| `test_combat.py` | formule `atk−def/2` (min 1), **régression §2.5** (contre-attaque hors-portée) |
| `test_map_generator.py` | déterminisme par seed (même hors random global) |
| `test_config_speed.py` | scaling `GameSpeed` des délais |
| `test_turn_flow.py` | **tour IA borné** (fix `has_acted`), détection fin de tour auto |
| `test_battle_resolver.py` | auto-résolution headless : terminaison, pertes répercutées, reproductibilité par seed |
| `test_character.py` | couche vrai/connu : invariant (l'intervalle contient la vraie valeur), resserrement, divineresse, label sans chiffre |

Fixture utile (`tests/conftest.py`) : `make_grid` (grille hexagonale d'un terrain
donné). `TacticalBattle` se construit sans écran (logique découplée de Pygame) ;
la session pygame headless reste initialisée par `conftest.py` pour les modules
qui importent Pygame.

### Vérifs d'import rapides

```bash
uv run python -c "from game.tactical_map import TacticalBattle; print('OK')"
uv run python game/main.py   # jeu complet
```

---

## Conventions

- Classes : `PascalCase`
- Fonctions : `snake_case`
- Privées : `_snake_case`
- Constantes : `UPPER_SNAKE_CASE`
- Enums : `PascalCase` (enum), `UPPER_SNAKE_CASE` (valeurs)
