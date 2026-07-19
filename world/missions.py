"""
Missions (Phase 4→5) — le levier essentiel de l'action des personnages sur le
monde : à terme, le cœur du jeu.

Une mission se **lance depuis une case** (la panoplie dépend du lieu — une
ville en offre naturellement plus qu'un hex sauvage), avec une **équipe** de
1 à ``EQUIPE_MAX`` participants qui deviennent **indisponibles** (PA à zéro,
pas de déplacement, pas de sélection) pendant ``tours_restants`` tours. Le
lancement consomme les PA restants des participants : ils s'y consacrent.

À échéance (``avancer_missions``, appelée par la fin de tour), un **tirage
collectif** décide de l'issue :

- le **porteur** est le participant au meilleur *trait porteur* de
  l'archétype (recrutement → Charisme) ;
- chaque coéquipier ajoute un **soutien** dérivé de son propre trait ;
- les **liens d'amitié** entre participants bonifient le tirage — et chaque
  mission vécue ensemble renforce ces liens (échec compris : l'épreuve
  partagée soude). C'est la fondation du système de compagnons —
  complémentarité, rancunes et événements s'y grefferont en Phase 5.

Un seul archétype pour l'instant : **recrutement** (2 tours) — l'ancienne
action instantanée devient le tirage porteur de la mission. Les archétypes
suivants (espionnage, assassinat, vol de relique…) et les **missions à
objectif lointain** (« va voir si X est prisonnier là-bas et sauve-le »)
arriveront avec la Phase 5 : le modèle est déjà positionnel pour les
accueillir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

from engine.rng import SeededRNG
from world.actions import (
    ResultatAction,
    TIRAGE_PLAFOND,
    TIRAGE_PLANCHER,
    chance_recrutement,
)
from world.character import Trait
from world.world_state import WorldState

# Boutons d'équilibrage des missions.
EQUIPE_MAX: int = 3
DUREE_RECRUTEMENT: int = 2       # tours
POIDS_SOUTIEN: float = 0.08      # apport max d'un coéquipier (trait à 100)
POIDS_AFFINITE: float = 0.02     # apport de chaque point d'affinité d'une paire

# Trait porteur par archétype de mission.
TRAIT_PORTEUR = {"recrutement": Trait.CHARISME}


@dataclass
class Mission:
    """Une mission en cours — vit dans ``WorldState.missions``."""
    id: int
    type: str
    position: Tuple[int, int]
    participants: List[int]
    tours_restants: int
    cible_id: Optional[int] = None   # recrutement : le résident convoité


@dataclass
class MissionPossible:
    """Descripteur d'une mission lançable depuis une case (pour l'UI)."""
    type: str
    libelle: str
    duree: int
    cible_id: Optional[int] = None


@dataclass
class ResultatMission:
    """Issue d'une mission résolue, remontée par la fin de tour."""
    mission: Mission
    reussite: bool
    message: str


# =============================================================================
# LIENS D'AMITIÉ — l'embryon du système de compagnons
# =============================================================================

def _paire(a: int, b: int) -> Tuple[int, int]:
    return (a, b) if a < b else (b, a)


def affinite(world: WorldState, a: int, b: int) -> int:
    """Affinité entre deux personnages (0 = ils ne se connaissent pas)."""
    return world.liens.get(_paire(a, b), 0)


def _renforcer_liens(world: WorldState, participants: List[int]) -> None:
    """+1 d'affinité par paire : l'épreuve partagée soude, succès ou non."""
    for i, a in enumerate(participants):
        for b in participants[i + 1:]:
            world.liens[_paire(a, b)] = world.liens.get(_paire(a, b), 0) + 1


# =============================================================================
# LANCEMENT
# =============================================================================

def missions_possibles(world: WorldState, pos: Tuple[int, int]) -> List[MissionPossible]:
    """
    La panoplie de missions lançables depuis cette case. Aujourd'hui :
    recruter chaque résident libre du lieu ; les archétypes suivants
    s'ajouteront ici (et une ville en offrira toujours plus qu'un hex nu).
    """
    possibles: List[MissionPossible] = []
    for perso in world.personnages:
        deja_courtise = any(
            m.type == "recrutement" and m.cible_id == perso.id for m in world.missions
        )
        if perso.location == pos and perso.affiliation is None and not deja_courtise:
            possibles.append(MissionPossible(
                type="recrutement",
                libelle=f"Recruter {perso.nom}",
                duree=DUREE_RECRUTEMENT,
                cible_id=perso.id,
            ))
    return possibles


def lancer_mission(
    world: WorldState,
    type: str,
    pos: Tuple[int, int],
    participants: List[int],
    cible_id: Optional[int] = None,
) -> ResultatAction:
    """
    Lance une mission depuis ``pos`` avec ``participants`` (membres de la main,
    sur place, disponibles). Consomme leurs PA restants et les rend
    indisponibles jusqu'à la résolution.
    """
    if type not in TRAIT_PORTEUR:
        return ResultatAction(ok=False, erreur=f"archétype inconnu : {type}")
    if not 1 <= len(participants) <= EQUIPE_MAX:
        return ResultatAction(ok=False, erreur=f"équipe de 1 à {EQUIPE_MAX} requise")
    if len(set(participants)) != len(participants):
        return ResultatAction(ok=False, erreur="participants en double")

    for pid in participants:
        perso = world.personnage(pid)
        if perso.affiliation != 0:
            return ResultatAction(ok=False, erreur=f"{perso.nom} n'est pas des vôtres")
        if perso.location != pos:
            return ResultatAction(ok=False, erreur=f"{perso.nom} n'est pas sur place")
        if perso.mission_id is not None:
            return ResultatAction(ok=False, erreur=f"{perso.nom} est déjà en mission")

    if type == "recrutement":
        cible = world.personnage(cible_id)
        if cible.location != pos or cible.affiliation is not None:
            return ResultatAction(ok=False, erreur="cible introuvable ici")
        if any(m.type == "recrutement" and m.cible_id == cible_id
               for m in world.missions):
            return ResultatAction(ok=False, erreur=f"{cible.nom} est déjà courtisé")

    mission = Mission(
        id=world.prochaine_mission_id,
        type=type,
        position=pos,
        participants=list(participants),
        tours_restants=DUREE_RECRUTEMENT,
        cible_id=cible_id,
    )
    world.prochaine_mission_id += 1
    world.missions.append(mission)
    for pid in participants:
        perso = world.personnage(pid)
        perso.mission_id = mission.id
        perso.pa_restants = 0  # ils s'y consacrent
    return ResultatAction(ok=True)


# =============================================================================
# RÉSOLUTION — le tirage collectif
# =============================================================================

def chance_mission(world: WorldState, mission: Mission) -> float:
    """
    Probabilité (bornée) de réussite : le tirage du **porteur** + le soutien
    des coéquipiers + les liens d'affinité de l'équipe.
    """
    trait = TRAIT_PORTEUR[mission.type]
    persos = [world.personnage(pid) for pid in mission.participants]
    porteur = max(persos, key=lambda p: p.caracteristiques[trait].true_value)

    if mission.type == "recrutement":
        base = chance_recrutement(porteur, world.personnage(mission.cible_id))
    else:  # pragma: no cover — garde-fou pour les archétypes à venir
        base = 0.5

    soutien = sum(
        p.caracteristiques[trait].true_value / 100 * POIDS_SOUTIEN
        for p in persos if p is not porteur
    )
    liens = POIDS_AFFINITE * sum(
        affinite(world, a, b)
        for i, a in enumerate(mission.participants)
        for b in mission.participants[i + 1:]
    )
    return min(TIRAGE_PLAFOND, max(TIRAGE_PLANCHER, base + soutien + liens))


def _appliquer(world: WorldState, mission: Mission, reussite: bool) -> str:
    """Applique les effets d'une mission résolue et rend le message d'annonce."""
    if mission.type == "recrutement":
        cible = world.personnage(mission.cible_id)
        if reussite:
            cible.affiliation = 0
            return f"{cible.nom} rejoint votre main !"
        return f"{cible.nom} décline votre offre."
    return "mission achevée"  # pragma: no cover


def avancer_missions(
    world: WorldState, rng: Optional[SeededRNG] = None
) -> List[ResultatMission]:
    """
    Fait avancer d'un tour toutes les missions en cours et **résout** celles à
    échéance : tirage, effets, liens renforcés, participants libérés. Sans
    ``rng`` fourni, un sous-flux déterministe est dérivé du seed du monde et
    du tour courant (reproductible).
    """
    if rng is None:
        rng = SeededRNG(world.seed).derive(f"missions:{world.tour}")

    resultats: List[ResultatMission] = []
    for mission in list(world.missions):
        mission.tours_restants -= 1
        if mission.tours_restants > 0:
            continue

        reussite = rng.random() < chance_mission(world, mission)
        message = _appliquer(world, mission, reussite)
        _renforcer_liens(world, mission.participants)
        for pid in mission.participants:
            world.personnage(pid).mission_id = None
        world.missions.remove(mission)
        resultats.append(ResultatMission(mission=mission, reussite=reussite,
                                         message=message))
    return resultats
