"""
Moteur de tour (Phase 3) — le tempo de la campagne.

Distribue en début de tour les **points d'action** de chaque personnage
(PROJET.md §4), avance le compteur de tours et décrémente l'**horloge du
destin** (§1, §6). Pur et headless, comme ``world/actions.py``.

Le déferlement lui-même (horloge à 0) est du ressort du moteur narratif
(Phase 5) : ici on ne fait que tenir le compte.
"""

from __future__ import annotations

from typing import List, Optional

from engine.rng import SeededRNG
from world.actions import points_action_max, verifier_ralliement
from world.missions import ResultatMission, avancer_missions
from world.world_state import WorldState


def distribuer_points_action(world: WorldState) -> None:
    """Redonne à chaque personnage son plein de PA (début de tour).

    Les personnages **en mission** restent à zéro : ils sont indisponibles.
    """
    for perso in world.personnages:
        perso.pa_restants = (
            0 if perso.mission_id is not None else points_action_max(perso)
        )


def demarrer_partie(world: WorldState) -> None:
    """Prépare un ``WorldState`` fraîchement généré pour le tour 1."""
    distribuer_points_action(world)


def finir_tour(
    world: WorldState, rng: Optional[SeededRNG] = None
) -> List[ResultatMission]:
    """
    Clôt le tour courant et amorce le suivant. Fait avancer (et résout) les
    **missions** — leurs issues sont retournées pour l'annonce — avant de
    redistribuer les PA, si bien qu'une équipe libérée peut agir dès ce tour.
    """
    world.tour += 1
    world.horloge_du_destin = max(0, world.horloge_du_destin - 1)
    resultats = avancer_missions(world, rng)
    # Une condition de ralliement peut s'être remplie entre-temps (renom gagné
    # ailleurs) : on revérifie les royaumes à disposition pleine.
    for royaume in world.royaumes:
        verifier_ralliement(world, royaume)
    distribuer_points_action(world)
    return resultats
