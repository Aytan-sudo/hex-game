"""
Carte de campagne (Phase 3, volet UI) : l'état de sélection (``CampaignState``)
pilote bien la couche d'actions pure, et le rendu tourne headless (SDL dummy).
"""

import pygame

from engine.camera import Camera
from engine.hex_grid import HexGrid
from engine.rng import SeededRNG
from game.campaign_map import CampaignRenderer, CampaignState
from world.actions import destinations_accessibles, points_action_max
from world.turn import demarrer_partie
from world.worldgen import WorldGenConfig, generer_monde


def _monde_de_test():
    cfg = WorldGenConfig(
        map_width=30, map_height=30, roster_size=12, settlements_total=8,
        kingdom_count=3, starting_hand=3, exceptional_quota=2,
    )
    monde = generer_monde(SeededRNG(42), cfg)
    demarrer_partie(monde)
    return monde


def _capitale_depart(monde):
    return monde.settlement(monde.royaume(0).capitale_id).position


# --- Sélection --------------------------------------------------------------

def test_persos_joueur_est_la_main_de_depart():
    monde = _monde_de_test()
    state = CampaignState(monde)
    assert sorted(p.id for p in state.persos_joueur()) == sorted(monde.main_depart)


def test_clic_selectionne_puis_cycle_entre_cohabitants():
    monde = _monde_de_test()
    state = CampaignState(monde)
    capitale = _capitale_depart(monde)  # toute la main y démarre

    action, perso = state.clic_hex(capitale)
    assert action == "selection" and perso is not None
    premier = perso.id
    assert state.destinations  # la surbrillance est prête

    action, perso = state.clic_hex(capitale)  # re-clic = perso suivant
    assert action == "selection" and perso.id != premier


def test_clic_droit_deselectionne():
    monde = _monde_de_test()
    state = CampaignState(monde)
    state.clic_hex(_capitale_depart(monde))
    state.deselectionner()
    assert state.perso_selectionne is None and state.destinations == set()


def test_clic_hors_destination_conserve_la_selection():
    monde = _monde_de_test()
    state = CampaignState(monde)
    state.clic_hex(_capitale_depart(monde))
    hors_portee = max(monde.tiles)  # un coin de la carte, hors des PA d'un tour
    assert hors_portee not in state.destinations
    action, _ = state.clic_hex(hors_portee)
    assert action == "rien" and state.perso_selectionne is not None


# --- Déplacement & tour -----------------------------------------------------

def test_clic_sur_destination_deplace_et_consomme_les_pa():
    monde = _monde_de_test()
    state = CampaignState(monde)
    state.clic_hex(_capitale_depart(monde))
    perso = state.perso_selectionne

    cible = next(iter(state.destinations))
    action, resultat = state.clic_hex(cible)
    assert action == "deplacement" and resultat.ok
    assert perso.location == cible
    assert perso.pa_restants == points_action_max(perso) - resultat.cout
    # La surbrillance est recalculée depuis la nouvelle position / les PA restants.
    assert state.destinations == destinations_accessibles(monde, perso.id)


def test_finir_tour_rafraichit_les_destinations():
    monde = _monde_de_test()
    state = CampaignState(monde)
    state.clic_hex(_capitale_depart(monde))
    perso = state.perso_selectionne
    perso.pa_restants = 0
    state._rafraichir_destinations()
    assert state.destinations == set()

    tour = monde.tour
    state.finir_tour()
    assert monde.tour == tour + 1
    assert perso.pa_restants == points_action_max(perso)
    assert state.destinations  # de nouveau en surbrillance


# --- Recrutement (panneau de ville) ----------------------------------------

class _RngForce:
    """Stub de RNG au tirage fixé — force l'issue du recrutement."""

    def __init__(self, valeur):
        self.valeur = valeur

    def random(self):
        return self.valeur


def _avec_recrutable(monde):
    """Installe un personnage libre à la capitale de départ et le retourne."""
    libre = next(p for p in monde.personnages if p.affiliation is None)
    libre.location = _capitale_depart(monde)
    return libre


def test_recrutables_ici_liste_les_residents_libres():
    monde = _monde_de_test()
    libre = _avec_recrutable(monde)
    state = CampaignState(monde)
    state.clic_hex(_capitale_depart(monde))  # sélectionne un perso de la main
    assert libre in state.recrutables_ici()
    assert all(p.affiliation is None for p in state.recrutables_ici())


def test_recruter_depuis_l_etat_fait_grossir_la_main():
    monde = _monde_de_test()
    libre = _avec_recrutable(monde)
    state = CampaignState(monde, action_rng=_RngForce(0.0))  # toujours gagnant
    state.clic_hex(_capitale_depart(monde))
    taille_main = len(state.persos_joueur())

    resultat = state.recruter(libre.id)
    assert resultat.ok and resultat.reussite
    assert libre.affiliation == 0
    assert len(state.persos_joueur()) == taille_main + 1
    assert libre not in state.recrutables_ici()  # plus recrutable


def test_recrutement_rate_ne_change_rien_a_la_main():
    monde = _monde_de_test()
    libre = _avec_recrutable(monde)
    state = CampaignState(monde, action_rng=_RngForce(0.999))  # perd toujours
    state.clic_hex(_capitale_depart(monde))
    taille_main = len(state.persos_joueur())

    resultat = state.recruter(libre.id)
    assert resultat.ok and resultat.reussite is False
    assert libre.affiliation is None
    assert len(state.persos_joueur()) == taille_main


# --- Diplomatie (bloc royaume du panneau) -----------------------------------

def test_royaume_ici_et_convaincre():
    monde = _monde_de_test()
    state = CampaignState(monde, action_rng=_RngForce(0.0))  # toujours gagnant
    state.clic_hex(_capitale_depart(monde))

    royaume = state.royaume_ici()
    assert royaume is monde.royaume(0)
    assert royaume.rallie                    # le royaume de départ est acquis d'office
    assert not state.convaincre().ok         # rien à plaider chez soi

    # Chez un royaume qui reste à convaincre : la disposition monte.
    royaume.rallie = False
    royaume.disposition = 10
    resultat = state.convaincre()
    assert resultat.ok and resultat.reussite
    assert royaume.disposition > 10


# --- Rendu (fumée, SDL dummy) ----------------------------------------------

def test_render_frame_headless():
    monde = _monde_de_test()
    _avec_recrutable(monde)  # le panneau de ville doit se dessiner aussi
    state = CampaignState(monde)
    state.clic_hex(_capitale_depart(monde))

    screen = pygame.display.get_surface()
    renderer = CampaignRenderer(screen, pygame.font.Font(None, 24))
    camera = Camera(screen.get_width(), screen.get_height())
    grid = HexGrid(hex_size=camera.hex_size, pointy_top=True)
    renderer.render_frame(state, camera, grid, hover_hex=None,
                          message="test", message_timer=1.0)
    # Le résumé de ville expose son bouton « Entrer » au clic.
    assert renderer.bouton_entrer is not None
    assert renderer.entrer_clique(renderer.bouton_entrer.center)
