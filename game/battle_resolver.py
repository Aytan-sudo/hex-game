"""
BattleResolver — point d'entrée unique pour résoudre une bataille entre deux armées.

Pivot technique de la Phase 1 (cf. PROJET.md §7) : le combat devient *appelable*
sans ouvrir de fenêtre. Deux modes :

- ``AUTO`` : résolution headless — les deux camps sont joués par l'IA tactique
  sur un vrai champ de bataille généré, sans rendu ni délais de pacing. C'est
  le mode destiné à la future couche campagne (batailles intermédiaires).
- ``TACTICAL`` : bataille interactive jouée dans la fenêtre (délègue à
  ``run_tactical_battle``).

Dans les deux cas, les armées d'origine sont mises à jour (pertes, sort des
héros) et un ``BattleReport`` est retourné.
"""

from __future__ import annotations
from enum import Enum
from typing import Dict, Optional, Tuple

import pygame

from engine.unit import Army
from game.ai import AIPersonality
from game.terrain import TerrainType
from game.tactical_map import (
    BattleReport,
    TacticalBattle,
    run_tactical_battle,
)


class BattleMode(Enum):
    AUTO = "auto"          # résolution headless, sans rendu ni fenêtre
    TACTICAL = "tactical"  # bataille interactive jouée dans la fenêtre


# Garde-fou : borne large sur le nombre de pas d'auto-résolution (une bataille
# se termine bien avant — au pire au tirage de BATTLE.max_turns).
_MAX_AUTO_STEPS = 100_000


class BattleResolver:
    """
    Résout des batailles entre armées.

    Les dépendances de vue (``screen``, ``player_colors``) ne sont requises que
    pour le mode ``TACTICAL`` ; un resolver sans vue résout en ``AUTO``
    uniquement.
    """

    def __init__(
        self,
        screen: Optional[pygame.Surface] = None,
        player_colors: Optional[Dict[int, Tuple[int, int, int]]] = None,
    ):
        self.screen = screen
        self.player_colors = player_colors

    def resolve(
        self,
        attacker: Army,
        defender: Army,
        strategic_terrain: TerrainType = TerrainType.PLAINS,
        *,
        mode: BattleMode = BattleMode.AUTO,
        seed: Optional[int] = None,
        ai_players: Optional[Dict[int, AIPersonality]] = None,
    ) -> BattleReport:
        """
        Résout la bataille et applique le résultat aux armées d'origine.

        Args:
            attacker: Armée attaquante.
            defender: Armée défenseuse.
            strategic_terrain: Terrain stratégique où a lieu la rencontre.
            mode: ``AUTO`` (headless) ou ``TACTICAL`` (fenêtre).
            seed: Seed du champ de bataille (reproductibilité) ; aléatoire si absent.
            ai_players: Camps pilotés par l'IA et leur personnalité. En ``AUTO``,
                les camps non listés reçoivent ``AGGRESSIVE`` par défaut (une
                personnalité passive des deux côtés mènerait au match nul).

        Returns:
            Le ``BattleReport`` de la bataille.
        """
        if mode is BattleMode.TACTICAL:
            return self._resolve_tactical(
                attacker, defender, strategic_terrain, seed, ai_players
            )
        return self._resolve_auto(
            attacker, defender, strategic_terrain, seed, ai_players
        )

    def _resolve_auto(
        self,
        attacker: Army,
        defender: Army,
        strategic_terrain: TerrainType,
        seed: Optional[int],
        ai_players: Optional[Dict[int, AIPersonality]],
    ) -> BattleReport:
        """Auto-résolution : les deux camps joués par l'IA tactique, sans rendu."""
        personalities = {
            attacker.player_id: AIPersonality.AGGRESSIVE,
            defender.player_id: AIPersonality.AGGRESSIVE,
        }
        if ai_players:
            personalities.update(ai_players)

        battle = TacticalBattle(
            attacker, defender, strategic_terrain,
            seed=seed, ai_players=personalities,
        )

        # Pompe la boucle IA avec un dt énorme : les délais de pacing (pensés
        # pour la lisibilité à l'écran) sont écoulés à chaque pas.
        steps = 0
        while not battle.battle_over:
            battle.update_ai_turn(dt_ms=10 ** 9)
            steps += 1
            if steps > _MAX_AUTO_STEPS:
                raise RuntimeError(
                    "Auto-résolution non terminée après "
                    f"{_MAX_AUTO_STEPS} pas (boucle IA bloquée ?)"
                )

        battle.update_armies_after_battle()
        return battle.battle_report

    def _resolve_tactical(
        self,
        attacker: Army,
        defender: Army,
        strategic_terrain: TerrainType,
        seed: Optional[int],
        ai_players: Optional[Dict[int, AIPersonality]],
    ) -> BattleReport:
        """Bataille interactive : délègue à la boucle fenêtrée du tactique."""
        if self.screen is None or self.player_colors is None:
            raise ValueError(
                "Mode TACTICAL : le resolver doit être construit avec "
                "screen et player_colors."
            )
        return run_tactical_battle(
            self.screen, attacker, defender, self.player_colors,
            strategic_terrain=strategic_terrain,
            seed=seed,
            ai_players=ai_players,
        )
