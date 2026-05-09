# training.py

import os
import pygame
import chess

import config

# Canonical "full" player army: only the white side at the bottom
# (top 6 ranks empty, then pawns on rank 2, pieces on rank 1).
DEFAULT_PLAYER_ARMY_FEN = "8/8/8/8/8/8/PPPPPPPP/RNBQKBNR"


def _scale_army_piece(surface: pygame.Surface) -> pygame.Surface:
    src_w, src_h = surface.get_width(), surface.get_height()
    target_w = int(round(config.SQUARE_SIZE * float(config.PIECE_BASE_FRACTION)))
    scale = target_w / float(src_w)
    new_w = max(1, int(round(src_w * scale)))
    new_h = max(1, int(round(src_h * scale)))

    scaled = pygame.transform.smoothscale(surface, (new_w, new_h))
    canvas = pygame.Surface((config.SQUARE_SIZE, new_h), pygame.SRCALPHA)
    canvas.blit(scaled, ((config.SQUARE_SIZE - new_w) // 2, 0))
    return canvas


def _army_piece_images(game) -> dict:
    """
    Training/upkeep boards are white-only army views, independent of the
    current encounter side. Keep their sprites separate from g.PIECE_IMAGES.
    """
    player_set = str(getattr(game, "player_set", 0))
    cache_key = (player_set, config.SQUARE_SIZE, config.PIECE_BASE_FRACTION)
    cached_key = getattr(game, "_army_piece_images_key", None)
    cached_images = getattr(game, "_army_piece_images", None)
    if cached_key == cache_key and cached_images:
        return cached_images

    images = {}
    for piece in ("R", "N", "B", "Q", "K", "P"):
        path = os.path.join(config.ASSET_PIECES_DIR, f"p_{player_set}_w_{piece}.png")
        if not os.path.exists(path):
            print(f"[TRAINING] Missing army piece sprite: {path}")
            continue
        images[piece] = _scale_army_piece(pygame.image.load(path).convert_alpha())

    game._army_piece_images_key = cache_key
    game._army_piece_images = images
    return images


# ─────────────────────────────────────────────────────────────
# Shared board + piece rendering helper
#   - Used by both ArmyUpkeepScreen and TrainingCenterScreen
# ─────────────────────────────────────────────────────────────
def draw_army_board(
    screen,
    board: chess.Board,
    game,
    board_origin_x: int,
    board_origin_y: int,
    kept: dict | None = None,
    translucent_unkept_alpha: int = 80,
):
    """
    Draw an 8x8 semi-transparent board plus white-side army pieces.

    - Uses dedicated white player army sprites, not encounter PIECE_IMAGES.
    - If `kept` is provided:
        * king and kept[sq] pieces are full alpha.
        * others are translucent.
    - If `kept` is None:
        * all pieces are full alpha.
    """
    square_size = config.SQUARE_SIZE
    board_w = 8 * square_size
    board_h = 8 * square_size

    # Semi-transparent board squares
    board_surf = pygame.Surface((board_w, board_h), pygame.SRCALPHA)
    for rank in range(8):
        for file in range(8):
            lx = file * square_size
            ly = (7 - rank) * square_size
            if (file + rank) % 2 == 0:
                color = (230, 230, 230, 190)
            else:
                color = (70, 70, 70, 190)
            pygame.draw.rect(board_surf, color, (lx, ly, square_size, square_size))

    screen.blit(board_surf, (board_origin_x, board_origin_y))

    # Pieces
    piece_images = _army_piece_images(game)
    fallback_piece_images = getattr(game, "PIECE_IMAGES", {}) or {}

    for sq, piece in board.piece_map().items():
        if piece.color != chess.WHITE:
            continue  # army view is white-only

        file = chess.square_file(sq)
        rank = chess.square_rank(sq)
        x = board_origin_x + file * square_size
        y = board_origin_y + (7 - rank) * square_size - 45

        key = piece.symbol().upper()
        surf = piece_images.get(key) or fallback_piece_images.get(key)
        if surf is None:
            # Fallback: simple circle if asset missing
            radius = square_size // 3
            center = (
                x + square_size // 2,
                y + square_size // 2,
            )
            pygame.draw.circle(screen, (220, 220, 220), center, radius)
            continue

        # Decide alpha
        if kept is None:
            alpha = 255
        else:
            if piece.piece_type == chess.KING or kept.get(sq, False):
                alpha = 255
            else:
                alpha = translucent_unkept_alpha

        img = surf.copy()
        img.set_alpha(alpha)
        rect = img.get_rect(
            center=(
                x + square_size // 2,
                y + square_size // 2,
            )
        )
        screen.blit(img, rect)


# ─────────────────────────────────────────────────────────────
# Training board helpers
# ─────────────────────────────────────────────────────────────

def _board_from_player_fen_bottom_only(fen_str: str) -> chess.Board:
    """
    Normalize g.player_army_fen to a board with only the bottom side
    populated (ranks 1 and 2). Anything above is empty:

        8/8/8/8/8/8/<rank2>/<rank1>

    All pieces are treated as white; this is army layout only.
    """
    if " " in fen_str:
        fen_str = fen_str.split(" ")[0]

    parts = fen_str.split("/")
    if len(parts) == 2:
        rank2, rank1 = parts
    elif len(parts) == 8:
        rank2 = parts[-2]
        rank1 = parts[-1]
    else:
        print(f"[TRAINING] Invalid player_army_fen; using default. ({fen_str})")
        parts = DEFAULT_PLAYER_ARMY_FEN.split("/")
        rank2, rank1 = parts[-2], parts[-1]

    layout_parts = ["8", "8", "8", "8", "8", "8", rank2, rank1]
    normalized_fen = "/".join(layout_parts)

    board = chess.Board(None)
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
            ptype = {
                "k": chess.KING,
                "q": chess.QUEEN,
                "r": chess.ROOK,
                "b": chess.BISHOP,
                "n": chess.KNIGHT,
                "p": chess.PAWN,
            }.get(ch.lower())
            if ptype is None:
                file += 1
                continue
            board.set_piece_at(sq, chess.Piece(ptype, chess.WHITE))
            file += 1

    return board


def build_full_army_board_with_training(stage_id: int) -> chess.Board:
    """
    Build a fresh full army (white at bottom only), then apply stage-specific
    training upgrades (same behavior you had at the bottom of army_upkeep):

      - Stage 0: pawns in front of rooks (a2, h2) become rooks
      - Stage 3: pawns in front of bishops (c2, f2) become bishops
      - Stage 9: pawns in front of knights (b2, g2) become knights
    """
    board = _board_from_player_fen_bottom_only(DEFAULT_PLAYER_ARMY_FEN)

    def promote_if_pawn(square_name: str, new_type: chess.PieceType):
        sq = chess.parse_square(square_name)
        piece = board.piece_at(sq)
        if piece and piece.color == chess.WHITE and piece.piece_type == chess.PAWN:
            board.set_piece_at(sq, chess.Piece(new_type, chess.WHITE))

    if stage_id == 0:
        for name in ("a2", "h2"):
            promote_if_pawn(name, chess.ROOK)
    elif stage_id == 3:
        for name in ("c2", "f2"):
            promote_if_pawn(name, chess.BISHOP)
    elif stage_id == 9:
        for name in ("b2", "g2"):
            promote_if_pawn(name, chess.KNIGHT)

    return board


def build_trained_board_from_player_fen(player_fen: str, stage_id: int) -> chess.Board:
    """
    Training-center logic:

    - Start from the player's current army FEN (bottom-only view).
    - Build a "full" army with training bonuses for this stage.
    - For each square:
        * If full-board has a piece and current-board is empty → add that piece.
        * Existing pieces are kept as-is.
    """
    current_board = _board_from_player_fen_bottom_only(player_fen)
    full_board = build_full_army_board_with_training(stage_id)

    for sq in chess.SQUARES:
        desired = full_board.piece_at(sq)
        current = current_board.piece_at(sq)
        if desired is None:
            continue
        if current is None:
            current_board.set_piece_at(sq, desired)
        elif (
            current.color == chess.WHITE
            and current.piece_type == chess.PAWN
            and desired.piece_type != chess.PAWN
        ):
            current_board.set_piece_at(sq, desired)

    return current_board


# ─────────────────────────────────────────────────────────────
# Training Center Screen
# ─────────────────────────────────────────────────────────────

def _player_army_fen_from_board(board: chess.Board) -> str:
    full_fen = board.board_fen()
    parts = full_fen.split("/")
    if len(parts) == 8:
        return f"{parts[-2]}/{parts[-1]}"

    print(f"[TRAINING] Unexpected trained board FEN: {full_fen}")
    return "PPPPPPPP/RNBQKBNR"


class TrainingCenterScreen:
    """
    Training Center UI.

    - Uses the same board rendering as ArmyUpkeep (via draw_army_board).
    - Sites with training centers do NOT pay upkeep this month.
    - Training center restores missing units for free, applying
      stage-specific training bonuses (0, 3, 9).
    """

    def __init__(self, game, world, training_pos=None):
        self.g = game
        self.world = world
        self.training_pos = training_pos if training_pos is not None else world.player_pos
        self.screen = self.g.screen
        self.clock = pygame.time.Clock()
        self.running = False

        self.font = pygame.font.SysFont(None, 30)

        # Background image (train.png)
        bg_path = os.path.join("assets", "GFX", "UI", "train.png")
        if os.path.exists(bg_path):
            bg = pygame.image.load(bg_path).convert_alpha()
            self.bg_image = pygame.transform.smoothscale(
                bg, (config.WIDTH, config.HEIGHT)
            )
        else:
            self.bg_image = None
            print(f"[TRAINING] Background not found: {bg_path}")

        # Board geometry (same centering logic as ArmyUpkeep)
        board_w = 8 * config.SQUARE_SIZE
        board_h = 8 * config.SQUARE_SIZE
        self.board_origin_x = (config.WIDTH - board_w) // 2
        self.board_origin_y = (config.HEIGHT - board_h) // 2

        # Determine stage_id at the training center being used. Monthly upkeep
        # applies when leaving a tile, before world.player_pos changes.
        cell = world.world_data.get(self.training_pos, {})
        self.stage_id = cell.get("stage_id", 0)

        # Starting army FEN
        self.original_fen = getattr(game, "player_army_fen", DEFAULT_PLAYER_ARMY_FEN)

        # Build the trained board
        self.board = build_trained_board_from_player_fen(self.original_fen, self.stage_id)

        # Done button at bottom-center
        btn_w, btn_h = 200, 56
        self.done_rect = pygame.Rect(
            (config.WIDTH - btn_w) // 2,
            config.HEIGHT - btn_h - 40,
            btn_w,
            btn_h,
        )

        self.message = (
            "Your troops have been retrained to full strength for this land.\n"
            "No upkeep is charged this month."
        )

    # ----------------------- helpers --------------------------

    def _draw_text_outline(self, text, x, y, fg=(255, 255, 255), outline=(0, 0, 0)):
        base = self.font.render(text, True, fg)
        border = self.font.render(text, True, outline)
        for ox, oy in [
            (-1, -1), (1, -1),
            (-1, 1),  (1, 1),
            (0, -1),  (0, 1),
            (-1, 0),  (1, 0),
        ]:
            self.screen.blit(border, (x + ox, y + oy))
        self.screen.blit(base, (x, y))

    def _draw_player_gold(self):
        x, y = 60, 20
        coin_size = 48
        font = pygame.font.SysFont(None, 48)

        if getattr(self.g, "gold_coins", None):
            coin_img = self.g.gold_coins[0]
        else:
            coin_img = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(coin_img, (212, 175, 55), (20, 20), 18)
            pygame.draw.circle(coin_img, (120, 90, 20), (20, 20), 18, 3)

        coin_img = pygame.transform.smoothscale(coin_img, (coin_size, coin_size))
        text = f"= {int(getattr(self.g, 'player_gold', 0))}"
        text_surface = font.render(text, True, (255, 255, 255))
        shadow_surface = font.render(text, True, (0, 0, 0))
        text_y = y + (coin_size // 2 - text_surface.get_height() // 2)

        self.screen.blit(shadow_surface, (x + coin_size + 12, text_y + 2))
        self.screen.blit(coin_img, (x, y))
        self.screen.blit(text_surface, (x + coin_size + 10, text_y))

    def _draw_done_button(self):
        pygame.draw.rect(self.screen, (40, 120, 160), self.done_rect, border_radius=10)
        pygame.draw.rect(self.screen, (10, 30, 50), self.done_rect, 2, border_radius=10)
        label = self.font.render("Done", True, (255, 255, 255))
        self.screen.blit(label, label.get_rect(center=self.done_rect.center))

    def _draw_message_block(self):
        if not self.message:
            return
        lines = self.message.split("\n")
        x = 60
        y = 80
        for line in lines:
            self._draw_text_outline(line, x, y)
            y += 32

    def _draw(self):
        # Background
        if self.bg_image is not None:
            self.screen.blit(self.bg_image, (0, 0))
        else:
            self.screen.fill((15, 25, 30))

        # Board + pieces (same helper as upkeep, no 'kept' map → all opaque)
        draw_army_board(
            self.screen,
            self.board,
            self.g,
            self.board_origin_x,
            self.board_origin_y,
            kept=None,
        )

        self._draw_player_gold()
        self._draw_message_block()
        self._draw_done_button()

    # ---------------------- main loop -------------------------

    def run(self):
        self.running = True
        while self.running:
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    self.running = False
                elif event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_ESCAPE or event.key == pygame.K_RETURN:
                        self._apply_and_exit()
                elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    if self.done_rect.collidepoint(event.pos):
                        self._apply_and_exit()

            self._draw()
            pygame.display.flip()
            self.clock.tick(60)

    def _apply_and_exit(self):
        # Commit the trained army back to the game FEN
        new_fen = _player_army_fen_from_board(self.board)
        self.g.player_army_fen = new_fen
        print(f"[TRAINING] Training complete. New army FEN: {new_fen}")
        self.running = False
