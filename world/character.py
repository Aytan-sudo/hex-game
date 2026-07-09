"""
Modèle de personnage (Phase 2) — la brique centrale du jeu.

**Composition, pas héritage** : un ``Character`` n'est *pas* une unité de combat.
Ses **caractéristiques primaires** sont la source ; tout le reste (aptitudes,
points d'action, stats de combat) se **dérive** par des fonctions pures, sans
rien stocker. Le combat n'est qu'une facette, branchée plus tard par adaptateur.

Quatre couches (cf. PROJET.md §3) :

1. **Identité & état de jeu** — visible (nom, portrait, affiliation, position).
2. **Caractéristiques primaires** — la source ; certaines cachées, via la couche
   *vrai/connu* (§5.1) : chaque valeur a une ``true_value`` semée + un
   ``knowledge_level`` qui resserre un intervalle. L'UI n'affiche **jamais** le
   chiffre, seulement un ``label``.
3. **Grand livre** — réputation à facettes, cicatrices, missions : l'accumulation
   qui façonne le perso (l'aptitude à un rôle s'en **dérive**, §5.2).
4. **Faits secrets** — allégeance, Élu, potentiels magiques : semés au worldgen,
   lus par le moteur, **cachés** de l'UI.

Ce module est **headless** (ni Pygame ni couche militaire) et sérialisable.

Hors périmètre volontaire (à venir) : le **générateur procédural** (profils,
budget, faits semés — cf. PROJET §5.7), la dérivation d'**aptitude**, l'**adaptateur
de combat**, et les **mécaniques de magie** (§5.4, backlog). Seule la *forme* des
données est figée ici.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple


# =============================================================================
# COUCHE VRAI/CONNU (§5.1) — « Option A », honnête par construction
# =============================================================================

# Demi-largeur de l'intervalle connu, par niveau de connaissance (0..N).
# Niveau 0 = inconnu (intervalle très large) ; le dernier = valeur exacte
# (c'est ce que collapse/​la divineresse atteignent).
KNOWLEDGE_WIDTHS: Tuple[int, ...] = (50, 30, 16, 8, 3, 0)
MAX_KNOWLEDGE: int = len(KNOWLEDGE_WIDTHS) - 1

# Bornes hautes (exclues) des paliers de label sur 0-100, avec leur nom.
_BUCKETS: Tuple[Tuple[int, str], ...] = ((33, "faible"), (67, "moyen"), (101, "fort"))


@dataclass
class HiddenValue:
    """
    Une caractéristique cachée : valeur vraie (0-100, semée, **jamais affichée**)
    + niveau de connaissance du joueur qui resserre l'intervalle montré.

    Invariant *Option A* : l'intervalle connu **contient toujours** la vraie
    valeur — on ne ment jamais, seule la précision augmente.
    """
    true_value: int
    knowledge_level: int = 0

    def known_interval(self) -> Tuple[int, int]:
        """Intervalle [bas, haut] déduit du niveau de connaissance courant."""
        width = KNOWLEDGE_WIDTHS[min(self.knowledge_level, MAX_KNOWLEDGE)]
        return (max(0, self.true_value - width), min(100, self.true_value + width))

    def reveal(self, steps: int = 1) -> None:
        """Resserre l'intervalle (exercice du rôle, événement, observation)."""
        self.knowledge_level = min(self.knowledge_level + steps, MAX_KNOWLEDGE)

    def collapse(self) -> None:
        """Effondre l'intervalle sur la valeur exacte (la divineresse, §5.1)."""
        self.knowledge_level = MAX_KNOWLEDGE

    @property
    def is_known(self) -> bool:
        """Vrai dès qu'on a la moindre information (niveau > 0)."""
        return self.knowledge_level > 0


def _bucket(value: int) -> str:
    """Nom de palier (faible/moyen/fort) pour une valeur 0-100."""
    for upper, name in _BUCKETS:
        if value < upper:
            return name
    return _BUCKETS[-1][1]


def label(hidden: HiddenValue) -> str:
    """
    Rendu textuel destiné à l'UI — **jamais** un chiffre (§5.1).

    Le phrasé dérive de l'intervalle : large = hésitant (« semble … »),
    à cheval sur deux paliers = « X à Y », étroit = affirmé. Vocabulaire
    volontairement grossier et facile à ajuster.
    """
    if hidden.knowledge_level == 0:
        return "inconnu"

    lo, hi = hidden.known_interval()
    lo_name, hi_name = _bucket(lo), _bucket(hi)

    if lo_name == hi_name:
        base = lo_name
    elif lo_name == "faible" and hi_name == "fort":
        # L'intervalle couvre tout le spectre : rien de saillant à dire.
        return "difficile à cerner"
    else:
        base = f"{lo_name} à {hi_name}"

    # Première impression (niveau 1) : on hedge le propos.
    if hidden.knowledge_level == 1:
        return f"semble {base}"
    return base


# =============================================================================
# CARACTÉRISTIQUES & MAGIES — données, pas champs figés
# =============================================================================

class Trait(Enum):
    """
    Les 9 caractéristiques primaires. Règle de conception : chacune porte un
    levier de gameplay qu'aucune autre ne porte seule (cf. PROJET §5.2).
    """
    PUISSANCE = "puissance"        # combat/duel brut, intimidation physique
    VIVACITE = "vivacité"          # initiative, furtivité → assassinat fin, fuite
    VIGUEUR = "vigueur"            # points d'action, endurance de voyage, survie
    INTELLIGENCE = "intelligence"  # stratégie (Général), gestion, apprentissage
    PERSPICACITE = "perspicacité"  # juger autrui : révèle ses attributs, traîtres
    VOLONTE = "volonté"            # résiste à l'Ombre + garde-fou de la magie
    CHARISME = "charisme"          # séduction, recrutement, ralliement des foules
    COMMANDEMENT = "commandement"  # loyauté des troupes, bonus de général
    CHANCE = "chance"              # infléchit les tirages (mort du général, dés…)
    # 10e candidate à creuser : NOBLESSE (ouvre positions royales / offres d'institutions)


class Magie(Enum):
    """
    Les 6 magies, chacune avec un **verbe stratégique** distinct. Les potentiels
    sont des faits secrets rares ; les *mécaniques* restent backlog (§5.4).
    """
    GUERISON = "guérison"              # survivre : % mort du général, efface cicatrices
    LIEN_DES_BETES = "lien des bêtes"  # éclairer : scout, embuscade, compagnon lié
    EMPRISE = "emprise"                # forcer : éléments, sièges, travaux de terrain
    ESPRIT = "esprit"                  # subvertir : diplomatie, révèle l'allégeance
    SONGE = "songe"                    # prévoir : prophéties, indices Élu/traîtres
    ANCIENS = "anciens"                # relier : pierres de portail, artefacts, forge


class Sexe(Enum):
    """Sexe du personnage — pilote portrait et nom. L'Élu peut être de l'un ou l'autre."""
    FEMININ = "féminin"
    MASCULIN = "masculin"


# =============================================================================
# GRAND LIVRE (§5.2 / §5.3) — append-only, l'accumulation qui façonne le perso
# =============================================================================

@dataclass
class Cicatrice:
    """Modificateur permanent (bataille, torture, sur-usage de magie…)."""
    source: str
    trait: Trait
    delta: int  # généralement négatif


@dataclass
class MissionAccomplie:
    """Trace d'une mission menée à bien (référence un archétype, §5.7)."""
    template_id: str


@dataclass
class GrandLivre:
    """Réputation à facettes (domaine **et** royaume, §5.3), cicatrices, missions."""
    reputation_domaine: Dict[str, int] = field(default_factory=dict)  # "guerrier", "diplomate"…
    reputation_royaume: Dict[int, int] = field(default_factory=dict)  # kingdom_id -> standing
    cicatrices: List[Cicatrice] = field(default_factory=list)
    missions: List[MissionAccomplie] = field(default_factory=list)


# =============================================================================
# POSITIONS (§5.2) — une charge RÉELLE, accordée par quelqu'un
# =============================================================================

@dataclass
class Position:
    """
    Un poste réellement occupé (« Général de la 3ᵉ armée », « Ambassadeur »…).
    À ne pas confondre avec l'**aptitude** (calculée, cachée). Les *définitions*
    de rôles vivent dans un registre de données à part (à venir).
    """
    role_id: str            # référence au registre de rôles
    accordee_par: str       # "joueur" | "institution:<id>"
    perimetre: Optional[str] = None  # sur quoi (armée, royaume, guilde…) — à typer plus tard


# =============================================================================
# FAITS SECRETS — semés au worldgen, lus par le moteur, cachés de l'UI
# =============================================================================

@dataclass
class Allegiance:
    """Alignement moral secret. Peut **basculer** (traîtres, §3)."""
    du_mal: bool = False
    revele: bool = False  # le joueur connaît-il l'allégeance ?


@dataclass
class FaitsSecrets:
    """Vérité que le moteur consulte mais que l'UI ne montre jamais."""
    allegiance: Allegiance = field(default_factory=Allegiance)
    est_elu: bool = False
    # Potentiels magiques : RARES (souvent aucun). Cachés comme les caractéristiques.
    potentiels: Dict[Magie, HiddenValue] = field(default_factory=dict)


# =============================================================================
# LE PERSONNAGE — composition pure, aucune stat de combat en dur
# =============================================================================

@dataclass
class Character:
    """La brique centrale. Voir l'en-tête du module pour les 4 couches."""
    # 1. Identité & état de jeu (visible)
    id: int
    nom: str
    portrait_id: int
    # 2. Caractéristiques primaires (la source ; couche vrai/connu)
    caracteristiques: Dict[Trait, HiddenValue]
    # 1 (suite) — identité, affiliation/position sur la carte
    sexe: Sexe = Sexe.MASCULIN
    affiliation: Optional[int] = None  # faction qui le contrôle ; None = indépendant
    location: Optional[object] = None  # HexCoord | ref. settlement (durci en Phase 4)
    # 3. Grand livre + positions occupées
    grand_livre: GrandLivre = field(default_factory=GrandLivre)
    positions: List[Position] = field(default_factory=list)
    # 4. Faits secrets
    secrets: FaitsSecrets = field(default_factory=FaitsSecrets)


def nouveau_character(
    id: int,
    nom: str,
    portrait_id: int = 0,
    valeurs: Optional[Dict[Trait, int]] = None,
    sexe: Sexe = Sexe.MASCULIN,
    **extra,
) -> Character:
    """
    Construit un ``Character`` avec **toutes** les caractéristiques présentes,
    à connaissance vierge (niveau 0). Valeurs manquantes → 0.

    Constructeur **déterministe et sans règles** : les valeurs sont posées telles
    quelles. La génération procédurale (profils, budget, faits secrets semés) vit
    dans ``world/worldgen.py`` (PROJET §5.7).
    """
    valeurs = valeurs or {}
    caracs = {trait: HiddenValue(true_value=valeurs.get(trait, 0)) for trait in Trait}
    return Character(
        id=id, nom=nom, portrait_id=portrait_id, caracteristiques=caracs, sexe=sexe, **extra
    )
