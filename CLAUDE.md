# CLAUDE.md

Guidance for Claude Code (and any AI agent) working in this repository.

## Changement de cap — IMPORTANT

Le projet **pivote** d'un wargame hexagonal vers un **jeu de gestion de personnages et de
royaumes** (inspiré de la *Roue du Temps* / Robin Hobb). La couche de combat tactique existante
est **conservée mais rétrogradée** (batailles intermédiaires + finale). La vision, les entités
cibles et la roadmap font foi dans [`PROJET.md`](PROJET.md) — lis-le avant tout travail de
gameplay.

## Les documents (et lequel maintenir)

- **`PROJET.md`** — source de vérité de **l'intention** (vision, entités, boucle de jeu,
  systèmes, roadmap). À mettre à jour quand la *direction* ou la *conception* évolue.
- **`README_DEV.md`** — **guide développeur vivant** : source de vérité de *comment le code est
  organisé aujourd'hui*. Il décrit le **code réel**, pas la cible — ne pas y documenter des
  modules qui n'existent pas encore (la cible vit dans `PROJET.md`).
- **`docs/archive/`** — instantanés datés historiques (ex. `AUDIT.md`). **Ne pas réécrire** ;
  au plus mettre à jour un tableau de suivi.

**Tu dois garder `README_DEV.md` synchronisé avec le code.** Quand un changement touche :

- le découpage modules/fichiers (`engine/`, `game/`),
- une classe clé ou ses responsabilités,
- le flux d'exécution,
- les mécaniques combat / pathfinding / IA / terrain décrites dans le guide,
- la surface de configuration dans `game/config.py`,

→ mets à jour la section concernée de `README_DEV.md` **dans le même changement**. Ne le laisse
pas dériver. Si le changement fait avancer la roadmap, reflète-le aussi dans `PROJET.md`.

## Conventions

- Code style and naming: see the "Conventions" section of `README_DEV.md`.
- Comments and docstrings in this project are written in **French**; match the surrounding style.
- **Dépôt public : pas de mention de co-authoring avec Claude.** N'ajoute aucune ligne
  `Co-Authored-By: Claude ...` ni « 🤖 Generated with Claude Code » dans les messages de
  commit, les descriptions de PR, ou tout autre contenu poussé sur ce dépôt.

## Environment

The project uses **[uv](https://docs.astral.sh/uv/)** (deps in `pyproject.toml`, locked in
`uv.lock`, Python pinned via `.python-version`). Use `uv run` instead of activating a venv.

## Quick checks

```bash
uv sync   # ensure the environment is installed

# Imports
uv run python -c "from game.terrain import TerrainType; print('OK')"
uv run python -c "from game.ai import AIPlayer, TacticalAI; print('OK')"
uv run python -c "from game.tactical_map import TacticalBattle; print('OK')"

# Run the game
uv run python game/main.py
```

Une suite `pytest` existe (`tests/`, lancée par `uv run pytest`, headless via
`SDL_VIDEODRIVER=dummy`). Vérifie tes changements avec elle, les checks d'import ci-dessus, et —
pour la logique de gameplay — un script headless ciblé (`SDL_VIDEODRIVER=dummy uv run python ...`).
