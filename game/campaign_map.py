"""
Carte de campagne (Phase 3, volet UI) — « sélectionne perso → points d'action ».

C'est l'écran du **pivot** : on y pilote les personnages de la main du joueur
sur le monde du worldgen (``WorldState``), à la place des armées du wargame.
Toute la logique de jeu vit dans ``world/actions.py`` et ``world/turn.py``
(pures, headless) ; ce module ne fait que **sélectionner, afficher, appeler**.

Découpage (même patron que ``strategic_map.py``) :

- ``CampaignState`` — l'état d'interface (sélection courante, destinations en
  surbrillance). **Sans Pygame**, donc testable headless.
- ``CampaignRenderer`` — le rendu (terrain, settlements colorés par royaume,
  marqueurs de personnages, panneaux, bouton fin de tour).
- ``run_campaign(screen, config)`` — génère un monde, le démarre et boucle.

L'écran inclut un **panneau de ville minimal** (embryon de l'interface
d'interaction du §4, étoffée en Phase 4) : un perso sélectionné posé sur un
settlement voit les personnages qui y résident et peut tenter de les
**recruter** (tirage semé côté ``world/actions``, échec possible qui coûte
les PA). Hors périmètre (phases suivantes) : convaincre/gérer, l'interface
de ville complète dimensionnée par la taille.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Set, Tuple

import pygame

from engine.camera import Camera
from engine.hex_grid import HexCoord, HexGrid
from engine.input_handler import CameraController
from engine.rng import SeededRNG
from game.config import INPUT, UI
from game.mission_ui import run_missions
from game.ville_ui import ROYAUME_PALETTE, libelle_disposition, run_ville
from world.actions import (
    ResultatAction,
    convaincre,
    deplacer,
    destinations_accessibles,
    points_action_max,
)
from world.missions import (
    MissionPossible,
    ResultatMission,
    lancer_mission,
    missions_possibles,
)
from world.settlement import Royaume
from world.character import Character, Trait, label
from world.settlement import Settlement, TailleSettlement
from world.turn import demarrer_partie, finir_tour
from world.world_state import WorldState
from world.worldgen import WorldGenConfig, generer_monde

# Durée (s) du voile « le temps passe » affiché à chaque fin de tour.
TRANSITION_TOUR_S = 1.2

# Rayon du marqueur de settlement, en fraction de la taille d'hex.
_RAYON_PAR_TAILLE = {
    TailleSettlement.CAMPEMENT: 0.22,
    TailleSettlement.VILLAGE: 0.32,
    TailleSettlement.BOURGADE: 0.42,
    TailleSettlement.CAPITALE: 0.55,
}


class CampaignState:
    """
    État d'interface de la campagne : quel personnage est sélectionné, quels
    hexes sont atteignables. Ne contient **aucune règle** : la validation et
    les effets passent par ``world/actions.py`` / ``world/turn.py``.
    """

    def __init__(self, world: WorldState, action_rng: Optional[SeededRNG] = None):
        self.world = world
        self.selected_id: Optional[int] = None
        self.destinations: Set[Tuple[int, int]] = set()
        # Index positionnel des settlements, pour les panneaux d'info.
        self.settlement_par_pos: Dict[Tuple[int, int], Settlement] = {
            s.position: s for s in world.settlements
        }
        # Flux d'aléa des tirages d'action, dérivé du seed du monde (injectable
        # en test) : même monde + mêmes tentatives ⇒ mêmes issues.
        self.action_rng = action_rng or SeededRNG(world.seed).derive("actions")

    # --- sélection ----------------------------------------------------------

    @property
    def perso_selectionne(self) -> Optional[Character]:
        if self.selected_id is None:
            return None
        return self.world.personnage(self.selected_id)

    def persos_joueur(self) -> List[Character]:
        """Les personnages que le joueur contrôle (sa main, affiliation 0)."""
        return [p for p in self.world.personnages if p.affiliation == 0]

    def persos_en(self, pos: Tuple[int, int]) -> List[Character]:
        return [p for p in self.persos_joueur() if p.location == pos]

    def selectionner(self, perso_id: Optional[int]) -> None:
        self.selected_id = perso_id
        self._rafraichir_destinations()

    def deselectionner(self) -> None:
        self.selectionner(None)

    def _rafraichir_destinations(self) -> None:
        if self.selected_id is None:
            self.destinations = set()
        else:
            self.destinations = destinations_accessibles(self.world, self.selected_id)

    # --- entrées de jeu -----------------------------------------------------

    def clic_hex(self, pos: Tuple[int, int]) -> Tuple[str, object]:
        """
        Clic gauche sur un hex. Le **déplacement prime** : si un perso est
        sélectionné et la case atteignable, il s'y rend — y compris quand
        elle est occupée par d'autres membres de la main (une ville héberge
        tout le monde) ; la sélection des occupants se fait ensuite (re-clic
        sur place = cycle). Sinon : (``"selection"``, perso) si un personnage
        du joueur s'y trouve, (``"rien"``, None) autrement — la sélection est
        conservée (la désélection passe par le clic droit).
        """
        perso = self.perso_selectionne
        if perso is not None and pos in self.destinations and pos != perso.location:
            resultat = deplacer(self.world, self.selected_id, pos)
            if resultat.ok:
                self._rafraichir_destinations()
            return ("deplacement", resultat)

        # Les persos en mission sont indisponibles : pas sélectionnables.
        persos = [p for p in self.persos_en(pos) if p.mission_id is None]
        if persos:
            ids = [p.id for p in persos]
            if self.selected_id in ids:
                suivant = ids[(ids.index(self.selected_id) + 1) % len(ids)]
            else:
                suivant = ids[0]
            self.selectionner(suivant)
            return ("selection", self.perso_selectionne)

        return ("rien", None)

    def recrutables_ici(self) -> List[Character]:
        """Les résidents recrutables là où se tient le perso sélectionné."""
        perso = self.perso_selectionne
        if perso is None or perso.location not in self.settlement_par_pos:
            return []
        return [p for p in self.world.personnages
                if p.location == perso.location and p.affiliation is None]

    def missions_possibles_ici(self) -> List[MissionPossible]:
        """La panoplie de missions lançables depuis la case du perso sélectionné."""
        perso = self.perso_selectionne
        if perso is None or perso.location is None:
            return []
        return missions_possibles(self.world, perso.location)

    def lancer_mission(
        self, possible: MissionPossible, participants: List[int]
    ) -> ResultatAction:
        """Lance une mission depuis la case du perso sélectionné."""
        perso = self.perso_selectionne
        if perso is None:
            return ResultatAction(ok=False, erreur="aucun personnage sélectionné")
        resultat = lancer_mission(self.world, possible.type, perso.location,
                                  participants, possible.cible_id)
        if resultat.ok:
            self.deselectionner()  # l'équipe est partie en mission
        return resultat

    def royaume_ici(self) -> Optional[Royaume]:
        """Le royaume du settlement où se tient le perso sélectionné."""
        perso = self.perso_selectionne
        if perso is None:
            return None
        lieu = self.settlement_par_pos.get(perso.location)
        return None if lieu is None else self.world.royaume(lieu.royaume_id)

    def convaincre(self) -> ResultatAction:
        """Plaide pour la coalition auprès du royaume du lieu (tirage semé)."""
        royaume = self.royaume_ici()
        if self.selected_id is None or royaume is None:
            return ResultatAction(ok=False, erreur="aucun émissaire en ville")
        resultat = convaincre(self.world, self.action_rng, self.selected_id, royaume.id)
        if resultat.ok:
            self._rafraichir_destinations()  # les PA ont bougé
        return resultat

    def finir_tour(self) -> List[ResultatMission]:
        """Clôt le tour ; retourne les issues des missions résolues (annonces)."""
        resultats = finir_tour(self.world, self.action_rng)
        self._rafraichir_destinations()  # les PA sont revenus
        return resultats


class CampaignRenderer:
    """Rendu de la carte de campagne (même patron que ``StrategicRenderer``)."""

    def __init__(self, screen: pygame.Surface, font: pygame.font.Font):
        self.screen = screen
        self.font = font
        self.gros_font = pygame.font.Font(None, 72)  # « Tour N » du voile
        self.screen_width = screen.get_width()
        self.screen_height = screen.get_height()
        self.end_turn_button_rect = pygame.Rect(
            self.screen_width - UI.button_width - UI.button_margin,
            UI.button_margin,
            UI.button_width,
            UI.button_height,
        )
        # Boutons reconstruits à chaque frame rendue : « Entrer » du résumé de
        # ville (l'interaction vit dans game/ville_ui.py) et « Mission » du
        # panneau bas (la porte d'entrée du levier essentiel, game/mission_ui.py).
        self.bouton_entrer: Optional[pygame.Rect] = None
        self.bouton_mission: Optional[pygame.Rect] = None

    def render_frame(
        self,
        state: CampaignState,
        camera: Camera,
        hex_grid: HexGrid,
        hover_hex: Optional[HexCoord],
        message: str,
        message_timer: float,
    ) -> None:
        self.screen.fill(UI.screen_bg_color)
        self._render_tiles(state, camera, hex_grid, hover_hex)
        self._render_settlements(state, camera, hex_grid)
        self._render_persos(state, camera, hex_grid)
        self._render_top_panel(state, camera)
        self._render_ville_panel(state)
        self._render_bottom_panel(state, hover_hex)
        self._render_message(message, message_timer)

    # --- couches ------------------------------------------------------------

    def _render_tiles(
        self,
        state: CampaignState,
        camera: Camera,
        hex_grid: HexGrid,
        hover_hex: Optional[HexCoord],
    ) -> None:
        selectionne = state.perso_selectionne
        pos_selection = selectionne.location if selectionne else None

        for coord_tuple, tile in state.world.tiles.items():
            coord = HexCoord(*coord_tuple)
            center = hex_grid.hex_to_pixel(coord, camera.offset)
            if not self._is_on_screen(center, camera.hex_size):
                continue

            color = tile.display_color
            if coord_tuple in state.destinations:
                color = tuple(min(255, c + 45) for c in color)
            if coord_tuple == pos_selection:
                color = UI.selection_color
            if hover_hex and coord_tuple == hover_hex.to_tuple():
                color = tuple(min(255, c + 20) for c in color)

            vertices = hex_grid.get_hex_corners(coord, camera.offset)
            pygame.draw.polygon(self.screen, color, vertices)
            pygame.draw.polygon(self.screen, (50, 50, 60), vertices, 1)

    def _render_settlements(
        self, state: CampaignState, camera: Camera, hex_grid: HexGrid
    ) -> None:
        for settlement in state.world.settlements:
            center = hex_grid.hex_to_pixel(HexCoord(*settlement.position), camera.offset)
            x, y = int(center[0]), int(center[1])
            if not self._is_on_screen((x, y), camera.hex_size):
                continue

            color = ROYAUME_PALETTE[settlement.royaume_id % len(ROYAUME_PALETTE)]
            rayon = max(3, int(camera.hex_size * _RAYON_PAR_TAILLE[settlement.taille]))
            pygame.draw.circle(self.screen, color, (x, y), rayon)
            contour = (255, 255, 255) if settlement.taille is TailleSettlement.CAPITALE else (30, 30, 40)
            pygame.draw.circle(self.screen, contour, (x, y), rayon, 2)

            # Le nom n'apparaît qu'à un zoom lisible (capitales toujours).
            if camera.hex_size >= 24 or settlement.taille is TailleSettlement.CAPITALE:
                nom = self.font.render(settlement.nom, True, UI.text_color)
                self.screen.blit(nom, nom.get_rect(center=(x, y + rayon + 10)))

    def _render_persos(
        self, state: CampaignState, camera: Camera, hex_grid: HexGrid
    ) -> None:
        # Groupés par case : un seul losange + badge de cohabitation.
        par_pos: Dict[Tuple[int, int], List[Character]] = {}
        for perso in state.persos_joueur():
            if perso.location is not None:
                par_pos.setdefault(perso.location, []).append(perso)

        for pos, persos in par_pos.items():
            center = hex_grid.hex_to_pixel(HexCoord(*pos), camera.offset)
            x, y = int(center[0]), int(center[1])
            if not self._is_on_screen((x, y), camera.hex_size):
                continue

            devant = state.perso_selectionne if state.perso_selectionne in persos else persos[0]
            rayon = int(camera.hex_size * 0.38)
            points = [(x, y - rayon), (x + rayon, y), (x, y + rayon), (x - rayon, y)]
            # Losange grisé quand tout le monde ici est parti en mission.
            en_mission = all(p.mission_id is not None for p in persos)
            fond = (150, 150, 150) if en_mission else UI.hero_gold_color
            pygame.draw.polygon(self.screen, fond, points)
            pygame.draw.polygon(self.screen, (30, 30, 40), points, 2)

            if devant is state.perso_selectionne:
                r2 = rayon + 4
                halo = [(x, y - r2), (x + r2, y), (x, y + r2), (x - r2, y)]
                pygame.draw.polygon(self.screen, UI.selection_color, halo, 3)

            initiale = self.font.render(devant.nom[0].upper(), True, (30, 30, 40))
            self.screen.blit(initiale, initiale.get_rect(center=(x, y)))

            if len(persos) > 1:
                badge = self.font.render(str(len(persos)), True, UI.text_color)
                self.screen.blit(badge, (x + rayon - 2, y - rayon - 6))

    # --- panneaux -----------------------------------------------------------

    def _render_top_panel(self, state: CampaignState, camera: Camera) -> None:
        pygame.draw.rect(self.screen, UI.panel_bg_color,
                         (0, 0, self.screen_width, UI.top_panel_height))
        monde = state.world
        tour = self.font.render(f"Tour {monde.tour}", True, UI.text_color)
        texte_horloge = f"Horloge du destin : {monde.horloge_du_destin}"
        if monde.missions:
            texte_horloge += f"  ·  Missions en cours : {len(monde.missions)}"
        horloge = self.font.render(texte_horloge, True, (255, 180, 120))
        self.screen.blit(tour, (10, 8))
        self.screen.blit(horloge, (10, 28))

        hint = self.font.render(
            "Clic: sélectionner/déplacer | Entrée: ville | M: mission | Espace: fin de tour",
            True, UI.hint_color,
        )
        self.screen.blit(hint, (240, 18))

        zoom = self.font.render(f"Zoom: {camera.zoom_level_name}", True, UI.hint_color)
        self.screen.blit(zoom, (self.screen_width - 300, 8))
        self._render_end_turn_button()

    def _render_end_turn_button(self) -> None:
        hovered = self.end_turn_button_rect.collidepoint(pygame.mouse.get_pos())
        btn_color = (80, 120, 80) if hovered else (60, 100, 60)
        pygame.draw.rect(self.screen, btn_color, self.end_turn_button_rect, border_radius=5)
        pygame.draw.rect(self.screen, (100, 150, 100), self.end_turn_button_rect, 2, border_radius=5)
        texte = self.font.render("Fin de tour", True, UI.text_color)
        self.screen.blit(texte, texte.get_rect(center=self.end_turn_button_rect.center))

    def _render_ville_panel(self, state: CampaignState) -> None:
        """
        Résumé de ville : l'identité du lieu en un coup d'œil. Toute
        l'**interaction** vit dans l'écran de ville (``game/ville_ui.py``),
        ouvert par le bouton « Entrer » ou la touche Entrée.
        """
        self.bouton_entrer = None
        perso = state.perso_selectionne
        lieu = state.settlement_par_pos.get(perso.location) if perso else None
        if perso is None or lieu is None:
            return

        royaume = state.world.royaume(lieu.royaume_id)
        largeur = 320
        x = self.screen_width - largeur - UI.button_margin
        y = UI.top_panel_height + UI.button_height + 2 * UI.button_margin
        panel = pygame.Rect(x, y, largeur, 96)
        pygame.draw.rect(self.screen, UI.panel_bg_color, panel, border_radius=6)
        pygame.draw.rect(self.screen, (90, 90, 110), panel, 2, border_radius=6)

        titre = self.font.render(
            f"{lieu.taille.value.capitalize()} de {lieu.nom}", True, UI.text_color
        )
        self.screen.blit(titre, (x + 10, y + 8))

        couleur_royaume = ROYAUME_PALETTE[royaume.id % len(ROYAUME_PALETTE)]
        etat = ("ralliée à la coalition" if royaume.rallie
                else f"disposition : {libelle_disposition(royaume.disposition)}")
        nom_r = self.font.render(f"{royaume.nom} — {etat}", True, couleur_royaume)
        self.screen.blit(nom_r, (x + 10, y + 32))

        nb = len(state.recrutables_ici())
        infos = self.font.render(f"{nb} résident(s) à rencontrer", True, UI.hint_color)
        self.screen.blit(infos, (x + 10, y + 62))

        bouton = pygame.Rect(x + largeur - 130, y + 56, 120, 30)
        survole = bouton.collidepoint(pygame.mouse.get_pos())
        pygame.draw.rect(self.screen, (80, 100, 140) if survole else (60, 80, 120),
                         bouton, border_radius=5)
        texte = self.font.render("Entrer (Entrée)", True, UI.text_color)
        self.screen.blit(texte, texte.get_rect(center=bouton.center))
        self.bouton_entrer = bouton

    def entrer_clique(self, pos: Tuple[int, int]) -> bool:
        """Vrai si le bouton « Entrer » du résumé de ville est sous ``pos``."""
        return self.bouton_entrer is not None and self.bouton_entrer.collidepoint(pos)

    def mission_clique(self, pos: Tuple[int, int]) -> bool:
        """Vrai si le bouton « Mission » du panneau bas est sous ``pos``."""
        return self.bouton_mission is not None and self.bouton_mission.collidepoint(pos)

    def _render_bottom_panel(self, state: CampaignState, hover_hex: Optional[HexCoord]) -> None:
        pygame.draw.rect(
            self.screen, UI.panel_bg_color,
            (0, self.screen_height - UI.bottom_panel_height,
             self.screen_width, UI.bottom_panel_height),
        )

        self.bouton_mission = None
        perso = state.perso_selectionne
        if perso is not None:
            vigueur = label(perso.caracteristiques[Trait.VIGUEUR])
            info = (f"{perso.nom} — PA {perso.pa_restants}/{points_action_max(perso)}"
                    f" — Vigueur : {vigueur}")
            lieu = state.settlement_par_pos.get(perso.location)
            if lieu is not None:
                info += f" — à {lieu.nom}"
            surf = self.font.render(info, True, (255, 215, 100))
            self.screen.blit(surf, (10, self.screen_height - 52))

            # La porte d'entrée des missions : depuis n'importe quelle case.
            if perso.mission_id is None:
                bouton = pygame.Rect(
                    self.screen_width - 150,
                    self.screen_height - UI.bottom_panel_height + 14, 135, 32,
                )
                survole = bouton.collidepoint(pygame.mouse.get_pos())
                pygame.draw.rect(self.screen,
                                 (120, 90, 150) if survole else (100, 70, 130),
                                 bouton, border_radius=5)
                texte = self.font.render("Mission (M)", True, UI.text_color)
                self.screen.blit(texte, texte.get_rect(center=bouton.center))
                self.bouton_mission = bouton

        if hover_hex and hover_hex.to_tuple() in state.world.tiles:
            pos = hover_hex.to_tuple()
            tile = state.world.tiles[pos]
            texte = f"{tile.display_name} (coût {tile.get_movement_cost()})"
            lieu = state.settlement_par_pos.get(pos)
            if lieu is not None:
                royaume = state.world.royaume(lieu.royaume_id)
                texte = f"{lieu.taille.value.capitalize()} de {lieu.nom} ({royaume.nom}) — {texte}"
            surf = self.font.render(texte, True, UI.hint_color)
            self.screen.blit(surf, (10, self.screen_height - 30))

    def render_transition_tour(self, monde: WorldState, progression: float) -> None:
        """
        Voile « le temps passe » après une fin de tour : la carte s'assombrit
        d'un coup puis réapparaît (``progression`` 1 → 0), avec le numéro du
        nouveau tour et l'horloge — rien d'autre ne montrerait que le monde a
        avancé.
        """
        alpha = int(210 * max(0.0, min(1.0, progression)))
        voile = pygame.Surface((self.screen_width, self.screen_height))
        voile.set_alpha(alpha)
        voile.fill((8, 8, 16))
        self.screen.blit(voile, (0, 0))

        centre_x, centre_y = self.screen_width // 2, self.screen_height // 2
        titre = self.gros_font.render(f"Tour {monde.tour}", True, UI.text_color)
        titre.set_alpha(alpha)
        self.screen.blit(titre, titre.get_rect(center=(centre_x, centre_y - 24)))
        sous = self.font.render(
            f"Horloge du destin : {monde.horloge_du_destin}", True, (255, 180, 120)
        )
        sous.set_alpha(alpha)
        self.screen.blit(sous, sous.get_rect(center=(centre_x, centre_y + 26)))

    def _render_message(self, message: str, timer: float) -> None:
        if timer > 0 and message:
            surf = self.font.render(message, True, (255, 200, 100))
            rect = surf.get_rect(center=(self.screen_width // 2, 70))
            pygame.draw.rect(self.screen, UI.panel_bg_color, rect.inflate(20, 10))
            self.screen.blit(surf, rect)

    def _is_on_screen(self, center: Tuple[float, float], hex_size: int) -> bool:
        margin = hex_size * 2
        return (-margin < center[0] < self.screen_width + margin
                and -margin < center[1] < self.screen_height + margin)

    def is_end_turn_clicked(self, pos: Tuple[int, int]) -> bool:
        return self.end_turn_button_rect.collidepoint(pos)


def run_campaign(screen: pygame.Surface, config: dict) -> bool:
    """
    Boucle de la campagne. Génère un monde (taille tirée du menu), distribue
    les PA du tour 1 et rend la main au joueur. Retourne True pour revenir au
    menu, False pour quitter.
    """
    world = generer_monde(
        SeededRNG(config.get("seed")),
        WorldGenConfig(map_width=config["map_width"], map_height=config["map_height"]),
    )
    demarrer_partie(world)
    state = CampaignState(world)

    camera = Camera(screen.get_width(), screen.get_height())
    controller = CameraController(
        camera, INPUT.drag_threshold, INPUT.scroll_speed, INPUT.fast_scroll_multiplier
    )
    font = pygame.font.Font(None, 24)
    renderer = CampaignRenderer(screen, font)

    # Départ caméra : la capitale où la main du joueur est rassemblée.
    depart = world.settlement(world.royaume(0).capitale_id)
    camera.center_on(HexCoord(*depart.position), controller.hex_grid)

    clock = pygame.time.Clock()
    hover_hex: Optional[HexCoord] = None
    message, message_timer = "", 0.0
    transition_tour = 0.0  # secondes restantes du voile de fin de tour
    dt = 0.0

    def fin_de_tour() -> None:
        """Clôt le tour, annonce les missions résolues, déclenche le voile."""
        nonlocal message, message_timer, transition_tour
        resultats = state.finir_tour()
        if resultats:
            message = "  ·  ".join(r.message for r in resultats)
            message_timer = 4.0
        transition_tour = TRANSITION_TOUR_S

    def ouvrir_missions() -> bool:
        """Ouvre le panneau de mission du perso sélectionné. False = quitter."""
        nonlocal message, message_timer
        perso = state.perso_selectionne
        if perso is None or perso.location is None or perso.mission_id is not None:
            return True
        continuer, dernier = run_missions(screen, font, state, perso.location)
        if dernier:
            message, message_timer = dernier, 2.5
        return continuer

    def entrer_en_ville() -> bool:
        """Ouvre l'écran de ville du perso sélectionné. False = quitter le jeu."""
        nonlocal message, message_timer
        perso = state.perso_selectionne
        lieu = state.settlement_par_pos.get(perso.location) if perso else None
        if lieu is None:
            return True
        continuer, dernier_message = run_ville(screen, font, state, lieu)
        if dernier_message:
            message, message_timer = dernier_message, 2.5
        return continuer

    while True:
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False

            # La caméra d'abord (drag/zoom) ; un clic droit sec désélectionne.
            if controller.handle_event(event, mouse_pos):
                if (event.type == pygame.MOUSEBUTTONUP and event.button == 3
                        and controller.was_right_click_not_drag(event, mouse_pos)):
                    state.deselectionner()
                continue

            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return True
                elif event.key == pygame.K_SPACE:
                    fin_de_tour()
                elif event.key == pygame.K_RETURN:
                    if not entrer_en_ville():
                        return False
                elif event.key == pygame.K_m:
                    if not ouvrir_missions():
                        return False

            elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if renderer.is_end_turn_clicked(mouse_pos):
                    fin_de_tour()
                    continue

                # Les boutons des panneaux sont au-dessus de la carte : ils
                # priment sur le clic-hex.
                if renderer.entrer_clique(mouse_pos):
                    if not entrer_en_ville():
                        return False
                    continue
                if renderer.mission_clique(mouse_pos):
                    if not ouvrir_missions():
                        return False
                    continue

                clique = controller.hex_grid.pixel_to_hex(
                    mouse_pos[0], mouse_pos[1], camera.offset
                ).to_tuple()
                if clique in world.tiles:
                    action, data = state.clic_hex(clique)
                    if action == "deplacement" and not data.ok:
                        message, message_timer = data.erreur, 2.5

        controller.handle_continuous_input()

        hovered = controller.hex_grid.pixel_to_hex(mouse_pos[0], mouse_pos[1], camera.offset)
        hover_hex = hovered if hovered.to_tuple() in world.tiles else None

        if message_timer > 0:
            message_timer -= dt

        renderer.render_frame(state, camera, controller.hex_grid, hover_hex,
                              message, message_timer)
        if transition_tour > 0:
            renderer.render_transition_tour(world, transition_tour / TRANSITION_TOUR_S)
            transition_tour -= dt
        pygame.display.flip()
        dt = clock.tick(60) / 1000.0
