"""
Générateur de personnages & de roster (world/worldgen.py).

On verrouille les invariants de conception : déterminisme par seed, pyramide
banals/utiles/exceptionnels avec quota de compagnons garanti, l'Élu unique
« quelconque en surface » mais à fort potentiel magique caché, les traîtres, la
main de départ, et le biais de profil (signature + magie).
"""

from engine.rng import SeededRNG
from world.character import Trait, Magie, Sexe
from world.worldgen import (
    WorldGenConfig,
    Profil,
    generer_character,
    generer_roster,
)


def _max_trait(perso):
    return max(hv.true_value for hv in perso.caracteristiques.values())


def _snapshot(roster):
    return [
        {t: hv.true_value for t, hv in p.caracteristiques.items()}
        for p in roster.personnages
    ]


# --- Déterminisme ----------------------------------------------------------

def test_roster_is_deterministic_by_seed():
    cfg = WorldGenConfig(roster_size=30)
    a = generer_roster(SeededRNG(42), cfg)
    b = generer_roster(SeededRNG(42), cfg)
    assert a.elu_id == b.elu_id
    assert a.main_depart == b.main_depart
    assert _snapshot(a) == _snapshot(b)


def test_character_is_deterministic():
    cfg = WorldGenConfig()
    a = generer_character(SeededRNG(7), cfg, id=0, profil=Profil.RODEUR, calibre=0.5)
    b = generer_character(SeededRNG(7), cfg, id=0, profil=Profil.RODEUR, calibre=0.5)
    assert {t: hv.true_value for t, hv in a.caracteristiques.items()} == \
           {t: hv.true_value for t, hv in b.caracteristiques.items()}


# --- Structure du roster ---------------------------------------------------

def test_roster_size_and_starting_hand():
    cfg = WorldGenConfig(roster_size=40, starting_hand=5)
    r = generer_roster(SeededRNG(1), cfg)
    assert len(r.personnages) == 40
    assert len(r.main_depart) == 5
    assert len(set(r.main_depart)) == 5           # tous distincts
    assert r.elu_id in r.main_depart


def test_exactly_one_chosen_one():
    r = generer_roster(SeededRNG(1), WorldGenConfig(roster_size=40))
    elus = [p for p in r.personnages if p.secrets.est_elu]
    assert len(elus) == 1
    assert elus[0].id == r.elu_id


def test_all_characteristics_start_hidden():
    r = generer_roster(SeededRNG(3), WorldGenConfig(roster_size=20))
    for p in r.personnages:
        assert all(hv.knowledge_level == 0 for hv in p.caracteristiques.values())


# --- L'Élu -----------------------------------------------------------------

def test_elu_is_designated_after_generation_not_generated_differently():
    """
    L'Élu est un membre de la main de départ, désigné APRÈS génération : il n'a ni
    calibre ni magie imposés. On le vérifie en montrant que sur de nombreux seeds
    il suit la distribution générale (parfois quelconque, parfois exceptionnel) et
    que, comme la masse, il n'a le plus souvent aucune magie.
    """
    cfg = WorldGenConfig(roster_size=40)
    elu_max = []
    elu_sans_magie = 0
    for seed in range(40):
        r = generer_roster(SeededRNG(seed), cfg)
        elu = r.personnages[r.elu_id]
        assert elu.id in r.main_depart            # l'Élu est dans la main de départ
        elu_max.append(_max_trait(elu))
        if not elu.secrets.potentiels:
            elu_sans_magie += 1
    # Suit la distribution générale : ni bridé bas, ni forcé exceptionnel.
    assert min(elu_max) < 60
    assert max(elu_max) >= 78
    # La magie n'est PAS imposée : la plupart des Élus n'ont aucun potentiel.
    assert elu_sans_magie > len(elu_max) // 2


def test_elu_can_be_either_sex():
    cfg = WorldGenConfig(roster_size=40)
    sexes = set()
    for s in range(30):
        r = generer_roster(SeededRNG(s), cfg)
        sexes.add(r.personnages[r.elu_id].sexe)
    assert sexes == {Sexe.FEMININ, Sexe.MASCULIN}


# --- Pyramide & quotas -----------------------------------------------------

def test_exceptional_quota_is_guaranteed():
    cfg = WorldGenConfig(roster_size=40, exceptional_quota=5)
    r = generer_roster(SeededRNG(2026), cfg)
    exceptionnels = [p for p in r.personnages if _max_trait(p) >= 78]
    assert len(exceptionnels) >= cfg.exceptional_quota


def test_most_characters_are_ordinary():
    """La masse est banale/utile ; les exceptionnels sont une minorité."""
    cfg = WorldGenConfig(roster_size=40, exceptional_quota=5)
    r = generer_roster(SeededRNG(2026), cfg)
    exceptionnels = sum(1 for p in r.personnages if _max_trait(p) >= 80)
    assert exceptionnels < len(r.personnages) / 2


# --- Traîtres --------------------------------------------------------------

def test_traitors_seeded_and_never_the_chosen_one():
    cfg = WorldGenConfig(roster_size=40, traitor_fraction=0.15)
    r = generer_roster(SeededRNG(5), cfg)
    traitres = [p for p in r.personnages if p.secrets.allegiance.du_mal]
    assert len(traitres) == round(cfg.traitor_fraction * cfg.roster_size)
    assert all(p.id != r.elu_id for p in traitres)
    # L'allégeance reste cachée du joueur.
    assert all(not p.secrets.allegiance.revele for p in traitres)


# --- Biais de profil -------------------------------------------------------

def test_profile_shapes_the_signature_trait():
    cfg = WorldGenConfig()
    guerrier = generer_character(SeededRNG(9), cfg, id=0, profil=Profil.GUERRIER, calibre=0.9)
    assert guerrier.caracteristiques[Trait.PUISSANCE].true_value > \
           guerrier.caracteristiques[Trait.INTELLIGENCE].true_value


def test_mystique_channels_more_than_a_warrior():
    cfg = WorldGenConfig()
    root = SeededRNG(11)

    def count_channelers(profil, n=200):
        stream = root.derive(profil.value)
        total = 0
        for i in range(n):
            p = generer_character(stream.derive(str(i)), cfg, id=i, profil=profil, calibre=0.4)
            if p.secrets.potentiels:
                total += 1
        return total

    assert count_channelers(Profil.MYSTIQUE) > count_channelers(Profil.GUERRIER)
