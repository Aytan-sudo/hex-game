"""
Actions de personnage (Phase 3) — la brique « sélectionne perso → points d'action ».

Couche **pure et headless** : les fonctions lisent et font évoluer un
``WorldState`` (PROJET.md §4), sans Pygame ni entrée/sortie. L'UI stratégique
ne fera qu'appeler ces fonctions.

**Formule des points d'action** (tranche la question ouverte PROJET §8) :

    PA = PA_BASE + Vigueur // PA_PALIER_VIGUEUR        # soit 4..9 pour 0..100

La Vigueur est *la* caractéristique d'endurance (§5.2) : le moteur lit la
``true_value`` (le joueur, lui, ne voit que le label, §5.1). Ordre de
grandeur : un personnage moyen (Vigueur ~50) dispose de 6 PA, soit ~6 cases
de plaine ou 3 de forêt par tour — voyager coûte du temps (§4).

Seule action codée ici : **se déplacer** (le coût dépend du terrain traversé,
via ``Tile.get_movement_cost()`` et le pathfinding hexagonal). Les suivantes
(recruter, convaincre, gérer…) s'ajouteront sur la même forme :
valider → appliquer → ``ResultatAction``.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from engine.pathfinding import calculate_valid_moves, find_path
from world.character import Character, Trait
from world.world_state import WorldState

# Boutons d'équilibrage de la formule des PA (à rééquilibrer en jouant).
PA_BASE: int = 4
PA_PALIER_VIGUEUR: int = 20


def points_action_max(perso: Character) -> int:
    """PA distribués à ce personnage en début de tour (dérivés de la Vigueur)."""
    vigueur = perso.caracteristiques[Trait.VIGUEUR].true_value
    return PA_BASE + vigueur // PA_PALIER_VIGUEUR


@dataclass
class ResultatAction:
    """
    Issue d'une action : succès + coût payé, ou refus motivé (``erreur``).
    Un refus n'a **jamais** modifié l'état du monde. ``cout``/``chemin`` sont
    renseignés dès qu'ils sont calculables (même sur refus, pour l'UI).
    """
    ok: bool
    cout: int = 0
    erreur: Optional[str] = None
    chemin: Optional[List[Tuple[int, int]]] = None


def deplacer(world: WorldState, perso_id: int, destination: Tuple[int, int]) -> ResultatAction:
    """
    Déplace un personnage vers ``destination`` (q, r) en consommant ses PA.

    Le coût est la somme des ``get_movement_cost()`` des cases traversées le
    long du chemin optimal (Dijkstra). Se déplacer sur place est un no-op à
    coût nul.
    """
    perso = world.personnage(perso_id)
    if perso.location is None:
        return ResultatAction(ok=False, erreur="personnage hors carte")
    if destination not in world.tiles:
        return ResultatAction(ok=False, erreur="destination hors carte")
    if not world.tiles[destination].is_passable:
        return ResultatAction(ok=False, erreur="destination infranchissable")

    depart = perso.location
    if destination == depart:
        return ResultatAction(ok=True, cout=0, chemin=[depart])

    chemin = find_path(depart, destination, world.tiles)
    if chemin is None:
        return ResultatAction(ok=False, erreur="aucun chemin")

    cout = sum(world.tiles[pos].get_movement_cost() for pos in chemin[1:])
    if cout > perso.pa_restants:
        return ResultatAction(
            ok=False, cout=cout, chemin=chemin,
            erreur=f"points d'action insuffisants ({perso.pa_restants} PA, coût {cout})",
        )

    perso.location = destination
    perso.pa_restants -= cout
    return ResultatAction(ok=True, cout=cout, chemin=chemin)


def destinations_accessibles(world: WorldState, perso_id: int) -> Set[Tuple[int, int]]:
    """
    Hexes atteignables avec les PA restants (pour l'UI : surbrillance).

    À l'échelle stratégique, un personnage ne bloque pas une case (une ville
    héberge tout le monde) : tout hex franchissable est destination valide.
    """
    perso = world.personnage(perso_id)
    if perso.location is None:
        return set()
    return calculate_valid_moves(
        start=perso.location,
        movement_remaining=perso.pa_restants,
        tiles=world.tiles,
        can_move_to=lambda tile, pos: True,
        can_pass_through=lambda tile: True,
    )
