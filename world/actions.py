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

Actions codées ici, toutes sur la même forme valider → appliquer →
``ResultatAction`` :

- **se déplacer** — le coût dépend du terrain traversé, via
  ``Tile.get_movement_cost()`` et le pathfinding hexagonal ;
- **recruter** — tirage semé : Charisme du recruteur contre l'**exigence** du
  recruté (dérivée de son calibre), infléchi par la Chance (§5.2). L'échec
  est possible et **coûte quand même les PA** (la tentative prend du temps).

Les suivantes (convaincre, gérer…) s'ajouteront sur le même patron.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Set, Tuple

from engine.pathfinding import calculate_valid_moves, find_path
from engine.rng import SeededRNG
from world.character import Character, Trait
from world.world_state import WorldState

# Boutons d'équilibrage de la formule des PA (à rééquilibrer en jouant).
PA_BASE: int = 4
PA_PALIER_VIGUEUR: int = 20

# Boutons d'équilibrage du recrutement.
PA_COUT_RECRUTEMENT: int = 2
RECRUTEMENT_BASE: int = 50           # points de % quand Charisme == exigence
RECRUTEMENT_POIDS_CHANCE: float = 0.2  # la Chance infléchit de ±10 points max
RECRUTEMENT_PLANCHER: float = 0.05   # jamais impossible…
RECRUTEMENT_PLAFOND: float = 0.95    # …jamais garanti


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
    # Issue du tirage pour les actions à réussite incertaine (recruter…) :
    # None = sans objet, sinon True/False. Un échec de tirage reste ok=True
    # (l'action a bien été tentée, les PA sont dépensés).
    reussite: Optional[bool] = None


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


# =============================================================================
# RECRUTER — grossir la main (PROJET §4 ; Charisme = levier, §5.2)
# =============================================================================

def exigence_recrutement(cible: Character) -> int:
    """
    Ce que « vaut » la cible à ses propres yeux : la moyenne de ses
    caractéristiques vraies (0-100). Approxime le calibre du worldgen sans le
    stocker — plus un personnage est doué, plus il se fait désirer.
    """
    valeurs = [hv.true_value for hv in cible.caracteristiques.values()]
    return round(sum(valeurs) / len(valeurs))


def chance_recrutement(recruteur: Character, cible: Character) -> float:
    """
    Probabilité (bornée) de réussite d'une tentative de recrutement :
    50 % à Charisme == exigence, ±1 point de % par point d'écart, la Chance
    du recruteur infléchissant le tout de ±10 points (§5.2 : elle « infléchit
    les tirages »). Le moteur lit les vraies valeurs ; l'UI n'en montre
    qu'un libellé grossier.
    """
    charisme = recruteur.caracteristiques[Trait.CHARISME].true_value
    chance = recruteur.caracteristiques[Trait.CHANCE].true_value
    points = (RECRUTEMENT_BASE
              + (charisme - exigence_recrutement(cible))
              + (chance - 50) * RECRUTEMENT_POIDS_CHANCE)
    return min(RECRUTEMENT_PLAFOND, max(RECRUTEMENT_PLANCHER, points / 100))


def recruter(
    world: WorldState, rng: SeededRNG, recruteur_id: int, cible_id: int
) -> ResultatAction:
    """
    Tente de rallier ``cible`` à la main du joueur. Il faut être **sur place**
    (là où la cible réside) et payer ``PA_COUT_RECRUTEMENT``, que le tirage
    réussisse ou non — la tentative prend du temps. Recrutée, la cible passe
    ``affiliation=0`` (son allégeance secrète, elle, ne change pas : les
    traîtres se recrutent comme les autres).
    """
    recruteur = world.personnage(recruteur_id)
    cible = world.personnage(cible_id)

    if recruteur.location is None or recruteur.location != cible.location:
        return ResultatAction(ok=False, erreur="la cible n'est pas sur place")
    if cible.affiliation == 0:
        return ResultatAction(ok=False, erreur="déjà dans votre main")
    if cible.affiliation is not None:
        return ResultatAction(ok=False, erreur="engagé ailleurs")
    if recruteur.pa_restants < PA_COUT_RECRUTEMENT:
        return ResultatAction(
            ok=False,
            erreur=(f"points d'action insuffisants "
                    f"({recruteur.pa_restants} PA, coût {PA_COUT_RECRUTEMENT})"),
        )

    recruteur.pa_restants -= PA_COUT_RECRUTEMENT
    reussite = rng.random() < chance_recrutement(recruteur, cible)
    if reussite:
        cible.affiliation = 0
    return ResultatAction(ok=True, cout=PA_COUT_RECRUTEMENT, reussite=reussite)
