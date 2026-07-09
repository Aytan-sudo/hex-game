"""
Génération procédurale du roster de personnages (worldgen, PROJET §5.7).

**Headless, déterministe** (piloté par ``engine.rng.SeededRNG``), sans Pygame.
Deux niveaux :

- ``generer_character`` — **un** personnage. Modèle *hybride* : un **calibre**
  tiré d'une **loi de puissance** (``C = U^p``) donne le **budget** de points et
  la **concentration** ; un **profil** (silhouette) donne les **poids** par trait.
  Résultat : une pyramide « banals / utiles / exceptionnels » (cf. discussion).
- ``generer_roster`` — l'ensemble. Impose des **quotas** (les compagnons
  exceptionnels sont *garantis*, pas laissés au hasard), sème l'**Élu** (normal en
  surface, mais **potentiel magique très haut caché** ; il grandira via la
  *prophétie des élus*, arc exclusif — moteur narratif Phase 5), les **traîtres**,
  et désigne la **main de départ**.

Hors périmètre (à venir) : **noms** (banques par royaume), **banque de portraits**,
**placement sur la carte** (dépend du terrain/settlements), et les **arcs de
prophétie**. La génération pose le socle ; le jeu ajoute par-dessus (prophéties →
montée des valeurs, cicatrices, artefacts).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from engine.rng import SeededRNG
from world.character import (
    Character,
    HiddenValue,
    Magie,
    Sexe,
    Trait,
    nouveau_character,
)


# =============================================================================
# PROFILS — silhouettes qui biaisent la distribution des traits
# =============================================================================

class Profil(Enum):
    GUERRIER = "guerrier"
    ERUDIT = "érudit"
    COURTISAN = "courtisan"
    RODEUR = "rôdeur"
    MYSTIQUE = "mystique"


# Poids par trait (défaut 1.0 pour les traits non listés). Un poids élevé attire
# davantage de budget → c'est la « signature » du profil.
PROFIL_POIDS: Dict[Profil, Dict[Trait, float]] = {
    Profil.GUERRIER: {Trait.PUISSANCE: 2.6, Trait.VIGUEUR: 1.9, Trait.COMMANDEMENT: 1.6},
    Profil.ERUDIT: {Trait.INTELLIGENCE: 2.6, Trait.PERSPICACITE: 1.9, Trait.VOLONTE: 1.5},
    Profil.COURTISAN: {Trait.CHARISME: 2.6, Trait.INTELLIGENCE: 1.7, Trait.PERSPICACITE: 1.6},
    Profil.RODEUR: {Trait.VIVACITE: 2.6, Trait.VIGUEUR: 1.7, Trait.PERSPICACITE: 1.5},
    Profil.MYSTIQUE: {Trait.VOLONTE: 2.6, Trait.PERSPICACITE: 1.7, Trait.INTELLIGENCE: 1.5},
}

# Magies vers lesquelles chaque profil penche (choix biaisé, quand il canalise).
PROFIL_MAGIE_POIDS: Dict[Profil, Dict[Magie, float]] = {
    Profil.GUERRIER: {Magie.EMPRISE: 3.0, Magie.GUERISON: 1.5},
    Profil.ERUDIT: {Magie.SONGE: 2.5, Magie.ANCIENS: 2.5},
    Profil.COURTISAN: {Magie.ESPRIT: 3.0},
    Profil.RODEUR: {Magie.LIEN_DES_BETES: 3.0},
    Profil.MYSTIQUE: {Magie.SONGE: 2.0, Magie.ESPRIT: 2.0, Magie.GUERISON: 2.0},
}


# =============================================================================
# CONFIG — les boutons d'échelle (PROJET §5.7 : WorldGenConfig)
# =============================================================================

@dataclass
class WorldGenConfig:
    roster_size: int = 40            # nombre total de personnages du monde
    starting_hand: int = 5           # main de départ du joueur (Élu inclus)
    exceptional_quota: int = 5       # compagnons exceptionnels GARANTIS

    # Loi de puissance du calibre : C = U^p (p élevé = monde plus élitiste).
    calibre_exponent: float = 2.5
    exceptional_calibre_min: float = 0.85  # bande « exceptionnel » (quota)
    elu_calibre_min: float = 0.25          # l'Élu paraît quelconque en surface
    elu_calibre_max: float = 0.5

    # Budget de points réparti sur les 9 traits, et concentration, selon calibre.
    budget_min: int = 185
    budget_max: int = 330
    concentration_min: float = 0.10
    concentration_max: float = 0.45
    trait_jitter: float = 5.0

    # Magie (hors budget) : incidence, force, potentiel forcé de l'Élu.
    magic_incidence: float = 0.10
    magic_incidence_mystique: float = 0.55
    potential_min: int = 25
    potential_max: int = 100
    elu_potential_min: int = 88

    # Faits collectifs.
    traitor_fraction: float = 0.15
    feminine_ratio: float = 0.5


@dataclass
class Roster:
    """Résultat du worldgen (niveau roster)."""
    personnages: List[Character]
    main_depart: List[int]  # ids de la main de départ (contient l'Élu)
    elu_id: int


# =============================================================================
# GÉNÉRATION — un personnage
# =============================================================================

def _lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t


def _repartir_budget(
    rng: SeededRNG, profil: Profil, budget: float, concentration: float, jitter: float
) -> Dict[Trait, int]:
    """Répartit le budget sur les 9 traits selon les poids du profil.

    La concentration accentue les traits-signature (calibre haut = plus « pointu »).
    Jitter gaussien, valeurs bornées à [0, 100].
    """
    poids = PROFIL_POIDS[profil]
    exposant = 1.0 + concentration * 1.2
    eff = {t: poids.get(t, 1.0) ** exposant for t in Trait}
    total = sum(eff.values())

    valeurs: Dict[Trait, int] = {}
    for trait in Trait:
        part = budget * eff[trait] / total + rng.gauss(0, jitter)
        valeurs[trait] = int(max(0, min(100, round(part))))
    return valeurs


def _tirer_magie(rng: SeededRNG, profil: Profil) -> Magie:
    """Tire une magie, biaisée par le profil (défaut : poids 1.0 par magie)."""
    poids_profil = PROFIL_MAGIE_POIDS.get(profil, {})
    magies = list(Magie)
    poids = [poids_profil.get(m, 1.0) for m in magies]
    return rng.choices(magies, weights=poids, k=1)[0]


def generer_character(
    rng: SeededRNG,
    config: WorldGenConfig,
    *,
    id: int,
    profil: Optional[Profil] = None,
    calibre: Optional[float] = None,
    sexe: Optional[Sexe] = None,
    nom: Optional[str] = None,
) -> Character:
    """
    Génère un personnage. ``rng`` doit être un flux **dédié** à ce personnage
    (reproductible par (seed monde, id)). ``profil``/``calibre``/``sexe`` peuvent
    être imposés (l'Élu, les quotas) ; sinon ils sont tirés.
    """
    if profil is None:
        profil = rng.choice(list(Profil))
    if sexe is None:
        sexe = Sexe.FEMININ if rng.random() < config.feminine_ratio else Sexe.MASCULIN
    if calibre is None:
        calibre = rng.random() ** config.calibre_exponent

    budget = _lerp(config.budget_min, config.budget_max, calibre)
    concentration = _lerp(config.concentration_min, config.concentration_max, calibre)
    valeurs = _repartir_budget(rng, profil, budget, concentration, config.trait_jitter)

    perso = nouveau_character(
        id=id,
        nom=nom or f"Personnage {id}",
        portrait_id=rng.randint(0, 999),
        valeurs=valeurs,
        sexe=sexe,
    )

    # Magie éventuelle (hors budget) : incidence plus haute pour le Mystique.
    incidence = (
        config.magic_incidence_mystique
        if profil is Profil.MYSTIQUE
        else config.magic_incidence
    )
    if rng.random() < incidence:
        magie = _tirer_magie(rng, profil)
        # Potentiel : faible souvent, fort rare (même esprit « exceptions rares »).
        force = int(_lerp(config.potential_min, config.potential_max, rng.random() ** 2))
        perso.secrets.potentiels[magie] = HiddenValue(true_value=force)

    return perso


# =============================================================================
# GÉNÉRATION — le roster (quotas, Élu, traîtres, main de départ)
# =============================================================================

def generer_roster(rng: SeededRNG, config: WorldGenConfig) -> Roster:
    """
    Génère l'ensemble des personnages du monde, avec quotas et faits collectifs.

    Déterministe : même seed racine ⇒ même roster (chaque perso tire d'un
    sous-flux ``char:<id>`` indépendant de l'ordre).
    """
    root = rng.derive("roster")

    # Calibres : les `exceptional_quota` premiers sont forcés dans la bande haute
    # (compagnons garantis) ; le reste suit la loi de puissance.
    calibre_rng = root.derive("calibres")
    personnages: List[Character] = []
    for i in range(config.roster_size):
        if i < config.exceptional_quota:
            calibre = _lerp(config.exceptional_calibre_min, 1.0, calibre_rng.random())
        else:
            calibre = calibre_rng.random() ** config.calibre_exponent
        perso = generer_character(
            root.derive(f"char:{i}"), config, id=i, calibre=calibre
        )
        personnages.append(perso)

    # L'Élu : un personnage d'apparence NORMALE (hors quota exceptionnel), regénéré
    # avec un calibre médian, puis doté d'un potentiel magique très haut CACHÉ.
    elu_rng = root.derive("elu")
    normaux = [p.id for p in personnages if p.id >= config.exceptional_quota]
    elu_id = elu_rng.choice(normaux)
    elu_calibre = _lerp(config.elu_calibre_min, config.elu_calibre_max, elu_rng.random())
    elu = generer_character(root.derive(f"char:{elu_id}:elu"), config, id=elu_id, calibre=elu_calibre)
    magie_elu = elu_rng.choice(list(Magie))
    elu.secrets.potentiels[magie_elu] = HiddenValue(
        true_value=elu_rng.randint(config.elu_potential_min, 100)
    )
    elu.secrets.est_elu = True
    personnages[elu_id] = elu

    # Traîtres : une fraction du roster (jamais l'Élu), allégeance cachée.
    traitor_rng = root.derive("traitres")
    n_traitres = round(config.traitor_fraction * config.roster_size)
    candidats = [p.id for p in personnages if p.id != elu_id]
    for traitre_id in traitor_rng.sample(candidats, min(n_traitres, len(candidats))):
        personnages[traitre_id].secrets.allegiance.du_mal = True

    # Main de départ : l'Élu + (starting_hand - 1) autres tirés au sort.
    hand_rng = root.derive("main")
    autres = [p.id for p in personnages if p.id != elu_id]
    main_depart = [elu_id] + hand_rng.sample(autres, config.starting_hand - 1)

    return Roster(personnages=personnages, main_depart=main_depart, elu_id=elu_id)
