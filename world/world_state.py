"""
``WorldState`` — la sortie du worldgen (PROJET.md §3, §5.7).

Structure de données **pure** : tout l'état d'une partie qui naît de la
génération, **headless** et sérialisable. Le moteur de jeu (Phase 3+) lit et fait
évoluer cet état ; la génération ne fait que le **produire**.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple

from engine.tile import Tile
from world.character import Character
from world.settlement import Settlement, Royaume


@dataclass
class WorldState:
    seed: int
    tiles: Dict[Tuple[int, int], Tile]
    personnages: List[Character]
    settlements: List[Settlement]
    royaumes: List[Royaume]

    # Main de départ du joueur + identité (cachée) de l'Élu.
    main_depart: List[int] = field(default_factory=list)
    elu_id: int = -1

    # Tempo de la partie.
    tour: int = 1
    horloge_du_destin: int = 60  # tours avant le déferlement (PROJET §1, §6)

    def personnage(self, perso_id: int) -> Character:
        return self.personnages[perso_id]

    def settlement(self, settlement_id: int) -> Settlement:
        return self.settlements[settlement_id]

    def royaume(self, royaume_id: int) -> Royaume:
        return self.royaumes[royaume_id]
