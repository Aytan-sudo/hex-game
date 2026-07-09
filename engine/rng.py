"""
Générateur pseudo-aléatoire semé, unique et **propagé**.

Corrige la dette héritée « random global » (AUDIT §2.11, PROJET §5.7). Le
problème : le code reseedait le module ``random`` *partagé* (`random.seed(...)`)
un peu partout, si bien que l'ordre des tirages d'un sous-système influait sur
la reproductibilité des autres. La correction : **chaque sous-système possède
une instance ``SeededRNG``** (état isolé) au lieu de piocher dans le module.

On peut **dériver** des sous-flux indépendants par étiquette (``derive``) : deux
couches (terrain, roster, combat…) tirées de sous-flux distincts n'interfèrent
plus — ajouter un tirage dans l'une ne décale pas l'autre. C'est la base du
worldgen déterministe en couches.

Primitive **générique** (aucune dépendance à Pygame) : elle vit dans ``engine/``
pour être utilisable par le moteur *et* par la couche campagne ``world/``.
"""

from __future__ import annotations

import hashlib
import random
from typing import List, Optional, Sequence, TypeVar

T = TypeVar("T")

_SEED_BITS = 64
_SEED_RANGE = 1 << _SEED_BITS


class SeededRNG:
    """
    Enveloppe un ``random.Random`` à l'état isolé.

    - Semé explicitement → **reproductible** (même seed ⇒ même suite).
    - Sans seed → tiré de l'entropie OS via une instance ``random.Random``
      jetable (jamais le module global partagé).
    """

    def __init__(self, seed: Optional[int] = None):
        # `seed is not None` (et pas `seed or ...`) : un seed 0 est valide.
        self.seed = seed if seed is not None else random.Random().randrange(_SEED_RANGE)
        self._rng = random.Random(self.seed)

    def derive(self, label: str) -> "SeededRNG":
        """
        Sous-flux déterministe et indépendant, nommé par ``label``.

        Le seed enfant vient d'un hash **stable** (``hashlib`` — pas ``hash()``
        de Python, salé par process) du seed parent et de l'étiquette, donc
        reproductible d'une exécution à l'autre.
        """
        digest = hashlib.sha256(f"{self.seed}:{label}".encode()).digest()
        return SeededRNG(int.from_bytes(digest[:8], "big"))

    # --- primitives (délèguent à random.Random) -----------------------------

    def random(self) -> float:
        return self._rng.random()

    def randint(self, a: int, b: int) -> int:
        return self._rng.randint(a, b)

    def randrange(self, *args: int) -> int:
        return self._rng.randrange(*args)

    def uniform(self, a: float, b: float) -> float:
        return self._rng.uniform(a, b)

    def choice(self, seq: Sequence[T]) -> T:
        return self._rng.choice(seq)

    def choices(self, population: Sequence[T], weights=None, k: int = 1) -> List[T]:
        return self._rng.choices(population, weights=weights, k=k)

    def shuffle(self, seq: List) -> None:
        self._rng.shuffle(seq)

    def sample(self, population: Sequence[T], k: int) -> List[T]:
        return self._rng.sample(population, k)

    def gauss(self, mu: float, sigma: float) -> float:
        return self._rng.gauss(mu, sigma)
