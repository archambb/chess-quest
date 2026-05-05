# army_upkeep.py

import os
import random

import pygame
import chess

import config
from training import draw_army_board  # shared board rendering helper

# Canonical "full" player army: only the white side at the bottom
DEFAULT_PLAYER_ARMY_FEN = "PPPPPPPP/RNBQKBNR"


class ArmyUpkeepScreen:
    """
    Monthly "pay your army" UI.

    - Shows player's army as if it were white at the bottom.
    - King is always kept (opaque).
    - Other pieces start transparent; clicking them "buys" them
      (opaque) for gold_per_unit. Clicking again refunds.
    - On Done:
        * If only king is kept and player could afford at least one
          more piece, show a confirmation dialog.
        * Otherwise, commit the new army FEN into g.player_army_fen.
    """

    def __init__(self, game, world):
        self.g = game
        self.world = world
        self.screen = self.g.screen
        self.clock = pygame.time.Clock()
        self.running = False

        # Fonts
        self.font = pygame.font.SysFont(None, 28)

        # Background image
        bg_path = os.path.join("assets", "GFX", "UI", "army_upkeep.png")
        if os.path.exists(bg_path):
            bg = pygame.image.load(bg_path).convert_alpha()
            self.bg_image = pygame.transform.smoothscale(
                bg, (config.WIDTH, config.HEIGHT)
            )
        else:
            self.bg_image = None
            print(f"[ARMY] Background not found: {bg_path}")

        # Board geometry: center the 8x8 board
        board_w = 8 * config.SQUARE_SIZE
        board_h = 8 * config.SQUARE_SIZE
        self.board_origin_x = (config.WIDTH - board_w) // 2
        self.board_origin_y = (config.HEIGHT - board_h) // 2

        # Gold icon (random from g.gold_coins if present)
        if getattr(self.g, "gold_coins", None):
            self.gold_icon = random.choice(self.g.gold_coins)
        else:
            self.gold_icon = None

        # Cost per non-king unit
        self.gold_per_unit = getattr(
            self.g,
            "gold_per_unit",
            getattr(self.world, "army_cost_per_unit", 1),
        )

        # Internal board: white-only representation of the army
        self.board = chess.Board(None)
        self.kept = {}  # square -> bool (True if purchased/kept)
        self.message = ""

        # Confirm dialog state
        self.confirm_no_purchases = False
        self.confirm_choice = None  # "yes" or "no"
        self._yes_rect = None
        self._no_rect = None

        # Done button in bottom-right
        btn_w, btn_h = 160, 50
        self.done_rect = pygame.Rect(
            config.WIDTH - btn_w - 40,
            config.HEIGHT - btn_h - 30,
            btn_w,
            btn_h,
        )

        # Build internal board from the current player_army_fen
        fen = getattr(self.g, "player_army_fen", DEFAULT_PLAYER_ARMY_FEN)
        self._setup_board_from_fen(fen)

    # ------------------------------------------------------------------
    # Board construction
    # ------------------------------------------------------------------

    def _setup_board_from_fen(self, fen_str: str):
        """
        Build self.board from the player's FEN, but only treat the *bottom*
        side as the player's army.

        Accepted formats (from White's point of view):

        - New format (preferred):
            "PPPPPPPP/RNBQKBNR"      (rank 2 / rank 1)

        - Legacy format:
            "8/8/8/8/8/8/PPPPPPPP/RNBQKBNR"
              (we only care about the bottom two ranks)

        Internally we normalize to:

            8/8/8/8/8/8/<rank2>/<rank1>

        and treat all pieces as white (shape only).
        """
        if " " in fen_str:
            fen_str = fen_str.split(" ")[0]

        parts = fen_str.split("/")

        if len(parts) == 2:
            # New format: "rank2/rank1"
            rank2, rank1 = parts

        elif len(parts) == 8:
            # Legacy full-board format: use bottom two ranks
            rank2 = parts[-2]
            rank1 = parts[-1]

        else:
            print(f"[ARMY] Invalid player_army_fen; using default. ({fen_str})")
            parts = DEFAULT_PLAYER_ARMY_FEN.split("/")
            rank2, rank1 = parts[-2], parts[-1]

        layout_parts = ["8", "8", "8", "8", "8", "8", rank2, rank1]
        normalized_fen = "/".join(layout_parts)

        self.board.clear()
        rank = 7
        file = 0

        for ch in normalized_fen:
            if ch == "/":
                rank -= 1
                file = 0
            elif ch.isdigit():
                file += int(ch)
            else:
                if file > 7 or rank < 0:
                    continue
                sq = chess.square(file, rank)
                piece_type = {
                    "k": chess.KING,
                    "q": chess.QUEEN,
                    "r": chess.ROOK,
                    "b": chess.BISHOP,
                    "n": chess.KNIGHT,
                    "p": chess.PAWN,
                }.get(ch.lower())
                if piece_type is None:
                    file += 1
                    continue
                self.board.set_piece_at(sq, chess.Piece(piece_type, chess.WHITE))
                file += 1

        # Initialize kept flags (all False to start; king is always implicitly kept)
        self.kept = {
            sq: False
            for sq, p in self.board.piece_map().items()
            if p.color == chess.WHITE
        }


    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------

    def _square_from_mouse(self, mx, my):
        file = (mx - self.board_origin_x) // config.SQUARE_SIZE
        rank = 7 - (my - self.board_origin_y) // config.SQUARE_SIZE
        if 0 <= file < 8 and 0 <= rank < 8:
            return chess.square(file, rank)
        return None

    # ------------------------------------------------------------------
    # Interaction
    # ------------------------------------------------------------------

    def _handle_board_click(self, mx, my):
        sq = self._square_from_mouse(mx, my)
        if sq is None:
            return

        piece = self.board.piece_at(sq)
        if not piece or piece.color != chess.WHITE:
            return

        # King is mandatory - can't buy or refund it
        if piece.piece_type == chess.KING:
            return

        already_kept = self.kept.get(sq, False)

        if already_kept:
            # Refund: un-keep this piece and give gold back
            self.g.player_gold += self.gold_per_unit
            self.kept[sq] = False
            self.message = ""
            print(
                f"[ARMY] Refunded {piece.symbol()} at {chess.square_name(sq)}; "
                f"gold now {self.g.player_gold}"
            )
            return

        # Not yet kept → attempt to buy
        if self.g.player_gold < self.gold_per_unit:
            self.message = "You can't afford this soldier."
            return

        self.g.player_gold -= self.gold_per_unit
        self.kept[sq] = True
        self.message = ""

        print(
            f"[ARMY] Kept {piece.symbol()} at {chess.square_name(sq)}; "
            f"gold now {self.g.player_gold}"
        )

    def _compute_resulting_fen(self) -> str:
        """
        Build a new board containing:
        - the king (always kept)
        - any non-king piece with kept[sq] == True

        Return the *player army* FEN in the normalized 2-rank form:

            "PPPPPPPP/RNBQKBNR"

        (rank 2 / rank 1 from White's perspective).
        """
        new_board = chess.Board(None)

        for sq, piece in self.board.piece_map().items():
            if piece.color != chess.WHITE:
                continue
            if piece.piece_type == chess.KING or self.kept.get(sq, False):
                new_board.set_piece_at(sq, piece)

        full_fen = new_board.board_fen()
        parts = full_fen.split("/")

        if len(parts) == 8:
            rank2 = parts[-2]
            rank1 = parts[-1]
            return f"{rank2}/{rank1}"

        # Fallback - shouldn't really happen, but be safe
        print(f"[ARMY] Unexpected board_fen while computing army FEN: {full_fen}")
        return DEFAULT_PLAYER_ARMY_FEN


    def _handle_done_click(self):
        # How many non-king pieces are kept?
        kept_count = sum(
            1
            for sq, p in self.board.piece_map().items()
            if p.color == chess.WHITE
            and p.piece_type != chess.KING
            and self.kept.get(sq, False)
        )

        # Could the player afford at least one piece (if they wanted to)?
        can_afford_any = self.g.player_gold >= self.gold_per_unit and any(
            p.piece_type != chess.KING
            for p in self.board.piece_map().values()
            if p.color == chess.WHITE
        )

        if kept_count == 0 and can_afford_any:
            # Need confirmation
            self.confirm_no_purchases = True
            self.confirm_choice = None
            self.message = ""
            return

        # Finalize immediately
        new_fen = self._compute_resulting_fen()
        self.g.player_army_fen = new_fen
        print(f"[ARMY] Upkeep complete. New army FEN: {new_fen}")
        self.running = False

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------

    def _draw_gold(self):
        x = 60
        y = 20
        coin_size = 48

        if self.gold_icon is not None:
            icon = pygame.transform.smoothscale(self.gold_icon, (coin_size, coin_size))
            icon_rect = icon.get_rect(topleft=(x, y))
            self.screen.blit(icon, icon_rect)
            text_x = icon_rect.right + 8
        else:
            text_x = x

        font = pygame.font.SysFont(None, 48)
        txt = f"= {int(getattr(self.g, 'player_gold', 0))}"
        surf = font.render(txt, True, (255, 255, 255))
        shadow = font.render(txt, True, (0, 0, 0))
        text_y = y + (coin_size // 2 - surf.get_height() // 2)
        self.screen.blit(shadow, (text_x + 2, text_y + 2))
        self.screen.blit(surf, (text_x, text_y))

    def _draw_done_button(self):
        pygame.draw.rect(self.screen, (40, 120, 40), self.done_rect, border_radius=8)
        pygame.draw.rect(self.screen, (10, 40, 10), self.done_rect, 2, border_radius=8)
        label = self.font.render("Done", True, (255, 255, 255))
        lr = label.get_rect(center=self.done_rect.center)
        self.screen.blit(label, lr)

    def _draw_confirm_popup(self):
        # Dimmed overlay
        overlay = pygame.Surface(self.screen.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        self.screen.blit(overlay, (0, 0))

        # Centered panel
        panel_w, panel_h = 520, 180
        panel_rect = pygame.Rect(
            (config.WIDTH - panel_w) // 2,
            (config.HEIGHT - panel_h) // 2,
            panel_w,
            panel_h,
        )

        pygame.draw.rect(self.screen, (40, 40, 60), panel_rect, border_radius=10)
        pygame.draw.rect(self.screen, (220, 220, 230), panel_rect, 2, border_radius=10)

        text = "No pieces purchased. Are you sure?"
        surf = self.font.render(text, True, (255, 255, 255))
        tr = surf.get_rect(center=(panel_rect.centerx, panel_rect.y + 50))
        self.screen.blit(surf, tr)

        # Yes / No buttons
        btn_w, btn_h = 120, 44
        spacing = 30

        yes_rect = pygame.Rect(
            panel_rect.centerx - btn_w - spacing // 2,
            panel_rect.bottom - btn_h - 30,
            btn_w,
            btn_h,
        )
        no_rect = pygame.Rect(
            panel_rect.centerx + spacing // 2,
            panel_rect.bottom - btn_h - 30,
            btn_w,
            btn_h,
        )

        pygame.draw.rect(self.screen, (60, 130, 60), yes_rect, border_radius=8)
        pygame.draw.rect(self.screen, (130, 60, 60), no_rect, border_radius=8)
        pygame.draw.rect(self.screen, (10, 40, 10), yes_rect, 2, border_radius=8)
        pygame.draw.rect(self.screen, (40, 10, 10), no_rect, 2, border_radius=8)

        yes_label = self.font.render("Yes", True, (255, 255, 255))
        no_label = self.font.render("No", True, (255, 255, 255))
        self.screen.blit(yes_label, yes_label.get_rect(center=yes_rect.center))
        self.screen.blit(no_label, no_label.get_rect(center=no_rect.center))

        # Save for click handling
        self._yes_rect = yes_rect
        self._no_rect = no_rect

    def _draw(self):
        # Background
        if self.bg_image is not None:
            self.screen.blit(self.bg_image, (0, 0))
        else:
            self.screen.fill((15, 20, 35))

        # Shared board + pieces (comes from training.draw_army_board)
        draw_army_board(
            self.screen,
            self.board,
            self.g,
            self.board_origin_x,
            self.board_origin_y,
            kept=self.kept,
        )

        # Gold & Done button
        self._draw_gold()
        self._draw_done_button()

        # Message
        if self.message:
            msg_surf = self.font.render(self.message, True, (255, 220, 60))
            self.screen.blit(msg_surf, (40, config.HEIGHT - 60))

        # Confirm popup (if needed)
        if self.confirm_no_purchases:
            self._draw_confirm_popup()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self):
        self.running = True
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False

                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    mx, my = event.pos

                    if self.confirm_no_purchases:
                        # Handle Yes/No in confirmation dialog
                        if self._yes_rect and self._yes_rect.collidepoint(mx, my):
                            # Confirm: commit "king only"
                            new_fen = self._compute_resulting_fen()
                            self.g.player_army_fen = new_fen
                            print(
                                f"[ARMY] Upkeep confirmed with king-only army. FEN: {new_fen}"
                            )
                            self.running = False
                        elif self._no_rect and self._no_rect.collidepoint(mx, my):
                            # Cancel confirmation; go back to selection
                            self.confirm_no_purchases = False
                            self.confirm_choice = None
                        # Ignore clicks elsewhere when dialog is up
                    else:
                        if self.done_rect.collidepoint(mx, my):
                            self._handle_done_click()
                        else:
                            self._handle_board_click(mx, my)

            self._draw()
            pygame.display.flip()
            self.clock.tick(60)


# ----------------------------------------------------------------------
# Public entry point for GameWorld._advance_month
# ----------------------------------------------------------------------

def apply_monthly_upkeep(world, game, upkeep_pos=None):
    """
    Called from GameWorld._advance_month(world, game).

    - If the current tile has a Training Center (building == "train"):
        * Skip the upkeep UI.
        * Open TrainingCenterScreen (training.py), which restores missing units
          for this land and applies training bonuses.
    - Otherwise:
        * Open the ArmyUpkeepScreen so the player can buy/keep pieces.
    """
    pos = upkeep_pos if upkeep_pos is not None else world.player_pos
    cell = world.world_data.get(pos)
    if not cell:
        print(f"[ARMY] No world cell for upkeep position {pos}; skipping upkeep.")
        return

    building = cell.get("building")
    stage_id = cell.get("stage_id", 0)
    building_upkeep_ready = cell.get("building_upkeep_ready", True)

    print(
        "[ARMY_FLOW] trigger=departure "
        f"site={pos} destination={getattr(world, '_pending_destination_pos', None)} "
        f"stage_id={stage_id} building={building!r} "
        f"building_upkeep_ready={building_upkeep_ready}"
    )

    if building == "train" and building_upkeep_ready:
        try:
            from training import TrainingCenterScreen
            print("[ARMY_FLOW] action=training_center_restore reason=departure_from_ready_training_center")
            t_screen = TrainingCenterScreen(game, world, training_pos=pos)
            t_screen.run()
        except Exception as e:
            print(f"[ARMY] TrainingCenterScreen failed ({e}); no upkeep charged.")
        return

    # Normal case → open upkeep UI
    if building == "train":
        print("[ARMY_FLOW] action=normal_upkeep reason=new_training_center_not_ready")
    else:
        print("[ARMY_FLOW] action=normal_upkeep reason=departure_from_non_training_site")

    screen = ArmyUpkeepScreen(game, world)
    screen.run()

# ----------------------------------------------------------------------
# Standalone test harness
# ----------------------------------------------------------------------
if __name__ == "__main__":
    pygame.init()
    try:
        pygame.mixer.init()
    except pygame.error:
        # Audio isn't required for this test
        pass

    # If you're running this outside the full game, give config some defaults.
    # (If your real config module already has these, this won't overwrite them.)
    if not hasattr(config, "WIDTH"):
        config.WIDTH = 1024
    if not hasattr(config, "HEIGHT"):
        config.HEIGHT = 768
    if not hasattr(config, "SQUARE_SIZE"):
        config.SQUARE_SIZE = 64

    screen = pygame.display.set_mode((config.WIDTH, config.HEIGHT))
    pygame.display.set_caption("Army Upkeep Test Harness")

    class DummyGame:
        def __init__(self):
            self.screen = screen

            # Starting player gold for testing
            self.player_gold = 30

            # Cost per non-king unit (ArmyUpkeepScreen will read this)
            self.gold_per_unit = 5

            # Optional list of coin images; keep empty for now
            self.gold_coins = []

            # Starting army: full default army
            self.player_army_fen = DEFAULT_PLAYER_ARMY_FEN

    class DummyWorld:
        def __init__(self):
            # Single world cell at (0, 0)
            self.player_pos = (0, 0)
            self.world_data = {
                self.player_pos: {
                    # Change to "train" to test the Training Center branch
                    "building": None,
                    "stage_id": 1,
                }
            }

            # Fallback army cost per unit if g.gold_per_unit isn't set
            self.army_cost_per_unit = 5

    game = DummyGame()
    world = DummyWorld()

    # Kick off the monthly upkeep flow
    apply_monthly_upkeep(world, game)

    # After you close the upkeep window, you'll see these prints
    print("[TEST] Final army FEN:", getattr(game, "player_army_fen", None))
    print("[TEST] Remaining gold:", getattr(game, "player_gold", None))

    pygame.quit()
