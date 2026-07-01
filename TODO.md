# TODO - Hex Strategy Game

## Carte Tactique - Améliorations

### Génération contextuelle
- [ ] Combat urbain (ville) - génération de rues, bâtiments, places
- [ ] Combat sur pont - rivière traversant la carte avec pont au centre
- [ ] Combat en collines - terrain vallonné avec avantages de hauteur

### Avantages tactiques
- [ ] **Couvert** : Bonus défense en forêt, malus pour les attaques à distance
- [ ] **Hauteur** : Bonus attaque/portée pour archers sur montagnes/collines
- [ ] **Charge** : Bonus d'attaque pour cavalerie en terrain ouvert (plaines)
- [ ] **Embuscade** : Bonus premier tour pour le défenseur en forêt
- [ ] **Fortification** : Bonus défense en ville/bâtiments

### Mécanique de combat
- [ ] Flanquement : Bonus si attaque depuis plusieurs directions
- [ ] Moral : Fuite possible si HP < 25%
- [ ] Fatigue : Malus après plusieurs tours de combat

---

## Carte Stratégique - Personnages

### Héros - Extensions
- [ ] Compétences spéciales (magie, inspiration, sorts)
- [ ] Équipement (armes, armures, objets)
- [ ] Arbre de talents par classe

### Autres personnages
- [ ] **Éclaireur** : Révèle le brouillard de guerre, rapide
- [ ] **Marchand** : Génère de l'or, peut commercer entre villes
- [ ] **Diplomate** : Peut négocier avec factions neutres
- [ ] **Espion** : Sabotage, information sur armées ennemies

### Système de stack
- [ ] Limite de personnages par case (ex: 3 max)
- [ ] Plusieurs héros dans une armée

---

## Villes et économie

### Villes
- [ ] Capture de villes (contrôle = revenus)
- [ ] Production d'unités
- [ ] Recrutement de héros
- [ ] Fortifications améliorables

### Ressources
- [ ] Or (recrutement, entretien)
- [ ] Nourriture (limite de taille d'armée)
- [ ] Matériaux (équipement, fortifications)

---

## Interface

### Améliorations UI
- [ ] Mini-carte
- [ ] Liste des armées/héros avec raccourcis
- [ ] Historique des combats
- [ ] Sauvegarde/Chargement
- [ ] Tooltip au survol des unités

### Brouillard de guerre
- [ ] Cases non explorées masquées
- [ ] Vision limitée par unité
- [ ] Éclaireurs révèlent plus loin

---

## IA

### IA stratégique
- [ ] Défense des villes
- [ ] Gestion des héros indépendants

### IA tactique
- [ ] Utilisation du terrain (bonus défensifs)
- [ ] Coordination des attaques

---

## Audio/Visuel

### Sprites
- [ ] Sprites pour les unités (remplacer les cercles)
- [ ] Sprites pour les héros
- [ ] Icônes de terrain et constructions
- [ ] Animations d'attaque

### Audio
- [ ] Musique de fond
- [ ] Sons de combat
- [ ] Sons d'interface

---

## Fondations techniques (dette / qualité)

Piste **en cours** (voir `AUDIT.md` pour le détail et le suivi des corrections).

- [x] Suite de tests `pytest` (`tests/`, `uv run pytest`) — *AUDIT reco 12*
- [x] Centraliser le BFS de mouvement sur `engine.pathfinding` — *AUDIT §2.2*
- [x] Timers IA/animation pilotés par `dt` injecté (plus d'horloge murale) — *AUDIT §2.3 (C1)*
- [ ] Sortir `screen`/`camera` de `TacticalBattle` — *AUDIT §2.3 (C2)*
- [ ] Éclater `run_strategic_game` (input / animation / batailles) — *AUDIT §2.4*
- [ ] Rééquilibrage unités (mage/cavalerie, triangle de types) — *AUDIT §3.2*

---

## Priorités

**Court terme (technique)** : finir le découplage Pygame (C2), puis rééquilibrage.

**Gameplay** :
1. Combat en collines (carte tactique pour nouveau terrain)
2. Avantages tactiques de base (couvert, hauteur)
3. Mini-carte
