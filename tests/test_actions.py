"""
Boucle d'actions (Phase 3) : formule des PA (dérivée de la Vigueur), moteur de
tour (distribution, horloge du destin) et action « se déplacer » (coût
dépendant du terrain traversé, refus sans effet de bord).
"""

from engine.hex_grid import HexCoord
from engine.rng import SeededRNG
from engine.tile import Tile
from game.terrain import TerrainType
from world.actions import (
    CONVAINCRE_REPUTATION_DIPLOMATE,
    CONVAINCRE_REPUTATION_ROYAUME,
    GAIN_DISPOSITION,
    PA_BASE,
    PA_COUT_CONVAINCRE,
    PA_COUT_RECRUTEMENT,
    SEUIL_RALLIEMENT,
    TIRAGE_PLAFOND,
    TIRAGE_PLANCHER,
    chance_convaincre,
    chance_recrutement,
    convaincre,
    deplacer,
    destinations_accessibles,
    exigence_recrutement,
    points_action_max,
    recruter,
    verifier_ralliement,
)
from world.settlement import ConditionRalliement, Royaume, Settlement, TailleSettlement
from world.character import Trait, nouveau_character
from world.turn import demarrer_partie, finir_tour
from world.world_state import WorldState
from world.worldgen import WorldGenConfig, generer_monde


def _tuile(q, r, terrain=TerrainType.PLAINS):
    return Tile(position=HexCoord(q, r), base_terrain=terrain)


def _monde_ligne(terrains):
    """Un monde-couloir : cases (0,0)..(n,0), et un perso (Vigueur 40) en (0,0)."""
    tiles = {(q, 0): _tuile(q, 0, t) for q, t in enumerate(terrains)}
    perso = nouveau_character(0, "Testeur", valeurs={Trait.VIGUEUR: 40}, location=(0, 0))
    return WorldState(seed=0, tiles=tiles, personnages=[perso], settlements=[], royaumes=[])


# --- Formule des points d'action -------------------------------------------

def test_points_action_derives_de_la_vigueur():
    faible = nouveau_character(0, "A", valeurs={Trait.VIGUEUR: 0})
    moyen = nouveau_character(1, "B", valeurs={Trait.VIGUEUR: 50})
    fort = nouveau_character(2, "C", valeurs={Trait.VIGUEUR: 100})
    assert points_action_max(faible) == PA_BASE
    assert points_action_max(moyen) == PA_BASE + 2
    assert points_action_max(fort) == PA_BASE + 5


# --- Moteur de tour ---------------------------------------------------------

def test_demarrer_partie_distribue_les_pa():
    monde = _monde_ligne([TerrainType.PLAINS] * 3)
    demarrer_partie(monde)
    perso = monde.personnage(0)
    assert perso.pa_restants == points_action_max(perso)


def test_finir_tour_avance_le_temps_et_redistribue():
    monde = _monde_ligne([TerrainType.PLAINS] * 4)
    demarrer_partie(monde)
    assert deplacer(monde, 0, (2, 0)).ok
    tour, horloge = monde.tour, monde.horloge_du_destin
    finir_tour(monde)
    assert monde.tour == tour + 1
    assert monde.horloge_du_destin == horloge - 1
    assert monde.personnage(0).pa_restants == points_action_max(monde.personnage(0))


def test_horloge_du_destin_ne_devient_pas_negative():
    monde = _monde_ligne([TerrainType.PLAINS])
    monde.horloge_du_destin = 0
    finir_tour(monde)
    assert monde.horloge_du_destin == 0


# --- Action « se déplacer » -------------------------------------------------

def test_deplacer_consomme_les_pa_selon_le_terrain():
    monde = _monde_ligne([TerrainType.PLAINS] * 4)
    demarrer_partie(monde)  # Vigueur 40 → 6 PA
    res = deplacer(monde, 0, (3, 0))
    assert res.ok and res.cout == 3
    assert monde.personnage(0).location == (3, 0)
    assert monde.personnage(0).pa_restants == 3


def test_deplacer_terrain_couteux():
    # Plaine puis 2 forêts (coût 2 chacune) : (0,0) → (2,0) coûte 4.
    monde = _monde_ligne([TerrainType.PLAINS, TerrainType.FOREST, TerrainType.FOREST])
    demarrer_partie(monde)
    res = deplacer(monde, 0, (2, 0))
    assert res.ok and res.cout == 4
    assert monde.personnage(0).pa_restants == 2


def test_deplacer_refuse_si_pa_insuffisants():
    monde = _monde_ligne([TerrainType.PLAINS] * 9)
    demarrer_partie(monde)  # 6 PA < 8 cases
    res = deplacer(monde, 0, (8, 0))
    assert not res.ok and "insuffisants" in res.erreur
    assert res.cout == 8                            # le coût reste montrable à l'UI
    assert monde.personnage(0).location == (0, 0)   # refus = aucun effet de bord
    assert monde.personnage(0).pa_restants == 6


def test_deplacer_refuse_hors_carte_et_infranchissable():
    monde = _monde_ligne([TerrainType.PLAINS, TerrainType.WATER, TerrainType.PLAINS])
    demarrer_partie(monde)
    assert not deplacer(monde, 0, (9, 9)).ok        # hors carte
    assert not deplacer(monde, 0, (1, 0)).ok        # l'eau est infranchissable
    assert not deplacer(monde, 0, (2, 0)).ok        # coupé du reste par l'eau
    assert monde.personnage(0).location == (0, 0)


def test_deplacer_sur_place_est_un_noop():
    monde = _monde_ligne([TerrainType.PLAINS])
    demarrer_partie(monde)
    res = deplacer(monde, 0, (0, 0))
    assert res.ok and res.cout == 0
    assert monde.personnage(0).pa_restants == points_action_max(monde.personnage(0))


def test_destinations_accessibles_coherentes():
    monde = _monde_ligne([TerrainType.PLAINS] * 9)
    demarrer_partie(monde)
    monde.personnage(0).pa_restants = 2
    assert destinations_accessibles(monde, 0) == {(1, 0), (2, 0)}


# --- Action « recruter » ----------------------------------------------------

class _RngForce:
    """Stub de RNG dont le tirage est fixé — pour tester les deux issues."""

    def __init__(self, valeur):
        self.valeur = valeur

    def random(self):
        return self.valeur


def _monde_recrutement(chance_tirage, charisme=50, exigence=50):
    """Un hex, un recruteur (6 PA) et une cible libre au même endroit."""
    tiles = {(0, 0): _tuile(0, 0)}
    recruteur = nouveau_character(
        0, "Recruteur",
        valeurs={Trait.VIGUEUR: 40, Trait.CHARISME: charisme, Trait.CHANCE: 50},
        location=(0, 0), affiliation=0,
    )
    # Toutes les caractéristiques de la cible à la même valeur ⇒ exigence = valeur.
    cible = nouveau_character(
        1, "Cible", valeurs={t: exigence for t in Trait}, location=(0, 0),
    )
    monde = WorldState(seed=0, tiles=tiles, personnages=[recruteur, cible],
                       settlements=[], royaumes=[])
    demarrer_partie(monde)
    return monde, _RngForce(chance_tirage)


def test_exigence_et_chance_de_recrutement():
    monde, _ = _monde_recrutement(0.0)
    recruteur, cible = monde.personnage(0), monde.personnage(1)
    assert exigence_recrutement(cible) == 50
    # Charisme == exigence, Chance neutre : pile 50 %.
    assert chance_recrutement(recruteur, cible) == 0.5
    # Bornes : jamais garanti, jamais impossible.
    ecrase = nouveau_character(2, "X", valeurs={t: 100 for t in Trait})
    assert chance_recrutement(ecrase, cible) == TIRAGE_PLAFOND
    assert chance_recrutement(cible, ecrase) == TIRAGE_PLANCHER


def test_recruter_reussi():
    monde, rng = _monde_recrutement(0.0)  # tirage toujours gagnant
    resultat = recruter(monde, rng, 0, 1)
    assert resultat.ok and resultat.reussite
    assert monde.personnage(1).affiliation == 0
    assert monde.personnage(0).pa_restants == points_action_max(monde.personnage(0)) - PA_COUT_RECRUTEMENT


def test_recruter_echoue_mais_coute_les_pa():
    monde, rng = _monde_recrutement(0.999)  # au-dessus du plafond : perd toujours
    resultat = recruter(monde, rng, 0, 1)
    assert resultat.ok and resultat.reussite is False
    assert monde.personnage(1).affiliation is None       # pas recrutée…
    assert monde.personnage(0).pa_restants == points_action_max(monde.personnage(0)) - PA_COUT_RECRUTEMENT


def test_recruter_refus_sans_effet_de_bord():
    monde, rng = _monde_recrutement(0.0)
    recruteur, cible = monde.personnage(0), monde.personnage(1)

    cible.location = (9, 9)                              # plus sur place
    assert not recruter(monde, rng, 0, 1).ok
    cible.location = (0, 0)

    cible.affiliation = 0                                # déjà dans la main
    assert "main" in recruter(monde, rng, 0, 1).erreur
    cible.affiliation = None

    recruteur.pa_restants = PA_COUT_RECRUTEMENT - 1      # trop fatigué
    resultat = recruter(monde, rng, 0, 1)
    assert not resultat.ok and "insuffisants" in resultat.erreur
    assert recruteur.pa_restants == PA_COUT_RECRUTEMENT - 1  # rien dépensé
    assert cible.affiliation is None


# --- Action « convaincre » & ralliement -------------------------------------

def _monde_diplomatie(chance_tirage, taille=TailleSettlement.VILLAGE,
                      disposition=50, conditions=None):
    """Un settlement d'un royaume non rallié, et un émissaire (6 PA) dessus."""
    tiles = {(0, 0): _tuile(0, 0)}
    lieu = Settlement(id=0, nom="Bourg", position=(0, 0), taille=taille, royaume_id=0)
    royaume = Royaume(id=0, nom="Essai", capitale_id=0, settlement_ids=[0],
                      disposition=disposition, conditions=conditions or [])
    emissaire = nouveau_character(
        0, "Émissaire",
        valeurs={Trait.VIGUEUR: 40, Trait.CHARISME: 50, Trait.CHANCE: 50},
        location=(0, 0), affiliation=0,
    )
    monde = WorldState(seed=0, tiles=tiles, personnages=[emissaire],
                       settlements=[lieu], royaumes=[royaume])
    demarrer_partie(monde)
    return monde, _RngForce(chance_tirage)


def test_chance_convaincre_et_bornes():
    monde, _ = _monde_diplomatie(0.0)
    assert chance_convaincre(monde.personnage(0)) == 0.5  # Charisme et Chance moyens
    dore = nouveau_character(1, "X", valeurs={t: 100 for t in Trait})
    terne = nouveau_character(2, "Y", valeurs={t: 0 for t in Trait})
    assert chance_convaincre(dore) == TIRAGE_PLAFOND
    assert chance_convaincre(terne) == TIRAGE_PLANCHER


def test_convaincre_reussi_fait_monter_disposition_et_renom():
    monde, rng = _monde_diplomatie(0.0)  # tirage toujours gagnant
    resultat = convaincre(monde, rng, 0, 0)
    assert resultat.ok and resultat.reussite
    assert monde.royaume(0).disposition == 50 + GAIN_DISPOSITION[TailleSettlement.VILLAGE]
    livre = monde.personnage(0).grand_livre
    assert livre.reputation_domaine["diplomate"] == CONVAINCRE_REPUTATION_DIPLOMATE
    assert livre.reputation_royaume[0] == CONVAINCRE_REPUTATION_ROYAUME
    assert monde.personnage(0).pa_restants == 6 - PA_COUT_CONVAINCRE


def test_convaincre_audience_pese_selon_la_taille():
    petit, rng = _monde_diplomatie(0.0, taille=TailleSettlement.VILLAGE)
    grand, _ = _monde_diplomatie(0.0, taille=TailleSettlement.CAPITALE)
    convaincre(petit, rng, 0, 0)
    convaincre(grand, rng, 0, 0)
    assert petit.royaume(0).disposition == 50 + GAIN_DISPOSITION[TailleSettlement.VILLAGE]
    assert grand.royaume(0).disposition == 50 + GAIN_DISPOSITION[TailleSettlement.CAPITALE]


def test_convaincre_refuse_dans_un_campement():
    # Un campement n'offre aucune audience (l'interface de ville n'y montre
    # d'ailleurs pas l'onglet) : refus sans PA dépensés.
    monde, rng = _monde_diplomatie(0.0, taille=TailleSettlement.CAMPEMENT)
    resultat = convaincre(monde, rng, 0, 0)
    assert not resultat.ok and "campement" in resultat.erreur
    assert monde.personnage(0).pa_restants == 6
    assert monde.royaume(0).disposition == 50


def test_convaincre_echec_coute_les_pa_sans_rien_changer():
    monde, rng = _monde_diplomatie(0.999)  # perd toujours
    resultat = convaincre(monde, rng, 0, 0)
    assert resultat.ok and resultat.reussite is False
    assert monde.royaume(0).disposition == 50
    assert monde.personnage(0).grand_livre.reputation_domaine == {}
    assert monde.personnage(0).pa_restants == 6 - PA_COUT_CONVAINCRE


def test_convaincre_refus_sans_effet_de_bord():
    monde, rng = _monde_diplomatie(0.0)
    emissaire = monde.personnage(0)

    emissaire.location = (9, 9)                          # pas dans le royaume
    assert "settlement" in convaincre(monde, rng, 0, 0).erreur
    emissaire.location = (0, 0)

    monde.royaume(0).rallie = True                       # déjà acquis
    assert "rallié" in convaincre(monde, rng, 0, 0).erreur
    monde.royaume(0).rallie = False

    emissaire.pa_restants = PA_COUT_CONVAINCRE - 1
    resultat = convaincre(monde, rng, 0, 0)
    assert not resultat.ok and "insuffisants" in resultat.erreur
    assert emissaire.pa_restants == PA_COUT_CONVAINCRE - 1  # rien dépensé
    assert monde.royaume(0).disposition == 50


def test_ralliement_disposition_pleine_sans_condition():
    monde, rng = _monde_diplomatie(0.0, disposition=SEUIL_RALLIEMENT - 1)
    convaincre(monde, rng, 0, 0)
    assert monde.royaume(0).disposition == SEUIL_RALLIEMENT  # écrêté
    assert monde.royaume(0).rallie


def test_ralliement_bloque_puis_debloque_par_la_condition():
    condition = ConditionRalliement(domaine_requis="guerrier", seuil=40)
    monde, rng = _monde_diplomatie(
        0.0, disposition=SEUIL_RALLIEMENT - 1, conditions=[condition]
    )
    convaincre(monde, rng, 0, 0)
    assert monde.royaume(0).disposition == SEUIL_RALLIEMENT
    assert not monde.royaume(0).rallie                   # le renom manque

    # Le renom exigé arrive plus tard (bataille, mission…) : la fin de tour
    # revérifie et déclenche le ralliement.
    monde.personnage(0).grand_livre.reputation_domaine["guerrier"] = 40
    finir_tour(monde)
    assert monde.royaume(0).rallie


# --- Intégration avec le worldgen ------------------------------------------

def test_boucle_sur_monde_genere():
    cfg = WorldGenConfig(
        map_width=30, map_height=30, roster_size=12, settlements_total=8,
        kingdom_count=3, starting_hand=3, exceptional_quota=2,
    )
    monde = generer_monde(SeededRNG(42), cfg)
    demarrer_partie(monde)
    assert all(p.pa_restants >= PA_BASE for p in monde.personnages)

    heros = monde.personnage(monde.main_depart[0])
    dests = destinations_accessibles(monde, heros.id)
    assert dests
    res = deplacer(monde, heros.id, next(iter(dests)))
    assert res.ok
    assert heros.pa_restants == points_action_max(heros) - res.cout
