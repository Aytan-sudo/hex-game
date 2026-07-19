"""
Settlements & royaumes (worldgen palier A, PROJET.md §3).

Hiérarchie **campement → village → bourgade → capitale**. Les settlements se
regroupent en **royaumes** qui décident, in fine, de rejoindre la coalition —
avec d'éventuelles **conditions de ralliement** (cf. les Aiels de Jordan).

Structures de données pures (headless, sérialisables). La **résolution** de la
diplomatie (faire monter la disposition, remplir les conditions) est du ressort
de la Phase 4 ; ici on ne fait que **semer** l'état initial.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional, Tuple


class TailleSettlement(Enum):
    """Du plus petit au plus grand. Dimensionne l'armée et l'interface de ville."""
    CAMPEMENT = "campement"
    VILLAGE = "village"
    BOURGADE = "bourgade"
    CAPITALE = "capitale"


# Force d'armée fournie par taille (valeurs abstraites, affinées en Phase 4/6).
FORCE_PAR_TAILLE = {
    TailleSettlement.CAMPEMENT: 12,
    TailleSettlement.VILLAGE: 30,
    TailleSettlement.BOURGADE: 60,
    TailleSettlement.CAPITALE: 100,
}


@dataclass
class ConditionRalliement:
    """
    Ce qu'un royaume exige pour rejoindre la coalition : un seuil de réputation
    dans un **domaine** donné (§5.3). Extensible (prophétie requise, etc.).
    """
    domaine_requis: str  # facette de réputation : "guerrier", "diplomate", "mage"…
    seuil: int           # 0-100


@dataclass
class Settlement:
    """Un lieu peuplé, rattaché à un royaume, fournissant une armée."""
    id: int
    nom: str
    position: Tuple[int, int]  # (q, r) sur la carte
    taille: TailleSettlement
    royaume_id: Optional[int] = None
    force_armee: int = 0
    # Particularités du lieu (onglet « Spécial » de l'interface de ville) :
    # persos particuliers / histoires spécifiques (divineresse, lieu de
    # prophétie, artefact…). Décorrélées de la taille — la chose la plus
    # importante du monde peut se nicher dans un campement perdu. Semées
    # vides aujourd'hui ; remplies par le worldgen/le narratif (Phase 5).
    particularites: List[str] = field(default_factory=list)


@dataclass
class Royaume:
    """
    Un ensemble de settlements autour d'une capitale. C'est le royaume — pas le
    settlement isolé — qui **décide de rejoindre** la lutte finale.
    """
    id: int
    nom: str
    capitale_id: int
    settlement_ids: List[int] = field(default_factory=list)
    # Disposition courante envers la coalition (0-100) : semée basse, montée par
    # la diplomatie (Phase 4). Le ralliement se déclenche conditions remplies.
    disposition: int = 0
    conditions: List[ConditionRalliement] = field(default_factory=list)
    rallie: bool = False
