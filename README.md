# Hex Strategy Game

Jeu de stratégie au tour par tour sur plateau hexagonal en Python avec Pygame.

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

| Touche | Action |
|--------|--------|
| Flèches | Déplacer la carte |
| Clic molette + glisser | Déplacer la carte (drag) |
| Clic droit + glisser | Déplacer la carte (drag trackpad) |
| +/- | Zoom avant/arrière |
| Ctrl + Molette | Zoom avant/arrière |
| C | Afficher/masquer les coordonnées |
| Clic gauche | Sélectionner une case |
| Clic droit | Désélectionner |
| Espace | Fin de tour |
| ESC | Retour au menu |

## Structure du projet

```
hex-game/
├── engine/                 # Moteur de jeu générique
│   ├── hex_grid.py         # Grille hexagonale (coordonnées axiales q, r)
│   ├── tile.py             # Classe Tile de base
│   ├── unit.py             # Classes Unit, Army, Hero
│   ├── combat.py           # Système de combat
│   └── renderer.py         # Rendu Pygame
├── game/                   # Implémentation concrète du jeu
│   ├── terrain.py          # Types de terrain
│   ├── units.py            # Types d'unités
│   ├── cities.py           # Système de villes
│   └── main.py             # Point d'entrée
├── assets/                 # Sprites (à venir)
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
| Route | 1 | -1 | Relie les villes |
| Ville | 1 | +3 | Points stratégiques |
| Pont | 1 | -2 | Traverse l'eau |

## Unités disponibles

- **Lancier** : Infanterie équilibrée
- **Archer** : Attaque à distance (portée 2)
- **Cavalerie** : Haute mobilité, fort en attaque
- **Mage** : Puissant mais fragile (portée 3)
- **Piquier** : Défensif, anti-cavalerie

## Système de coordonnées

Le jeu utilise les coordonnées axiales (q, r) pour les hexagones pointy-top :
- `q` : colonne (augmente vers la droite)
- `r` : ligne (augmente vers le bas-droite)

Référence : [Red Blob Games - Hexagonal Grids](https://www.redblobgames.com/grids/hexagons/)
