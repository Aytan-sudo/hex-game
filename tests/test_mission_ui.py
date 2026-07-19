"""
Panneau de mission (carte) : panoplie de la case, équipe à cocher parmi les
disponibles, lancement au travers de l'écran — headless (SDL dummy).
"""

import pygame

from engine.rng import SeededRNG
from game.campaign_map import CampaignState
from game.mission_ui import MissionScreen
from world.turn import demarrer_partie
from world.worldgen import WorldGenConfig, generer_monde


class _RngForce:
    def __init__(self, valeur):
        self.valeur = valeur

    def random(self):
        return self.valeur


def _etat_en_ville():
    cfg = WorldGenConfig(
        map_width=30, map_height=30, roster_size=12, settlements_total=8,
        kingdom_count=3, starting_hand=3, exceptional_quota=2,
    )
    monde = generer_monde(SeededRNG(42), cfg)
    demarrer_partie(monde)
    state = CampaignState(monde, action_rng=_RngForce(0.0))
    capitale = monde.settlement(monde.royaume(0).capitale_id)
    libre = next(p for p in monde.personnages if p.affiliation is None)
    libre.location = capitale.position
    state.clic_hex(capitale.position)
    return state, capitale, libre


def _ecran(state, pos):
    # Une fenêtre réaliste : le layout du panneau suppose plus que le 320×240
    # de la session de tests.
    screen = pygame.display.set_mode((1024, 768))
    return MissionScreen(screen, pygame.font.Font(None, 24), state, pos)


def test_panneau_choisit_equipe_et_lance():
    state, capitale, libre = _etat_en_ville()
    ecran = _ecran(state, capitale.position)
    assert any(p.cible_id == libre.id for p in ecran.possibles)
    assert ecran.equipe == [state.selected_id]  # l'ouvreur embarque d'office

    ecran.render()
    ecran.clic(ecran.rects_missions[0][0].center)   # choisir la mission
    assert ecran.choix == 0

    ecran.render()
    rect, coequipier = next(
        (r, pid) for r, pid in ecran.rects_equipe if pid not in ecran.equipe
    )
    ecran.clic(rect.center)                          # embarquer un coéquipier
    assert coequipier in ecran.equipe

    ecran.render()
    ecran.clic(ecran.bouton_lancer.center)           # lancer
    assert ecran.lancee is not None
    assert state.world.missions and len(state.world.missions[0].participants) == 2


def test_panneau_refuse_sans_choix():
    state, capitale, _ = _etat_en_ville()
    ecran = _ecran(state, capitale.position)
    ecran.render()
    ecran.clic(ecran.bouton_lancer.center)           # rien de choisi
    assert ecran.lancee is None and ecran.message
    assert state.world.missions == []
