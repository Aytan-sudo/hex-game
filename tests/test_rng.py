"""
RNG semé unique (engine/rng.py).

Garantit ce sur quoi repose le worldgen déterministe : même seed ⇒ même suite,
sous-flux dérivés reproductibles **et** indépendants, et absence de dépendance à
un état ``random`` global partagé.
"""

from engine.rng import SeededRNG


def _draws(rng, n=20):
    return [rng.random() for _ in range(n)]


def test_same_seed_same_sequence():
    assert _draws(SeededRNG(1234)) == _draws(SeededRNG(1234))


def test_different_seed_differs():
    assert _draws(SeededRNG(1)) != _draws(SeededRNG(2))


def test_seed_zero_is_respected():
    # `seed or ...` traiterait 0 comme absent : on vérifie que 0 est bien gardé.
    assert SeededRNG(0).seed == 0
    assert _draws(SeededRNG(0)) == _draws(SeededRNG(0))


def test_unseeded_has_a_concrete_seed():
    rng = SeededRNG()
    assert isinstance(rng.seed, int)
    # Reproductible une fois le seed connu.
    assert _draws(SeededRNG(rng.seed)) == _draws(SeededRNG(rng.seed))


def test_derive_is_reproducible_across_roots():
    """Deux racines de même seed donnent des sous-flux identiques par étiquette."""
    a = SeededRNG(42).derive("terrain")
    b = SeededRNG(42).derive("terrain")
    assert _draws(a) == _draws(b)


def test_derive_labels_are_independent():
    root = SeededRNG(42)
    assert _draws(root.derive("terrain")) != _draws(root.derive("roster"))


def test_derive_does_not_consume_parent():
    """Dériver un sous-flux ne perturbe pas la suite du parent."""
    root_a = SeededRNG(7)
    root_b = SeededRNG(7)
    root_b.derive("aside")  # ne doit rien tirer sur root_b
    assert _draws(root_a) == _draws(root_b)


def test_map_generation_is_isolated_from_global_random():
    """Le générateur de carte reste déterministe quel que soit l'état ailleurs."""
    import random
    from game.map_generator import MapConfig, MapGenerator

    def terrains(seed):
        tiles = MapGenerator(MapConfig(width=16, height=16, seed=seed)).generate()
        return {p: t.base_terrain for p, t in tiles.items()}

    a = terrains(99)
    random.seed(123)
    [random.random() for _ in range(100)]  # pollue le module global
    b = terrains(99)
    assert a == b
