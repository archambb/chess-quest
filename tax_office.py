# tax_office.py

import os
import pygame

import config


class TaxOfficeScreen:
    """
    Tax Collector UI:

    - Shows a narrative text at the top:
        "Your collected taxes are ready for you, Sire.
         You have earned <balance> gold pieces.

         Your current tax income is: <income> gold per month"
    - Player's current gold appears in the top-right corner.
    - A single "Done" button at the bottom center:
        * On click:
            - Add world.tax_office_balance to g.player_gold
            - Set world.tax_office_balance to 0
            - Close the screen
    """

    def __init__(self, game, world):
        self.g = game
        self.world = world
        self.screen = self.g.screen
        self.clock = pygame.time.Clock()
        self.running = False

        # Ensure values exist on world with safe defaults
        if not hasattr(world, "tax_office_balance"):
            world.tax_office_balance = 0
        if not hasattr(world, "tax_office_income_per_month"):
            world.tax_office_income_per_month = 0

        self.tax_balance = world.tax_office_balance
        self.tax_income = world.tax_office_income_per_month

        # Fonts
        self.body_font = pygame.font.SysFont(None, 32)
        self.title_font = pygame.font.SysFont(None, 40)

        # Background
        bg_path = os.path.join("assets", "GFX", "UI", "tax.png")
        if os.path.exists(bg_path):
            bg = pygame.image.load(bg_path).convert_alpha()
            self.bg_image = pygame.transform.smoothscale(
                bg, (config.WIDTH, config.HEIGHT)
            )
        else:
            self.bg_image = None
            print(f"[TAX] Background not found: {bg_path}")

        # Done button at bottom center
        btn_w, btn_h = 200, 60
        self.done_rect = pygame.Rect(
            (config.WIDTH - btn_w) // 2,
            config.HEIGHT - btn_h - 40,
            btn_w,
            btn_h,
        )

        self.message = ""  # optional footer message if we ever want it

    # ------------------------------------------------------------------
    # Text helpers
    # ------------------------------------------------------------------

    def _draw_text_outline(
        self, text, font, x, y,
        fg=(255, 255, 255),
        outline=(0, 0, 0),
    ):
        base = font.render(text, True, fg)
        border = font.render(text, True, outline)

        for ox, oy in [
            (-1, -1), (1, -1),
            (-1, 1),  (1, 1),
            (0, -1),  (0, 1),
            (-1, 0),  (1, 0),
        ]:
            self.screen.blit(border, (x + ox, y + oy))
        self.screen.blit(base, (x, y))

    def _wrap_text(self, text, font, max_width):
        """Simple word-wrap utility."""
        words = text.split()
        lines = []
        current = []

        for w in words:
            test = " ".join(current + [w])
            if font.size(test)[0] <= max_width:
                current.append(w)
            else:
                lines.append(" ".join(current))
                current = [w]
        if current:
            lines.append(" ".join(current))
        return lines

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_background(self):
        if self.bg_image is not None:
            self.screen.blit(self.bg_image, (0, 0))
        else:
            self.screen.fill((25, 20, 30))

    def _draw_player_gold(self):
        label = self.body_font.render("Gold on Hand:", True, (255, 255, 255))
        value = self.body_font.render(
            str(int(self.g.player_gold)),
            True,
            (255, 255, 128),
        )

        right_x = config.WIDTH - 20
        label_rect = label.get_rect(topright=(right_x, 20))
        value_rect = value.get_rect(topright=(right_x, 55))

        self.screen.blit(label, label_rect)
        self.screen.blit(value, value_rect)

    def _draw_text_block(self):
        # Main narrative text
        main_text = (
            f"Your collected taxes are ready for you, Sire. "
            f"You have earned {self.tax_balance} gold pieces.\n\n"
            f"Your current tax income is: {self.tax_income} gold per month."
        )

        # Wrap into lines to fit nicely
        max_width = config.WIDTH - 120
        lines = []
        for paragraph in main_text.split("\n\n"):
            wrapped = self._wrap_text(paragraph, self.body_font, max_width)
            lines.extend(wrapped)
            lines.append("")  # blank line between paragraphs

        start_y = 100
        x = 60
        y = start_y

        for line in lines:
            if not line:  # blank spacer
                y += 10
                continue
            self._draw_text_outline(line, self.body_font, x, y)
            y += 32

    def _draw_done_button(self):
        pygame.draw.rect(
            self.screen,
            (60, 120, 50),
            self.done_rect,
            border_radius=10,
        )
        pygame.draw.rect(
            self.screen,
            (20, 40, 15),
            self.done_rect,
            2,
            border_radius=10,
        )

        label = self.body_font.render("Done", True, (255, 255, 255))
        self.screen.blit(label, label.get_rect(center=self.done_rect.center))

    def _draw_message(self):
        if not self.message:
            return
        surf = self.body_font.render(self.message, True, (255, 230, 140))
        rect = surf.get_rect(center=(config.WIDTH // 2, config.HEIGHT - 20))
        self.screen.blit(surf, rect)

    def _draw(self):
        self._draw_background()
        self._draw_player_gold()
        self._draw_text_block()
        self._draw_done_button()
        self._draw_message()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        self.running = True
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        self._apply_and_exit()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos
                    if self.done_rect.collidepoint(mx, my):
                        self._apply_and_exit()

            self._draw()
            pygame.display.flip()
            self.clock.tick(60)

    def _apply_and_exit(self):
        """Grant collected taxes to player and zero the office balance."""
        if self.tax_balance > 0:
            self.g.player_gold += self.tax_balance
            self.tax_balance = 0

        # Push back to world
        self.world.tax_office_balance = self.tax_balance

        self.running = False


