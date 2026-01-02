# TODO - Hex Strategy Game

## Carte Tactique - Améliorations futures

### Génération contextuelle (EN COURS)
- [x] Adapter la génération selon le terrain stratégique
- [ ] Combat urbain (ville) - génération de rues, bâtiments, places
- [ ] Combat sur pont - rivière traversant la carte avec pont au centre

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

### Héros (à implémenter)
- [ ] **Héros** : Unité unique avec stats personnelles, niveau, expérience
- [ ] Peut se déplacer seul sur la carte (1 tuile = 1 héros)
- [ ] Peut rejoindre une armée (stackable)
- [ ] Bonus à l'armée quand attaché (leadership, moral, etc.)
- [ ] Compétences spéciales (magie, inspiration, etc.)

### Autres personnages
- [ ] **Éclaireur** : Révèle le brouillard de guerre, rapide
- [ ] **Marchand** : Génère de l'or, peut commercer entre villes
- [ ] **Diplomate** : Peut négocier avec factions neutres
- [ ] **Espion** : Sabotage, information sur armées ennemies

### Système de stack
- [ ] Plusieurs personnages peuvent être sur la même case
- [ ] Un héros peut commander une armée
- [ ] Limite de personnages par case (ex: 3 max)

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
- [ ] Liste des armées/héros
- [ ] Historique des combats
- [ ] Sauvegarde/Chargement

### Brouillard de guerre
- [ ] Cases non explorées masquées
- [ ] Vision limitée par unité
- [ ] Éclaireurs révèlent plus loin

---

## IA

### IA ennemie basique
- [ ] Déplacement vers objectifs
- [ ] Attaque si avantage numérique
- [ ] Retraite si désavantage
- [ ] Défense des villes

---

## Priorités actuelles

1. ~~Génération carte tactique contextuelle~~
2. **Héros sur carte stratégique** (EN COURS)
3. Combat urbain
4. Avantages tactiques de base
