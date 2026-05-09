import os
import math
import re
import pygame

# We still keep the particle engine "internal" to the overworld system.
try:
    from particle import ParticleSystem
except ImportError:
    ParticleSystem = None


class GameWorldRenderer:
    """
    Handles all overworld rendering and UI popups for GameWorld.

    - Uses GameWorld for:
        * world_data, tile_states, player_pos
        * calendar (month/year)
        * building helpers (_building_at, _apply_building_choice)
        * layout tuning values (TILE_SIZE, CELL_SPACING_X/Y, COLUMN_DROP, ROW_STAGGER)
        * stage_info metadata
        * active_quests
    """

    def __init__(self, world):
        self.world = world

        # Layout margins (computed each frame based on screen size)
        self.MARGIN_X = 50
        self.MARGIN_Y = 50

        # The "ground" line within each cell (bottom of the cell)
        self.BASELINE_IN_CELL = self.world.TILE_SIZE

        # Rendering assets
        self.default_tile = pygame.Surface(
            (self.world.TILE_SIZE, self.world.TILE_SIZE), pygame.SRCALPHA
        )
        self.default_tile.fill((255, 0, 0, 180))

        # tile_images[stage_id][state] = Surface
        self.tile_images = {i: {} for i in range(16)}
        self._load_all_tiles()

        # Cache for brightened tiles (for hover gamma effect)
        # key: (stage_id, state) -> Surface
        self._brightened_tiles = {}

        # Player image
        player_path = os.path.join("assets", "GFX", "world", "player.png")
        try:
            player_img = pygame.image.load(player_path).convert_alpha()
        except (pygame.error, FileNotFoundError):
            player_img = pygame.Surface(
                (self.world.TILE_SIZE, self.world.TILE_SIZE), pygame.SRCALPHA
            )
            player_img.fill((255, 0, 0, 128))  # fallback transparent red

        self.player_img = pygame.transform.smoothscale(
            player_img, (self.world.TILE_SIZE, self.world.TILE_SIZE)
        )

        # Optional: background image
        bg_path = os.path.join("assets", "GFX", "world", "world_background.png")
        self.background = pygame.image.load(bg_path).convert() if os.path.exists(bg_path) else None

        # Fonts (lazy init)
        self.debug_font = None
        self.ui_font = None
        self.ui_font_italic = None
        self.calendar_font = None

        # Internal particle system & emitters
        self.particle_system = None
        self.volcano_emitter_id = None

    # ─────────────────────────────────────────────────────────────
    # Public API used by GameWorld
    # ─────────────────────────────────────────────────────────────

    def update(self, dt: float):
        """Advance particle system."""
        if self.particle_system is not None:
            self.particle_system.update(dt)

    def compute_margins(self, screen: pygame.Surface):
        """Center the 4x4 overworld on the screen."""
        self._compute_margins(screen)

    def cell_screen_origin(self, x: int, y: int):
        """Expose logical cell origin for click / hover hit-testing."""
        return self._cell_screen_origin(x, y)

    def get_tile_rect(self, x: int, y: int) -> pygame.Rect:
        """
        Compute the exact rect used when drawing the tile at (x, y),
        so hover/click hit testing matches visuals.
        """
        cell = self.world.world_data[(x, y)]
        stage_id = cell["stage_id"]
        state = cell.get("state", "new")

        base_tile_img = self.tile_images.get(stage_id, {}).get(state)
        if base_tile_img is None:
            base_tile_img = self.tile_images.get(stage_id, {}).get(
                "new", self.default_tile
            )

        cell_x, cell_y = self._cell_screen_origin(x, y)
        screen_baseline = cell_y + self.BASELINE_IN_CELL

        base_rect = base_tile_img.get_rect()
        base_rect.midbottom = (
            cell_x + self.world.TILE_SIZE // 2,
            screen_baseline,
        )
        return base_rect

    def draw_world(self, screen: pygame.Surface, traversable_squares, hovered_pos=None):
        """
        Main draw call for the overworld.

        hovered_pos: (x, y) of the currently hovered tile, or None.
        """
        self._compute_margins(screen)
        self._ensure_fonts()

        # Lazily create internal particle system once we know the screen size
        if self.particle_system is None and ParticleSystem is not None:
            self.particle_system = ParticleSystem(screen.get_size(), tick_rate=60)
            self._setup_volcano_emitter()

        # Animation for tile highlight
        t = pygame.time.get_ticks() * 0.005
        glow_phase = (math.sin(t) + 1) / 2
        highlight_alpha = int(80 + 120 * glow_phase)
        scale_breathe = 1.0 + 0.05 * math.sin(t * 2.0)

        # Draw background
        if self.background:
            screen.blit(self.background, (0, 0))
        else:
            screen.fill((0, 0, 0))

        # Ocean surface waves (non-particle)
        self._draw_ocean_waves(screen)

        volcano_world_pos = None
        volcano_active = False

        # Draw tiles
        for y in range(4):
            for x in range(4):
                cell = self.world.world_data[(x, y)]
                stage_id = cell["stage_id"]
                state = cell.get("state", "new")

                base_tile_img = self.tile_images.get(stage_id, {}).get(state)
                if base_tile_img is None:
                    base_tile_img = self.tile_images.get(stage_id, {}).get(
                        "new", self.default_tile
                    )

                # Hover gamma / brightness: ~20% bump via additive blend
                if hovered_pos == (x, y):
                    tile_img = self._get_brightened_tile(stage_id, state, base_tile_img)
                else:
                    tile_img = base_tile_img

                cell_x, cell_y = self._cell_screen_origin(x, y)
                screen_baseline = cell_y + self.BASELINE_IN_CELL

                base_rect = tile_img.get_rect()
                base_rect.midbottom = (
                    cell_x + self.world.TILE_SIZE // 2,
                    screen_baseline,
                )

                screen.blit(tile_img, base_rect.topleft)

                # Volcano location for smoke (stage_id == 2, new or lost)
                if stage_id == 2 and state in ("new", "lost"):
                    volcano_active = True
                    volcano_world_pos = (
                        base_rect.centerx,
                        base_rect.centery - base_rect.height * 0.35,
                    )

                # Highlight reachable tiles
                if (x, y) in traversable_squares:
                    w, h = base_tile_img.get_size()
                    hw = max(1, int(w * scale_breathe))
                    hh = max(1, int(h * scale_breathe))
                    highlight = pygame.transform.smoothscale(base_tile_img, (hw, hh))
                    highlight.set_alpha(highlight_alpha)
                    h_rect = highlight.get_rect(center=base_rect.center)
                    screen.blit(highlight, h_rect.topleft)

        # Move volcano emitter to the crater position if needed
        if (
            self.particle_system is not None
            and self.volcano_emitter_id is not None
        ):
            em = self.particle_system.emitters[self.volcano_emitter_id]
            if volcano_active and volcano_world_pos is not None:
                self.particle_system.set_emitter_position(
                    self.volcano_emitter_id,
                    volcano_world_pos[0],
                    volcano_world_pos[1],
                )
                em.enabled = True
            else:
                em.enabled = False

        # Draw particles over the tiles
        if self.particle_system is not None:
            self.particle_system.draw(screen, sort_by_y=True)

        # --- Draw player (small knight, no yellow circle) ---
        px_cell, py_cell = self._cell_screen_origin(
            self.world.player_pos[0], self.world.player_pos[1]
        )

        knight_size = 50  # ~50px knight
        knight_img = pygame.transform.smoothscale(
            self.player_img, (knight_size, knight_size)
        )

        knight_rect = knight_img.get_rect(
            center=(
                px_cell + self.world.TILE_SIZE // 2,
                py_cell + self.world.TILE_SIZE // 2,
            )
        )
        screen.blit(knight_img, knight_rect.topleft)

        # --- Calendar in top-right with outline text ---
        month_name = self.world.month_names[self.world.current_month_index]
        calendar_text = f"{month_name} {self.world.current_year} CY"
        cal_surface = self.calendar_font.render(calendar_text, True, (255, 255, 255))
        cal_rect = cal_surface.get_rect()
        cal_x = screen.get_width() - cal_rect.width - 10
        cal_y = 10
        self._draw_text_outline(screen, calendar_text, self.calendar_font, cal_x, cal_y)

        # --- Debug overlay: spacing X / Y / Drop / Stagger under the calendar ---
        spacing_text = (
            f"X: {self.world.CELL_SPACING_X}  "
            f"Y: {self.world.CELL_SPACING_Y}  "
            f"Drop: {self.world.COLUMN_DROP}  "
            f"Stagger: {self.world.ROW_STAGGER}"
        )
        spacing_surf = self.debug_font.render(spacing_text, True, (0, 0, 0))
        spacing_rect = spacing_surf.get_rect(
            topright=(screen.get_width() - 10, cal_y + cal_rect.height + 4)
        )
        screen.blit(spacing_surf, spacing_rect)

        # --- Right-hand info panel for the hovered tile ---
        if hovered_pos is not None:
            self._draw_info_panel(screen, hovered_pos)

    def choose_building_for_tile(self, screen: pygame.Surface, pos):
        """
        When visiting a liberated tile that has no building yet, show a
        simple modal popup asking what building to place there.
        (Delegates building application back into GameWorld.)
        """
        self._choose_building_for_tile(screen, pos)

    # ─────────────────────────────────────────────────────────────
    # Text helpers
    # ─────────────────────────────────────────────────────────────

    def _ensure_fonts(self):
        if self.debug_font is None:
            self.debug_font = pygame.font.SysFont(None, 24)
        if self.ui_font is None:
            self.ui_font = pygame.font.SysFont(None, 28)
        if self.ui_font_italic is None:
            self.ui_font_italic = pygame.font.SysFont(None, 28, italic=True)
        if self.calendar_font is None:
            self.calendar_font = pygame.font.SysFont(None, 30)

    def _draw_text_outline(self, surface, text, font, x, y,
                           fg=(255, 255, 255), outline=(0, 0, 0)):
        """Draw text with a simple 8-direction outline (like the shop)."""
        base = font.render(text, True, fg)
        outline_img = font.render(text, True, outline)

        for ox, oy in [
            (-1, -1), (1, -1), (-1, 1), (1, 1),
            (0, -1), (0, 1), (-1, 0), (1, 0),
        ]:
            surface.blit(outline_img, (x + ox, y + oy))

        surface.blit(base, (x, y))

    # ─────────────────────────────────────────────────────────────
    # Tile loading / processing
    # ─────────────────────────────────────────────────────────────

    def _load_all_tiles(self):
        """Load/scale all tiles for all states."""
        base_dir = os.path.join("assets", "GFX", "world")

        for tile_id in range(16):
            for state in self.world.tile_states:
                # filenames like "0new.png", "0lost.png", "0wonbank.png", etc.
                filename = f"{tile_id}{state}.png"
                path = os.path.join(base_dir, filename)

                if os.path.exists(path):
                    surf = self._load_and_process_tile(path)
                else:
                    surf = None

                if surf is None:
                    surf = self.default_tile.copy()

                self.tile_images[tile_id][state] = surf

            # Ensure all states have *something* (mirror "new" if missing)
            new_surf = self.tile_images[tile_id].get("new", self.default_tile)
            for state in self.world.tile_states:
                if state not in self.tile_images[tile_id]:
                    self.tile_images[tile_id][state] = new_surf

    def _load_and_process_tile(self, path: str) -> pygame.Surface:
        """
        Load a tile, crop horizontally to the active (non-alpha) region, then
        scale to world.TILE_SIZE width while keeping aspect ratio.
        We assume the island base is aligned with the bottom of the image.
        """
        try:
            img = pygame.image.load(path).convert_alpha()
        except (pygame.error, FileNotFoundError):
            return None

        width, height = img.get_size()

        # Mask from alpha channel, used for horizontal cropping
        mask = pygame.mask.from_surface(img)
        rects = mask.get_bounding_rects()

        if rects:
            bbox = rects[0]  # pygame.Rect
            # Crop only horizontally; keep full height so top alpha sky remains
            crop_rect = pygame.Rect(bbox.x, 0, bbox.w, height)
            img = img.subsurface(crop_rect).copy()
            width, height = img.get_size()
        # If rects is empty, fully transparent; we just keep as-is

        # Scale to target width, keep aspect ratio
        target_w = self.world.TILE_SIZE
        if width != target_w:
            scale = target_w / float(width)
            target_h = max(1, int(height * scale))
            img = pygame.transform.smoothscale(img, (target_w, target_h))

        return img

    def _get_brightened_tile(self, stage_id: int, state: str, base_img: pygame.Surface):
        """
        Return a cached brightened version of the given tile, approximating
        a +20% gamma/brightness by adding a small constant to RGB channels.
        """
        key = (stage_id, state)
        cached = self._brightened_tiles.get(key)
        if cached is not None:
            return cached

        # Copy & brighten via additive blending
        surf = base_img.copy()
        brighten = pygame.Surface(surf.get_size(), flags=pygame.SRCALPHA)
        # Roughly 20% of 255 ≈ 50
        brighten.fill((50, 50, 50, 0))
        surf.blit(brighten, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

        self._brightened_tiles[key] = surf
        return surf
    
    def _get_base_tile_img_for_cell(self, x: int, y: int) -> pygame.Surface:
        """Return the base tile surface (no hover brightening) for the cell."""
        cell = self.world.world_data[(x, y)]
        stage_id = cell["stage_id"]
        state = cell.get("state", "new")

        base_tile_img = self.tile_images.get(stage_id, {}).get(state)
        if base_tile_img is None:
            base_tile_img = self.tile_images.get(stage_id, {}).get(
                "new", self.default_tile
            )
        return base_tile_img

    def pick_tile_at(self, mouse_x: int, mouse_y: int):
        """
        Return (x, y) of the *frontmost* tile under the mouse, or None.

        - Iterates tiles in reverse draw order (front row first),
          so closer islands win when sprites overlap.
        - Uses per-pixel alpha hit testing so we only count visible parts
          of the island image.
        """
        # Frontmost first: bottom row to top row, right to left
        for y in reversed(range(4)):
            for x in reversed(range(4)):
                base_img = self._get_base_tile_img_for_cell(x, y)
                rect = self.get_tile_rect(x, y)

                if not rect.collidepoint(mouse_x, mouse_y):
                    continue

                # Convert mouse to local tile coordinates
                local_x = mouse_x - rect.x
                local_y = mouse_y - rect.y

                if 0 <= local_x < base_img.get_width() and 0 <= local_y < base_img.get_height():
                    # Per-pixel alpha check: only count non-transparent pixels
                    pixel_alpha = base_img.get_at((local_x, local_y)).a
                    if pixel_alpha > 5:  # small threshold to ignore almost-transparent bits
                        return (x, y)

        return None

    # ─────────────────────────────────────────────────────────────
    # Layout helpers
    # ─────────────────────────────────────────────────────────────

    def _compute_margins(self, screen):
        """
        Compute MARGIN_X/Y so the 4x4 world is centered on the screen,
        then shift the entire land area left by 125 pixels.
        """
        # max stagger factor for top row
        max_factor = 3
        extra_stagger_x = abs(self.world.ROW_STAGGER * max_factor)
        extra_stagger_y = abs(self.world.ROW_STAGGER * max_factor)

        world_w = self.world.TILE_SIZE + self.world.CELL_SPACING_X * 3 + extra_stagger_x

        extra_drop = abs(self.world.COLUMN_DROP * 3)  # col 0..3 difference
        world_h = (
            self.world.TILE_SIZE
            + self.world.CELL_SPACING_Y * 3
            + extra_drop
            + extra_stagger_y
        )

        self.MARGIN_X = (screen.get_width() - world_w) // 2
        self.MARGIN_Y = (screen.get_height() - world_h) // 2

        # Manual tweak: shift whole land mass left by 125px
        self.MARGIN_X -= 125


    def _cell_screen_origin(self, x: int, y: int):
        """
        Logical cell origin, including per-column vertical drop
        and per-row diagonal stagger.
        """
        # base grid position
        base_x = self.MARGIN_X + x * self.world.CELL_SPACING_X
        base_y = self.MARGIN_Y + y * self.world.CELL_SPACING_Y

        # COLUMN_DROP: slants columns vertically
        col_drop = self.world.COLUMN_DROP * x

        # ROW_STAGGER: diagonal shift per row:
        # y=0 -> factor 3, y=1 -> 2, y=2 -> 1, y=3 -> 0
        factor = 3 - y
        stagger_x = self.world.ROW_STAGGER * factor
        stagger_y = self.world.ROW_STAGGER * factor

        base_x += stagger_x
        base_y += col_drop + stagger_y
        return base_x, base_y

    # ─────────────────────────────────────────────────────────────
    # Building choice popup
    # ─────────────────────────────────────────────────────────────

    def _choose_building_for_tile(self, screen, pos):
        self._ensure_fonts()

        x, y = pos
        cell = self.world.world_data[(x, y)]

        options = [
            ("market", "Market"),
            ("bank", "Bank"),
            ("tax", "Tax Collector"),
            ("train", "Training Center"),
        ]

        descriptions = {
            "market": (
                "A market allows you to purchase goods the next time you come "
                "back to this land. If there is a bargain for this land, it "
                "will be listed here."
            ),
            "bank": (
                "A bank allows you to deposit money and collect interest the "
                "next time you come back to this land. Only one bank is "
                "allowed in the world."
            ),
            "tax": (
                "A tax collector takes gold from all adjacent controlled "
                "neighbors (including diagonals) each month."
            ),
            "train": (
                "A training center allows you to regain all of your units "
                "without spending money that month."
            ),
        }

        # Modal loop
        running = True
        hovered_index = None
        message = "What type of building would you like on this land?"

        clock = pygame.time.Clock()

        while running:
            mouse_x, mouse_y = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    return  # bail out entirely

                elif event.type == pygame.MOUSEMOTION:
                    hovered_index = None

                    # Options laid out vertically in the panel
                    panel_width = 700
                    panel_height = 260
                    panel_rect = pygame.Rect(
                        (screen.get_width() - panel_width) // 2,
                        (screen.get_height() - panel_height) // 2,
                        panel_width,
                        panel_height,
                    )

                    option_x = panel_rect.x + 40
                    option_y = panel_rect.y + 70
                    option_h = 32

                    for i, (bkey, _label) in enumerate(options):
                        rect = pygame.Rect(option_x, option_y + i * option_h, 320, option_h)
                        if rect.collidepoint(mouse_x, mouse_y):
                            hovered_index = i
                            break

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if hovered_index is not None:
                        bkey, _label = options[hovered_index]

                        # Enforce uniqueness for bank & tax collector
                        if bkey in ("bank", "tax"):
                            existing = self.world._building_at(bkey)
                            if existing is not None and existing != pos:
                                message = (
                                    "You already have a "
                                    + ("Bank" if bkey == "bank" else "Tax Collector")
                                    + " elsewhere in the world."
                                )
                                # Don't allow selection; stay in dialog
                                continue

                        # Accept selection
                        self.world._apply_building_choice(pos, bkey)
                        running = False
                        break

                elif event.type == pygame.KEYDOWN:
                    # Allow ESC to cancel without changing building.
                    if event.key == pygame.K_ESCAPE:
                        running = False
                        break

            # --- Draw popup ---
            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 160))  # dim background

            # Panel with simple "dithered" background
            panel_width = 700
            panel_height = 260
            panel_rect = pygame.Rect(
                (screen.get_width() - panel_width) // 2,
                (screen.get_height() - panel_height) // 2,
                panel_width,
                panel_height,
            )

            panel = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
            panel.fill((40, 40, 40, 230))

            # Fake dither: tiny lighter pixels in a checker pattern
            for py in range(0, panel_height, 4):
                for px in range(0, panel_width, 4):
                    if (px // 4 + py // 4) % 2 == 0:
                        panel.set_at((px, py), (70, 70, 80, 60))

            # Border
            pygame.draw.rect(panel, (220, 220, 220, 255), panel.get_rect(), 2)

            # Blit panel to overlay
            overlay.blit(panel, (0, 0))
            screen.blit(overlay, panel_rect.topleft)

            # Title text (white with no outline, inside panel)
            title_x = panel_rect.x + 20
            title_y = panel_rect.y + 20
            self._draw_text_outline(
                screen,
                message,
                self.ui_font,
                title_x,
                title_y,
                fg=(255, 255, 255),
            )

            # Options
            option_x = panel_rect.x + 40
            option_y = panel_rect.y + 70
            option_h = 32

            for i, (bkey, label) in enumerate(options):
                y = option_y + i * option_h
                is_hover = (hovered_index == i)
                color = (255, 255, 255) if is_hover else (220, 220, 220)

                # Indicate uniqueness constraints
                suffix = ""
                if bkey in ("bank", "tax"):
                    existing = self.world._building_at(bkey)
                    if existing is not None and existing != pos:
                        suffix = " (already built elsewhere)"
                        color = (180, 120, 120)

                text = label + suffix
                self._draw_text_outline(
                    screen,
                    text,
                    self.ui_font,
                    option_x,
                    y,
                    fg=color,
                )

            # Description of hovered option
            if hovered_index is not None:
                bkey, _ = options[hovered_index]
                desc = descriptions[bkey]
            else:
                desc = (
                    "Hover over an option to see details. "
                    "Click to place that building on this land."
                )

            desc_lines = self._wrap_text(desc, self.ui_font, panel_rect.width - 80)
            desc_x = panel_rect.x + 40
            desc_y = panel_rect.y + panel_rect.height - 80
            for line in desc_lines:
                self._draw_text_outline(
                    screen,
                    line,
                    self.ui_font,
                    desc_x,
                    desc_y,
                    fg=(230, 230, 230),
                )
                desc_y += 26

            pygame.display.flip()
            clock.tick(60)

    def _wrap_text(self, text, font, max_width):
        """Simple word-wrap helper."""
        words = text.split()
        lines = []
        current = []

        for w in words:
            test = " ".join(current + [w])
            if font.size(test)[0] <= max_width:
                current.append(w)
            else:
                if current:
                    lines.append(" ".join(current))
                current = [w]
        if current:
            lines.append(" ".join(current))
        return lines

    # ─────────────────────────────────────────────────────────────
    # Volcano emitter + smoke frames
    # ─────────────────────────────────────────────────────────────

    def _make_smoke_frames(self, size=40, frames=10):
        """Soft, translucent smoke puffs without a hard outline."""
        frames_list = []
        cx = cy = size // 2
        for i in range(frames):
            surf = pygame.Surface((size, size), pygame.SRCALPHA)
            t = i / max(1, frames - 1)
            radius = int(size * (0.3 + 0.35 * t))
            # draw a few overlapping circles with fading alpha
            for j in range(4):
                r = max(1, int(radius * (1.0 - 0.18 * j)))
                alpha = int(50 * (1.0 - t)) - j * 6
                alpha = max(10, alpha)
                pygame.draw.circle(
                    surf,
                    (185, 185, 185, alpha),
                    (cx, cy),
                    r,
                )
            frames_list.append(surf)
        return frames_list

    def _setup_volcano_emitter(self):
        """Create a soft smoke/ash emitter for the volcano tile (stage_id == 2)."""
        if self.particle_system is None:
            return

        # Find where tile_id 2 lives in the 4x4 grid
        volcano_present = any(
            cell["stage_id"] == 2 for cell in self.world.world_data.values()
        )
        if not volcano_present:
            return

        smoke_frames = self._make_smoke_frames()
        smoke_id = self.particle_system.register_surfaces(
            "volcano_smoke",
            smoke_frames,
            anim_mode="once",
            ticks_per_frame=4,
            start_delay_ticks=0,
        )

        # Base emitter; we'll move it each frame to the volcano's on-screen position
        self.volcano_emitter_id = self.particle_system.create_emitter(
            emitter_type="spray",
            emitter_angle=270.0,                # straight up
            particles_per_second=22,
            burst_count=0,
            x=0,
            y=0,
            particle_numbers=[smoke_id],
            velocity_speed_range=(30, 60),
            angle_spread_deg=30,
            air_resistance=0.7,
            wind_vector_range=((-8, 8), (-4, 4)),
            gravity_vector_range=((-4, -12), (-30, -55)),  # drift upward
            sustain_time=-1.0,
            decay_time=2.2,
            decay_result_color=(150, 150, 150, 30),
            decay_layer_paint=False,
            decay_paint_radius=2,
            pos_jitter_xy=(4, 4),
            size_range=(0.8, 1.3),
            alpha_range=(80, 150),  # softer overall
            align_to_velocity=False,
            image_rotation_offset_deg=0.0,
            anim_delay_ticks_override=None,
            max_particles=300,
        )

    # ─────────────────────────────────────────────────────────────
    # Ocean waves (non-particle)
    # ─────────────────────────────────────────────────────────────

    def _draw_ocean_waves(self, screen):
        """Draw gentle perspective waves across all visible ocean."""
        width, height = screen.get_size()
        wave_surf = pygame.Surface((width, height), pygame.SRCALPHA)

        t = pygame.time.get_ticks() / 1000.0

        # Start waves a bit below the islands and run them down to the bottom
        top = int(height * 0.55)     # tweak if you want waves higher/lower
        bottom = height - 20
        rows = 8                     # number of visible wave "bands"

        for i in range(rows):
            # 0 (near islands) → 1 (near bottom)
            d = i / (rows - 1) if rows > 1 else 0.0

            # Non-linear mapping so rows spread farther apart near the bottom
            y = int(top + (d ** 1.7) * (bottom - top))

            # Slightly larger waves and slower drift as we go "deeper"
            amp = 3.0 + 3.0 * d + 1.0 * math.sin(t * 0.7 + i * 0.6)
            freq = 0.020 + 0.006 * d
            speed = 0.9 + 0.35 * d

            # Softer as they recede; brighter up near the islands
            alpha = int(90 + 80 * (1.0 - d))
            color = (190, 230, 255, max(40, min(255, alpha)))

            phase = t * speed

            last_pos = None
            for x in range(-40, width + 40, 10):
                y_offset = math.sin(x * freq + phase) * amp
                yy = y + y_offset

                if last_pos is not None:
                    # Skip occasional segments so the line isn't perfectly continuous
                    segment_index = (x // 40) + i
                    if segment_index % 7 != 0:
                        pygame.draw.line(
                            wave_surf,
                            color,
                            last_pos,
                            (x, yy),
                            2,
                        )
                last_pos = (x, yy)

        screen.blit(wave_surf, (0, 0))

    # ─────────────────────────────────────────────────────────────
    # Hover info panel
    # ─────────────────────────────────────────────────────────────

    def _draw_info_panel(self, screen: pygame.Surface, hovered_pos):
        """Draw the black semi-transparent box with tile details."""
        self._ensure_fonts()

        cell = self.world.world_data[hovered_pos]
        stage_id = cell["stage_id"]
        info = self.world.stage_info.get(stage_id, {})

        name = info.get("name", f"Stage {stage_id}")
        element = info.get("element", "Unknown")
        wizard = info.get("wizard", "Unknown")

        win_flag = cell.get("win", False)
        state = cell.get("state", "new")
        building = cell.get("building")

        # Status
        if win_flag:
            status = "Won"
        elif state == "lost":
            status = "Lost"
        else:
            status = "New / Unconquered"

        # Current bonus (based on current building, if won)
        current_bonus = None
        if win_flag and info:
            if building == "market":
                current_bonus = self._format_gold_amounts(info.get("market_bonus"))
            elif building == "bank":
                current_bonus = self._format_gold_amounts(info.get("bank_bonus"))
            elif building == "tax":
                current_bonus = self._format_gold_amounts(info.get("tax_bonus"))
            elif building == "train":
                current_bonus = info.get("train_bonus")

        if not current_bonus:
            if not win_flag:
                current_bonus = "None (land not yet liberated)"
            else:
                current_bonus = "None"

        # Available bonuses (all non-None building bonuses here)
        available_bonus_lines = []
        if info:
            if info.get("market_bonus"):
                available_bonus_lines.append(f"Market: {self._format_gold_amounts(info['market_bonus'])}")
            if info.get("bank_bonus"):
                available_bonus_lines.append(f"Bank: {self._format_gold_amounts(info['bank_bonus'])}")
            if info.get("tax_bonus"):
                available_bonus_lines.append(f"Tax: {self._format_gold_amounts(info['tax_bonus'])}")
            if info.get("train_bonus"):
                available_bonus_lines.append(f"Training: {info['train_bonus']}")

        if not available_bonus_lines:
            available_bonus_lines = ["None"]

        # Active quests that touch this stage
        quests_for_stage = []
        for qname, qdata in self.world.active_quests.items():
            if qdata.get("stage_id") == stage_id:
                state_str = qdata.get("state", "active")
                quests_for_stage.append(f"{qname} ({state_str})")
        if not quests_for_stage:
            quests_for_stage = ["None"]

        # Panel geometry
        panel_width = max(360, int(screen.get_width() * 0.25))
        panel_height = screen.get_height() - 60
        panel_rect = pygame.Rect(
            screen.get_width() - panel_width - 20,
            30,
            panel_width,
            panel_height,
        )

        panel_surf = pygame.Surface(panel_rect.size, pygame.SRCALPHA)
        panel_surf.fill((0, 0, 0, 180))
        screen.blit(panel_surf, panel_rect.topleft)

        x = panel_rect.x + 18
        y = panel_rect.y + 16

        # Tile name
        self._draw_text_outline(screen, f"{name}", self.ui_font, x, y)
        y += 32

        # Element (italic, under the name)
        elem_text = f"{element} Element"
        self._draw_text_outline(screen, elem_text, self.ui_font_italic, x, y, fg=(210, 210, 255))
        y += 36

        # Status
        self._draw_text_outline(screen, f"Current status: {status}", self.ui_font, x, y)
        y += 30

        # Building or Wizard depending on state
        if win_flag:
            # If won: show current building
            b_label = building if building is not None else "None"
            self._draw_text_outline(
                screen,
                f"Current building: {b_label}",
                self.ui_font,
                x,
                y,
            )
            y += 30
        elif state == "lost":
            # If lost: show wizard
            self._draw_text_outline(
                screen,
                f"Wizard: {wizard}",
                self.ui_font,
                x,
                y,
            )
            y += 30
        else:
            # New tile: still can show wizard for flavor if you want
            self._draw_text_outline(
                screen,
                f"Wizard: {wizard}",
                self.ui_font,
                x,
                y,
            )
            y += 30

        # Current Bonus
        self._draw_text_outline(screen, "Current Bonus:", self.ui_font, x, y)
        y += 26

        for line in self._wrap_text(current_bonus, self.ui_font, panel_width - 36):
            self._draw_text_outline(screen, line, self.ui_font, x + 10, y)
            y += 24

        y += 8

        # Available Bonuses
        self._draw_text_outline(screen, "Available Bonuses:", self.ui_font, x, y)
        y += 26
        for entry in available_bonus_lines:
            wrapped = self._wrap_text(entry, self.ui_font, panel_width - 40)
            for line in wrapped:
                self._draw_text_outline(screen, f"- {line}", self.ui_font, x + 10, y)
                y += 24
        y += 8

        # Active Quests
        self._draw_text_outline(screen, "Active Quests:", self.ui_font, x, y)
        y += 26
        for entry in quests_for_stage:
            wrapped = self._wrap_text(entry, self.ui_font, panel_width - 40)
            for line in wrapped:
                self._draw_text_outline(screen, f"- {line}", self.ui_font, x + 10, y)
                y += 24

    def _format_gold_amounts(self, text):
        """Normalize gold amounts in overworld tooltips without changing source data."""
        if not text:
            return text

        formatted = str(text)
        formatted = re.sub(
            r"(?P<num>[+-]?\d+)\s*(?:gold|coin|coins)\b",
            r"\g<num>g",
            formatted,
            flags=re.IGNORECASE,
        )
        formatted = re.sub(r"(:\s*)(?P<num>\d+)(?!\s*g\b)", r"\1\g<num>g", formatted)
        formatted = re.sub(
            r"(\bfor\s+)(?P<num>\d+)(?!\s*g\b)",
            r"\1\g<num>g",
            formatted,
            flags=re.IGNORECASE,
        )
        return formatted
