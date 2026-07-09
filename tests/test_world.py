"""
Worldgen palier A + assemblage (world/worldgen.generer_monde).

Vérifie le monde complet : terrain + settlements hiérarchisés + royaumes
(partition, capitale unique) + roster nommé + placement de la main de départ,
le tout déterministe par seed et headless.
"""

from engine.rng import SeededRNG
from game.terrain import TerrainType
from world.worldgen import generer_monde, WorldGenConfig
from world.settlement import TailleSettlement


def _cfg():
    return WorldGenConfig(
        map_width=40, map_height=40, settlements_total=20, kingdom_count=4, roster_size=30
    )


def test_world_is_deterministic_by_seed():
    cfg = _cfg()
    a = generer_monde(SeededRNG(42), cfg)
    b = generer_monde(SeededRNG(42), cfg)
    assert a.seed == b.seed
    assert a.elu_id == b.elu_id
    assert a.main_depart == b.main_depart
    assert [s.nom for s in a.settlements] == [s.nom for s in b.settlements]
    assert [p.nom for p in a.personnages] == [p.nom for p in b.personnages]
    assert [r.nom for r in a.royaumes] == [r.nom for r in b.royaumes]


def test_world_shape():
    cfg = _cfg()
    w = generer_monde(SeededRNG(1), cfg)
    assert len(w.settlements) == cfg.settlements_total
    assert len(w.royaumes) == cfg.kingdom_count
    assert len(w.personnages) == cfg.roster_size
    assert w.horloge_du_destin == cfg.horloge_du_destin


def test_each_kingdom_has_exactly_one_capital():
    w = generer_monde(SeededRNG(3), _cfg())
    for r in w.royaumes:
        assert r.capitale_id in r.settlement_ids
        capitales = [sid for sid in r.settlement_ids
                     if w.settlements[sid].taille is TailleSettlement.CAPITALE]
        assert capitales == [r.capitale_id]


def test_settlements_partition_kingdoms():
    """Chaque settlement appartient à exactement un royaume."""
    w = generer_monde(SeededRNG(3), _cfg())
    from_kingdoms = [sid for r in w.royaumes for sid in r.settlement_ids]
    assert sorted(from_kingdoms) == list(range(len(w.settlements)))  # partition exacte
    for s in w.settlements:
        assert s.royaume_id is not None
        assert s.id in w.royaumes[s.royaume_id].settlement_ids


def test_settlements_on_buildable_land():
    w = generer_monde(SeededRNG(5), _cfg())
    positions = [s.position for s in w.settlements]
    assert len(set(positions)) == len(positions)  # positions distinctes
    for s in w.settlements:
        assert s.nom
        terrain = w.tiles[s.position].base_terrain
        assert terrain not in (TerrainType.WATER, TerrainType.MOUNTAIN)


def test_starting_hand_placed_and_owned():
    w = generer_monde(SeededRNG(7), _cfg())
    assert w.elu_id in w.main_depart
    depart = w.settlements[w.royaumes[0].capitale_id].position
    for pid in w.main_depart:
        perso = w.personnages[pid]
        assert perso.affiliation == 0          # contrôlé par le joueur
        assert perso.location == depart        # rassemblé au point de départ
    # Les autres sont indépendants, mais tous placés sur la carte.
    autres = [p for p in w.personnages if p.id not in w.main_depart]
    assert all(p.affiliation is None for p in autres)
    assert all(p.location is not None for p in w.personnages)


def test_kingdoms_have_rally_conditions():
    w = generer_monde(SeededRNG(9), _cfg())
    for r in w.royaumes:
        assert r.conditions                      # au moins une condition
        assert 0 <= r.disposition <= 100
        for c in r.conditions:
            assert 0 <= c.seuil <= 100
            assert c.domaine_requis
