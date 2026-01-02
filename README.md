# Hex Strategy Game

Jeu de stratégie au tour par tour sur plateau hexagonal en Python avec Pygame.

## Caractéristiques

- **Carte stratégique** : déplacement des armées et héros sur une grande carte (jusqu'à 200x200 hex)
- **Carte tactique** : combats au tour par tour quand deux armées se rencontrent
- **Génération procédurale** : terrains variés avec rivières, forêts, montagnes, villes et routes
- **Système de héros** : personnages uniques avec classes et niveaux
- **IA complète** : l'adversaire joue automatiquement (carte stratégique et combats tactiques)
- **Multi-zoom** : 9 niveaux de zoom

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# ou .venv\Scripts\activate  # Windows

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
| Maj + Flèches | Déplacer rapidement |
| Clic molette + glisser | Drag |
| +/- ou Ctrl + Molette | Zoom |
| C | Afficher les coordonnées |
| Clic gauche | Sélectionner / déplacer |
| Clic droit | Désélectionner |
| Espace | Fin de tour |
| ESC | Retour au menu |

### Carte tactique (combat)

| Touche | Action |
|--------|--------|
| Clic gauche | Sélectionner / attaquer |
| Espace | Fin de tour |
| ESC | Auto-résolution |

## Terrains

### Terrains de base

| Terrain | Mouvement | Défense |
|---------|-----------|---------|
| Plaine | 1 | 0 |
| Collines | 2 | +2 |
| Forêt | 2 | +2 |
| Montagne | 3 | +4 |
| Eau | - | - |
| Marais | 3 | +1 |
| Désert | 2 | -1 |

### Constructions

| Type | Effet | Défense |
|------|-------|---------|
| Route | Mouvement = 1 | -1 |
| Ville | Mouvement = 1 | +3 |
| Pont | Traverse l'eau | -2 |
| Ruines | - | +1 |

## Unités

| Unité | PV | ATK | DEF | Mouv | Portée |
|-------|-----|-----|-----|------|--------|
| Lancier | 10 | 8 | 6 | 3 | 1 |
| Archer | 6 | 10 | 3 | 3 | 2 |
| Cavalerie | 12 | 12 | 4 | 5 | 1 |
| Mage | 4 | 15 | 2 | 2 | 3 |
| Piquier | 8 | 6 | 10 | 2 | 1 |

## Héros

| Classe | Leadership | Magie |
|--------|------------|-------|
| Warrior | 12 | 0 |
| Mage | 8 | 15 |
| Scout | 6 | 0 |
| Commander | 20 | 0 |
| Paladin | 10 | 5 |

Les héros peuvent se déplacer seuls ou rejoindre une armée.

## IA

L'adversaire (Player 2) est contrôlé par une IA avec une personnalité :

| Personnalité | Comportement |
|--------------|--------------|
| Agressif | Cherche le combat |
| Défensif | Évite les combats, cherche le bon terrain |
| Mobile | Privilégie l'exploration |
| Passif | Reste en position |

L'IA joue automatiquement sur la carte stratégique ET pendant les combats tactiques.
