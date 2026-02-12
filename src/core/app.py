"""High-level pygame app orchestration."""
from __future__ import annotations

import logging
from enum import Enum, auto
from math import sqrt
from typing import Dict, List, Sequence, Tuple

import pygame as pg

from settings import Settings
from src.core.camera import Camera
from src.core.events import EventManager
from src.game_objects.kingdom import KingdomRepository
from src.game_objects.unit import UnitRenderer, UnitRepository
from src.map.map_manager import MapManager
from src.ui.panels import SelectionOverlay

logger = logging.getLogger(__name__)

SQRT3 = sqrt(3)

YANGTZE_POINTS_1: Sequence[Tuple[float, float]] = (
    (4.5, 6.0),
    (5.0, 5.5),
    (6.0, 5.5),
    (6.5, 5.0),
    (7.5, 5.0),
    (8.0, 5.5),
    (9.0, 5.5),
    (9.5, 5.0),
    (10.5, 5.0),
    (11.0, 4.5),
    (12.0, 4.5),
    (12.5, 5.0),
    (13.5, 5.0),
    (14.0, 4.5),
    (15.0, 4.5),
    (15.5, 4.0),
)
YANGTZE_POINTS_2: Sequence[Tuple[float, float]] = (
    (10.5, 5.0),
    (11.0, 5.5),
    (10.5, 6.0),
    (11.0, 6.5),
    (10.5, 7.0),
)
YELLOW_RIVER_POINTS: Sequence[Tuple[float, float]] = (
    (9.0, 0.5),
    (9.5, 1.0),
    (9.0, 1.5),
    (9.5, 2.0),
    (9.0, 2.5),
    (9.5, 3.0),
    (10.5, 3.0),
    (11.0, 2.5),
    (12.0, 2.5),
    (12.5, 2.0),
    (13.5, 2.0),
    (14.0, 1.5),
)
BAN_LINE_POINTS: Sequence[Tuple[float, float]] = (
    (7.5, 9.0),
    (8.0, 8.5),
    (7.5, 8.0),
    (8.0, 7.5),
    (9.0, 7.5),
    (9.5, 7.0),
    (10.5, 7.0),
)

SelectionEntry = Tuple[int, int]


class GameState(Enum):
    LOADING = auto()
    CHOOSING = auto()
    PLAYING = auto()


class GameApp:
    def __init__(self, *, settings: Settings, debug: bool = False) -> None:
        self.settings = settings
        self.debug = debug
        self._running = False

        pg.init()
        self.clock = pg.time.Clock()
        display_info = pg.display.Info()
        self.screen_width = display_info.current_w
        self.screen_height = display_info.current_h
        flags = pg.NOFRAME if settings.borderless else 0
        self.window = pg.display.set_mode((self.screen_width, self.screen_height), flags)
        pg.display.set_caption(settings.window_title)

        self.hex_side = self.screen_height * 2 / (19 * SQRT3)

        self.state = GameState.LOADING
        self.player_country: str | None = None
        self.country_labels: Dict[str, str] = {"SHU": "蜀", "WU": "吴", "WEI": "魏"}
        self.country_button_colors: Dict[str, pg.Color] = {
            "SHU": pg.Color("red"),
            "WU": pg.Color("green"),
            "WEI": pg.Color("blue"),
        }

        self.kingdom_repository = KingdomRepository(settings.kingdoms_file)
        self.map_manager = MapManager(
            definition_file=settings.map_definition_file,
            terrain_graphics_dir=settings.map_graphics_dir,
            color_resolver=self.kingdom_repository.get_color,
        )
        self.map_manager.set_hex_side(self.hex_side)

        self.unit_repository = UnitRepository(
            settings.units_file,
            settings.asset_root,
        )
        self.unit_renderer = UnitRenderer(
            repository=self.unit_repository,
            slot_factor=settings.icon_slot_size_factor,
        )
        self.unit_renderer.on_hex_side_changed(self.hex_side)

        self.selection_overlay = SelectionOverlay()
        self.selected_units: List[SelectionEntry] = []

        self.camera = Camera()
        self.event_manager = EventManager(self)

        self._build_loading_assets()
        self._build_choosing_assets()
        self._build_play_assets()

    def run(self) -> None:
        self._running = True
        logger.info(
            "Starting game loop at %s FPS, resolution %sx%s",
            self.settings.fps,
            self.screen_width,
            self.screen_height,
        )
        while self._running:
            self.event_manager.process()
            self._update()
            self._render()
            pg.display.flip()
            self.clock.tick(self.settings.fps)

        pg.quit()

    def stop(self) -> None:
        self._running = False

    def clear_selection(self) -> None:
        self.selected_units.clear()

    def add_selection(self, province_id: int, slot_index: int) -> None:
        self.selected_units.append((province_id, slot_index))

    def handle_event(self, event: pg.event.Event) -> None:
        if event.type == pg.QUIT:
            self.stop()
            return

        if self.state == GameState.LOADING:
            self._handle_loading_event(event)
        elif self.state == GameState.CHOOSING:
            self._handle_choosing_event(event)
        elif self.state == GameState.PLAYING:
            self._handle_playing_event(event)

    def _handle_loading_event(self, event: pg.event.Event) -> None:
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            if self.start_button_rect.collidepoint(event.pos):
                self.state = GameState.CHOOSING

    def _handle_choosing_event(self, event: pg.event.Event) -> None:
        if event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            for country, button in self.faction_buttons.items():
                cx, cy = button["center"]
                dx = event.pos[0] - cx
                dy = event.pos[1] - cy
                if dx * dx + dy * dy <= self.faction_button_radius**2:
                    self.player_country = country
                    self.state = GameState.PLAYING
                    self.clear_selection()
                    return

    def _handle_playing_event(self, event: pg.event.Event) -> None:
        if event.type == pg.KEYDOWN and event.key == pg.K_ESCAPE:
            self.clear_selection()
        elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            if pg.key.get_mods() & pg.KMOD_SHIFT:
                self._handle_selection_click(event.pos)

    def _handle_selection_click(self, mouse_pos: Tuple[int, int]) -> None:
        if not self.player_country:
            return
        for province in self.map_manager.provinces:
            if province.country != self.player_country or not province.units:
                continue
            center = province.compute_center(self.hex_side)
            rects = self.unit_renderer.selection_rects(center, len(province.units))
            for idx, rect in enumerate(rects):
                if rect.collidepoint(mouse_pos):
                    self.add_selection(province.province_id, idx)
                    return

    def _update(self) -> None:
        self.camera.handle_input()

    def _render(self) -> None:
        if self.state == GameState.LOADING:
            self._render_loading_screen()
        elif self.state == GameState.CHOOSING:
            self._render_choosing_screen()
        else:
            self._render_gameplay()

    def _render_loading_screen(self) -> None:
        self.window.fill(pg.Color("white"))
        self.window.blit(self.loading_image_right, self.loading_image_right_pos)
        self.window.blit(self.loading_image_left, self.loading_image_left_pos)
        self.window.blit(self.loading_title_surface, self.loading_title_pos)
        pg.draw.rect(self.window, pg.Color("yellow"), self.start_button_rect)
        self.window.blit(self.loading_button_surface, self.loading_button_pos)

    def _render_choosing_screen(self) -> None:
        self.window.fill(pg.Color("white"))
        for surface, position in self.choosing_portraits:
            self.window.blit(surface, position)
        self.window.blit(self.choosing_title_surface, self.choosing_title_pos)
        for country, button in self.faction_buttons.items():
            pg.draw.circle(self.window, button["color"], button["center"], self.faction_button_radius)
            self.window.blit(button["label_surface"], button["label_pos"])

    def _render_gameplay(self) -> None:
        self.window.fill(pg.Color("white"))
        self.map_manager.draw(self.window)
        for province in self.map_manager.provinces:
            center = province.compute_center(self.hex_side)
            self.unit_renderer.draw_units(self.window, center, province.units)

        for polyline in self.yangtze_polylines:
            pg.draw.lines(self.window, pg.Color(173, 216, 230), False, polyline, 20)
        pg.draw.lines(self.window, pg.Color(173, 216, 230), False, self.yellow_river_polyline, 20)
        pg.draw.lines(self.window, pg.Color("black"), False, self.ban_line_polyline, 20)

        pg.draw.circle(
            self.window,
            pg.Color("black"),
            self.next_turn_center,
            self.next_turn_radius,
            10,
        )
        self.window.blit(self.arrow_image, self.arrow_pos)

        if self.player_country:
            tag_surface = self.country_tag_surfaces[self.player_country]
            self.window.blit(tag_surface, self.country_tag_pos)

        self.selection_overlay.draw(
            surface=self.window,
            selections=self.selected_units,
            province_lookup=self.map_manager.get_by_id,
            rect_provider=self.unit_renderer.selection_rects,
            hex_side=self.hex_side,
        )

    # --- asset builders -------------------------------------------------
    def _build_loading_assets(self) -> None:
        height = self.screen_height
        width = self.screen_width

        self.loading_image_right = self._load_ui_image(
            "start_ZHUGELIANG.jpg", (int(height * 0.6), int(height * 0.7))
        )
        self.loading_image_right_pos = (int(width - height * 0.65), int(height * 0.2))

        raw_left = self._load_ui_image(
            "start_SIMAYI.jpg", (int(height * 0.5), int(height * 0.625))
        )
        self.loading_image_left = pg.transform.flip(raw_left, True, False)
        self.loading_image_left_pos = (int(height * 0.03), int(height * 0.25))

        self.start_button_rect = pg.Rect(
            int(width * 0.3),
            int(height * 0.75),
            int(width * 0.4),
            int(height * 0.1),
        )

        self.loading_title_surface = self._render_text("STLITI.TTF", int(width * 0.1), "三足鼎立")
        self.loading_title_pos = (int(width * 0.3), 0)

        self.loading_button_surface = self._render_text(
            "STXINGKA.TTF", int(height * 0.1), "开始游戏"
        )
        self.loading_button_pos = (int(width * 0.5 - height * 0.2), int(height * 0.75))

    def _build_choosing_assets(self) -> None:
        height = self.screen_height
        width = self.screen_width
        image_size = (int(height * 0.3), int(height * 0.3))
        self.choosing_portraits = [
            (
                self._load_ui_image("choosing_LIUBEI.jpg", image_size),
                (int(width * 0.4 - height * 0.45), int(height * 0.2)),
            ),
            (
                self._load_ui_image("choosing_SUNQUAN.jpg", image_size),
                (int(width * 0.5 - height * 0.15), int(height * 0.2)),
            ),
            (
                self._load_ui_image("choosing_CAOCAO.jpg", image_size),
                (int(width * 0.6 + height * 0.15), int(height * 0.2)),
            ),
        ]

        self.choosing_title_surface = self._render_text("SIMLI.TTF", int(height * 0.1), "选择势力")
        self.choosing_title_pos = (int(width * 0.5 - height * 0.2), 0)

        self.faction_button_radius = int(height * 0.1)
        self.faction_buttons: Dict[str, Dict[str, object]] = {}

        label_surfaces = {
            country: self._render_text("STLITI.TTF", int(height * 0.1), label)
            for country, label in self.country_labels.items()
        }

        self.faction_buttons["SHU"] = {
            "center": (int(width * 0.4 - height * 0.3), int(height * 0.7)),
            "color": self.country_button_colors["SHU"],
            "label_surface": label_surfaces["SHU"],
            "label_pos": (int(width * 0.4 - height * 0.35), int(height * 0.65)),
        }
        self.faction_buttons["WU"] = {
            "center": (int(width * 0.5), int(height * 0.7)),
            "color": self.country_button_colors["WU"],
            "label_surface": label_surfaces["WU"],
            "label_pos": (int(width * 0.5 - height * 0.05), int(height * 0.65)),
        }
        self.faction_buttons["WEI"] = {
            "center": (int(width * 0.6 + height * 0.3), int(height * 0.7)),
            "color": self.country_button_colors["WEI"],
            "label_surface": label_surfaces["WEI"],
            "label_pos": (int(width * 0.6 + height * 0.25), int(height * 0.65)),
        }

    def _build_play_assets(self) -> None:
        height = self.screen_height
        width = self.screen_width

        self.next_turn_center = (int(width - height * 0.15), int(height * 0.85))
        self.next_turn_radius = int(height * 0.15)

        arrow_size = int(height * 0.13 * sqrt(2))
        self.arrow_image = self._load_ui_image("arrow.jpg", (arrow_size, arrow_size))
        self.arrow_pos = (
            int(width - height * 0.15 - height * 0.13 * 0.5 * sqrt(2)),
            int(height * 0.85 - height * 0.065 * sqrt(2)),
        )

        self.country_tag_font = self._font("STZHONGS.TTF", int(height * 0.1))
        self.country_tag_surfaces = {
            country: self.country_tag_font.render(label, True, pg.Color("black"))
            for country, label in self.country_labels.items()
        }
        self.country_tag_pos = (int(width - height * 0.15), 0)

        self.yangtze_polylines = tuple(self._scale_points(points) for points in (YANGTZE_POINTS_1, YANGTZE_POINTS_2))
        self.yellow_river_polyline = tuple(self._scale_points(YELLOW_RIVER_POINTS))
        self.ban_line_polyline = tuple(self._scale_points(BAN_LINE_POINTS))

    # --- helpers --------------------------------------------------------
    def _scale_points(self, normalized_points: Sequence[Tuple[float, float]]) -> List[Tuple[int, int]]:
        scaled = []
        for x_factor, y_factor in normalized_points:
            x = int(x_factor * self.hex_side)
            y = int(y_factor * SQRT3 * self.hex_side)
            scaled.append((x, y))
        return scaled

    def _load_ui_image(self, filename: str, size: Tuple[int, int]) -> pg.Surface:
        surface = pg.image.load(self.settings.ui_graphics_dir / filename).convert_alpha()
        return pg.transform.smoothscale(surface, size)

    def _font(self, filename: str, size: int) -> pg.font.Font:
        return pg.font.Font(self.settings.fonts_dir / filename, size)

    def _render_text(self, filename: str, size: int, text: str, color: pg.Color | str = "black") -> pg.Surface:
        font = self._font(filename, size)
        return font.render(text, True, pg.Color(color))
