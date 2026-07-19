"""
Missions (Phase 4→5) : lancement (validations, PA consommés, indisponibilité),
compte à rebours et résolution par tirage collectif (porteur + soutien +
affinité), liens d'amitié renforcés, annonces remontées par la fin de tour.
"""

from engine.hex_grid import HexCoord
from engine.tile import Tile
from game.terrain import TerrainType
from world.actions import points_action_max
from world.character import Trait, nouveau_character
from world.missions import (
    DUREE_RECRUTEMENT,
    EQUIPE_MAX,
    affinite,
    avancer_missions,
    chance_mission,
    lancer_mission,
    missions_possibles,
)
from world.turn import demarrer_partie, finir_tour
from world.world_state import WorldState


class _RngForce:
    """Stub de RNG au tirage fixé — force l'issue des résolutions."""

    def __init__(self, valeur):
        self.valeur = valeur

    def random(self):
        return self.valeur


def _monde(nb_main=2, charisme=50):
    """Un hex, ``nb_main`` persos de la main et une cible libre, tous en (0,0)."""
    tiles = {(0, 0): Tile(position=HexCoord(0, 0), base_terrain=TerrainType.PLAINS)}
    persos = [
        nouveau_character(
            i, f"Main{i}",
            valeurs={Trait.VIGUEUR: 40, Trait.CHARISME: charisme, Trait.CHANCE: 50},
            location=(0, 0), affiliation=0,
        )
        for i in range(nb_main)
    ]
    cible = nouveau_character(
        nb_main, "Cible", valeurs={t: 50 for t in Trait}, location=(0, 0),
    )
    monde = WorldState(seed=0, tiles=tiles, personnages=persos + [cible],
                       settlements=[], royaumes=[])
    demarrer_partie(monde)
    return monde, cible


# --- Panoplie & lancement ----------------------------------------------------

def test_missions_possibles_liste_les_recrutements():
    monde, cible = _monde()
    possibles = missions_possibles(monde, (0, 0))
    assert [p.cible_id for p in possibles] == [cible.id]
    assert possibles[0].duree == DUREE_RECRUTEMENT


def test_lancement_consomme_les_pa_et_rend_indisponible():
    monde, cible = _monde()
    resultat = lancer_mission(monde, "recrutement", (0, 0), [0, 1], cible.id)
    assert resultat.ok
    for pid in (0, 1):
        assert monde.personnage(pid).mission_id is not None
        assert monde.personnage(pid).pa_restants == 0
    # La cible n'est plus proposée (déjà courtisée).
    assert missions_possibles(monde, (0, 0)) == []
    # La distribution de PA du tour suivant les laisse à zéro.
    finir_tour(monde, _RngForce(0.0))
    assert monde.personnage(0).pa_restants == 0


def test_lancement_refuse_sans_effet_de_bord():
    monde, cible = _monde()
    assert not lancer_mission(monde, "inconnu", (0, 0), [0], cible.id).ok
    assert not lancer_mission(monde, "recrutement", (0, 0), [], cible.id).ok
    assert not lancer_mission(monde, "recrutement", (0, 0), [0] * (EQUIPE_MAX + 1),
                              cible.id).ok
    monde.personnage(1).location = (9, 9)  # plus sur place
    assert "sur place" in lancer_mission(
        monde, "recrutement", (0, 0), [0, 1], cible.id
    ).erreur
    assert monde.missions == [] and monde.personnage(0).mission_id is None
    monde.personnage(1).location = (0, 0)

    lancer_mission(monde, "recrutement", (0, 0), [0], cible.id)
    assert "déjà en mission" in lancer_mission(
        monde, "recrutement", (0, 0), [0], cible.id
    ).erreur
    assert "déjà courtisé" in lancer_mission(
        monde, "recrutement", (0, 0), [1], cible.id
    ).erreur


# --- Résolution --------------------------------------------------------------

def test_mission_se_resout_apres_sa_duree():
    monde, cible = _monde()
    lancer_mission(monde, "recrutement", (0, 0), [0, 1], cible.id)

    resultats = finir_tour(monde, _RngForce(0.0))   # tour 1 : encore en route
    assert resultats == [] and monde.missions

    resultats = finir_tour(monde, _RngForce(0.0))   # tour 2 : échéance, gagné
    assert len(resultats) == 1 and resultats[0].reussite
    assert "rejoint votre main" in resultats[0].message
    assert cible.affiliation == 0
    assert monde.missions == []
    # L'équipe est libérée ET redotée en PA dès ce tour.
    assert monde.personnage(0).mission_id is None
    assert monde.personnage(0).pa_restants == points_action_max(monde.personnage(0))


def test_echec_libere_et_soude_quand_meme():
    monde, cible = _monde()
    lancer_mission(monde, "recrutement", (0, 0), [0, 1], cible.id)
    finir_tour(monde, _RngForce(0.999))
    resultats = finir_tour(monde, _RngForce(0.999))  # au-dessus du plafond : perdu
    assert not resultats[0].reussite
    assert cible.affiliation is None                 # pas recrutée…
    assert affinite(monde, 0, 1) == 1                # …mais l'épreuve a soudé


# --- Tirage collectif : soutien & affinité -----------------------------------

def test_le_soutien_des_coequipiers_ameliore_le_tirage():
    monde, cible = _monde(nb_main=2)
    lancer_mission(monde, "recrutement", (0, 0), [0], cible.id)
    solo = chance_mission(monde, monde.missions[0])
    duo_monde, duo_cible = _monde(nb_main=2)
    lancer_mission(duo_monde, "recrutement", (0, 0), [0, 1], duo_cible.id)
    duo = chance_mission(duo_monde, duo_monde.missions[0])
    assert duo > solo


def test_l_affinite_ameliore_le_tirage():
    monde, cible = _monde(nb_main=2)
    lancer_mission(monde, "recrutement", (0, 0), [0, 1], cible.id)
    sans_lien = chance_mission(monde, monde.missions[0])
    monde.liens[(0, 1)] = 5  # vieux compagnons
    avec_lien = chance_mission(monde, monde.missions[0])
    assert avec_lien > sans_lien
