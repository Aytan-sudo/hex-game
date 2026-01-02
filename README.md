# Hex Strategy Game

Jeu de stratégie au tour par tour sur plateau hexagonal en Python avec Pygame.

## Caractéristiques

- **Carte stratégique** (jusqu'à 200x200 hexagones) : déplacement des armées et héros
- **Carte tactique** (20x20) : combats au tour par tour quand deux armées se rencontrent
- **Génération procédurale** : terrains variés avec rivières, forêts, montagnes, villes et routes
- **Système de héros** : personnages uniques avec classes et niveaux
- **Multi-zoom** : 9 niveaux de zoom (de 6 à 96 pixels par hex)

## Installation

```bash
# Créer et activer l'environnement virtuel
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows

# Installer les dépendances
pip install -r requirements.txt
```

## Lancer le jeu

```bash
source .venv/bin/activate
python game/main.py
```

## Contrôles

### Carte stratégique

| Touche | Action |
|--------|--------|
| Flèches | Déplacer la carte |
| Maj + Flèches | Déplacer la carte rapidement |
| Clic molette + glisser | Déplacer la carte (drag) |
| Clic droit + glisser | Déplacer la carte (drag trackpad) |
| +/- | Zoom avant/arrière |
| Ctrl + Molette | Zoom avant/arrière |
| C | Afficher/masquer les coordonnées |
| Clic gauche | Sélectionner armée/héros, ou déplacer |
| Clic droit | Désélectionner |
| Espace | Fin de tour |
| ESC | Retour au menu |

### Carte tactique (combat)

| Touche | Action |
|--------|--------|
| Clic gauche | Sélectionner unité / attaquer |
| Espace | Fin de tour |
| ESC | Auto-résolution du combat |

## Structure du projet

```
hex-game/
├── engine/                 # Moteur de jeu générique
│   ├── hex_grid.py         # Grille hexagonale (coordonnées axiales q, r)
│   ├── tile.py             # Classe Tile de base
│   ├── unit.py             # Classes Unit, Army, Hero
│   ├── camera.py           # Caméra avec zoom multi-niveaux
│   ├── combat.py           # Système de combat
│   ├── pathfinding.py      # Algorithmes BFS et Dijkstra
│   ├── input_handler.py    # Gestion caméra (drag, zoom, scroll)
│   └── renderer.py         # Rendu Pygame
├── game/                   # Implémentation concrète du jeu
│   ├── main.py             # Point d'entrée et menu
│   ├── config.py           # Configuration centralisée
│   ├── strategic_map.py    # Carte stratégique (armées, héros)
│   ├── tactical_map.py     # Carte tactique (combats)
│   ├── map_generator.py    # Génération procédurale
│   ├── terrain.py          # Types de terrain
│   ├── units.py            # Types d'unités
│   ├── heroes.py           # Classes de héros
│   └── cities.py           # Système de villes
├── assets/                 # Sprites (à venir)
├── TODO.md                 # Améliorations futures
└── requirements.txt
```

## Terrains

| Terrain | Coût mouvement | Bonus défense | Description |
|---------|----------------|---------------|-------------|
| Plaine | 1 | 0 | Terrain de base |
| Forêt | 2 | +2 | Couverture naturelle |
| Montagne | 3 | +4 | Massifs montagneux |
| Eau | Infranchissable | - | Rivières et lacs |
| Marais | 3 | +1 | Près de l'eau |
| Désert | 2 | 0 | Terrain aride |
| Route | 1 | -1 | Relie les villes |
| Ville | 1 | +3 | Points stratégiques |
| Pont | 1 | -2 | Traverse l'eau |

## Unités

### Troupes (dans les armées)

| Unité | Type | PV | Attaque | Défense | Mouvement | Portée |
|-------|------|-----|---------|---------|-----------|--------|
| Lancier | Infanterie | 10 | 8 | 6 | 3 | 1 |
| Archer | Distance | 6 | 10 | 3 | 3 | 2 |
| Cavalerie | Cavalerie | 12 | 12 | 4 | 5 | 1 |
| Mage | Distance | 4 | 15 | 2 | 2 | 3 |
| Piquier | Infanterie | 8 | 6 | 10 | 2 | 1 |

### Héros (unités uniques)

| Classe | Description | Leadership | Magie |
|--------|-------------|------------|-------|
| Warrior | Combattant de première ligne | 12 | 0 |
| Mage | Attaques à distance puissantes | 8 | 15 |
| Scout | Mouvement rapide | 6 | 0 |
| Commander | Boost significatif à l'armée | 20 | 0 |
| Paladin | Guerrier équilibré avec magie | 10 | 5 |

Les héros peuvent :
- Se déplacer indépendamment sur la carte
- Rejoindre une armée alliée (clic sur l'armée)
- Monter de niveau et améliorer leurs stats

## Combats tactiques

Quand une armée attaque une autre, une bataille tactique s'ouvre :
- Carte 20x20 générée selon le terrain stratégique
- Chaque unité de l'armée devient une unité tactique
- Combat au tour par tour, unité par unité
- La bataille se termine quand une armée est éliminée

Le terrain de la carte tactique dépend du terrain stratégique :
- **Plaine** : champ ouvert avec quelques forêts
- **Forêt** : forêt dense avec clairières
- **Montagne** : passes et plateaux rocheux
- **Marais** : terrain marécageux avec mares
- **Désert** : sable avec affleurements rocheux
- **Route** : terrain ouvert traversé par une route

## Système de coordonnées

Le jeu utilise les coordonnées axiales (q, r) pour les hexagones pointy-top :
- `q` : colonne (augmente vers la droite)
- `r` : ligne (augmente vers le bas-droite)

Référence : [Red Blob Games - Hexagonal Grids](https://www.redblobgames.com/grids/hexagons/)
