# CLAUDE.md

Guidance for Claude Code (and any AI agent) working in this repository.

## Documentation maintenance — IMPORTANT

`README_DEV.md` is the **living developer guide** for this project (architecture, flux
d'exécution, classes clés, "guide par fonctionnalité", conventions). It is the source of
truth for *how the code is organized*.

**You must keep `README_DEV.md` in sync with the code.** Whenever a change affects:

- the module/file layout (`engine/`, `game/`),
- a key class or its responsibilities,
- the execution flow (`main.py` → strategic → tactical),
- combat / pathfinding / AI / terrain mechanics described in the guide,
- the configuration surface in `game/config.py`,

→ update the relevant section of `README_DEV.md` **in the same change**. Do not let it drift.

`AUDIT.md` is different: it is a **dated, historical snapshot** of a code/design review.
Do not rewrite its findings — at most update its "Suivi des corrections" status table when
an audit item is resolved.

## Conventions

- Code style and naming: see the "Conventions" section of `README_DEV.md`.
- Comments and docstrings in this project are written in **French**; match the surrounding style.

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

There is no automated test suite yet (see `AUDIT.md` §4 reco 12). Until one exists, verify
changes with the import checks above and, for gameplay logic, a focused headless script
(`SDL_VIDEODRIVER=dummy uv run python ...`).
