"""
Moteur de tour (Phase 3) — le tempo de la campagne.

Distribue en début de tour les **points d'action** de chaque personnage
(PROJET.md §4), avance le compteur de tours et décrémente l'**horloge du
destin** (§1, §6). Pur et headless, comme ``world/actions.py``.

Le déferlement lui-même (horloge à 0) est du ressort du moteur narratif
(Phase 5) : ici on ne fait que tenir le compte.
"""

from __future__ import annotations

from world.actions import points_action_max, verifier_ralliement
from world.world_state import WorldState


def distribuer_points_action(world: WorldState) -> None:
    """Redonne à chaque personnage son plein de PA (début de tour)."""
    for perso in world.personnages:
        perso.pa_restants = points_action_max(perso)


def demarrer_partie(world: WorldState) -> None:
    """Prépare un ``WorldState`` fraîchement généré pour le tour 1."""
    distribuer_points_action(world)


def finir_tour(world: WorldState) -> None:
    """Clôt le tour courant et amorce le suivant."""
    world.tour += 1
    world.horloge_du_destin = max(0, world.horloge_du_destin - 1)
    # Une condition de ralliement peut s'être remplie entre-temps (renom gagné
    # ailleurs) : on revérifie les royaumes à disposition pleine.
    for royaume in world.royaumes:
        verifier_ralliement(world, royaume)
    distribuer_points_action(world)
