"""
Écran de ville (Phase 4) — l'« interface d'interaction dimensionnée par la
taille de la ville » (PROJET.md §4), amorce de la couche ``settlement_ui/``
de l'architecture cible.

Trois cadres :

1. **Résumé** (bandeau) — l'identité du lieu : nom, taille, royaume,
   disposition/ralliement, condition.
2. **Présents** (colonne persistante) — les membres de la main sur place.
   Le perso surligné est **l'acteur** : toute action de l'onglet actif est
   faite par lui, et les libellés de chance se recalculent quand on change
   d'acteur (envoyer *la bonne personne* au bon endroit).
3. **Onglets** — le contenu spécifique. Leur *existence* dépend du lieu :
   Résidents (toujours), Audience (village et plus ; « Cour royale » à la
   capitale), Garnison (bourgade et plus), Spécial (si le lieu porte des
   ``particularites`` — décorrélé de la taille, cf. `world/settlement.py`).

Écran **modal** au-dessus de la carte (Échap pour sortir), même patron que
``run_tactical_battle``. Aucune règle ici : tout passe par ``world/actions``
via le ``CampaignState``. Chances et disposition restent des **libellés**
(jamais un chiffre — même esprit que la couche vrai/connu).

Ce module héberge aussi le vocabulaire visuel partagé avec la carte
(``ROYAUME_PALETTE``, libellés) — importé par ``campaign_map``, jamais
l'inverse, pour éviter le cycle d'imports.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional, Tuple

import pygame

from game.config import UI
from world.actions import (
    PA_COUT_CONVAINCRE,
    PA_COUT_RECRUTEMENT,
    chance_convaincre,
    chance_recrutement,
    condition_remplie,
    points_action_max,
)
from world.character import Character, Trait, label
from world.settlement import Settlement, TailleSettlement

if TYPE_CHECKING:
    from game.campaign_map import CampaignState

# Couleur de marqueur par royaume (cycle si plus de royaumes que d'entrées).
ROYAUME_PALETTE: Tuple[Tuple[int, int, int], ...] = (
    (66, 135, 245),   # bleu
    (235, 87, 87),    # rouge
    (39, 174, 96),    # vert
    (242, 153, 74),   # orange
    (155, 81, 224),   # violet
    (241, 196, 15),   # jaune
    (26, 188, 156),   # turquoise
    (149, 165, 166),  # gris
)

_VERT_OK = (140, 220, 140)
_ORANGE_ATTENTE = (220, 160, 120)
_OR = (255, 215, 100)


def libelle_chance(p: float) -> str:
    """Libellé grossier d'une probabilité de tirage — jamais un chiffre."""
    if p < 0.35:
        return "difficile"
    if p < 0.65:
        return "incertain"
    return "favorable"


def libelle_disposition(disposition: int) -> str:
    """Libellé grossier de la disposition d'un royaume — jamais un chiffre."""
    if disposition < 20:
        return "hostile"
    if disposition < 40:
        return "méfiante"
    if disposition < 60:
        return "hésitante"
    if disposition < 80:
        return "réceptive"
    return "presque acquise"


# =============================================================================
# ONGLETS — leur existence est pilotée par le lieu
# =============================================================================

def onglets_du_lieu(lieu: Settlement) -> List[str]:
    """Les onglets qu'offre ce lieu (c'est là que la taille *se sent*)."""
    onglets = ["residents"]
    if lieu.taille is not TailleSettlement.CAMPEMENT:
        onglets.append("audience")
    if lieu.taille in (TailleSettlement.BOURGADE, TailleSettlement.CAPITALE):
        onglets.append("garnison")
    if lieu.particularites:
        onglets.append("special")
    return onglets


def libelle_onglet(onglet: str, lieu: Settlement) -> str:
    if onglet == "audience" and lieu.taille is TailleSettlement.CAPITALE:
        return "Cour royale"
    return {"residents": "Résidents", "audience": "Audience",
            "garnison": "Garnison", "special": "Spécial"}[onglet]


# =============================================================================
# L'ÉCRAN
# =============================================================================

class VilleScreen:
    """Rendu + interactions de l'écran de ville. L'état de jeu reste dans
    ``CampaignState`` ; ici ne vivent que l'onglet actif et les zones
    cliquables de la frame courante."""

    HAUT = 84    # hauteur du bandeau résumé
    COL = 250    # largeur de la colonne des présents

    def __init__(self, screen: pygame.Surface, font: pygame.font.Font,
                 state: "CampaignState", lieu: Settlement):
        self.screen, self.font = screen, font
        self.state, self.lieu = state, lieu
        self.screen_width = screen.get_width()
        self.screen_height = screen.get_height()
        self.onglets = onglets_du_lieu(lieu)
        self.onglet_actif = self.onglets[0]
        self.message, self.message_timer = "", 0.0
        # Zones cliquables, reconstruites à chaque rendu.
        self.rects_onglets: List[Tuple[pygame.Rect, str]] = []
        self.rects_presents: List[Tuple[pygame.Rect, int]] = []
        self.boutons_recruter: List[Tuple[pygame.Rect, int]] = []
        self.bouton_convaincre: Optional[pygame.Rect] = None

    @property
    def acteur(self) -> Optional[Character]:
        return self.state.perso_selectionne

    # --- interactions -------------------------------------------------------

    def clic(self, pos: Tuple[int, int]) -> None:
        for rect, onglet in self.rects_onglets:
            if rect.collidepoint(pos):
                self.onglet_actif = onglet
                return
        for rect, perso_id in self.rects_presents:
            if rect.collidepoint(pos):
                self.state.selectionner(perso_id)  # nouvel acteur
                return
        if self.bouton_convaincre and self.bouton_convaincre.collidepoint(pos):
            self._agir_convaincre()
            return
        for rect, cible_id in self.boutons_recruter:
            if rect.collidepoint(pos):
                self._agir_recruter(cible_id)
                return

    def _annonce(self, texte: str) -> None:
        self.message, self.message_timer = texte, 2.5

    def _agir_convaincre(self) -> None:
        royaume = self.state.world.royaume(self.lieu.royaume_id)
        resultat = self.state.convaincre()
        if not resultat.ok:
            self._annonce(resultat.erreur)
        elif not resultat.reussite:
            self._annonce(f"Les émissaires de {royaume.nom} restent de marbre.")
        elif royaume.rallie:
            self._annonce(f"{royaume.nom} rejoint la coalition !")
        else:
            self._annonce(f"La disposition de {royaume.nom} s'améliore.")

    def _agir_recruter(self, cible_id: int) -> None:
        cible = self.state.world.personnage(cible_id)
        resultat = self.state.recruter(cible_id)
        if not resultat.ok:
            self._annonce(resultat.erreur)
        elif resultat.reussite:
            self._annonce(f"{cible.nom} rejoint votre main !")
        else:
            self._annonce(f"{cible.nom} décline votre offre.")

    # --- rendu --------------------------------------------------------------

    def render(self) -> None:
        self.rects_onglets, self.rects_presents = [], []
        self.boutons_recruter, self.bouton_convaincre = [], None

        self.screen.fill(UI.screen_bg_color)
        self._render_resume()
        self._render_presents()
        self._render_barre_onglets()
        self._render_contenu()
        self._render_message()
        aide = self.font.render("Échap : retour à la carte  |  1-4 : onglets",
                                True, UI.hint_color)
        self.screen.blit(aide, aide.get_rect(
            center=(self.screen_width // 2, self.screen_height - 18)))

    def _render_resume(self) -> None:
        """Cadre ① — l'identité du lieu."""
        pygame.draw.rect(self.screen, UI.panel_bg_color,
                         (0, 0, self.screen_width, self.HAUT))
        royaume = self.state.world.royaume(self.lieu.royaume_id)
        couleur_royaume = ROYAUME_PALETTE[royaume.id % len(ROYAUME_PALETTE)]

        titre = self.font.render(
            f"{self.lieu.taille.value.capitalize()} de {self.lieu.nom}",
            True, UI.text_color,
        )
        self.screen.blit(titre, (14, 10))
        nom_r = self.font.render(f"Royaume : {royaume.nom}", True, couleur_royaume)
        self.screen.blit(nom_r, (self.screen_width - nom_r.get_width() - 14, 10))

        if royaume.rallie:
            etat = self.font.render("ralliée à la coalition !", True, _VERT_OK)
            self.screen.blit(etat, (14, 34))
        else:
            etat = self.font.render(
                f"disposition : {libelle_disposition(royaume.disposition)}",
                True, UI.hint_color,
            )
            self.screen.blit(etat, (14, 34))
            for condition in royaume.conditions[:1]:
                remplie = condition_remplie(self.state.world, condition)
                texte = f"exige : renom de {condition.domaine_requis}"
                texte += " (remplie)" if remplie else ""
                cond = self.font.render(texte, True,
                                        _VERT_OK if remplie else _ORANGE_ATTENTE)
                self.screen.blit(cond, (14, 56))

    def _render_presents(self) -> None:
        """Cadre ② — les membres de la main sur place ; le surligné = acteur."""
        zone = pygame.Rect(0, self.HAUT, self.COL, self.screen_height - self.HAUT)
        pygame.draw.rect(self.screen, (32, 32, 42), zone)
        titre = self.font.render("Présents", True, UI.text_color)
        self.screen.blit(titre, (14, self.HAUT + 10))

        y = self.HAUT + 40
        for perso in self.state.persos_en(self.lieu.position):
            rangee = pygame.Rect(6, y, self.COL - 12, 52)
            if perso is self.acteur:
                pygame.draw.rect(self.screen, (55, 55, 75), rangee, border_radius=6)
                pygame.draw.rect(self.screen, UI.selection_color, rangee, 2, border_radius=6)

            # Portrait placeholder : cercle doré + initiale (la banque de
            # portraits réelle est au backlog worldgen).
            cx, cy = 28, y + 26
            pygame.draw.circle(self.screen, UI.hero_gold_color, (cx, cy), 16)
            pygame.draw.circle(self.screen, (30, 30, 40), (cx, cy), 16, 2)
            initiale = self.font.render(perso.nom[0].upper(), True, (30, 30, 40))
            self.screen.blit(initiale, initiale.get_rect(center=(cx, cy)))

            nom = self.font.render(perso.nom, True, _OR)
            self.screen.blit(nom, (52, y + 8))
            pa = self.font.render(
                f"PA {perso.pa_restants}/{points_action_max(perso)}",
                True, UI.hint_color,
            )
            self.screen.blit(pa, (52, y + 28))

            self.rects_presents.append((rangee, perso.id))
            y += 58

    def _render_barre_onglets(self) -> None:
        x = self.COL + 14
        for onglet in self.onglets:
            texte = libelle_onglet(onglet, self.lieu)
            surf = self.font.render(texte, True, UI.text_color)
            rect = pygame.Rect(x, self.HAUT + 8, surf.get_width() + 24, 30)
            actif = onglet == self.onglet_actif
            couleur = (70, 70, 95) if actif else (45, 45, 58)
            pygame.draw.rect(self.screen, couleur, rect, border_radius=5)
            if actif:
                pygame.draw.rect(self.screen, UI.selection_color, rect, 2, border_radius=5)
            self.screen.blit(surf, surf.get_rect(center=rect.center))
            self.rects_onglets.append((rect, onglet))
            x += rect.width + 8

    def _zone_contenu(self) -> pygame.Rect:
        return pygame.Rect(
            self.COL + 14, self.HAUT + 48,
            self.screen_width - self.COL - 28,
            self.screen_height - self.HAUT - 88,
        )

    def _render_contenu(self) -> None:
        """Cadre ③ — le contenu de l'onglet actif."""
        zone = self._zone_contenu()
        pygame.draw.rect(self.screen, (32, 32, 42), zone, border_radius=6)
        if self.onglet_actif == "residents":
            self._contenu_residents(zone)
        elif self.onglet_actif == "audience":
            self._contenu_audience(zone)
        elif self.onglet_actif == "garnison":
            self._contenu_garnison(zone)
        elif self.onglet_actif == "special":
            self._contenu_special(zone)

    def _bouton(self, rect: pygame.Rect, texte: str, actif: bool,
                teinte=(60, 100, 60), teinte_survol=(80, 120, 80)) -> None:
        if actif:
            survole = rect.collidepoint(pygame.mouse.get_pos())
            couleur = teinte_survol if survole else teinte
        else:
            couleur = (70, 70, 80)
        pygame.draw.rect(self.screen, couleur, rect, border_radius=5)
        surf = self.font.render(texte, True, UI.text_color)
        self.screen.blit(surf, surf.get_rect(center=rect.center))

    def _contenu_residents(self, zone: pygame.Rect) -> None:
        acteur = self.acteur
        recrues = self.state.recrutables_ici()
        if not recrues:
            vide = self.font.render("Personne à recruter ici.", True, UI.hint_color)
            self.screen.blit(vide, (zone.x + 14, zone.y + 14))
            return

        y = zone.y + 12
        for recrue in recrues:
            nom = self.font.render(recrue.nom, True, _OR)
            self.screen.blit(nom, (zone.x + 14, y))

            # Ce qu'on *croit* savoir : la couche vrai/connu à l'écran.
            traits = " · ".join(
                f"{t.value.capitalize()} : {label(recrue.caracteristiques[t])}"
                for t in (Trait.PUISSANCE, Trait.CHARISME, Trait.VIGUEUR)
            )
            connu = self.font.render(traits, True, UI.hint_color)
            self.screen.blit(connu, (zone.x + 14, y + 20))

            avis = self.font.render(
                f"recrutement {libelle_chance(chance_recrutement(acteur, recrue))}",
                True, UI.hint_color,
            )
            self.screen.blit(avis, (zone.x + 14, y + 40))

            # max() : sur un écran étroit, le bouton reste dans sa zone (il ne
            # doit jamais chevaucher la colonne des présents).
            bouton = pygame.Rect(max(zone.x + 8, zone.right - 144), y + 12, 130, 30)
            self._bouton(bouton, f"Recruter ({PA_COUT_RECRUTEMENT} PA)",
                         acteur.pa_restants >= PA_COUT_RECRUTEMENT)
            self.boutons_recruter.append((bouton, recrue.id))
            y += 68

    def _contenu_audience(self, zone: pygame.Rect) -> None:
        acteur = self.acteur
        royaume = self.state.world.royaume(self.lieu.royaume_id)
        if royaume.rallie:
            texte = self.font.render(
                f"{royaume.nom} est rallié à la coalition.", True, _VERT_OK
            )
            self.screen.blit(texte, (zone.x + 14, zone.y + 14))
            return

        plaidoyer = self.font.render(
            f"Votre plaidoyer s'annonce {libelle_chance(chance_convaincre(acteur))}.",
            True, UI.hint_color,
        )
        self.screen.blit(plaidoyer, (zone.x + 14, zone.y + 14))

        bouton = pygame.Rect(zone.x + 14, zone.y + 44, 160, 30)
        self._bouton(bouton, f"Convaincre ({PA_COUT_CONVAINCRE} PA)",
                     acteur.pa_restants >= PA_COUT_CONVAINCRE,
                     teinte=(60, 80, 120), teinte_survol=(80, 100, 140))
        self.bouton_convaincre = bouton

    def _contenu_garnison(self, zone: pygame.Rect) -> None:
        royaume = self.state.world.royaume(self.lieu.royaume_id)
        force = self.font.render(
            f"Force d'armée : {self.lieu.force_armee}", True, UI.text_color
        )
        self.screen.blit(force, (zone.x + 14, zone.y + 14))
        destin = ("Aux ordres de la coalition." if royaume.rallie
                  else "Rejoindra la coalition au ralliement du royaume.")
        note = self.font.render(destin, True, UI.hint_color)
        self.screen.blit(note, (zone.x + 14, zone.y + 38))

    def _contenu_special(self, zone: pygame.Rect) -> None:
        y = zone.y + 14
        for particularite in self.lieu.particularites:
            ligne = self.font.render(f"• {particularite}", True, _OR)
            self.screen.blit(ligne, (zone.x + 14, y))
            y += 24

    def _render_message(self) -> None:
        if self.message_timer > 0 and self.message:
            surf = self.font.render(self.message, True, (255, 200, 100))
            rect = surf.get_rect(center=(self.screen_width // 2, self.HAUT + 24))
            pygame.draw.rect(self.screen, UI.panel_bg_color, rect.inflate(20, 10))
            self.screen.blit(surf, rect)


def run_ville(screen: pygame.Surface, font: pygame.font.Font,
              state: "CampaignState", lieu: Settlement) -> Tuple[bool, str]:
    """
    Boucle modale de l'écran de ville. Retourne ``(continuer, dernier_message)``
    — ``continuer=False`` propage la fermeture du jeu ; le dernier message est
    réaffiché sur la carte au retour.
    """
    ecran = VilleScreen(screen, font, state, lieu)
    clock = pygame.time.Clock()
    dt = 0.0

    while True:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False, ecran.message
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return True, ecran.message
                index = event.key - pygame.K_1
                if 0 <= index < len(ecran.onglets):
                    ecran.onglet_actif = ecran.onglets[index]
            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                ecran.clic(event.pos)

        if ecran.message_timer > 0:
            ecran.message_timer -= dt

        ecran.render()
        pygame.display.flip()
        dt = clock.tick(60) / 1000.0
