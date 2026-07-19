"""
Panneau de mission (Phase 4→5) — lancer une mission depuis la carte.

Le flux voulu : on clique un perso sur une case (ville ou non), bouton
**« Mission »** (ou touche M) → la **panoplie de la case** s'affiche (une
ville en offre plus), on choisit la mission et on compose l'**équipe** parmi
les présents disponibles (1..EQUIPE_MAX), puis Lancer. Les missions sont le
levier essentiel de l'action des persos sur le monde — ce panneau est leur
porte d'entrée.

Fenêtre modale légère au-dessus de la carte (Échap pour annuler). Aucune
règle ici : validation et effets vivent dans ``world/missions.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

import pygame

from game.config import UI
from game.ville_ui import libelle_chance
from world.missions import (
    EQUIPE_MAX,
    MissionPossible,
    chance_mission,
    Mission,
    missions_possibles,
)

if TYPE_CHECKING:
    from game.campaign_map import CampaignState

_OR = (255, 215, 100)


class MissionScreen:
    """Fenêtre de lancement : choix de la mission + composition de l'équipe."""

    def __init__(self, screen: pygame.Surface, font: pygame.font.Font,
                 state: "CampaignState", pos: Tuple[int, int]):
        self.screen, self.font = screen, font
        self.state, self.pos = state, pos
        self.possibles = missions_possibles(state.world, pos)
        self.choix: Optional[int] = None      # index dans self.possibles
        # Le perso qui a ouvert le panneau embarque d'office.
        self.equipe: List[int] = [state.selected_id] if state.selected_id is not None else []
        self.message = ""
        self.lancee: Optional[str] = None     # message final si mission lancée
        # Zones cliquables, reconstruites à chaque rendu.
        self.rects_missions: List[Tuple[pygame.Rect, int]] = []
        self.rects_equipe: List[Tuple[pygame.Rect, int]] = []
        self.bouton_lancer: Optional[pygame.Rect] = None

    def disponibles(self):
        """Les membres de la main sur cette case, libres de tout engagement."""
        return [p for p in self.state.persos_en(self.pos) if p.mission_id is None]

    # --- interactions -------------------------------------------------------

    def clic(self, pos: Tuple[int, int]) -> None:
        for rect, index in self.rects_missions:
            if rect.collidepoint(pos):
                self.choix = index
                return
        for rect, perso_id in self.rects_equipe:
            if rect.collidepoint(pos):
                if perso_id in self.equipe:
                    self.equipe.remove(perso_id)
                elif len(self.equipe) < EQUIPE_MAX:
                    self.equipe.append(perso_id)
                return
        if self.bouton_lancer and self.bouton_lancer.collidepoint(pos):
            self._lancer()

    def _lancer(self) -> None:
        if self.choix is None or not self.equipe:
            self.message = "choisis une mission et au moins un participant"
            return
        possible = self.possibles[self.choix]
        resultat = self.state.lancer_mission(possible, list(self.equipe))
        if resultat.ok:
            self.lancee = f"Mission lancée : {possible.libelle} ({possible.duree} tours)"
        else:
            self.message = resultat.erreur

    # --- rendu --------------------------------------------------------------

    def render(self) -> None:
        self.rects_missions, self.rects_equipe = [], []
        self.bouton_lancer = None

        largeur = min(640, self.screen.get_width() - 40)
        hauteur = min(460, self.screen.get_height() - 40)
        fenetre = pygame.Rect(0, 0, largeur, hauteur)
        fenetre.center = (self.screen.get_width() // 2, self.screen.get_height() // 2)
        pygame.draw.rect(self.screen, UI.panel_bg_color, fenetre, border_radius=8)
        pygame.draw.rect(self.screen, (110, 110, 140), fenetre, 2, border_radius=8)
        x, y = fenetre.x + 16, fenetre.y + 12

        titre = self.font.render("Missions possibles ici", True, UI.text_color)
        self.screen.blit(titre, (x, y))
        y += 30

        if not self.possibles:
            vide = self.font.render("Aucune mission possible sur cette case.",
                                    True, UI.hint_color)
            self.screen.blit(vide, (x, y))
        for index, possible in enumerate(self.possibles):
            rect = pygame.Rect(x, y, largeur - 32, 28)
            if index == self.choix:
                pygame.draw.rect(self.screen, (55, 55, 75), rect, border_radius=5)
                pygame.draw.rect(self.screen, UI.selection_color, rect, 2, border_radius=5)
            ligne = self.font.render(
                f"{possible.libelle}  —  {possible.duree} tours", True, _OR
            )
            self.screen.blit(ligne, (rect.x + 8, rect.y + 5))
            self.rects_missions.append((rect, index))
            y += 32

        y += 12
        entete = self.font.render(
            f"Équipe (1 à {EQUIPE_MAX}) — cliquer pour embarquer :",
            True, UI.text_color,
        )
        self.screen.blit(entete, (x, y))
        y += 28
        for perso in self.disponibles():
            rect = pygame.Rect(x, y, largeur - 32, 26)
            embarque = perso.id in self.equipe
            if embarque:
                pygame.draw.rect(self.screen, (45, 70, 45), rect, border_radius=5)
            coche = "☑" if embarque else "☐"
            ligne = self.font.render(f"{coche}  {perso.nom}", True,
                                     _OR if embarque else UI.hint_color)
            self.screen.blit(ligne, (rect.x + 8, rect.y + 4))
            self.rects_equipe.append((rect, perso.id))
            y += 30

        # L'estimation collective, en libellé — recalculée selon l'équipe.
        if self.choix is not None and self.equipe:
            possible = self.possibles[self.choix]
            apercu = Mission(id=-1, type=possible.type, position=self.pos,
                             participants=list(self.equipe),
                             tours_restants=possible.duree,
                             cible_id=possible.cible_id)
            estimation = self.font.render(
                f"issue estimée : {libelle_chance(chance_mission(self.state.world, apercu))}",
                True, UI.hint_color,
            )
            self.screen.blit(estimation, (x, fenetre.bottom - 76))

        bouton = pygame.Rect(fenetre.right - 156, fenetre.bottom - 46, 140, 32)
        actif = self.choix is not None and bool(self.equipe)
        survole = bouton.collidepoint(pygame.mouse.get_pos())
        couleur = ((80, 120, 80) if survole else (60, 100, 60)) if actif else (70, 70, 80)
        pygame.draw.rect(self.screen, couleur, bouton, border_radius=5)
        texte = self.font.render("Lancer", True, UI.text_color)
        self.screen.blit(texte, texte.get_rect(center=bouton.center))
        self.bouton_lancer = bouton

        if self.message:
            erreur = self.font.render(self.message, True, (235, 150, 130))
            self.screen.blit(erreur, (x, fenetre.bottom - 46))

        aide = self.font.render("Échap : annuler", True, UI.hint_color)
        self.screen.blit(aide, (x, fenetre.bottom - 24))


def run_missions(screen: pygame.Surface, font: pygame.font.Font,
                 state: "CampaignState", pos: Tuple[int, int]) -> Tuple[bool, str]:
    """
    Boucle modale du panneau de mission. Retourne ``(continuer,
    dernier_message)`` — la fenêtre se ferme d'elle-même une fois la mission
    lancée, et le message est réaffiché sur la carte.
    """
    ecran = MissionScreen(screen, font, state, pos)
    clock = pygame.time.Clock()

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False, ""
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return True, ""
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                ecran.clic(event.pos)
                if ecran.lancee:
                    return True, ecran.lancee

        ecran.render()
        pygame.display.flip()
        clock.tick(60)
