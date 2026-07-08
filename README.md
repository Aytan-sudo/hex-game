# Hex-Game

Jeu de **gestion de personnages et de royaumes** au tour par tour, sur carte hexagonale
(Python + Pygame). Le joueur mène quelques personnages sur la carte du monde, découvre lequel
est l'**Élu**, et coalise les royaumes pour la lutte finale contre l'Ombre avant le déferlement
de ses armées. Librement inspiré de la *Roue du Temps* et de *l'Art et le Vif* de Robin Hobb.

> ⚠️ Le projet **change de cap** : d'un wargame hexagonal vers ce jeu de personnages. La couche
> de combat tactique existante est conservée mais rétrogradée (batailles intermédiaires + finale).

## Documentation

- [`PROJET.md`](PROJET.md) — **vision & conception** (le *quoi* et le *pourquoi*) + roadmap.
- [`README_DEV.md`](README_DEV.md) — **guide de développement vivant** (le *comment* : archi, flux, conventions).
- [`CLAUDE.md`](CLAUDE.md) — instructions pour les agents IA.
- [`docs/archive/`](docs/archive/) — instantanés historiques (ex. `AUDIT.md`).

## Installation & lancement

Le projet utilise **[uv](https://docs.astral.sh/uv/)**.

```bash
uv sync                       # installe l'environnement
uv run python game/main.py    # lance le jeu
uv run pytest                 # tests
```
