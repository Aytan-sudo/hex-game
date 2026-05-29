# Audit — Hex Strategy Game

> Instantané d'analyse (snapshot daté). Ce document est **historique** : il n'est pas
> maintenu à jour avec le code. Le guide vivant est [`README_DEV.md`](README_DEV.md).
>
> **Date :** 2026-05-29
> **Périmètre :** ~7 500 lignes Python + Pygame, séparé en `engine/` (moteur) et `game/` (gameplay).

## Suivi des corrections

| Item | Sujet | Statut |
|------|-------|--------|
| §2.1 | Code mort (`game_state.py`, `renderer.py`, `cities.py`) | ✅ Supprimé |
| §2.5 | Contre-attaque ignorant la distance | ✅ Corrigé (`combat.py`) |
| §2.7 | Héros non déployé en bataille tactique | ✅ Corrigé (`tactical_map.py`) |
| Reco 5 | Gain d'XP héros post-bataille | ✅ Branché (`tactical_map._resolve_hero_outcomes`) |
| §2.2 | BFS de mouvement dupliqué (×4 → reste ×3 après suppression du mort) | ⬜ À faire |
| §2.6 | `attacker_terrain_bonus` ambigu | ⬜ À clarifier |
| §2.8 | XP/level-up héros décoratif | ✅ Désormais effectif (cf. Reco 5) |
| Autres | Voir sections ci-dessous | ⬜ Backlog |

---

## 1) Forces

- Architecture `engine`/`game` propre en intention : isolation des primitives hex, tiles, unit, combat, camera.
- Hex axial bien fait (`HexCoord` immuable, `_round_hex` correct, conversion pixel↔hex propre, redblobgames référencé).
- Génération procédurale soignée : approche en couches (`_generate_base_terrain` → mountain clusters → rivières meandering → swamps adjacents → cities/roads MST → ruines). Noise multi-octave, distance minimale entre villes, A* pour les routes avec coût pénalisant montagnes/eau.
- Système overlay terrain + construction (ville/route/pont/ruine) propre et orthogonal au terrain de base.
- Caméra multi-zoom avec centre stable (`_zoom_to_index` recalcule l'offset pour garder le point central sous le curseur — détail souvent raté).
- IA à personnalités (AGGRESSIVE/DEFENSIVE/MOBILE/PASSIVE) déjà fonctionnelle pour strategic ET tactical, avec poids paramétrés.
- Config centralisée dans `game/config.py` (dataclasses INPUT/UI/ANIMATION/BATTLE/AI).

---

## 2) Problèmes côté code (dev)

### 2.1 Code mort / orphelin — ✅ RÉSOLU

- `engine/game_state.py` (421 lignes) : `GameState`, `GamePhase`, `Player` exportés mais jamais utilisés — `StrategicGameState` recopie tout.
- `engine/renderer.py` (`HexRenderer`, 586 lignes) : exporté, jamais consommé.
- `game/cities.py` (`City`, `Building`, `BuildingType`) : exporté, aucun import. Les villes ne sont qu'un `OverlayType.CITY`.
- **Conséquence (à l'époque) :** ~1 100 lignes (15 %) de code zombie. **Supprimé lors de la session de nettoyage.**

### 2.2 Duplication massive du BFS de mouvement — ⬜ À FAIRE

Implémentations quasi-identiques du calcul des mouvements valides :
- `engine/pathfinding.py` `calculate_valid_moves` (version canonique)
- `engine/game_state.py` (supprimé)
- `game/strategic_map.py` `StrategicGameState._calculate_valid_moves`
- `game/ai.py` `AIPlayer._calculate_valid_moves`

Le tactique (`game/tactical_map.py`) est le seul qui réutilise réellement `engine.pathfinding.calculate_valid_moves`. À uniformiser.

### 2.3 Couplage logique ↔ Pygame — ⬜

- `TacticalBattle` stocke `self.screen`, `self.camera` et lit `pygame.time.get_ticks()` directement → impossible à tester sans afficher une fenêtre.
- `StrategicGameState` lit aussi `pygame.time.get_ticks()` dans `MoveAnimation.advance`. L'animation devrait être pilotée par un `dt` injecté.

### 2.4 `run_strategic_game` (300 lignes) fait trop — ⬜

Boucle géante mêlant input, animation, IA, déclenchement bataille (3 variantes copiées), victoire, hover, render. À éclater en `InputController`, `BattleOrchestrator`, etc. Les blocs `if report.attacker_won` / `else` sont dupliqués à 3 endroits.

### 2.5 Combat : règles incorrectes — ✅ RÉSOLU

`engine/combat.py` : la contre-attaque ne vérifiait pas la distance — un archer (range 2) touchant à 2 cases mangeait la riposte d'un piquier (range 1). **Corrigé** : `resolve_combat` prend désormais `distance` et la contre-attaque n'a lieu que si `distance <= defender.stats.range`.

### 2.6 Bonus de terrain pour l'attaquant ignoré — ⬜

`combat.py` calcule `attacker_terrain_bonus = 0` mais ne l'assigne jamais depuis `attacker_tile.defense_bonus`. Le bonus n'est utilisé que dans le counter-damage. Intention/nommage à clarifier.

### 2.7 Héros oubliés en bataille tactique — ✅ RÉSOLU

`TacticalBattle._deploy_army_units` itérait sur `army.units` sans déployer `army.hero`, alors que `Army.get_attack_power` inclut le bonus héros au stratégique → incohérence. **Corrigé** : le héros est déployé comme `TacticalUnit` (champ `source_hero`), avec référence stable conservée pour la résolution post-combat.

### 2.8 Pas de gain d'XP — ✅ RÉSOLU

`Hero.gain_experience`/`_on_level_up` existaient mais n'étaient jamais appelés. **Corrigé** : `TacticalBattle._resolve_hero_outcomes` accorde `PROGRESSION.xp_per_kill` XP par unité ennemie détruite aux héros survivants, et détache/retire les héros tombés au combat.

### 2.9 Fog of war : champs morts — ⬜

`Tile.is_visible`, `is_explored` sont `True` par défaut et jamais touchés.

### 2.10 `Army._calculate_army_stats` : intention ambiguë — ⬜

Agrège `total_hp`, etc. Au tactique chaque `ArmyUnit` est éclatée en `count` `TacticalUnit`. L'agrégat ne sert qu'à l'IA stratégique et à l'UI. À documenter ou réduire à un `power_score` clair.

### 2.11 Détails — ⬜

- Pas de tests (le `README_DEV.md` propose seulement des `python -c "from X import Y"`).
- `random.seed(self.seed)` réappelé partout → l'ordre des `random.shuffle` ailleurs influe sur la repro.
- `valid_attacks` recalculé en O(range²) en plus de la boucle voisins.
- `calculate_path_cost` (Dijkstra) appelé à chaque clic puis re-appelé pour exécuter le move : redondant.
- `AIPlayer._score_move` mesure la force par `total_unit_count` → 10 lanciers = 10, 3 mages = 3 alors que les mages sont 4× plus forts. L'IA juge mal les armées hétérogènes.

---

## 3) Problèmes côté game design

### 3.1 Boucle de jeu incomplète

- Victoire = éliminer toutes les armées ennemies.
- Aucune production : pas de recrutement, pas de revenu, pas de réparation. Les armées initiales sont les seules.
- Le jeu est une chaîne de batailles d'attrition fixe. Pas de comeback, pas de tempo économique.
- Aucune raison de capturer une ville (+3 défense locale seulement, pas d'ownership ni production).

### 3.2 Équilibrage unités cassé

Formule : `dégâts = atk - def/2` (min 1), ±20 % rng.

| Attaquant | Cible | Dégâts | Verdict |
|-----------|-------|--------|---------|
| Mage (atk 15, range 3) | Lancier (def 6, hp 10) | 12 → one-shot | Pas de contre-attaque possible |
| Cavalerie (atk 12) | Archer (def 3, hp 6) | 11 → one-shot | Cav est aussi le plus mobile |
| Piquier (atk 6) | Cavalerie (def 4, hp 12) | 4 → 3 tours | Anti-cav cassé |

- Mages broken : range 3, ATK 15, jamais contre-attaqués → stratégie dominante = kiter.
- Cavalerie sur-tunée : meilleur PV, 2e meilleure attaque, meilleur mouvement, pas de hard counter.
- Pas de pierre/feuille/ciseaux : aucun bonus de type. C'est l'élément structurant manquant.

### 3.3 Combat sans profondeur tactique

- Pas de ligne de vue (archers tirent à travers montagnes).
- Pas de bonus de hauteur offensif pour ranged.
- Pas de flanquement (hex = 6 directions, dommage).
- Pas de zone of control / engagement.
- Le TODO le sait (couvert, hauteur, charge, embuscade, fortification).

### 3.4 Layer stratégique trop passif

- Jusqu'à 200×200 = 40 000 hex pour 3 armées/camp → densité dérisoire.
- Pas de fog of war (alors que `is_visible`/`is_explored` existent).
- Pas de mini-carte.
- Pas de prévisualisation de combat.

### 3.5 Héros : décoratifs (partiellement résolu)

- ✅ Combat tactique (cf §2.7) et XP réelle (cf §2.8) désormais branchés.
- ⬜ Pas de sorts (`Hero.magic` stocké mais inutilisé).
- ⬜ Pas d'attaque héros↔héros.
- ⬜ 5 classes pour peu de mécaniques réelles (bonus passifs leadership).

### 3.6 UX / lisibilité

- « ESC : Retreat » dans le tactique est trompeur : ESC = défaite forcée, pas une retraite.
- Pas d'undo de mouvement, pas de confirm fin de tour.
- Combat log limité à 3 lignes non scrollables.
- Menu : options largement inutiles tant qu'on ne capture/recrute pas.

### 3.7 IA stratégique : myope

- `_score_move` ne regarde qu'une armée à la fois, pas de coordination.
- `min_strength_ratio_to_attack` basé sur `total_unit_count` → mauvaise estimation des armées hétérogènes.
- Pas de plan multi-tour.
- IA tactique sans notion de rôle (tank devant, archer derrière).

---

## 4) Recommandations priorisées

### Court terme (nettoyage)
1. ✅ Supprimer le code mort.
2. ⬜ Centraliser le BFS sur `engine.pathfinding.calculate_valid_moves`.
3. ✅ Fixer le bug contre-attaque hors-portée.
4. ✅ Déployer le héros au tactique.
5. ✅ Brancher `Hero.gain_experience` post-bataille (proportionnel aux pertes infligées).

### Moyen terme (boucle de jeu)
6. ⬜ Faire vivre les villes : ownership, capture, revenu, recrutement.
7. ⬜ Fog of war minimal (réutilise les champs `Tile` existants).
8. ⬜ Bonus tactiques structurants (couvert, hauteur, charge).
9. ⬜ Triangle pierre-feuille-ciseaux (bonus de type).

### Long terme
10. ⬜ Mini-carte + prévisualisation de combat.
11. ⬜ Séparer logique/render au tactique (retirer screen/camera de `TacticalBattle`).
12. ⬜ Suite de tests (invariants pathfinding, formule combat, génération de map).

---

## Synthèse

Code bien structuré en surface mais qui souffrait d'une dette de duplication (code mort, BFS répété) et d'un gameplay non bouclé. Les corrections de cette itération ont supprimé le code mort et fermé les trous critiques du **combat** (contre-attaque à distance, héros en bataille, XP). Restent les grands chantiers de **game design** : économie/villes, fog of war, bonus tactiques et rééquilibrage (mages/cavaliers). Priorité n°1 : fermer la boucle stratégique (villes utiles → recrutement → raisons de manœuvrer).
