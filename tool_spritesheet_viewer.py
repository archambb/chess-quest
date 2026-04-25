#!/usr/bin/env python3
import os
import sys
import math
import pygame
from typing import List, Tuple, Optional

# Optional file dialog (press L)
try:
    import tkinter as tk
    from tkinter import filedialog
    TK_AVAILABLE = True
except Exception:
    TK_AVAILABLE = False

APP_TITLE = "SpriteSheet Animator • Drop a PNG here or press L to load"

# ---------------------------
# Utility & Data Structures
# ---------------------------

class LoopMode:
    LOOP = "loop"
    PINGPONG = "pingpong"
    ONCE = "once"
    ORDER = [LOOP, PINGPONG, ONCE]

class OrderMode:
    ROW_MAJOR = "row-major"
    COL_MAJOR = "col-major"
    ORDER = [ROW_MAJOR, COL_MAJOR]

BG_COLORS = [
    (24,24,24),    # dark gray
    (0,0,0),       # black
    (255,255,255), # white
    (50,50,90),    # midnight
    (120,120,120), # mid gray
    (180,220,255), # sky
    (255,220,180), # peach
]

HELP_TEXT = [
    "Controls:",
    "  Load:      L (file dialog), or drag & drop an image",
    "  Play/Pause: Space   |  Step: Left/Right   |  Reset: R",
    "  Speed:     +/- (fps)   |  Frame len (ms): Shift +/-",
    "  Loop mode: M (loop/pingpong/once)",
    "  Frames:    Rows (Q/A), Cols (W/S)",
    "  Range:     Start [ / ]  |  End ; / '",
    "  Order:     O (row-major / col-major)",
    "  Margin:    Shift , / .   |  Spacing: Shift / / ?",
    "  Zoom:      Z/X or MouseWheel     |  Pan: Right-drag",
    "  Grid:      G  |  Background: B   |  Filtering: N (nearest/linear)",
    "  Origin:    T (toggle crosshair)  |  HUD: H",
    "  Export:    P (PNG sequence to ./export)",
]

def draw_text(surface, text, pos, color=(230,230,230), size=18, align_left=True):
    font = pygame.font.SysFont("consolas,menlo,monospace", size)
    lines = text.splitlines()
    x, y = pos
    for line in lines:
        s = font.render(line, True, color)
        r = s.get_rect()
        if align_left:
            r.topleft = (x, y)
        else:
            r.topright = (x, y)
        surface.blit(s, r)
        y += r.height + 2

def clamp(v, lo, hi):
    return max(lo, min(hi, v))

# ---------------------------
# Core Animation Viewer
# ---------------------------

class SpriteSheetAnimator:
    def __init__(self):
        # state
        self.sheet: Optional[pygame.Surface] = None
        self.path: Optional[str] = None

        # grid & slicing
        self.rows = 1
        self.cols = 1
        self.margin = 0   # pixels around the sheet before first cell
        self.spacing = 0  # pixels between cells
        self.order_mode = OrderMode.ROW_MAJOR

        # playback
        self.loop_mode = LoopMode.LOOP
        self.playing = True
        self.frame_index = 0
        self.frame_count = 1
        self.start_frame = 0
        self.end_frame = 0  # inclusive, will clamp to frame_count-1
        self.direction = 1  # for pingpong

        # timing (two ways to control speed; they combine)
        self.fps = 12.0             # desired frames per second (coarse)
        self.frame_ms = 0           # override per-frame duration in ms (0 = disabled)
        self._accum = 0.0

        # view
        self.zoom = 2.0
        self.min_zoom = 0.1
        self.max_zoom = 32.0
        self.nearest = True  # scaling filter
        self.show_grid = True
        self.show_origin = True
        self.show_hud = True
        self.bg_index = 0
        self.bg = BG_COLORS[self.bg_index]

        # pan
        self.pan_x = 0
        self.pan_y = 0
        self._panning = False
        self._pan_start = (0,0)
        self._pan_origin = (0,0)

        # cache of frames
        self.frames: List[pygame.Rect] = []

    # ------------- Loading -------------
    def load(self, path: str):
        try:
            img = pygame.image.load(path).convert_alpha()
        except Exception as e:
            print(f"Failed to load {path}: {e}")
            return
        self.sheet = img
        self.path = path
        self._rebuild_frames()
        self.frame_index = 0
        self.start_frame = 0
        self.end_frame = self.frame_count - 1
        self.direction = 1
        self.playing = True
        # Auto-zoom to roughly fit height
        self._auto_fit()

    def _auto_fit(self):
        if not self.sheet:
            return
        # try to fit a single frame height to ~60% of window height
        fw, fh = self._frame_size()
        if fw == 0 or fh == 0:
            return
        screen = pygame.display.get_surface()
        if not screen:
            return
        sw, sh = screen.get_size()
        if fh > 0:
            target = (sh * 0.6) / fh
            self.zoom = clamp(target, self.min_zoom, self.max_zoom)
        self.pan_x, self.pan_y = 0, 0

    # ------------- Grid slicing -------------
    def _rebuild_frames(self):
        self.frames.clear()
        if not self.sheet:
            self.frame_count = 0
            return
        sheet_w, sheet_h = self.sheet.get_size()
        rows = max(1, self.rows)
        cols = max(1, self.cols)

        # Compute cell size from margin & spacing
        w_avail = sheet_w - 2*self.margin - (cols-1)*self.spacing
        h_avail = sheet_h - 2*self.margin - (rows-1)*self.spacing
        if w_avail <= 0 or h_avail <= 0:
            self.frame_count = 0
            return

        cell_w = w_avail // cols
        cell_h = h_avail // rows
        if cell_w <= 0 or cell_h <= 0:
            self.frame_count = 0
            return

        for r in range(rows):
            for c in range(cols):
                x = self.margin + c*(cell_w + self.spacing)
                y = self.margin + r*(cell_h + self.spacing)
                self.frames.append(pygame.Rect(x, y, cell_w, cell_h))

        if self.order_mode == OrderMode.COL_MAJOR:
            # convert row-major to col-major indexing order
            col_major = []
            for c in range(cols):
                for r in range(rows):
                    idx = r*cols + c
                    col_major.append(self.frames[idx])
            self.frames = col_major

        self.frame_count = len(self.frames)
        self.start_frame = clamp(self.start_frame, 0, max(0, self.frame_count-1))
        self.end_frame   = clamp(self.end_frame,   0, max(0, self.frame_count-1))
        if self.end_frame < self.start_frame:
            self.end_frame = self.start_frame

    def _frame_size(self) -> Tuple[int,int]:
        if not self.frames:
            return (0,0)
        r = self.frames[0]
        return (r.w, r.h)

    # ------------- Playback -------------
    def update(self, dt_ms: float):
        if not self.playing or self.frame_count == 0:
            return

        # compute how long until we advance a frame
        if self.frame_ms > 0:
            frame_len = float(self.frame_ms)
        else:
            # fps fallback
            fps = max(0.0001, self.fps)
            frame_len = 1000.0 / fps

        self._accum += dt_ms
        while self._accum >= frame_len:
            self._accum -= frame_len
            self._advance_frame()

    def _advance_frame(self):
        if self.frame_count == 0:
            return
        lo = self.start_frame
        hi = self.end_frame
        if lo > hi:
            lo, hi = hi, lo

        if self.loop_mode == LoopMode.LOOP:
            self.frame_index += 1
            if self.frame_index > hi:
                self.frame_index = lo

        elif self.loop_mode == LoopMode.PINGPONG:
            self.frame_index += self.direction
            if self.frame_index >= hi:
                self.frame_index = hi
                self.direction = -1
            elif self.frame_index <= lo:
                self.frame_index = lo
                self.direction = +1

        elif self.loop_mode == LoopMode.ONCE:
            if self.frame_index < hi:
                self.frame_index += 1
            else:
                self.playing = False

    # ------------- Rendering -------------
    def draw(self, screen: pygame.Surface):
        screen.fill(self.bg)
        if not self.sheet or self.frame_count == 0:
            draw_text(screen, "Drop a spritesheet image here (PNG w/ alpha recommended)\nOr press L to browse...",
                      (24,24), (240,240,240), 22)
            return

        frame_rect = self.frames[self.frame_index]
        frame_surf = self.sheet.subsurface(frame_rect)

        # scale
        fw, fh = frame_rect.size
        scale_w = max(1, int(round(fw * self.zoom)))
        scale_h = max(1, int(round(fh * self.zoom)))
        if self.nearest:
            scaled = pygame.transform.scale(frame_surf, (scale_w, scale_h))
        else:
            scaled = pygame.transform.smoothscale(frame_surf, (scale_w, scale_h))

        # center + pan
        sw, sh = screen.get_size()
        cx = sw//2 + int(self.pan_x)
        cy = sh//2 + int(self.pan_y)
        rect = scaled.get_rect(center=(cx, cy))
        screen.blit(scaled, rect)

        # origin crosshair (frame local origin)
        if self.show_origin:
            pygame.draw.line(screen, (255,40,40), (cx-100, cy), (cx+100, cy), 1)
            pygame.draw.line(screen, (255,40,40), (cx, cy-100), (cx, cy+100), 1)
            pygame.draw.circle(screen, (255,40,40), (cx, cy), 3, 1)

        # grid overlay (draw around frame bounds)
        if self.show_grid:
            # outer rect of the scaled frame
            pygame.draw.rect(screen, (0,0,0), rect, 1)
            # inner cell lines if zoomed in
            # here we just outline the current frame (not inner tiles),
            # but also optionally draw pixels grid if heavily zoomed
            if self.zoom >= 20:
                # pixel grid (careful: heavy)
                for x in range(rect.left, rect.right, int(self.zoom)):
                    pygame.draw.line(screen, (0,0,0), (x, rect.top), (x, rect.bottom), 1)
                for y in range(rect.top, rect.bottom, int(self.zoom)):
                    pygame.draw.line(screen, (0,0,0), (rect.left, y), (rect.right, y), 1)

        if self.show_hud:
            self._draw_hud(screen)

    def _draw_hud(self, screen: pygame.Surface):
        sw, sh = screen.get_size()
        sheet_w, sheet_h = (self.sheet.get_size() if self.sheet else (0,0))
        fw, fh = self._frame_size()
        info = [
            f"File: {os.path.basename(self.path) if self.path else '(none)'}  {sheet_w}x{sheet_h}",
            f"Rows={self.rows} Cols={self.cols}   Margin={self.margin} Spacing={self.spacing}   Order={self.order_mode}",
            f"Frames={self.frame_count}   Range=[{self.start_frame}..{self.end_frame}]   Index={self.frame_index}",
            f"FrameSize={fw}x{fh}   Zoom={self.zoom:.2f}x   Pan=({self.pan_x:+.0f},{self.pan_y:+.0f})   Filter={'Nearest' if self.nearest else 'Linear'}",
            f"Loop={self.loop_mode}   Playing={'Yes' if self.playing else 'No'}   FPS={self.fps:.2f}   FrameMS={self.frame_ms if self.frame_ms>0 else '(auto)'}",
        ]
        draw_text(screen, "\n".join(info), (10, 10), (240,240,240), 18, True)

        # Help/instructions (right side)
        draw_text(screen, "\n".join(HELP_TEXT), (sw-20, 10), (235,235,200), 16, align_left=False)

    # ------------- Input Handling -------------
    def handle_event(self, e: pygame.event.EventType):
        if e.type == pygame.DROPFILE:
            path = e.file
            self.load(path)

        elif e.type == pygame.MOUSEBUTTONDOWN:
            if e.button == 3:  # right click to pan
                self._panning = True
                self._pan_start = pygame.mouse.get_pos()
                self._pan_origin = (self.pan_x, self.pan_y)
            elif e.button == 4:  # wheel up (zoom in)
                self.zoom = clamp(self.zoom * 1.1, self.min_zoom, self.max_zoom)
            elif e.button == 5:  # wheel down (zoom out)
                self.zoom = clamp(self.zoom / 1.1, self.min_zoom, self.max_zoom)

        elif e.type == pygame.MOUSEBUTTONUP:
            if e.button == 3:
                self._panning = False

        elif e.type == pygame.MOUSEMOTION and self._panning:
            mx, my = e.pos
            sx, sy = self._pan_start
            dx = mx - sx
            dy = my - sy
            # pan is in screen pixels directly
            self.pan_x = self._pan_origin[0] + dx
            self.pan_y = self._pan_origin[1] + dy

        elif e.type == pygame.KEYDOWN:
            mods = pygame.key.get_mods()
            shift = mods & pygame.KMOD_SHIFT

            if e.key == pygame.K_ESCAPE:
                pygame.event.post(pygame.event.Event(pygame.QUIT))
                return

            if e.key == pygame.K_SPACE:
                self.playing = not self.playing

            elif e.key == pygame.K_r:
                self.frame_index = self.start_frame
                self.direction = 1
                self._accum = 0.0

            elif e.key == pygame.K_g:
                self.show_grid = not self.show_grid

            elif e.key == pygame.K_b:
                self.bg_index = (self.bg_index + 1) % len(BG_COLORS)
                self.bg = BG_COLORS[self.bg_index]

            elif e.key == pygame.K_h:
                self.show_hud = not self.show_hud

            elif e.key == pygame.K_t:
                self.show_origin = not self.show_origin

            elif e.key == pygame.K_n:
                self.nearest = not self.nearest

            elif e.key == pygame.K_m:
                # loop mode cycle
                idx = LoopMode.ORDER.index(self.loop_mode)
                self.loop_mode = LoopMode.ORDER[(idx+1)%len(LoopMode.ORDER)]
                self.direction = 1

            elif e.key == pygame.K_o:
                # order mode cycle
                idx = OrderMode.ORDER.index(self.order_mode)
                self.order_mode = OrderMode.ORDER[(idx+1)%len(OrderMode.ORDER)]
                self._rebuild_frames()
                self.frame_index = clamp(self.frame_index, self.start_frame, self.end_frame)

            elif e.key == pygame.K_l:
                if TK_AVAILABLE:
                    root = tk.Tk()
                    root.withdraw()
                    path = filedialog.askopenfilename(
                        title="Open spritesheet image",
                        filetypes=[("Images","*.png;*.bmp;*.jpg;*.jpeg;*.webp;*.tga")]
                    )
                    root.destroy()
                    if path:
                        self.load(path)
                else:
                    print("tkinter not available in this environment; use drag & drop instead.")

            # zoom
            elif e.key == pygame.K_z:
                self.zoom = clamp(self.zoom / 1.1, self.min_zoom, self.max_zoom)
            elif e.key == pygame.K_x:
                self.zoom = clamp(self.zoom * 1.1, self.min_zoom, self.max_zoom)

            # rows/cols
            elif e.key == pygame.K_q:  # rows up
                self.rows = clamp(self.rows + 1, 1, 512)
                self._rebuild_frames()
            elif e.key == pygame.K_a:  # rows down
                self.rows = clamp(self.rows - 1, 1, 512)
                self._rebuild_frames()
            elif e.key == pygame.K_w:  # cols up
                self.cols = clamp(self.cols + 1, 1, 512)
                self._rebuild_frames()
            elif e.key == pygame.K_s:  # cols down
                self.cols = clamp(self.cols - 1, 1, 512)
                self._rebuild_frames()

            # frame range
            elif e.key == pygame.K_LEFT:
                if not self.playing and self.frame_count > 0:
                    self.frame_index = clamp(self.frame_index - 1, self.start_frame, self.end_frame)
            elif e.key == pygame.K_RIGHT:
                if not self.playing and self.frame_count > 0:
                    self.frame_index = clamp(self.frame_index + 1, self.start_frame, self.end_frame)

            elif e.key == pygame.K_LEFTBRACKET:  # '[' start--
                self.start_frame = clamp(self.start_frame - 1, 0, max(0, self.frame_count-1))
                if self.start_frame > self.end_frame:
                    self.end_frame = self.start_frame
                self.frame_index = clamp(self.frame_index, self.start_frame, self.end_frame)
            elif e.key == pygame.K_RIGHTBRACKET:  # ']' start++
                self.start_frame = clamp(self.start_frame + 1, 0, max(0, self.frame_count-1))
                if self.start_frame > self.end_frame:
                    self.end_frame = self.start_frame
                self.frame_index = clamp(self.frame_index, self.start_frame, self.end_frame)

            elif e.key == pygame.K_SEMICOLON:  # ';' end--
                self.end_frame = clamp(self.end_frame - 1, 0, max(0, self.frame_count-1))
                if self.end_frame < self.start_frame:
                    self.start_frame = self.end_frame
                self.frame_index = clamp(self.frame_index, self.start_frame, self.end_frame)
            elif e.key == pygame.K_QUQUOTE if hasattr(pygame, "K_QUQUOTE") else pygame.K_QUOTE:  # ''' end++
                self.end_frame = clamp(self.end_frame + 1, 0, max(0, self.frame_count-1))
                if self.end_frame < self.start_frame:
                    self.start_frame = self.end_frame
                self.frame_index = clamp(self.frame_index, self.start_frame, self.end_frame)

            # margins & spacing (with Shift)
            elif shift and e.key == pygame.K_COMMA:
                self.margin = clamp(self.margin - 1, 0, 4096)
                self._rebuild_frames()
            elif shift and e.key == pygame.K_PERIOD:
                self.margin = clamp(self.margin + 1, 0, 4096)
                self._rebuild_frames()
            elif shift and e.key == pygame.K_SLASH:
                self.spacing = clamp(self.spacing - 1, 0, 4096)
                self._rebuild_frames()
            elif shift and e.key == pygame.K_QUESTION if hasattr(pygame, "K_QUESTION") else (shift and e.key == pygame.K_SLASH):
                # Fallback if K_QUESTION isn't available: same as shift-slash on some layouts
                self.spacing = clamp(self.spacing + 1, 0, 4096)
                self._rebuild_frames()

            # speed controls
            elif e.key in (pygame.K_EQUALS, pygame.K_PLUS):
                if shift:
                    # longer frame_ms (slower)
                    self.frame_ms = clamp((self.frame_ms or int(1000/max(0.0001,self.fps))) + 10, 0, 100000)
                else:
                    self.fps = clamp(self.fps + 1, 0.1, 480.0)
            elif e.key in (pygame.K_MINUS, pygame.K_UNDERSCORE):
                if shift:
                    # shorter frame_ms (faster) but don't go negative
                    val = (self.frame_ms or int(1000/max(0.0001,self.fps))) - 10
                    self.frame_ms = max(0, val)
                else:
                    self.fps = clamp(self.fps - 1, 0.1, 480.0)

            # export frames as PNG sequence
            elif e.key == pygame.K_p:
                self._export_png_sequence()

    def _export_png_sequence(self):
        if not self.sheet or self.frame_count == 0:
            print("Nothing to export.")
            return
        out_dir = os.path.join(os.getcwd(), "export")
        os.makedirs(out_dir, exist_ok=True)
        count = 0
        lo, hi = min(self.start_frame, self.end_frame), max(self.start_frame, self.end_frame)
        for i in range(lo, hi+1):
            r = self.frames[i]
            surf = self.sheet.subsurface(r).copy()
            name = f"frame_{i:04d}.png"
            path = os.path.join(out_dir, name)
            pygame.image.save(surf, path)
            count += 1
        print(f"Exported {count} frames to {out_dir}")

# ---------------------------
# Main App
# ---------------------------

def main():
    pygame.init()
    pygame.display.set_caption(APP_TITLE)
    # HiDPI-friendly default
    screen = pygame.display.set_mode((1100, 720), pygame.RESIZABLE)
    clock = pygame.time.Clock()

    viewer = SpriteSheetAnimator()

    # Support opening via CLI arg
    if len(sys.argv) > 1:
        viewer.load(sys.argv[1])

    running = True
    while running:
        dt = clock.tick(120)  # cap ~120 Hz
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            else:
                viewer.handle_event(e)

        viewer.update(dt)
        viewer.draw(screen)
        pygame.display.flip()

    pygame.quit()

if __name__ == "__main__":
    main()
