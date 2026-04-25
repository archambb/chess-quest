import os
import random
import pygame

# Try to use your config sizes if available; otherwise fall back.
try:
    import config
    SCREEN_WIDTH = config.WIDTH
    SCREEN_HEIGHT = config.HEIGHT
except Exception:
    SCREEN_WIDTH = 1280
    SCREEN_HEIGHT = 720


class MarketScreen:
    """
    Simple shop / market screen.

    Typical use in Chess Quest:
        from market import MarketScreen
        ...
        stage_id = self.world.world_data[(self.world.player_pos)]["stage_id"]
        shop = MarketScreen(self, stage_id)
        shop.run()
    """

    # Mask color → powerup key
    COLOR_TO_POWER = {
        (0x00, 0x00, 0x00): "bombs",             # #000000
        (0x7F, 0x7F, 0x7F): "freezes",           # #7F7F7F
        (0x88, 0x00, 0x15): "swaps",             # #880015
        (0xED, 0x1C, 0x24): "shields",           # #ED1C24
        (0xFF, 0x7F, 0x27): "advanced_shields",  # #FF7F27
        (0xFF, 0xF2, 0x00): "promotions",        # #FFF200
        (0x22, 0xB1, 0x4C): "time_warps",        # #22B14C
        (0x00, 0xA2, 0xE8): "magnets",           # #00A2E8
    }

    # Nicer on-screen names
    POWER_DISPLAY_NAMES = {
        "bombs": "Bombs",
        "freezes": "Freeze Potions",
        "swaps": "Piece Swaps",
        "shields": "Shields",
        "advanced_shields": "Advanced Shields",
        "promotions": "Instant Promotions",
        "time_warps": "Time Warps",
        "magnets": "Magnets",
    }

    # Base prices
    BASE_PRICES = {
        "bombs": 3,
        "freezes": 2,
        "swaps": 5,
        "shields": 2,
        "advanced_shields": 3,
        "promotions": 4,
        "time_warps": 1,
        "magnets": 3,
    }

    # Per-stage overrides
    STAGE_PRICE_OVERRIDES = {
        0: {"advanced_shields": 2, "shields": 1},
        2: {"bombs": 2},
        4: {"swaps": 3},
        5: {"freezes": 1},  # "freeze: 1" interpreted as freezes
        6: {"magnets": 2},
        9: {"promotions": 2},
        15: {
            "bombs": 2,
            "freezes": 1,
            "swaps": 3,
            "shields": 1,
            "advanced_shields": 2,
            "promotions": 2,
            "time_warps": 1,
            "magnets": 2,
        },
    }

    def __init__(self, game, stage_id: int, shop_index: int | None = None):
        """
        :param game:      Game / ChessScreen object (must have .screen and .powerups)
        :param stage_id:  current stage id (0-15) for price overrides
        :param shop_index: optional fixed shop number; if None, choose random 1-6
        """
        self.g = game
        self.stage_id = stage_id

        # Screen
        self.screen = getattr(game, "screen", None)
        if self.screen is None:
            self.screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))

        # Fonts
        self.title_font = pygame.font.SysFont(None, 32)
        self.info_font = pygame.font.SysFont(None, 26)

        # Which shop art to use (1-6 at random if not specified)
        if shop_index is None:
            shop_index = random.randint(1, 6)
        self.shop_index = shop_index

        # Load shop + mask images
        base_dir = os.path.join("assets", "GFX", "market")
        self.shop_image = pygame.image.load(
            os.path.join(base_dir, f"{self.shop_index}.png")
        ).convert_alpha()
        self.mask_image = pygame.image.load(
            os.path.join(base_dir, f"{self.shop_index} - Mask.png")
        ).convert()

        # Center the shop graphic
        self.shop_rect = self.shop_image.get_rect(
            center=(self.screen.get_width() // 2, self.screen.get_height() // 2)
        )

        # Build effective price table for this stage
        self.prices = dict(self.BASE_PRICES)
        overrides = self.STAGE_PRICE_OVERRIDES.get(stage_id, {})
        self.prices.update(overrides)

        # Status text (bottom line, used when not hovering)
        self.status_text = ""

        # Gold coin graphic for top-right display
        self.gold_icon = self._choose_gold_icon()

    # ------------------------------------------------------------------
    # Utility: text with black outline
    # ------------------------------------------------------------------
    def draw_text_outline(self, surface, text, font, x, y,
                          fg=(255, 255, 255), outline=(0, 0, 0)):
        """
        Draw text with a simple 8-direction black outline so it stays readable.
        """
        base = font.render(text, True, fg)
        outline_img = font.render(text, True, outline)

        for ox, oy in [
            (-1, -1), (1, -1), (-1, 1), (1, 1),
            (0, -1), (0, 1), (-1, 0), (1, 0)
        ]:
            surface.blit(outline_img, (x + ox, y + oy))

        surface.blit(base, (x, y))

    # ------------------------------------------------------------------
    # Gold helpers
    # ------------------------------------------------------------------
    def _get_gold(self) -> int:
        """
        Prefer player_gold (as in ChessScreen). If you later change gold
        tracking to an int gold_coins field, this still works.
        """
        if hasattr(self.g, "player_gold"):
            return int(self.g.player_gold)
        if hasattr(self.g, "gold_coins") and isinstance(self.g.gold_coins, int):
            return int(self.g.gold_coins)
        return 0

    def _set_gold(self, value: int) -> None:
        if hasattr(self.g, "player_gold"):
            self.g.player_gold = int(value)
        elif hasattr(self.g, "gold_coins") and isinstance(self.g.gold_coins, int):
            self.g.gold_coins = int(value)

    def _choose_gold_icon(self) -> pygame.Surface:
        """
        Choose a random gold coin graphic from the game if available.
        Falls back to a simple drawn coin if not.
        """
        # In ChessScreen, self.gold_coins is a list of coin surfaces.
        if hasattr(self.g, "gold_coins") and self.g.gold_coins:
            return random.choice(self.g.gold_coins)

        # Fallback: simple drawn coin
        surf = pygame.Surface((24, 24), pygame.SRCALPHA)
        pygame.draw.circle(surf, (255, 215, 0), (12, 12), 10)
        pygame.draw.circle(surf, (160, 120, 0), (12, 12), 10, 2)
        return surf

    # ------------------------------------------------------------------
    # Powerup + mask helpers
    # ------------------------------------------------------------------
    def _power_from_mouse(self, mouse_pos):
        """Return powerup key under the cursor, or None."""
        if not self.shop_rect.collidepoint(mouse_pos):
            return None

        local_x = mouse_pos[0] - self.shop_rect.left
        local_y = mouse_pos[1] - self.shop_rect.top

        if not (0 <= local_x < self.mask_image.get_width() and
                0 <= local_y < self.mask_image.get_height()):
            return None

        r, g, b, *_ = self.mask_image.get_at((local_x, local_y))
        return self.COLOR_TO_POWER.get((r, g, b))

    def _buy_power(self, power_key: str):
        cost = self.prices.get(power_key, 0)
        gold = self._get_gold()

        if gold < cost:
            self.status_text = "Not enough gold for that purchase."
            if hasattr(self.g, "send_feedback"):
                self.g.ui_state.send_feedback("You don't have enough gold.")
            return

        # Deduct gold and increment inventory (all purchases are final)
        self._set_gold(gold - cost)
        if not hasattr(self.g, "powerups") or self.g.powerups is None:
            self.g.powerups = {}
        self.g.powerups[power_key] = self.g.powerups.get(power_key, 0) + 1

        display_name = self.POWER_DISPLAY_NAMES.get(power_key, power_key)
        self.status_text = f"Purchased {display_name} for {cost} gold."

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _draw(self, hovered_power):
        self.screen.fill((20, 20, 30))

        # Shop graphic
        self.screen.blit(self.shop_image, self.shop_rect.topleft)

        # Top-left greeting
        self.draw_text_outline(
            self.screen,
            "Welcome to my shop! Press ESC to leave.",
            self.title_font,
            16, 10,
            fg=(255, 255, 255)
        )

        # Top-right gold display: [coin graphic] "(gold coin): N"
        gold_amount = self._get_gold()
        gold_text_str = f"(gold coin): {gold_amount}"

        # Measure text and coin to right-align the whole group
        measure_surf = self.title_font.render(gold_text_str, True, (255, 255, 255))
        text_w, text_h = measure_surf.get_size()
        icon_w, icon_h = self.gold_icon.get_size()

        group_w = icon_w + 6 + text_w
        base_x = self.screen.get_width() - 16 - group_w
        icon_x = base_x
        icon_y = 10

        # Blit the coin
        self.screen.blit(self.gold_icon, (icon_x, icon_y))

        # Text vertically centered to the coin
        text_x = icon_x + icon_w + 6
        text_y = icon_y + (icon_h - text_h) // 2

        self.draw_text_outline(
            self.screen,
            gold_text_str,
            self.title_font,
            text_x, text_y,
            fg=(255, 255, 255)
        )

        # Bottom info line (hover or status)
        if hovered_power is not None:
            display_name = self.POWER_DISPLAY_NAMES.get(hovered_power, hovered_power)
            cost = self.prices.get(hovered_power, 0)
            count = 0
            if hasattr(self.g, "powerups") and self.g.powerups:
                count = self.g.powerups.get(hovered_power, 0)
            info = f"{display_name}, Cost to purchase: {cost}, Count in your inventory: {count}"
        else:
            info = self.status_text

        if info:
            measure = self.info_font.render(info, True, (255, 255, 255))
            info_w, info_h = measure.get_size()
            info_x = (self.screen.get_width() - info_w) // 2
            info_y = self.screen.get_height() - info_h - 10
            self.draw_text_outline(
                self.screen,
                info,
                self.info_font,
                info_x, info_y,
                fg=(230, 230, 230)
            )

        pygame.display.flip()

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------
    def run(self):
        clock = pygame.time.Clock()
        running = True

        while running:
            hovered_power = None
            mouse_pos = pygame.mouse.get_pos()
            hovered_power = self._power_from_mouse(mouse_pos)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE:
                        running = False

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if hovered_power is not None:
                        self._buy_power(hovered_power)

            self._draw(hovered_power)
            clock.tick(60)


# ----------------------------------------------------------------------
# Stand-alone test harness
# ----------------------------------------------------------------------
if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Chess Quest - Market Test")

    class DummyGame:
        def __init__(self, screen):
            self.screen = screen
            self.powerups = {}
            self.player_gold = 10  # some gold in hand for testing

            # Fake gold coin list (real game gets this from AssetManager)
            self.gold_coins = []
            coin = pygame.Surface((24, 24), pygame.SRCALPHA)
            pygame.draw.circle(coin, (255, 215, 0), (12, 12), 10)
            pygame.draw.circle(coin, (160, 120, 0), (12, 12), 10, 2)
            self.gold_coins.append(coin)

        def send_feedback(self, message):
            print("[FEEDBACK]", message)

    dummy_game = DummyGame(screen)
    # Try a few times - each run should pick a random shop 1-6
    market = MarketScreen(dummy_game, stage_id=0)
    market.run()

    print("Final powerups:", dummy_game.powerups)
    print("Gold remaining:", dummy_game.player_gold)
    pygame.quit()
