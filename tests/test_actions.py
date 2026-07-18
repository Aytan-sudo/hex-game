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
    PA_BASE,
    deplacer,
    destinations_accessibles,
    points_action_max,
)
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
