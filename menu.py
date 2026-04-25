# menu.py
"""
Chess Quest - in-game pause/options menu (pygame)

Drop-in menu with:
- Vertical scrolling area with:
  - Mouse wheel scrolling
  - Scrollbar thumb drag
  - Click-on-track paging (jump)
  - Middle-mouse "grab" scrolling (hold MMB + drag up/down)
- Difficulty is a stepped slider (snaps to ranks, shows the rank text)
- Volume sliders are always visible (one per line). No "Volume (show/hide)".
- Uses ui_theme.py for palette + glimmer text (if present)

Usage:
    self.menu = GameMenu(self, on_save=..., on_load=..., on_exit_to_main=..., on_exit_os=...)

Event loop:
    if self.menu.is_open:
        closed = self.menu.handle_event(event)
        continue

Draw:
    if self.menu.is_open:
        self.menu.draw(screen)
"""

from __future__ import annotations

from typing import Callable, Optional, Tuple, List

import pygame
import config

# Theme helpers (you created this)
# Expected: PALETTE dict and draw_glimmer_text(surf, text, x, y, font=..., timer=..., mode=...)
try:
    import ui_theme
except Exception:  # fallback if file missing/renamed
    ui_theme = None


DIFFICULTY_RANKS: List[str] = [
    "VERY EASY", "EASY", "NORMAL", "CHALLENGING",
    "ADVANCED", "EXPERT", "MASTER", "GRANDMASTER"
]


def _clamp(v: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, v))


def _safe_getattr(obj, name: str, default):
    try:
        return getattr(obj, name)
    except Exception:
        return default

def _theme_color(name: str, fallback):
    if ui_theme and hasattr(ui_theme, "PALETTE"):
        try:
            return ui_theme.PALETTE.get(name, fallback)
        except Exception:
            return fallback
    return fallback


class _Button:
    def __init__(self, rect: pygame.Rect, label: str, on_click: Callable[[], None]):
        self.rect = rect
        self.label = label
        self.on_click = on_click
        self.hover = False

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.on_click()
                return True
        return False

    def draw(self, surf: pygame.Surface, font: pygame.font.Font, *, timer: float):
        panel_bg = _theme_color("panel_bg", (22, 24, 30))
        border = _theme_color("panel_border", (110, 120, 150))
        slate = _theme_color("panel_bg", (22, 24, 30))

        bg = (55, 60, 75) if not self.hover else (70, 78, 98)
        pygame.draw.rect(surf, bg, self.rect, border_radius=10)
        pygame.draw.rect(surf, border, self.rect, width=2, border_radius=10)

        # Glimmer label
        if ui_theme and hasattr(ui_theme, "draw_glimmer_text"):
            mode = "hover" if self.hover else "normal"
            # left-aligned glimmer looks more "spellbooky"
            ui_theme.draw_glimmer_text(
                surf,
                self.label,
                self.rect.x + 18,
                self.rect.y + (self.rect.h - font.get_height()) // 2,
                font=font,
                timer=timer,
                mode=mode,
            )
        else:
            text = font.render(self.label, True, (240, 240, 245))
            surf.blit(
                text,
                (self.rect.centerx - text.get_width() // 2, self.rect.centery - text.get_height() // 2),
            )


class _Slider:
    """
    Slider widget.

    - Range is min_value..max_value.
    - If steps is provided (list of ints), slider snaps to those values.
    - value_text can format the displayed string on the right.
    """

    def __init__(
        self,
        rect: pygame.Rect,
        label: str,
        get_value: Callable[[], int],
        set_value: Callable[[int], None],
        *,
        min_value: int = 0,
        max_value: int = 100,
        steps: Optional[List[int]] = None,
        value_text: Optional[Callable[[int], str]] = None,
    ):
        self.rect = rect
        self.label = label
        self.get_value = get_value
        self.set_value = set_value
        self.min_value = int(min_value)
        self.max_value = int(max_value)
        self.steps = steps[:] if steps else None
        self.value_text = value_text or (lambda v: f"{v}%")
        self.dragging = False
        self.hover = False

    def _snap(self, v: int) -> int:
        if not self.steps:
            return _clamp(v, self.min_value, self.max_value)
        best = self.steps[0]
        best_d = abs(v - best)
        for s in self.steps[1:]:
            d = abs(v - s)
            if d < best_d:
                best = s
                best_d = d
        return _clamp(best, self.min_value, self.max_value)

    def _value_from_x(self, x: int) -> int:
        x0 = self.rect.x + 160
        x1 = self.rect.right - 20
        if x1 <= x0:
            return self._snap(int(self.get_value()))
        t = (x - x0) / (x1 - x0)
        v = int(round(self.min_value + t * (self.max_value - self.min_value)))
        return self._snap(v)

    def handle_event(self, event: pygame.event.Event) -> bool:
        if event.type == pygame.MOUSEMOTION:
            self.hover = self.rect.collidepoint(event.pos)
            if self.dragging:
                self.set_value(self._value_from_x(event.pos[0]))
                return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self.rect.collidepoint(event.pos):
                self.dragging = True
                self.set_value(self._value_from_x(event.pos[0]))
                return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                return True

        return False

    def draw(self, surf: pygame.Surface, font: pygame.font.Font, small_font: pygame.font.Font, *, timer: float):
        bg = _theme_color("panel_bg", (22, 24, 30))
        border = _theme_color("panel_border", (110, 120, 150))

        card_bg = (35, 38, 48) if not self.hover else (45, 50, 65)
        pygame.draw.rect(surf, card_bg, self.rect, border_radius=10)
        pygame.draw.rect(surf, border, self.rect, width=2, border_radius=10)

        # Label (glimmer)
        if ui_theme and hasattr(ui_theme, "draw_glimmer_text"):
            mode = "hover" if self.hover else "normal"
            ui_theme.draw_glimmer_text(
                surf,
                self.label,
                self.rect.x + 14,
                self.rect.y + 10,
                font=font,
                timer=timer,
                mode=mode,
            )
        else:
            label = font.render(self.label, True, (235, 235, 240))
            surf.blit(label, (self.rect.x + 14, self.rect.y + 10))

        # Slider track
        x0 = self.rect.x + 160
        x1 = self.rect.right - 20
        y = self.rect.y + 30
        pygame.draw.line(surf, (130, 140, 165), (x0, y), (x1, y), 5)

        v = _clamp(int(self.get_value()), self.min_value, self.max_value)
        denom = max(1, (self.max_value - self.min_value))
        t = (v - self.min_value) / denom
        knob_x = int(x0 + (x1 - x0) * t)
        pygame.draw.circle(surf, (240, 240, 245), (knob_x, y), 9)
        pygame.draw.circle(surf, (35, 35, 40), (knob_x, y), 9, 2)

        # Steps ticks (nice for difficulty)
        if self.steps and len(self.steps) > 1:
            for s in self.steps:
                st = (s - self.min_value) / denom
                tx = int(x0 + (x1 - x0) * st)
                pygame.draw.line(surf, (90, 98, 120), (tx, y - 10), (tx, y + 10), 2)

        val_str = self.value_text(v)
        val_text = small_font.render(val_str, True, (220, 220, 225))
        surf.blit(val_text, (self.rect.right - val_text.get_width() - 14, self.rect.y + 10))


class GameMenu:
    """
    In-game menu overlay.

    - ESC or top-right X closes (returns to game).
    - Scroll area supports wheel, thumb drag, track click paging, and MMB grab-scroll.
    - Difficulty is a stepped slider.
    - Volume sliders always visible.
    - Uses ui_theme for colors + glimmer.
    """

    def __init__(
        self,
        game,
        on_save: Optional[Callable[[], None]] = None,
        on_load: Optional[Callable[[], None]] = None,
        on_exit_to_main: Optional[Callable[[], None]] = None,
        on_exit_os: Optional[Callable[[], None]] = None,
    ):
        self.g = game
        self.on_save = on_save
        self.on_load = on_load
        self.on_exit_to_main = on_exit_to_main
        self.on_exit_os = on_exit_os

        self.is_open = False

        self._font = None
        self._small_font = None
        self._title_font = None

        self._panel = pygame.Rect(0, 0, 620, 610)
        self._close_rect = pygame.Rect(0, 0, 36, 36)

        self._buttons: List[_Button] = []
        self._sliders: List[_Slider] = []

        # Scroll state
        self._scroll_y = 0
        self._scroll_max = 0
        self._content_view = pygame.Rect(0, 0, 0, 0)
        self._content_height = 0

        # Scrollbar drag state
        self._sb_dragging = False
        self._sb_drag_off_y = 0

        # Middle-mouse "grab scroll"
        self._mm_dragging = False
        self._mm_last_y = 0

        # UI timer (feeds glimmer)
        self._ui_timer = 0.0

        self._ui_built = False

        # Ensure config fields exist with sane defaults
        if not hasattr(config, "DIFFICULTY"):
            config.DIFFICULTY = "NORMAL"
        if not hasattr(config, "SFX_VOLUME"):
            config.SFX_VOLUME = 50
        if not hasattr(config, "MUSIC_VOLUME"):
            config.MUSIC_VOLUME = 50
        if not hasattr(config, "VOICE_VOLUME"):
            config.VOICE_VOLUME = 50

        self.g.audio.update_volumes()

    # ──────────────────────────────────────────────────────────────
    # Public control
    # ──────────────────────────────────────────────────────────────

    def open(self) -> None:
        self.is_open = True
        self._ui_built = False

    def close(self) -> None:
        self.is_open = False
        self._sb_dragging = False
        self._mm_dragging = False

    def toggle(self) -> None:
        if self.is_open:
            self.close()
        else:
            self.open()

    # ──────────────────────────────────────────────────────────────
    # Internal helpers: fonts, scrollbars
    # ──────────────────────────────────────────────────────────────

    def _ensure_fonts(self):
        if self._font is None:
            self._font = pygame.font.SysFont(None, 28)
        if self._small_font is None:
            self._small_font = pygame.font.SysFont(None, 22)
        if self._title_font is None:
            self._title_font = pygame.font.SysFont(None, 44)

    def _scroll_track_rect(self) -> pygame.Rect:
        return pygame.Rect(self._content_view.right - 10, self._content_view.y, 6, self._content_view.h)

    def _scroll_thumb_rect(self) -> pygame.Rect:
        track = self._scroll_track_rect()
        if self._scroll_max <= 0:
            return pygame.Rect(track.x, track.y, track.w, track.h)

        frac = self._content_view.h / max(1, self._content_height)
        thumb_h = max(24, int(track.h * frac))
        t = self._scroll_y / max(1, self._scroll_max)
        thumb_y = track.y + int((track.h - thumb_h) * t)
        return pygame.Rect(track.x, thumb_y, track.w, thumb_h)

    def _scroll_to_thumb_center(self, mouse_y: int) -> None:
        if self._scroll_max <= 0:
            return
        track = self._scroll_track_rect()
        thumb = self._scroll_thumb_rect()
        usable = max(1, track.h - thumb.h)
        thumb_top = mouse_y - (thumb.h // 2)
        t = (thumb_top - track.y) / usable
        self._scroll_y = _clamp(int(t * self._scroll_max), 0, self._scroll_max)

    # ──────────────────────────────────────────────────────────────
    # Internal: build UI layout
    # ──────────────────────────────────────────────────────────────

    def _build_ui(self, screen_size: Tuple[int, int]):
        self._ensure_fonts()

        w, h = screen_size
        self._panel.center = (w // 2, h // 2)

        # Close "X"
        self._close_rect = pygame.Rect(self._panel.right - 44, self._panel.y + 12, 32, 32)

        # Scrollable viewport: leave space for title and footer
        self._content_view = pygame.Rect(
            self._panel.x + 26,
            self._panel.y + 76,
            self._panel.w - 52,
            self._panel.h - 76 - 52,
        )

        # Layout rows in "content coordinates" (unscrolled)
        x = self._panel.x + 40
        y = self._panel.y + 80
        row_w = self._panel.w - 80
        row_h = 52
        gap = 14

        self._buttons.clear()
        self._sliders.clear()

        def add_button(text: str, callback: Callable[[], None]):
            nonlocal y
            r = pygame.Rect(x, y, row_w, row_h)
            self._buttons.append(_Button(r, text, callback))
            y += row_h + gap

        def add_slider(sl: _Slider):
            nonlocal y
            self._sliders.append(sl)
            y += row_h + gap

        # Actions
        add_button("Save", self._do_save)
        add_button("Load", self._do_load)

        # Difficulty as stepped slider
        def get_diff_idx() -> int:
            rank = str(_safe_getattr(config, "DIFFICULTY", "NORMAL")).upper()
            return DIFFICULTY_RANKS.index(rank) if rank in DIFFICULTY_RANKS else 2

        def set_diff_idx(idx: int) -> None:
            idx = _clamp(int(idx), 0, len(DIFFICULTY_RANKS) - 1)
            rank = DIFFICULTY_RANKS[idx]
            config.DIFFICULTY = rank
            if hasattr(config, "difficulty"):
                try:
                    config.difficulty = idx
                except Exception:
                    pass

        add_slider(
            _Slider(
                pygame.Rect(x, y, row_w, row_h),
                "Difficulty",
                get_diff_idx,
                set_diff_idx,
                min_value=0,
                max_value=len(DIFFICULTY_RANKS) - 1,
                steps=list(range(len(DIFFICULTY_RANKS))),
                value_text=lambda v: DIFFICULTY_RANKS[_clamp(v, 0, len(DIFFICULTY_RANKS) - 1)],
            )
        )

        # Volume sliders (each on its own line)
        add_slider(
            _Slider(
                pygame.Rect(x, y, row_w, row_h),
                "Sound FX",
                lambda: int(_safe_getattr(config, "SFX_VOLUME", 50)),
                self._set_sfx_volume,
            )
        )
        add_slider(
            _Slider(
                pygame.Rect(x, y, row_w, row_h),
                "Voices",
                lambda: int(_safe_getattr(config, "VOICE_VOLUME", 50)),
                self._set_voice_volume,
            )
        )
        add_slider(
            _Slider(
                pygame.Rect(x, y, row_w, row_h),
                "Music",
                lambda: int(_safe_getattr(config, "MUSIC_VOLUME", 50)),
                self._set_music_volume,
            )
        )
        add_button("Concede Match", self._do_concede_match)
        # Exits
        add_button("Exit to Main Screen", self._do_exit_to_main)
        add_button("Exit to OS", self._do_exit_os)

        # Compute content height + scroll bounds
        content_top = self._panel.y + 80
        self._content_height = max(0, (y - content_top))
        self._scroll_max = max(0, self._content_height - self._content_view.h)
        self._scroll_y = _clamp(self._scroll_y, 0, self._scroll_max)

        self._ui_built = True

    # ──────────────────────────────────────────────────────────────
    # Event handling
    # ──────────────────────────────────────────────────────────────

    def handle_event(self, event: pygame.event.Event) -> bool:
        """
        Returns True if the menu closed due to this event (so the game can resume immediately).
        """
        if not self.is_open:
            return False

        # ESC closes
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            self.close()
            return True

        # Ensure layout exists (in case events arrive before first draw)
        if not self._ui_built:
            surf = pygame.display.get_surface()
            if surf:
                self._build_ui(surf.get_size())
            else:
                return False

        # Click X closes
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            if self._close_rect.collidepoint(event.pos):
                self.close()
                return True

        # Mouse wheel scroll (when over panel)
        if event.type == pygame.MOUSEWHEEL and self._scroll_max > 0:
            mx, my = pygame.mouse.get_pos()
            if self._panel.collidepoint((mx, my)):
                self._scroll_y = _clamp(self._scroll_y - int(event.y) * 30, 0, self._scroll_max)
                return False

        # Scrollbar interactions (LMB)
        if self._scroll_max > 0 and event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            track = self._scroll_track_rect()
            thumb = self._scroll_thumb_rect()

            if thumb.collidepoint(event.pos):
                self._sb_dragging = True
                self._sb_drag_off_y = event.pos[1] - thumb.y
                return False

            if track.collidepoint(event.pos):
                self._scroll_to_thumb_center(event.pos[1])
                return False

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._sb_dragging = False

        if event.type == pygame.MOUSEMOTION and self._sb_dragging and self._scroll_max > 0:
            track = self._scroll_track_rect()
            thumb = self._scroll_thumb_rect()
            usable = max(1, track.h - thumb.h)

            thumb_top = event.pos[1] - self._sb_drag_off_y
            t = (thumb_top - track.y) / usable
            self._scroll_y = _clamp(int(t * self._scroll_max), 0, self._scroll_max)
            return False

        # Middle-mouse grab scrolling (hold MMB + drag up/down)
        if self._scroll_max > 0 and event.type == pygame.MOUSEBUTTONDOWN and event.button == 2:
            if self._panel.collidepoint(event.pos):
                self._mm_dragging = True
                self._mm_last_y = event.pos[1]
                return False

        if event.type == pygame.MOUSEBUTTONUP and event.button == 2:
            self._mm_dragging = False

        if event.type == pygame.MOUSEMOTION and self._mm_dragging and self._scroll_max > 0:
            dy = event.pos[1] - self._mm_last_y
            self._mm_last_y = event.pos[1]
            self._scroll_y = _clamp(self._scroll_y + dy, 0, self._scroll_max)
            return False

        # Build a "scrolled" mouse event so hit-tests match unscrolled rects
        ev = event
        if event.type in (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP):
            if hasattr(event, "pos") and self._content_view.collidepoint(event.pos):
                ev = pygame.event.Event(
                    event.type,
                    {**event.dict, "pos": (event.pos[0], event.pos[1] + self._scroll_y)},
                )

        # UI controls
        for b in self._buttons:
            b.handle_event(ev)

        for s in self._sliders:
            if s.handle_event(ev):
                self.g.audio.update_volumes()

        return False if self.is_open else True

    # ──────────────────────────────────────────────────────────────
    # Drawing
    # ──────────────────────────────────────────────────────────────

    def draw(self, screen: pygame.Surface) -> None:
        if not self.is_open:
            return

        if not self._ui_built:
            self._build_ui(screen.get_size())

        self._ensure_fonts()

        # advance UI timer (for glimmer) while menu is open
        self._ui_timer += 1.0

        panel_bg = _theme_color("panel_bg", (22, 24, 30))
        panel_border = _theme_color("panel_border", (110, 120, 150))

        # Dim background
        dim = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
        screen.blit(dim, (0, 0))

        # Panel
        pygame.draw.rect(screen, panel_bg, self._panel, border_radius=16)
        pygame.draw.rect(screen, panel_border, self._panel, width=3, border_radius=16)

        # Title (glimmer if available)
        if ui_theme and hasattr(ui_theme, "draw_glimmer_text"):
            ui_theme.draw_glimmer_text(
                screen,
                "Game Menu",
                self._panel.x + 40,
                self._panel.y + 22,
                font=self._title_font,
                timer=self._ui_timer,
                mode="normal",
            )
        else:
            title = self._title_font.render("Game Menu", True, (245, 245, 250))
            screen.blit(title, (self._panel.x + 40, self._panel.y + 22))

        # Close X
        pygame.draw.rect(screen, (45, 50, 65), self._close_rect, border_radius=8)
        pygame.draw.rect(screen, panel_border, self._close_rect, width=2, border_radius=8)
        x_text = self._font.render("X", True, (245, 245, 250))
        screen.blit(
            x_text,
            (
                self._close_rect.centerx - x_text.get_width() // 2,
                self._close_rect.centery - x_text.get_height() // 2 - 1,
            ),
        )

        # Controls: clip to viewport + draw with vertical scroll offset
        prev_clip = screen.get_clip()
        screen.set_clip(self._content_view)

        dy = -self._scroll_y

        for b in self._buttons:
            old = b.rect.copy()
            b.rect.y = old.y + dy
            b.draw(screen, self._font, timer=self._ui_timer)
            b.rect = old

        for s in self._sliders:
            old = s.rect.copy()
            s.rect.y = old.y + dy
            s.draw(screen, self._font, self._small_font, timer=self._ui_timer)
            s.rect = old

        screen.set_clip(prev_clip)

        # Scrollbar (only if needed)
        if self._scroll_max > 0:
            track = self._scroll_track_rect()
            thumb = self._scroll_thumb_rect()

            pygame.draw.rect(screen, (60, 65, 80), track, border_radius=4)

            thumb_col = (180, 190, 215) if self._sb_dragging else (140, 150, 175)
            pygame.draw.rect(screen, thumb_col, thumb, border_radius=4)

        # Footer hint
        hint_txt = "ESC or X to close • Wheel/MMB drag to scroll"
        hint = self._small_font.render(hint_txt, True, (205, 205, 215))
        screen.blit(hint, (self._panel.x + 40, self._panel.bottom - 36))

    # ──────────────────────────────────────────────────────────────
    # Actions / config setters
    # ──────────────────────────────────────────────────────────────

    def _do_save(self) -> None:
        if self.on_save:
            try:
                self.on_save()
            except Exception:
                pass

    def _do_load(self) -> None:
        if self.on_load:
            try:
                self.on_load()
            except Exception:
                pass

    def _do_exit_to_main(self) -> None:
        self.close()
        if self.on_exit_to_main:
            try:
                self.on_exit_to_main()
                return
            except Exception:
                pass

    def _do_exit_os(self) -> None:
        self.close()
        if self.on_exit_os:
            try:
                self.on_exit_os()
                return
            except Exception:
                pass
        pygame.quit()
        raise SystemExit

    def _set_sfx_volume(self, v: int) -> None:
        config.SFX_VOLUME = _clamp(int(v), 0, 100)
        self.g.audio.update_volumes()


    def _set_voice_volume(self, v: int) -> None:
        config.VOICE_VOLUME = _clamp(int(v), 0, 100)
        self.g.audio.update_volumes()


    def _set_music_volume(self, v: int) -> None:
        config.MUSIC_VOLUME = _clamp(int(v), 0, 100)
        self.g.audio.update_volumes()


    def _do_concede_match(self) -> None:
        self.close()
        self.g.lose_round()
