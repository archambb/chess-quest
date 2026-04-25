# bank.py

import os
import pygame

import config


class BankScreen:
    """
    Bank UI:

    - Shows 'Deposited Gold' (bank balance) on the left.
    - Shows 'Gold on Hand' (player_gold) on the right.
    - Two central buttons: Deposit / Withdraw.
    - When Deposit/Withdraw is active:
        * Top text (white w/ black outline) explains mode + interest rate.
        * Player can enter amount via:
            - Up/down arrow triangles
            - Digits 0-9
            - Backspace (remove last digit)
            - Delete (clear to zero)
        * Value is clamped to available funds:
            - Deposit: <= player_gold
            - Withdraw: <= bank_balance
        * Done applies the transaction and returns to main bank screen.
    """

    def __init__(self, game, world):
        self.g = game
        self.world = world
        self.screen = self.g.screen
        self.clock = pygame.time.Clock()
        self.running = False

        # Interest & bank state from world (with safe defaults)
        self.bank_interest_rate = getattr(world, "bank_interest_rate", 0.05)
        if not hasattr(world, "bank_balance"):
            world.bank_balance = 0
        self.bank_balance = world.bank_balance  # local mirror; commit back on exit

        # Fonts
        self.font = pygame.font.SysFont(None, 32)
        self.title_font = pygame.font.SysFont(None, 40)

        # Background
        bg_path = os.path.join("assets", "GFX", "UI", "bank.png")
        if os.path.exists(bg_path):
            bg = pygame.image.load(bg_path).convert_alpha()
            self.bg_image = pygame.transform.smoothscale(
                bg, (config.WIDTH, config.HEIGHT)
            )
        else:
            self.bg_image = None
            print(f"[BANK] Background not found: {bg_path}")

        # Main buttons
        btn_w, btn_h = 180, 60
        center_x = config.WIDTH // 2
        center_y = config.HEIGHT // 2

        self.deposit_rect = pygame.Rect(
            center_x - btn_w - 20,
            center_y - btn_h // 2,
            btn_w,
            btn_h,
        )
        self.withdraw_rect = pygame.Rect(
            center_x + 20,
            center_y - btn_h // 2,
            btn_w,
            btn_h,
        )

        # Active transaction state
        self.mode = None  # None | "deposit" | "withdraw"
        self.entry_value = 0
        self.message = ""

        # Amount input geometry (used only when mode is active)
        self.amount_rect = pygame.Rect(
            center_x - 120,
            center_y + 40,
            240,
            50,
        )

        # Up/down arrow rects (defined relative to amount_rect)
        arrow_w = 40
        arrow_h = 25
        self.up_rect = pygame.Rect(
            self.amount_rect.right + 20,
            self.amount_rect.y,
            arrow_w,
            arrow_h,
        )
        self.down_rect = pygame.Rect(
            self.amount_rect.right + 20,
            self.amount_rect.y + arrow_h + 4,
            arrow_w,
            arrow_h,
        )

        # Done button (only visible when mode is active)
        self.done_rect = pygame.Rect(
            center_x - 80,
            self.amount_rect.bottom + 20,
            160,
            50,
        )

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

    # ------------------------------------------------------------------
    # Input handling
    # ------------------------------------------------------------------

    def _clamp_entry_to_available(self):
        if self.mode == "deposit":
            max_val = max(0, int(self.g.player_gold))
        elif self.mode == "withdraw":
            max_val = max(0, int(self.bank_balance))
        else:
            max_val = 0

        if self.entry_value < 0:
            self.entry_value = 0
        if self.entry_value > max_val:
            self.entry_value = max_val

    def _handle_number_key(self, digit_char: str):
        if not digit_char.isdigit():
            return
        d = int(digit_char)
        # Append new digit; avoid leading zeros like "000"
        new_val = self.entry_value * 10 + d
        self.entry_value = new_val
        self._clamp_entry_to_available()

    def _handle_backspace(self):
        self.entry_value = self.entry_value // 10
        self._clamp_entry_to_available()

    def _handle_delete(self):
        self.entry_value = 0

    def _handle_arrow_click(self, rect_clicked):
        if rect_clicked == "up":
            self.entry_value += 1
        elif rect_clicked == "down":
            self.entry_value -= 1
        self._clamp_entry_to_available()

    def _apply_transaction(self):
        if self.entry_value <= 0:
            self.message = "Enter an amount greater than 0."
            return

        amount = self.entry_value

        if self.mode == "deposit":
            max_can = max(0, int(self.g.player_gold))
            amount = min(amount, max_can)
            if amount <= 0:
                self.message = "You have no gold to deposit."
                return
            self.g.player_gold -= amount
            self.bank_balance += amount
            self.message = f"Deposited {amount} gold."
        elif self.mode == "withdraw":
            max_can = max(0, int(self.bank_balance))
            amount = min(amount, max_can)
            if amount <= 0:
                self.message = "No gold available to withdraw."
                return
            self.bank_balance -= amount
            self.g.player_gold += amount
            self.message = f"Withdrew {amount} gold."
        else:
            return

        # Reset entry and exit transaction mode
        self.entry_value = 0
        self.mode = None

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_background(self):
        if self.bg_image is not None:
            self.screen.blit(self.bg_image, (0, 0))
        else:
            self.screen.fill((10, 20, 30))

    def _draw_balances(self):
        # Deposited Gold (left)
        dep_label = self.font.render("Deposited Gold:", True, (255, 255, 255))
        dep_value = self.font.render(str(self.bank_balance), True, (255, 255, 128))

        self.screen.blit(dep_label, (40, 40))
        self.screen.blit(dep_value, (40, 80))

        # Gold on Hand (right)
        onhand_label = self.font.render("Gold on Hand:", True, (255, 255, 255))
        onhand_value = self.font.render(
            str(int(self.g.player_gold)),
            True,
            (255, 255, 128),
        )

        right_x = config.WIDTH - 40
        label_rect = onhand_label.get_rect(topright=(right_x, 40))
        value_rect = onhand_value.get_rect(topright=(right_x, 80))

        self.screen.blit(onhand_label, label_rect)
        self.screen.blit(onhand_value, value_rect)

    def _draw_main_buttons(self):
        if self.mode is not None:
            # In transaction mode: main buttons visually muted
            bg_deposit = (60, 60, 60)
            bg_withdraw = (60, 60, 60)
        else:
            bg_deposit = (40, 120, 40)
            bg_withdraw = (120, 40, 40)

        # Deposit
        pygame.draw.rect(self.screen, bg_deposit, self.deposit_rect, border_radius=10)
        pygame.draw.rect(
            self.screen, (10, 40, 10), self.deposit_rect, 2, border_radius=10
        )
        label = self.font.render("Deposit", True, (255, 255, 255))
        self.screen.blit(label, label.get_rect(center=self.deposit_rect.center))

        # Withdraw
        pygame.draw.rect(self.screen, bg_withdraw, self.withdraw_rect, border_radius=10)
        pygame.draw.rect(
            self.screen, (40, 10, 10), self.withdraw_rect, 2, border_radius=10
        )
        label2 = self.font.render("Withdraw", True, (255, 255, 255))
        self.screen.blit(label2, label2.get_rect(center=self.withdraw_rect.center))

    def _draw_transaction_ui(self):
        if self.mode is None:
            # Simple hint when no mode active
            hint = "Click Deposit or Withdraw."
            surf = self.font.render(hint, True, (230, 230, 230))
            self.screen.blit(
                surf,
                surf.get_rect(center=(config.WIDTH // 2, config.HEIGHT // 2 + 120)),
            )
            return

        # Top text with outline
        if self.mode == "deposit":
            action_text = "How much money would you like to deposit?"
        else:
            action_text = "How much money would you like to withdraw?"

        rate_pct = self.bank_interest_rate * 100.0
        rate_text = f"Your interest rate is: {rate_pct:.1f}% per month"

        top_y = 120
        self._draw_text_outline(
            action_text,
            self.title_font,
            60,
            top_y,
        )
        self._draw_text_outline(
            rate_text,
            self.font,
            60,
            top_y + 40,
        )

        # Amount box
        pygame.draw.rect(
            self.screen,
            (20, 20, 40),
            self.amount_rect,
            border_radius=8,
        )
        pygame.draw.rect(
            self.screen,
            (200, 200, 220),
            self.amount_rect,
            2,
            border_radius=8,
        )

        amount_txt = str(self.entry_value)
        amount_surf = self.title_font.render(amount_txt, True, (255, 255, 255))
        self.screen.blit(
            amount_surf,
            amount_surf.get_rect(center=self.amount_rect.center),
        )

        # Up / Down "arrow" triangles
        # Up triangle
        ux, uy, uw, uh = self.up_rect
        up_points = [
            (ux + uw // 2, uy),
            (ux + uw - 4, uy + uh - 4),
            (ux + 4, uy + uh - 4),
        ]
        pygame.draw.polygon(self.screen, (230, 230, 230), up_points)
        pygame.draw.polygon(self.screen, (30, 30, 30), up_points, 2)

        # Down triangle
        dx, dy, dw, dh = self.down_rect
        down_points = [
            (dx + 4, dy + 4),
            (dx + dw - 4, dy + 4),
            (dx + dw // 2, dy + dh - 4),
        ]
        pygame.draw.polygon(self.screen, (230, 230, 230), down_points)
        pygame.draw.polygon(self.screen, (30, 30, 30), down_points, 2)

        # Done button
        pygame.draw.rect(
            self.screen,
            (40, 100, 140),
            self.done_rect,
            border_radius=10,
        )
        pygame.draw.rect(
            self.screen,
            (10, 30, 60),
            self.done_rect,
            2,
            border_radius=10,
        )

        done_label = self.font.render("Done", True, (255, 255, 255))
        self.screen.blit(
            done_label,
            done_label.get_rect(center=self.done_rect.center),
        )

    def _draw_message(self):
        if not self.message:
            return
        surf = self.font.render(self.message, True, (255, 230, 120))
        rect = surf.get_rect(
            center=(config.WIDTH // 2, config.HEIGHT - 40)
        )
        self.screen.blit(surf, rect)

    def _draw(self):
        self._draw_background()
        self._draw_balances()
        self._draw_main_buttons()
        self._draw_transaction_ui()
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
                        # Exit current transaction mode if active, otherwise close bank
                        if self.mode is not None:
                            self.mode = None
                            self.entry_value = 0
                            self.message = ""
                        else:
                            self.running = False
                    elif self.mode is not None:
                        # Numeric input
                        if event.key == pygame.K_BACKSPACE:
                            self._handle_backspace()
                        elif event.key == pygame.K_DELETE:
                            self._handle_delete()
                        else:
                            # Check for digit keys
                            ch = event.unicode
                            if ch and ch.isdigit():
                                self._handle_number_key(ch)

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos

                    if self.mode is None:
                        # Selecting deposit / withdraw
                        if self.deposit_rect.collidepoint(mx, my):
                            self.mode = "deposit"
                            self.entry_value = 0
                            self.message = ""
                        elif self.withdraw_rect.collidepoint(mx, my):
                            self.mode = "withdraw"
                            self.entry_value = 0
                            self.message = ""
                    else:
                        # In transaction mode
                        if self.up_rect.collidepoint(mx, my):
                            self._handle_arrow_click("up")
                        elif self.down_rect.collidepoint(mx, my):
                            self._handle_arrow_click("down")
                        elif self.done_rect.collidepoint(mx, my):
                            self._apply_transaction()

            self._draw()
            pygame.display.flip()
            self.clock.tick(60)

        # On exit: push local bank_balance back into world
        self.world.bank_balance = self.bank_balance


