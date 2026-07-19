"""
Écran de ville (Phase 4) : onglets pilotés par le lieu (la taille *se sent*),
colonne des présents (changement d'acteur), actions recruter/convaincre
traversées, rendu headless (SDL dummy).
"""

import pygame

from engine.rng import SeededRNG
from game.campaign_map import CampaignState
from game.ville_ui import VilleScreen, libelle_onglet, onglets_du_lieu
from world.settlement import Settlement, TailleSettlement
from world.turn import demarrer_partie
from world.worldgen import WorldGenConfig, generer_monde


class _RngForce:
    """Stub de RNG au tirage fixé — force l'issue des actions."""

    def __init__(self, valeur):
        self.valeur = valeur

    def random(self):
        return self.valeur


def _lieu(taille, particularites=None):
    return Settlement(id=0, nom="Essai", position=(0, 0), taille=taille,
                      royaume_id=0, particularites=particularites or [])


def _etat_en_ville():
    """Un monde généré, la main sélectionnée à la capitale, une recrue sur place."""
    cfg = WorldGenConfig(
        map_width=30, map_height=30, roster_size=12, settlements_total=8,
        kingdom_count=3, starting_hand=3, exceptional_quota=2,
    )
    monde = generer_monde(SeededRNG(42), cfg)
    demarrer_partie(monde)
    state = CampaignState(monde, action_rng=_RngForce(0.0))  # tirages gagnants
    capitale = monde.settlement(monde.royaume(0).capitale_id)
    libre = next(p for p in monde.personnages if p.affiliation is None)
    libre.location = capitale.position
    state.clic_hex(capitale.position)
    return state, capitale, libre


def _ecran(state, lieu):
    screen = pygame.display.get_surface()
    return VilleScreen(screen, pygame.font.Font(None, 24), state, lieu)


# --- Onglets pilotés par le lieu -------------------------------------------

def test_onglets_pilotes_par_le_lieu():
    assert onglets_du_lieu(_lieu(TailleSettlement.CAMPEMENT)) == ["residents"]
    assert onglets_du_lieu(_lieu(TailleSettlement.VILLAGE)) == ["residents", "audience"]
    assert onglets_du_lieu(_lieu(TailleSettlement.BOURGADE)) == \
        ["residents", "audience", "garnison"]
    assert onglets_du_lieu(_lieu(TailleSettlement.CAPITALE)) == \
        ["residents", "audience", "garnison"]


def test_onglet_special_decorrele_de_la_taille():
    # La chose la plus importante du monde peut se nicher dans un campement.
    assert "special" in onglets_du_lieu(
        _lieu(TailleSettlement.CAMPEMENT, ["la divineresse"])
    )


def test_l_audience_devient_cour_royale_a_la_capitale():
    assert libelle_onglet("audience", _lieu(TailleSettlement.VILLAGE)) == "Audience"
    assert libelle_onglet("audience", _lieu(TailleSettlement.CAPITALE)) == "Cour royale"


# --- L'écran : acteur, recrutement, audience --------------------------------

def test_changer_d_acteur_via_la_colonne_des_presents():
    state, capitale, _ = _etat_en_ville()
    ecran = _ecran(state, capitale)
    ecran.render()

    assert len(ecran.rects_presents) >= 2  # la main démarre groupée à la capitale
    rect, autre_id = next(
        (r, pid) for r, pid in ecran.rects_presents if pid != state.selected_id
    )
    ecran.clic(rect.center)
    assert state.selected_id == autre_id


def test_l_onglet_residents_est_informatif():
    # L'écran de ville informe ; recruter se lance en mission depuis la carte
    # (bouton Mission / touche M) — l'onglet n'a plus de bouton d'action.
    state, capitale, libre = _etat_en_ville()
    ecran = _ecran(state, capitale)
    ecran.render()  # onglet par défaut : résidents
    assert not hasattr(ecran, "boutons_recruter")
    assert libre.affiliation is None  # rien ne se recrute d'un simple clic ici


def test_convaincre_depuis_l_onglet_audience():
    state, capitale, _ = _etat_en_ville()
    royaume = state.world.royaume(0)
    royaume.rallie = False
    royaume.disposition = 10

    ecran = _ecran(state, capitale)
    ecran.onglet_actif = "audience"
    ecran.render()
    assert ecran.bouton_convaincre is not None
    ecran.clic(ecran.bouton_convaincre.center)
    assert royaume.disposition > 10
    assert "disposition" in ecran.message


def test_audience_d_un_royaume_rallie_est_en_repos():
    state, capitale, _ = _etat_en_ville()
    assert state.world.royaume(0).rallie  # le royaume de départ est acquis
    ecran = _ecran(state, capitale)
    ecran.onglet_actif = "audience"
    ecran.render()
    assert ecran.bouton_convaincre is None  # rien à plaider chez soi


def test_rendu_de_tous_les_onglets():
    state, capitale, _ = _etat_en_ville()
    capitale.particularites = ["la divineresse"]
    ecran = _ecran(state, capitale)
    assert ecran.onglets == ["residents", "audience", "garnison", "special"]
    for onglet in ecran.onglets:
        ecran.onglet_actif = onglet
        ecran.render()  # fumée : chaque onglet se dessine sans erreur
