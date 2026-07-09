"""
Génération de noms — personnages, settlements, royaumes.

Assemblage syllabique **semé** (déterministe via ``SeededRNG``) : variété
infinie sans grosses listes. Les noms de personnes sont légèrement genrés par
la terminaison. Placeholder honnête : pas de cultures/langues par royaume (à
enrichir plus tard), juste de quoi peupler le monde de noms plausibles.
"""

from __future__ import annotations

from engine.rng import SeededRNG
from world.character import Sexe


_DEBUTS = (
    "ar", "bel", "cor", "dae", "el", "fen", "gar", "hal", "ith", "jor",
    "kel", "lor", "mor", "nal", "or", "pel", "quen", "ral", "sel", "tor",
    "val", "wyn", "yr", "zen", "bran", "cael", "dorn", "eth", "fael", "gith",
)
_MILIEUX = ("a", "e", "i", "o", "u", "ae", "ia", "an", "or", "el", "ir", "en")
_FINS_F = ("a", "elle", "wyn", "ia", "ys", "aine", "eth", "ira", "ë", "enn")
_FINS_M = ("or", "an", "en", "us", "ar", "eth", "on", "ir", "ael", "urn")
_FINS_LIEU = ("gard", "hold", "vale", "moor", "fell", "reach", "watch", "mere",
              "ford", "crest", "haven", "march", "keep", "stead")
_FINS_ROYAUME = ("or", "ia", "eth", "mar", "gard", "land", "dor", "wyn", "ath")


def _assembler(rng: SeededRNG, fins: tuple, syllabes: int = 2) -> str:
    mot = rng.choice(_DEBUTS)
    for _ in range(syllabes - 1):
        mot += rng.choice(_MILIEUX)
    mot += rng.choice(fins)
    return mot.capitalize()


def nom_personne(rng: SeededRNG, sexe: Sexe) -> str:
    fins = _FINS_F if sexe is Sexe.FEMININ else _FINS_M
    return _assembler(rng, fins, syllabes=rng.randint(2, 3))


def nom_lieu(rng: SeededRNG) -> str:
    # Racine + suffixe de lieu (ex. « Elor-gard » → « Elorgard »).
    racine = _assembler(rng, _MILIEUX, syllabes=2)
    return (racine + rng.choice(_FINS_LIEU)).capitalize()


def nom_royaume(rng: SeededRNG) -> str:
    return _assembler(rng, _FINS_ROYAUME, syllabes=rng.randint(2, 3))
