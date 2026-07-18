"""
Génération procédurale du roster de personnages (worldgen, PROJET §5.7).

**Headless, déterministe** (piloté par ``engine.rng.SeededRNG``), sans Pygame.
Deux niveaux :

- ``generer_character`` — **un** personnage. Modèle *hybride* : un **calibre**
  tiré d'une **loi de puissance** (``C = U^p``) donne le **budget** de points et
  la **concentration** ; un **profil** (silhouette) donne les **poids** par trait.
  Résultat : une pyramide « banals / utiles / exceptionnels » (cf. discussion).
- ``generer_roster`` — l'ensemble. Impose des **quotas** (les compagnons
  exceptionnels sont *garantis*, pas laissés au hasard), tire la **main de départ**,
  puis **désigne l'Élu** parmi elle — **après** génération, sans traitement
  particulier (ni calibre ni magie imposés) : on garantit ainsi qu'il n'a pas été
  généré différemment des autres. Sa montée en puissance vient **en jeu**, via la
  *prophétie des élus* (arc exclusif branché sur le drapeau — Phase 5). Sème enfin
  les **traîtres** (allégeance cachée, jamais l'Élu).

Hors périmètre (à venir) : **noms** (banques par royaume), **banque de portraits**,
**placement sur la carte** (dépend du terrain/settlements), et les **arcs de
prophétie**. La génération pose le socle ; le jeu ajoute par-dessus (prophéties →
montée des valeurs, cicatrices, artefacts).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from engine.hex_grid import HexCoord
from engine.rng import SeededRNG
from game.map_generator import MapConfig, MapGenerator
from game.terrain import TerrainType
from world.character import (
    Character,
    HiddenValue,
    Magie,
    Sexe,
    Trait,
    nouveau_character,
)
from world.names import nom_lieu, nom_personne, nom_royaume
from world.settlement import (
    FORCE_PAR_TAILLE,
    ConditionRalliement,
    Royaume,
    Settlement,
    TailleSettlement,
)
from world.world_state import WorldState


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

    # Carte & géographie (palier A).
    map_width: int = 60
    map_height: int = 60
    settlements_total: int = 28      # lieux peuplés répartis sur la carte
    kingdom_count: int = 5           # royaumes (grappes de settlements)
    horloge_du_destin: int = 60      # tours avant le déferlement (§1, §6)

    # Loi de puissance du calibre : C = U^p (p élevé = monde plus élitiste).
    calibre_exponent: float = 2.5
    exceptional_calibre_min: float = 0.85  # bande « exceptionnel » (quota)

    # Budget de points réparti sur les 9 traits, et concentration, selon calibre.
    budget_min: int = 185
    budget_max: int = 330
    concentration_min: float = 0.10
    concentration_max: float = 0.45
    trait_jitter: float = 5.0

    # Magie (hors budget) : incidence et force du potentiel.
    magic_incidence: float = 0.10
    magic_incidence_mystique: float = 0.55
    potential_min: int = 25
    potential_max: int = 100

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

    # Main de départ : `starting_hand` personnages tirés au sort — générés
    # EXACTEMENT comme le reste du roster (aucun traitement particulier).
    hand_rng = root.derive("main")
    main_depart = hand_rng.sample([p.id for p in personnages], config.starting_hand)

    # L'Élu : désigné APRÈS génération, parmi la main de départ. Il ne reçoit que
    # le drapeau — ni calibre, ni magie imposés : on est ainsi sûr qu'il n'a pas
    # été généré différemment des autres. Sa montée en puissance vient EN JEU, via
    # la prophétie des élus (arc exclusif branché sur ce drapeau — Phase 5).
    elu_rng = root.derive("elu")
    elu_id = elu_rng.choice(main_depart)
    personnages[elu_id].secrets.est_elu = True

    # Traîtres : une fraction du roster (jamais l'Élu), allégeance cachée.
    traitor_rng = root.derive("traitres")
    n_traitres = round(config.traitor_fraction * config.roster_size)
    candidats = [p.id for p in personnages if p.id != elu_id]
    for traitre_id in traitor_rng.sample(candidats, min(n_traitres, len(candidats))):
        personnages[traitre_id].secrets.allegiance.du_mal = True

    return Roster(personnages=personnages, main_depart=main_depart, elu_id=elu_id)


# =============================================================================
# GÉOGRAPHIE — settlements & royaumes greffés sur le terrain (palier A)
# =============================================================================

_TERRAINS_INCONSTRUCTIBLES = (TerrainType.WATER, TerrainType.MOUNTAIN)


def _distance(a, b) -> int:
    return HexCoord(*a).distance_to(HexCoord(*b))


def _placer_settlements(rng, tiles, nombre, min_dist) -> List[tuple]:
    """Échantillonne des positions terrestres espacées d'au moins ``min_dist``."""
    terres = [
        pos for pos, tile in tiles.items()
        if tile.base_terrain not in _TERRAINS_INCONSTRUCTIBLES
    ]
    rng.shuffle(terres)
    choisis: List[tuple] = []
    for pos in terres:
        if all(_distance(pos, c) >= min_dist for c in choisis):
            choisis.append(pos)
            if len(choisis) >= nombre:
                break
    return choisis


def _choisir_capitales(rng, positions, k) -> List[tuple]:
    """k capitales bien réparties (première au hasard, puis point le plus loin)."""
    caps = [rng.choice(positions)]
    while len(caps) < k and len(caps) < len(positions):
        loin = max(positions, key=lambda p: min(_distance(p, c) for c in caps))
        if loin in caps:
            break
        caps.append(loin)
    return caps


def _generer_geographie(rng, tiles, config):
    """Crée settlements + royaumes à partir du terrain. Retourne (settlements, royaumes)."""
    place_rng = rng.derive("settlements")
    # Espacement dérivé de la densité voulue.
    aire = config.map_width * config.map_height
    min_dist = max(3, int((aire / max(1, config.settlements_total)) ** 0.5 * 0.55))
    positions = _placer_settlements(place_rng, tiles, config.settlements_total, min_dist)

    kingdom_rng = rng.derive("royaumes")
    k = min(config.kingdom_count, len(positions))
    capitales = _choisir_capitales(kingdom_rng, positions, k)
    cap_index = {pos: i for i, pos in enumerate(capitales)}

    name_rng = rng.derive("noms_lieux")

    # Un royaume par capitale.
    royaumes = [
        Royaume(
            id=i,
            nom=nom_royaume(name_rng),
            capitale_id=-1,  # fixé une fois le settlement de capitale créé
            disposition=kingdom_rng.randint(0, 40),  # semé bas : à convaincre
            conditions=[
                ConditionRalliement(
                    domaine_requis=kingdom_rng.choice(
                        ["guerrier", "diplomate", "mage", "royaute"]
                    ),
                    seuil=kingdom_rng.randint(40, 85),
                )
            ],
        )
        for i in range(k)
    ]

    # Chaque settlement rejoint la capitale la plus proche.
    settlements: List[Settlement] = []
    for sid, pos in enumerate(positions):
        royaume_id = min(range(k), key=lambda i: _distance(pos, capitales[i]))
        if pos in cap_index:
            taille = TailleSettlement.CAPITALE
        else:
            taille = name_rng.choices(
                [TailleSettlement.BOURGADE, TailleSettlement.VILLAGE, TailleSettlement.CAMPEMENT],
                weights=[0.15, 0.35, 0.50],
                k=1,
            )[0]
        settlement = Settlement(
            id=sid,
            nom=nom_lieu(name_rng),
            position=pos,
            taille=taille,
            royaume_id=royaume_id,
            force_armee=FORCE_PAR_TAILLE[taille],
        )
        settlements.append(settlement)
        royaumes[royaume_id].settlement_ids.append(sid)
        if taille is TailleSettlement.CAPITALE:
            royaumes[royaume_id].capitale_id = sid

    return settlements, royaumes


# =============================================================================
# ORCHESTRATION — un monde complet (palier A + B + C assemblés)
# =============================================================================

def generer_monde(rng: SeededRNG, config: Optional[WorldGenConfig] = None) -> WorldState:
    """
    Produit un ``WorldState`` complet, headless et déterministe : terrain →
    settlements → royaumes → roster (nommé) → placement de la main de départ.

    C'est la sortie du worldgen (PROJET §5.7). Le placement sur la carte et les
    noms se posent ici ; le moteur de jeu (Phase 3+) fait ensuite évoluer l'état.
    """
    config = config or WorldGenConfig()

    # Terrain (générateur existant, headless).
    terrain_seed = rng.derive("terrain").seed
    tiles = MapGenerator(
        MapConfig(width=config.map_width, height=config.map_height, seed=terrain_seed)
    ).generate()

    # Géographie puis roster.
    settlements, royaumes = _generer_geographie(rng, tiles, config)
    roster = generer_roster(rng, config)

    # Noms des personnages (déterministes, un flux dédié).
    name_rng = rng.derive("noms_persos")
    for perso in roster.personnages:
        perso.nom = nom_personne(name_rng, perso.sexe)

    # Placement : la main de départ autour de la capitale du royaume de départ ;
    # les autres « chez eux », à un settlement (lieu de recrutement).
    place_rng = rng.derive("placement")
    depart = settlements[royaumes[0].capitale_id]
    for perso_id in roster.main_depart:
        perso = roster.personnages[perso_id]
        perso.affiliation = 0                       # le joueur contrôle sa main
        perso.location = depart.position
    autres = [p for p in roster.personnages if p.id not in roster.main_depart]
    for perso in autres:
        perso.location = place_rng.choice(settlements).position

    # Le royaume de départ est acquis d'office : la coalition naît chez lui.
    royaumes[0].disposition = 100
    royaumes[0].rallie = True

    return WorldState(
        seed=rng.seed,
        tiles=tiles,
        personnages=roster.personnages,
        settlements=settlements,
        royaumes=royaumes,
        main_depart=roster.main_depart,
        elu_id=roster.elu_id,
        horloge_du_destin=config.horloge_du_destin,
    )
