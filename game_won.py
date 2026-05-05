#game_won.py
import pygame


class TerritoryWinScreen:
    """
    Modal screen shown immediately after the player wins a territory.

    - Darkens the current screen.
    - Shows a right-hand info panel with:
        * Territory name, element, wizard
        * Stage-specific building bonuses
        * Buttons for: Market, Tax Collector (if none exists yet),
          Bank (if none exists yet), Training Center.
    - Returns the chosen building type as a string:
        "market", "tax", "bank", or "train",
      or None if the player cancels / closes without choosing.
    """

    def __init__(self, world, tile_pos):
        """
        world: GameWorld instance
        tile_pos: (x, y) of the tile that was just won
        """
        self.world = world
        self.tile_pos = tile_pos
        self.g = getattr(world, "g", None) or getattr(world, "game", None)
        if self.g is None:
            raise AttributeError("GameWorld is missing both 'g' and 'game' references.")
        self.screen = self.g.screen

        pygame.font.init()
        self.clock = pygame.time.Clock()

        # Basic layout
        self.screen_width = self.screen.get_width()
        self.screen_height = self.screen.get_height()
        self.panel_width = int(self.screen_width * 0.40)
        self.panel_margin = 40
        self.panel_rect = pygame.Rect(
            self.screen_width - self.panel_width - self.panel_margin,
            self.panel_margin,
            self.panel_width,
            self.screen_height - 2 * self.panel_margin,
        )

        # Fonts
        self.title_font = pygame.font.SysFont(None, 42)
        self.subtitle_font = pygame.font.SysFont(None, 30)
        self.body_font = pygame.font.SysFont(None, 24)
        self.small_font = pygame.font.SysFont(None, 20)

        # Compute stage info + button layout
        self.stage_id = self.world.world_data[self.tile_pos]["stage_id"]
        self.stage_meta = self.world.stage_info.get(self.stage_id, {})

        self.buttons = self._create_buttons()

    # ─────────────────────────────────────────────────────────────
    # Button setup
    # ─────────────────────────────────────────────────────────────

    def _create_buttons(self):
        """
        Build the list of building choice buttons, with rects & labels.

        Always offer:
          - Market
          - Training Center

        Offer only if not already built elsewhere:
          - Tax Collector
          - Bank
        """
        buttons = []

        # Market
        buttons.append({
            "type": "market",
            "label": "Market",
            "desc": self.stage_meta.get("market_bonus")
                    or "Buy and sell items, shields, and powerups.",
        })

        # Tax Collector (one per world)
        if not self.world.has_tax_office():
            buttons.append({
                "type": "tax",
                "label": "Tax Collector",
                "desc": self.stage_meta.get("tax_bonus")
                        or "Collect +1 gold per adjacent liberated land each month.",
            })

        # Bank (one per world)
        if not self.world.has_bank():
            buttons.append({
                "type": "bank",
                "label": "Bank",
                "desc": self.stage_meta.get("bank_bonus")
                        or "Store gold safely and earn monthly interest.",
            })

        # Training Center (can exist in multiple places)
        buttons.append({
            "type": "train",
            "label": "Training Center",
            "desc": self.stage_meta.get("train_bonus")
                    or "Train and upgrade your army pieces.",
        })

        # Layout buttons vertically inside the panel
        button_height = 60
        gap = 15
        top_offset = 260  # space for header + territory info

        for i, btn in enumerate(buttons):
            y = self.panel_rect.y + top_offset + i * (button_height + gap)
            rect = pygame.Rect(
                self.panel_rect.x + 35,
                y,
                self.panel_rect.width - 70,
                button_height,
            )
            btn["rect"] = rect

        return buttons

    # ─────────────────────────────────────────────────────────────
    # Main loop
    # ─────────────────────────────────────────────────────────────

    def run(self):
        """
        Show the modal until the player picks a building or cancels.

        Returns:
            building_type: str | None
        """
        chosen = None
        running = True

        # Small helper so we can keep whatever the last frame was underneath us
        # and just draw a translucent overlay on top.
        pygame.display.flip()  # ensure current frame is visible

        while running:
            dt = self.clock.tick(60)
            mouse_pos = pygame.mouse.get_pos()

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False
                    chosen = None

                elif event.type == pygame.KEYDOWN:
                    # ESC: decide later, keep building=None
                    if event.key == pygame.K_ESCAPE:
                        running = False
                        chosen = None

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for btn in self.buttons:
                        if btn["rect"].collidepoint(mouse_pos):
                            chosen = btn["type"]
                            running = False
                            break

            self._draw(mouse_pos)
            pygame.display.flip()

        return chosen

    # ─────────────────────────────────────────────────────────────
    # Drawing
    # ─────────────────────────────────────────────────────────────

    def _draw(self, mouse_pos):
        # Redraw the overworld under the chooser; the previous frame may be combat.
        try:
            traversable = self.world.knight_moves(self.world.player_pos)
            self.world.renderer.draw_world(self.screen, traversable, hovered_pos=None)
        except Exception as e:
            print(f"[WARN] Could not draw overworld behind territory win screen: {e}")
            self.screen.fill((0, 0, 0))

        # Darken the whole screen while keeping the overworld visible.
        overlay = pygame.Surface(
            (self.screen_width, self.screen_height),
            pygame.SRCALPHA
        )
        overlay.fill((0, 0, 0, 160))
        self.screen.blit(overlay, (0, 0))

        # Panel background
        pygame.draw.rect(self.screen, (30, 30, 50), self.panel_rect)
        pygame.draw.rect(self.screen, (200, 200, 230), self.panel_rect, 2)

        # Header text
        territory_name = self.stage_meta.get("name", f"Stage {self.stage_id}")
        title_text = f"You have won the territory of"
        title_surface = self.title_font.render(title_text, True, (255, 255, 255))
        name_surface = self.title_font.render(territory_name, True, (255, 220, 150))

        self.screen.blit(
            title_surface,
            (self.panel_rect.x + 24, self.panel_rect.y + 24),
        )
        self.screen.blit(
            name_surface,
            (self.panel_rect.x + 24, self.panel_rect.y + 24 + title_surface.get_height() + 4),
        )

        question_surface = self.subtitle_font.render(
            "What would you like to build here?",
            True,
            (230, 230, 255),
        )
        self.screen.blit(
            question_surface,
            (self.panel_rect.x + 24,
             self.panel_rect.y + 24 + title_surface.get_height()
             + name_surface.get_height() + 12),
        )

        # Territory info (element, wizard)
        info_y = self.panel_rect.y + 140
        element = self.stage_meta.get("element", "Unknown")
        wizard = self.stage_meta.get("wizard", "Unknown wizard")

        self._draw_wrapped_text(
            f"Element: {element}",
            self.body_font,
            (210, 230, 210),
            self.panel_rect.x + 24,
            info_y,
            self.panel_rect.width - 48,
        )
        info_y += 30

        self._draw_wrapped_text(
            f"Guardian: {wizard}",
            self.body_font,
            (210, 210, 255),
            self.panel_rect.x + 24,
            info_y,
            self.panel_rect.width - 48,
        )

        info_y += 40
        self._draw_wrapped_text(
            "Choose one building for this land. "
            "You may only have one Bank and one Tax Collector in your realm.",
            self.small_font,
            (220, 220, 220),
            self.panel_rect.x + 24,
            info_y,
            self.panel_rect.width - 48,
        )

        # Buttons
        for btn in self.buttons:
            self._draw_button(btn, mouse_pos)

        # ESC hint
        hint_surface = self.small_font.render(
            "Press ESC to decide later.",
            True,
            (180, 180, 200),
        )
        self.screen.blit(
            hint_surface,
            (self.panel_rect.x + 24,
             self.panel_rect.bottom - hint_surface.get_height() - 16),
        )

    def _draw_button(self, btn, mouse_pos):
        rect = btn["rect"]
        hovered = rect.collidepoint(mouse_pos)

        base_color = (70, 70, 110)
        hover_color = (100, 100, 160)
        border_color = (230, 230, 255)

        pygame.draw.rect(
            self.screen,
            hover_color if hovered else base_color,
            rect,
            border_radius=8,
        )
        pygame.draw.rect(
            self.screen,
            border_color,
            rect,
            width=2,
            border_radius=8,
        )

        label_surface = self.body_font.render(btn["label"], True, (255, 255, 255))
        self.screen.blit(
            label_surface,
            (rect.x + 10, rect.y + 8),
        )

        # Bonus/description under the label
        if btn.get("desc"):
            self._draw_wrapped_text(
                f"Bonus: {btn['desc']}",
                self.small_font,
                (230, 230, 200),
                rect.x + 10,
                rect.y + 30,
                rect.width - 20,
            )

    def _draw_wrapped_text(self, text, font, color, x, y, max_width):
        """
        Utility: render text with simple word-wrapping into the panel.
        """
        words = text.split()
        lines = []
        current = ""

        for w in words:
            test = f"{current} {w}".strip()
            if font.size(test)[0] <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = w
        if current:
            lines.append(current)

        for i, line in enumerate(lines):
            surf = font.render(line, True, color)
            self.screen.blit(surf, (x, y + i * (font.get_height() + 2)))
