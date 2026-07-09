"""
Modèle Character (Phase 2) : couche vrai/connu (Option A) et structure.

On vérifie l'invariant clé — l'intervalle connu contient toujours la vraie
valeur — le resserrement par la connaissance, la divineresse (collapse), et que
le label ne fuite jamais de chiffre.
"""

from world.character import (
    HiddenValue,
    MAX_KNOWLEDGE,
    label,
    Trait,
    Magie,
    nouveau_character,
)


def test_interval_always_contains_true_value():
    """Invariant Option A : l'intervalle connu contient toujours la vraie valeur."""
    for true in range(0, 101, 7):
        for level in range(MAX_KNOWLEDGE + 1):
            lo, hi = HiddenValue(true, knowledge_level=level).known_interval()
            assert lo <= true <= hi


def test_interval_narrows_with_knowledge():
    hv = HiddenValue(true_value=50)
    widths = []
    for level in range(MAX_KNOWLEDGE + 1):
        hv.knowledge_level = level
        lo, hi = hv.known_interval()
        widths.append(hi - lo)
    # Largeur décroissante, jusqu'à 0 (valeur exacte).
    assert widths == sorted(widths, reverse=True)
    assert widths[-1] == 0


def test_collapse_gives_exact_value():
    hv = HiddenValue(true_value=42)
    hv.collapse()
    assert hv.known_interval() == (42, 42)
    assert hv.knowledge_level == MAX_KNOWLEDGE


def test_reveal_is_capped():
    hv = HiddenValue(true_value=10)
    hv.reveal(1000)
    assert hv.knowledge_level == MAX_KNOWLEDGE


def test_label_unknown_at_level_zero():
    assert label(HiddenValue(true_value=80, knowledge_level=0)) == "inconnu"


def test_label_hedged_on_first_impression():
    assert label(HiddenValue(true_value=10, knowledge_level=1)).startswith("semble")


def test_label_confident_when_collapsed():
    for true, expected in ((10, "faible"), (50, "moyen"), (90, "fort")):
        hv = HiddenValue(true_value=true)
        hv.collapse()
        assert label(hv) == expected


def test_label_never_leaks_a_number():
    for true in range(0, 101, 5):
        for level in range(MAX_KNOWLEDGE + 1):
            text = label(HiddenValue(true, knowledge_level=level))
            assert not any(ch.isdigit() for ch in text)


def test_nouveau_character_fills_all_traits_unknown():
    c = nouveau_character(1, "Rand", valeurs={Trait.PUISSANCE: 60})
    assert set(c.caracteristiques) == set(Trait)
    assert all(hv.knowledge_level == 0 for hv in c.caracteristiques.values())
    assert c.caracteristiques[Trait.PUISSANCE].true_value == 60
    # Trait non fourni -> 0.
    assert c.caracteristiques[Trait.CHANCE].true_value == 0


def test_secret_facts_default_hidden():
    c = nouveau_character(1, "Perrin")
    assert c.secrets.est_elu is False
    assert c.secrets.allegiance.du_mal is False
    assert c.secrets.allegiance.revele is False
    assert c.secrets.potentiels == {}


def test_magic_potential_is_a_hidden_value():
    c = nouveau_character(1, "Egwene")
    c.secrets.potentiels[Magie.SONGE] = HiddenValue(true_value=75)
    # Un potentiel magique se découvre comme une caractéristique.
    assert label(c.secrets.potentiels[Magie.SONGE]) == "inconnu"
