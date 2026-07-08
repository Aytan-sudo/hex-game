# Hex-Game — Vision & Conception

> *Nom de travail non définitif.*
>
> Ce document est la **source de vérité de l'intention** : ce qu'on veut faire et pourquoi.
> Pour *comment le code est organisé*, voir [`README_DEV.md`](README_DEV.md) (guide vivant).
> Pour les instructions agent, voir [`CLAUDE.md`](CLAUDE.md).

---

## 1. Vision

Hex-Game fait **revivre une épopée centrée sur les personnages et les royaumes**, librement
inspirée de la *Roue du Temps* (et, pour les magies, d'un mélange RdT × *l'Art et le Vif* de
Robin Hobb).

Le joueur contrôle au début **quelques personnages** — un portrait dans une case hexagonale —
sur la carte du monde. Chaque tour, il décide **où ils se déplacent et ce qu'ils font** :
recruter d'autres personnages, convaincre un campement / village / bourgade / capitale de
rejoindre la lutte contre le mal. Un personnage entrant dans une ville ouvre une **interface
d'interaction** dimensionnée selon la taille de la ville. Certaines actions exigent la
**présence de plusieurs personnages**.

Les personnages ont des caractéristiques individuelles (générées à la création du monde,
**cachées pour certaines**) : intelligence, charisme, commandement, puissance… qui dérivent
leurs aptitudes. Certains sont de futurs généraux, d'autres gestionnaires, membres de la
royauté, diplomates ; d'autres ont accès à l'une des **magies**. Leur **potentiel** ne se
révèle qu'au gré des événements vécus.

**Un des héros initiaux est l'Élu** (comme le Dragon Réincarné) — *le joueur ignore lequel*.
Toute la partie consiste à **découvrir son identité** et à **coaliser les royaumes** pour
qu'ils fournissent leurs armées à la lutte finale. Les royaumes peuvent poser des
**conditions** de ralliement (cf. les Aiels chez Jordan). Des **prophéties** font monter l'Élu
en puissance et jalonnent des étapes (dont la révélation de son identité).

**Certains personnages sont à la solde du mal** — le joueur ne le sait pas en les recrutant.

La partie se joue **en tours**, avec une **horloge du destin** : un nombre de tours avant le
déferlement des armées ennemies. La partie est **perdue** si l'Élu est tué, ou si le camp du
bien perd la bataille finale.

---

## 2. Piliers de design

1. **Personnages avant armées.** L'atome du jeu est le *personnage*, pas l'unité militaire.
   Le combat est un moyen, pas la fin.
2. **Information cachée & révélation graduelle.** Beaucoup de données (potentiels magiques,
   allégeance, force de l'Élu…) sont cachées et se **découvrent** en jouant.
3. **Émergence de règles simples.** *Rien n'est écrit à l'avance.* Un personnage n'a pas de
   « rôle » figé : son aptitude à un rôle **émerge** de la somme de ses caractéristiques et de
   son histoire (missions accomplies, cicatrices, réputations).
4. **L'ennemi est une main cachée.** Pas de faction miroir : le mal ourdit dans l'ombre,
   agit par ses traîtres et ses sbires, et n'apparaît qu'à la bataille finale.
5. **Rejouabilité par génération au seed.** Le monde et ses personnages sont générés à la
   création ; l'histoire **naît des choix** du joueur, pour la surprise à chaque partie.
6. **L'horloge du destin.** Un compte à rebours donne le tempo et la pression stratégique.

---

## 3. Entités du jeu

### Personnage (`Character`)
La brique centrale. **Composition, pas héritage** : un personnage *n'est pas* une unité de
combat. Il porte :
- des **caractéristiques** primaires (certaines cachées) → dérivent tout le reste ;
- un **historique / grand livre de modificateurs** : missions accomplies, cicatrices,
  réputations (par catégorie) — l'accumulation qui le façonne ;
- des **faits secrets semés au worldgen** : allégeance (bien / mal), potentiels magiques,
  et l'unique flag **Élu** ;
- un **portrait** (banque d'images) et un état de **connaissance** par attribut (cf. §5.1).

### Armée & Général
Une armée est un stack d'unités typées (infanterie, archers, cavalerie…). Un **général n'est
pas une unité** : c'est un *personnage exerçant le rôle Général*, qui applique des
**modificateurs par type d'unité** (p. ex. +archers / −guerriers), de forme et d'ampleur
dérivées de ses caractéristiques et de son histoire. Le puzzle « quel général pour quelle
composition » émerge tout seul.

### Settlement & Royaume
Hiérarchie : **campement → village → bourgade → capitale**. Chaque settlement a une
**allégeance** envers la coalition, d'éventuelles **conditions de ralliement**, et une armée
qu'il peut fournir. Les settlements se regroupent en **royaumes** qui décident, in fine, de
rejoindre (ou non) la lutte finale.

### L'Ennemi — la main de l'Ombre (« Metteur en scène »)
Contrôleur **systémique sans avatar** (sauf à la bataille finale). Trois leviers :
1. **Traîtres** — agents semés, cachés : sabotage, assassinat, détournement de royaumes.
2. **Sbires / incursions** (connus ou non) — menaces qui déclenchent les **batailles
   intermédiaires**.
3. **Escalade** — l'horloge du destin fait grossir la marée du **déferlement** final.

### Monde (`WorldState`)
Tour courant, **horloge du destin**, état de la coalition, registres des personnages /
settlements / royaumes, conditions de victoire/défaite.

### Événements & Prophéties
Moteur **data-driven réactif** : des événements se déclenchent selon l'état du monde et les
choix du joueur (pas de script figé). Ils **révèlent** des caractéristiques, appliquent des
bonus/malus, et **jalonnent** la progression (révélation de l'Élu, conditions des royaumes).
Les **prophéties** sont des arcs longs qui font monter l'Élu en puissance.

---

## 4. Boucle de jeu

- Le tour distribue à chaque personnage des **points d'action** dérivés de ses
  caractéristiques. **Se déplacer est une action** : voyager coûte du temps et de l'énergie
  (le coût dépend du terrain traversé).
- Actions typiques : **se déplacer, recruter, convaincre** (settlement / royaume), **gérer**
  une ville, **assassiner** une cible, engager un **duel**, **consulter** (cf. divineresse §5.1),
  accomplir une **mission** liée à un événement / une prophétie.
- Un personnage dans une ville ouvre une **interface d'interaction** dimensionnée par la taille
  de la ville.
- **Batailles intermédiaires** : affrontements contre les sbires de l'Ombre — sert de terrain
  d'entraînement (généraux, compositions) avant le climax.
- **Bataille finale** : set-piece **tactique** contre les armées du déferlement — l'Élu y
  affronte le big boss. C'est là que la coalition constituée paie (ou non).

---

## 5. Systèmes clés

### 5.1 Caractéristiques & révélation graduelle
Chaque attribut caché a une **valeur vraie** (semée) + un **état de connaissance** qui
**rétrécit un intervalle**. L'UI n'affiche **jamais** le chiffre : elle montre un **label**
dérivé de l'intervalle courant (`inconnu → « semble faible » → « faible » → « faible à moyen »
→ …`). L'intervalle se resserre en **exerçant le rôle**, via des **événements**, et par
l'**observation** dans le temps.

> **Exception — la divineresse.** Dans une ville spéciale, une action **payante** collapse
> l'intervalle à la **valeur exacte** d'une stat. Puits d'or + achat d'information stratégique.

Les chiffres bruts sont sinon **backlog** (affichage debug seulement).

### 5.2 Rôles émergents
Pas de rôle écrit. `aptitude(rôle) = f(caractéristiques, missions, cicatrices, réputations)`.
Chaque rôle (**Général, Diplomate, Gestionnaire, Royauté, Mage**) lit certains attributs et
agit dans son domaine. La complexité naît de règles simples appliquées à un historique riche.

### 5.3 Réputation par catégories
La réputation est **à facettes** — par **domaine** (guerrier, diplomate, mage…) et par
**royaume**. C'est le levier central de la diplomatie : convaincre un royaume dépend de la
réputation pertinente, pas d'une jauge unique.

### 5.4 Magie *(vision — mécaniques en backlog)*
Plusieurs magies coexistent : potentiels différenciés à la RdT, plus une inspiration de
*l'Art et le Vif* de Hobb (autres pistes à explorer). Le **potentiel** est une caractéristique
**cachée**, révélée par les événements. Les règles précises restent à concevoir.

### 5.5 Duels & assassinat
Bien que non-unités, les personnages peuvent **s'affronter en duel** (dérivé de certaines
caractéristiques) selon les besoins du scénario. L'**assassinat** est une **action** : on peut
tuer une cible — arme à double tranchant (un traître peut viser l'Élu ; un mauvais jugement
peut coûter cher).

### 5.6 Risque & mortalité du général
Si l'armée d'un général est attaquée et **détruite**, celui-ci a un **% de chances de mourir**.
Envoyer l'Élu au front n'est donc jamais gratuit.

---

## 6. Victoire & défaite

- **Défaite** : l'Élu est tué **ou** le camp du bien perd la **bataille finale**.
- **Victoire** : avoir coalisé assez de royaumes et **remporté la bataille finale**.
- L'**horloge du destin** borne la partie : le déferlement arrive à échéance, quel que soit
  l'état de préparation.

---

## 7. Roadmap

Migration **incrémentale** : le repo reste jouable à chaque phase. Le wargame tactique existant
n'est jamais supprimé — il est encapsulé, puis réutilisé pour les batailles.

- **Phase 0 — Cadrage & doc.** *(en cours)* Figer la vision, homogénéiser la doc.
- **Phase 1 — Fondations.** Terminer le découplage Pygame et introduire un `BattleResolver`
  (auto-résolution *ou* tactique) pour rendre le combat appelable sans ouvrir de fenêtre.
- **Phase 2 — Le personnage.** `Character` (composition), génération au seed (attributs cachés,
  Élu, traîtres), couche `vrai` / `connu` (§5.1).
- **Phase 3 — Boucle d'actions.** Remplacer « sélectionne armée → bouge » par « sélectionne
  perso → points d'action » (déplacer / recruter / convaincre…).
- **Phase 4 — Settlements & diplomatie.** Hiérarchie des villes, allégeance, conditions de
  ralliement, interface de ville.
- **Phase 5 — Moteur narratif.** Événements + prophéties data-driven, révélation graduelle,
  horloge du destin, l'ennemi « Metteur en scène ».
- **Phase 6 — Bataille finale.** Rebrancher le tactique comme climax.

---

## 8. Questions ouvertes (à trancher en avançant)

- **Échelle** : nombre de personnages de départ, nombre de tours avant le déferlement, taille
  du monde, nombre de royaumes. *(Paramètres à régler.)*
- **Points d'action** : formule exacte à partir des caractéristiques.
- **Magie** : mécaniques concrètes des différentes magies (§5.4).
- **Traîtres** : conditions de bascule, de révélation d'allégeance, marge de manœuvre de l'Ombre.
- **Duel / assassinat** : modèle de risque et de résolution.
