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
| WASD / Flèches | Déplacer la carte |
| C | Afficher/masquer les coordonnées |
| Clic gauche | Sélectionner une case |
| ESC | Quitter |

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

| Terrain | Coût mouvement | Bonus défense | Couleur |
|---------|----------------|---------------|---------|
| Plaine | 1 | 0 | Vert clair |
| Forêt | 2 | +2 | Vert foncé |
| Montagne | 3 | +4 | Gris |
| Eau | Infranchissable | - | Bleu |
| Désert | 2 | -1 | Jaune |
| Marais | 3 | +1 | Olive |
| Route | 1 | -1 | Beige |

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
