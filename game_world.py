import os
import json
import random
import pygame

from game_world_render import GameWorldRenderer


class GameWorld:

    def __init__(self, game):
        """
        game: your main game / ChessScreen object.
        We keep a reference so we can:
          - Open UIs (market, bank, etc.) using g.screen and game state.
          - Call army_upkeep.apply_monthly_upkeep(self, game) each month.
        """
        self.g = game
        self.game = game  # compatibility alias for older callers

        # All stage IDs except 0
        stage_ids = list(range(1, 16))
        random.shuffle(stage_ids)

        # Logical tile width after processing
        self.TILE_SIZE = 256  # width of each island after scaling

        # Layout values
        self.CELL_SPACING_X = 120
        self.CELL_SPACING_Y = 200
        self.COLUMN_DROP = 75
        self.ROW_STAGGER = 129  # diagonal row offset

        # Player position, starts at bottom-left
        self.player_pos = (0, 3)

        # Calendar: start June 1065 CY
        self.month_names = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December",
        ]
        self.current_year = 1065
        self.current_month_index = 5  # June

        # Possible visual states for a tile
        self.tile_states = [
            "new",
            "lost",
            "wonmarket",
            "wontax",
            "wonbank",
            "wontrain",
        ]

        # Create the 4x4 grid of data
        # world_data[(x, y)] = {
        #   "stage_id": int,
        #   "state": "new" | "lost" | "wonmarket" | "wontax" | "wonbank" | "wontrain",
        #   "win": bool,
        #   "lose": int,
        #   "visits": int,
        #   "building": None | "market" | "bank" | "tax" | "train"
        # }
        self.world_data = {}
        for y in range(4):
            for x in range(4):
                if (x, y) == (0, 3):
                    assigned_id = 0  # bottom-left always stage 0
                else:
                    assigned_id = stage_ids.pop()
                self.world_data[(x, y)] = {
                    "stage_id": assigned_id,
                    "state": "new",
                    "win": False,
                    "lose": 0,
                    "visits": 0,
                    "building": None,
                }

        # Stage metadata (from your spreadsheet)
        self._init_stage_info()

        # Active quests placeholder:
        # { quest_name: {"stage_id": int, "state": str}, ... }
        # We'll wire this to your actual quest system later.
        self.active_quests = {}

        # Economy: bank
        self.bank_interest_rate = 0.05     # 5% per month default
        self.bank_balance = 0              # gold stored in the bank

        # Economy: tax office
        self.tax_office_balance = 0            # stored tax revenue
        self.tax_office_income_per_month = 0   # last-month or expected income
        self.tax_office_bonus = 0.0            # multiplier or flat bonus

        # Army economics
        self.army_cost_per_unit = 1    # gold upkeep per piece per month (example)
        # Army layout (WHITE perspective only - default chess army)
        # Keys are "file+rank" (e.g., "a1", "e2")
        # Values are piece codes for WHITE: K,Q,R,B,N,P
        self.default_white_army_layout = {
            # Back rank
            "a1": "R",
            "b1": "N",
            "c1": "B",
            "d1": "Q",
            "e1": "K",
            "f1": "B",
            "g1": "N",
            "h1": "R",

            # Pawn rank
            "a2": "P",
            "b2": "P",
            "c2": "P",
            "d2": "P",
            "e2": "P",
            "f2": "P",
            "g2": "P",
            "h2": "P",
        }

        # Renderer: owns all visuals, images, fonts, particles, etc.
        self.renderer = GameWorldRenderer(self)

    # ─────────────────────────────────────────────────────────────
    # Stage metadata
    # ─────────────────────────────────────────────────────────────

    def _init_stage_info(self):
        """
        Encodes the spreadsheet you provided:

        Stage | Name                | Element | Wizard                  | Market      | Bank      | Tax Collector         | Train
        """
        self.stage_info = {
            0: {
                "name": "Hill Country",
                "element": "Stone",
                "wizard": "The Wizard of Stone",
                "market_bonus": "advanced shields: 2, shields: 1",
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": "2 pawns become rooks",
            },
            1: {
                "name": "The Misty Fens",
                "element": "Swamp",
                "wizard": "The Drowned Seer",
                "market_bonus": None,
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": None,
            },
            2: {
                "name": "The Ember Spire",
                "element": "Fire",
                "wizard": "The Magma Sage",
                "market_bonus": "bombs: 2",
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": None,
            },
            3: {
                "name": "The Emerald Grove",
                "element": "Forest",
                "wizard": "The Forest Druid",
                "market_bonus": None,
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": "2 pawns become bishops (elves)",
            },
            4: {
                "name": "The Shadow Realms",
                "element": "Shadow",
                "wizard": "The Dark Wizard",
                "market_bonus": "swaps: 3",
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": None,
            },
            5: {
                "name": "The Frozen Lake",
                "element": "Frozen",
                "wizard": "The Frostbound Oracle",
                "market_bonus": "freeze: 2 for 1",
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": None,
            },
            6: {
                "name": "The Storm Reaches",
                "element": "Storm",
                "wizard": "The Tempest Caller",
                "market_bonus": "magnet: 2",
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": None,
            },
            7: {
                "name": "The Grave Hollow",
                "element": "Grave",
                "wizard": "The Dark Necromancer",
                "market_bonus": None,
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": None,
            },
            8: {
                "name": "The Shifting Sands",
                "element": "Sand",
                "wizard": "The Sand Shaper",
                "market_bonus": None,
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": None,
            },
            9: {
                "name": "The Iron Keep",
                "element": "Castle",
                "wizard": "The Iron Castellan",
                "market_bonus": "promotions: 2",
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": "2 pawns become knights",
            },
            10: {
                "name": "The Astral Gate",
                "element": "Astral",
                "wizard": "The Cosmic Wizard",
                "market_bonus": None,
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": "While training center built, AI drops by 1 point",
            },
            11: {
                "name": "The Verdant Citadel",
                "element": "Life",
                "wizard": "The Wizard of Life",
                "market_bonus": None,
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": None,
            },
            12: {
                "name": "The Crimson Court",
                "element": "Blood",
                "wizard": "The Blood Wizard",
                "market_bonus": None,
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": None,
            },
            13: {
                "name": "The Sanctuary of Light",
                "element": "Light",
                "wizard": "The Wizard of Light",
                "market_bonus": None,
                "bank_bonus": None,
                "tax_bonus": "+1 coin per month (not per area, just +1 total)",
                "train_bonus": None,
            },
            14: {
                "name": "The Merchant's Square",
                "element": "Merchant",
                "wizard": "The Greedy Wizard",
                "market_bonus": "All goods marked down",
                "bank_bonus": "+5% interest",
                "tax_bonus": None,
                "train_bonus": None,
            },
            15: {
                "name": "The Hammock",
                "element": "Dream",
                "wizard": "The Mystagague of Dreams",
                "market_bonus": None,
                "bank_bonus": None,
                "tax_bonus": None,
                "train_bonus": None,
            },
        }

    # ─────────────────────────────────────────────────────────────
    # World state helpers
    # ─────────────────────────────────────────────────────────────

    def has_bank(self) -> bool:
        return self._building_at("bank") is not None

    def bank_tile(self):
        return self._building_at("bank")   # (x, y) or None

    def has_tax_office(self) -> bool:
        return self._building_at("tax") is not None

    def tax_office_tile(self):
        return self._building_at("tax")

    def knight_moves(self, pos):
        x, y = pos
        moves = [
            (x + 2, y + 1), (x + 2, y - 1),
            (x - 2, y + 1), (x - 2, y - 1),
            (x + 1, y + 2), (x - 1, y + 2),
            (x + 1, y - 2), (x - 1, y - 2),
        ]
        return [(mx, my) for (mx, my) in moves if 0 <= mx < 4 and 0 <= my < 4]

    def record_win(self, x, y):
        """
        Called from the main game when the player wins a stage.

        We mark the tile as 'win' and clear any prior building choice.

        New behavior:
        - Immediately opens a territory-win screen asking the player
          what building to construct here.
        - If the player picks a building, we call _apply_building_choice
          so the tile's 'building' and 'state' are set right away.
        - If the player cancels (ESC / closes), building stays None,
          and the old overworld behavior (choose_building_for_tile)
          will still handle it later.
        """
        cell = self.world_data[(x, y)]
        cell["win"] = True
        cell["building"] = None

        # Optionally clear a prior 'lost' look so it doesn't stay gloomy
        # while we're picking the building:
        if cell.get("state") == "lost":
            cell["state"] = "new"

        # ── Territory building selection UI ──
        chosen_building = None
        try:
            from game_won import TerritoryWinScreen

            territory_name = self.stage_info.get(
                cell["stage_id"], {}
            ).get("name", cell["stage_id"])

            print(f"[INFO] Territory {territory_name} won; opening build selection UI.")
            win_screen = TerritoryWinScreen(self, (x, y))
            chosen_building = win_screen.run()
        except ImportError:
            print("[INFO] game_won.py not found; territory building will be chosen later on the overworld.")
        except Exception as e:
            print(f"[WARN] TerritoryWinScreen failed: {e}")

        # If the player made a choice, apply it immediately.
        if chosen_building:
            self._apply_building_choice((x, y), chosen_building)
            print(f"[INFO] Player chose to build: {chosen_building!r} on tile {(x, y)}")



    def record_loss(self, x, y):
        """
        Called when the player loses a world.
        This sets the 'lost' state, which uses <id>lost.png.
        """
        self.world_data[(x, y)]["lose"] += 1
        self.world_data[(x, y)]["state"] = "lost"

    def record_visit(self, x, y):
        self.world_data[(x, y)]["visits"] += 1

    def save(self, filename="world_state.json"):
        with open(filename, "w") as f:
            json.dump(self.world_data, f, indent=2)
        print("World state saved.")

    def load(self, filename="world_state.json"):
        if os.path.exists(filename):
            with open(filename, "r") as f:
                self.world_data = json.load(f)
            # Backwards compatibility: older saves won't have "building"
            for pos, cell in self.world_data.items():
                if "building" not in cell:
                    cell["building"] = None
            print("World state loaded.")
        else:
            print("No saved world state found. Starting fresh.")

    def is_liberated(self, pos):
        return self.world_data.get(pos, {}).get("win", False)

    def set_liberated(self, pos, win_state="wonmarket"):
        if pos in self.world_data:
            self.record_win(pos[0], pos[1], win_state)

    def beaten_count(self) -> int:
        return sum(1 for cell in self.world_data.values() if cell.get("win"))

    # Building helpers -------------------------------------------------

    def _building_at(self, building_type: str):
        """Return (x, y) if a tile already has this building, else None."""
        for (x, y), cell in self.world_data.items():
            if cell.get("building") == building_type:
                return (x, y)
        return None

    def _apply_building_choice(self, pos, building_type: str):
        """Set building and map to tile state for visuals."""
        x, y = pos
        cell = self.world_data[(x, y)]
        cell["building"] = building_type

        if building_type == "market":
            cell["state"] = "wonmarket"
        elif building_type == "bank":
            cell["state"] = "wonbank"
        elif building_type == "tax":
            cell["state"] = "wontax"
        elif building_type == "train":
            cell["state"] = "wontrain"

    # Calendar ---------------------------------------------------------

    def _advance_month(self):
        """Advance game time by one month each time we move to a new land."""
        self.current_month_index += 1
        if self.current_month_index >= 12:
            self.current_month_index = 0
            self.current_year += 1

        # Monthly army upkeep (or training center behavior)
        try:
            from army_upkeep import apply_monthly_upkeep
        except ImportError:
            apply_monthly_upkeep = None

        if apply_monthly_upkeep is not None:
            try:
                # Signature: apply_monthly_upkeep(world, game)
                apply_monthly_upkeep(self, self.g)
            except Exception as e:
                print(f"[WARN] apply_monthly_upkeep failed: {e}")
        else:
            print("[INFO] army_upkeep.py not found; skipping monthly upkeep.")

        # Monthly economy (bank interest + taxes)
        self._update_bank_interest()
        self._update_tax_income()

    def _update_bank_interest(self):
        """Apply monthly interest to the bank balance, if a bank exists."""
        if not self.has_bank():
            return

        if self.bank_balance <= 0:
            return

        # Find which stage the bank is on
        bank_pos = self.bank_tile()
        if not bank_pos:
            return

        bank_cell = self.world_data.get(bank_pos, {})
        stage_id = bank_cell.get("stage_id", 0)

        # Base 5%; 10% if the bank is on stage 14
        rate = 0.10 if stage_id == 14 else self.bank_interest_rate

        raw_interest = self.bank_balance * rate
        interest = int(raw_interest)

        # If there is positive fractional interest, guarantee at least 1 gold
        if interest <= 0 and raw_interest > 0:
            interest = 1

        self.bank_balance += interest
        print(
            f"[ECON] Bank interest: +{interest} gold at rate {rate*100:.1f}% "
            f"(new balance: {self.bank_balance})"
        )

    def _update_tax_income(self):
        """
        Collect monthly taxes from tiles adjacent (8-way) to the tax office.

        - +1 gold per adjacent tile that is 'won' (player-controlled).
        - No tax from the tax office's own tile.
        - If the tax office is on stage 13, add +1 extra gold total.
        """
        # Reset "this month" income
        self.tax_office_income_per_month = 0

        if not self.has_tax_office():
            return

        tx, ty = self.tax_office_tile()
        tax_cell = self.world_data.get((tx, ty), {})
        stage_id = tax_cell.get("stage_id", 0)

        base_per_tile = 1
        income = 0

        for dy in (-1, 0, 1):
            for dx in (-1, 0, 1):
                if dx == 0 and dy == 0:
                    continue  # skip the tax office tile itself

                nx, ny = tx + dx, ty + dy
                if 0 <= nx < 4 and 0 <= ny < 4:
                    cell = self.world_data.get((nx, ny))
                    # Only count liberated (won) territories
                    if cell and cell.get("win"):
                        income += base_per_tile

        # Stage 13 bonus: +1 total, not per tile
        if stage_id == 13:
            income += 1

        # If you keep tax_office_bonus for future scaling, apply it here
        if self.tax_office_bonus:
            income = int(round(income * (1.0 + self.tax_office_bonus)))

        self.tax_office_income_per_month = income
        self.tax_office_balance += income

        print(
            f"[ECON] Tax office collected {income} gold this month "
            f"(balance now {self.tax_office_balance})."
        )

    # ─────────────────────────────────────────────────────────────
    # Overworld loop
    # ─────────────────────────────────────────────────────────────

    def overworld_move(self, fps=60):
        """
        Overworld / map loop.

        - Player clicks a reachable tile (knight move).
        - Month/year advance each time we move.
        - If tile is *not* yet won, we exit so the main game can start a battle.
        - If tile *is* won:
            * If no building chosen yet, we show the building popup.
            * If it has a Market/Bank/Tax/Training, we open the appropriate UI.
        """
        game = self.g
        screen = game.screen

        pygame.init()
        pygame.mixer.init()
        clock = pygame.time.Clock()

        running = True
        while running:
            dt = clock.tick(fps) / 1000.0

            # Update internal particle system (via renderer)
            self.renderer.update(dt)

            # Layout + traversable squares
            self.renderer.compute_margins(screen)
            traversable_squares = self.knight_moves(self.player_pos)

            # Hover detection: ask renderer which tile is under the mouse
            mouse_x, mouse_y = pygame.mouse.get_pos()
            hovered_pos = self.renderer.pick_tile_at(mouse_x, mouse_y)

            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    running = False

                elif event.type == pygame.KEYDOWN:
                    # Q / A -> adjust vertical spacing (Y)
                    # S / D -> adjust horizontal spacing (X)
                    # Z / X -> adjust per-column drop
                    # E / R -> adjust per-row diagonal stagger
                    if event.key == pygame.K_q:
                        self.CELL_SPACING_Y += 1
                    elif event.key == pygame.K_a:
                        self.CELL_SPACING_Y -= 1
                    elif event.key == pygame.K_s:
                        self.CELL_SPACING_X += 1
                    elif event.key == pygame.K_d:
                        self.CELL_SPACING_X -= 1
                    elif event.key == pygame.K_z:
                        self.COLUMN_DROP += 1
                    elif event.key == pygame.K_x:
                        self.COLUMN_DROP -= 1
                    elif event.key == pygame.K_e:
                        self.ROW_STAGGER += 1
                    elif event.key == pygame.K_r:
                        self.ROW_STAGGER -= 1

                    # Clamp so it doesn't go nuts or negative
                    self.CELL_SPACING_X = max(40, self.CELL_SPACING_X)
                    self.CELL_SPACING_Y = max(40, self.CELL_SPACING_Y)
                    self.COLUMN_DROP = max(-200, min(200, self.COLUMN_DROP))
                    self.ROW_STAGGER = max(0, min(200, self.ROW_STAGGER))

                elif event.type == pygame.MOUSEBUTTONDOWN:
                    if event.button == 1:
                        mouse_x, mouse_y = pygame.mouse.get_pos()

                        # Which tile is visually under the mouse?
                        picked = self.renderer.pick_tile_at(mouse_x, mouse_y)

                        # Only act if that tile is actually reachable this turn
                        if picked is not None and picked in traversable_squares:
                            x, y = picked
                            # Move knight to the new land
                            self.player_pos = (x, y)
                            self.record_visit(x, y)
                            self._advance_month()
                            print(f"[INFO] Moved to: {self.player_pos}")

                            cell = self.world_data[(x, y)]

                            if cell["win"]:
                                # Liberated land - building logic
                                if cell.get("building") is None:
                                    # Choose which building this land will host
                                    self.renderer.choose_building_for_tile(screen, (x, y))
                                    cell = self.world_data[(x, y)]  # refresh

                                building = cell.get("building")
                                print(f"[INFO] Visited liberated land with building: {building!r}")

                                if building == "market":
                                    self.open_market(game)
                                elif building == "bank":
                                    self.open_bank(game)
                                elif building == "tax":
                                    self.open_tax_office(game)
                                elif building == "train":
                                    self.open_training_center(game)
                                else:
                                    print("[WARN] Land has no recognized building; staying on overworld.")
                                # Stay in overworld after visiting won land.

                            else:
                                print("[INFO] New battle starts!")
                                running = False



            self.renderer.draw_world(screen, traversable_squares, hovered_pos)
            pygame.display.flip()

        print("Exited overworld loop.")
        return self.player_pos

    # ─────────────────────────────────────────────────────────────
    # Economic / building UIs
    # ─────────────────────────────────────────────────────────────

    def open_market(self, game):
        """
        Entry point for the Market UI.

        Tries to use market.py's MarketScreen if available; otherwise
        falls back to a simple placeholder window.
        """
        stage_id = self.world_data[self.player_pos]["stage_id"]

        try:
            from market import MarketScreen  # adjust import as needed

            print(f"[INFO] Opening real Market for stage {stage_id}.")
            market_screen = MarketScreen(game, stage_id)
            market_screen.run()  # or whatever entry method you use
            return
        except Exception as e:
            print(f"[WARN] Could not open real MarketScreen: {e}")
            print("[INFO] Falling back to placeholder Market window.")

        # --- Fallback placeholder ---
        screen = game.screen
        font = pygame.font.SysFont(None, 48)
        text = font.render("Market (placeholder)", True, (255, 255, 255))
        text_rect = text.get_rect(
            center=(screen.get_width() // 2, screen.get_height() // 2)
        )

        running = True
        clock = pygame.time.Clock()
        while running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT or event.type == pygame.KEYDOWN or event.type == pygame.MOUSEBUTTONDOWN:
                    running = False

            screen.fill((30, 30, 40))
            screen.blit(text, text_rect)
            pygame.display.flip()
            clock.tick(60)

        print("[INFO] Closed placeholder Market window.")

    def open_bank(self, game):
        from bank import BankScreen
        bank_screen = BankScreen(game, self)
        bank_screen.run()

    def open_tax_office(self, game):
        from tax_office import TaxOfficeScreen
        tax_screen = TaxOfficeScreen(game, self)
        tax_screen.run()

    def open_training_center(self, game):
        from training import TrainingCenterScreen
        training_screen = TrainingCenterScreen(game, self)
        training_screen.run()

    # Final Boss Fight
    def all_wizards_defeated(self) -> bool:
        """
        Return True if all non-starting tiles (stage_id != 0) have been won.
        This is your trigger condition for the Final Boss sequence.
        """
        for cell in self.world_data.values():
            if cell["stage_id"] != 0 and not cell.get("win", False):
                return False
        return True

    def get_stage_id(self):
        return self.world_data[self.player_pos]["stage_id"]
# ─────────────────────────────────────────────────────────────
# Standalone test harness
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    pygame.init()
    screen = pygame.display.set_mode((1280, 800))
    pygame.display.set_caption("Chess Quest - Overworld Layout Tuner")

    class _DummyGame:
        def __init__(self, screen):
            self.screen = screen
            # minimal fields if you want to test economic UIs here later
            self.player_gold = 0

    dummy_game = _DummyGame(screen)
    world = GameWorld(dummy_game)
    world.overworld_move()

    pygame.quit()
