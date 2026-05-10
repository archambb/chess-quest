# board_manager.py
from __future__ import annotations

import random
import chess
import chess.engine

from promotion_ui import PROMOTION_OPTIONS, choose_promotion_piece_type


class BoardManager:
    """
    Board / round setup pipeline + board helpers extracted from main.py.

    Goals:
    - Do NOT rename any g.self.* variables
    - Keep the same logic and side-effects
    - Let main.py keep backwards-compatible method names via wrappers
    """

    def __init__(self, game):
        self.g = game

    # ─────────────────────────────────────────────────────────────
    # Board creation helpers
    # ─────────────────────────────────────────────────────────────
    def apply_player_army_to_board(self, color):
        g = self.g

        def player_army_fen_to_color(partial_fen: str, player_color: str) -> str:
            """
            Convert a partial FEN representing only white's pieces into a full board FEN
            based on the assigned player color ("white" or "black").

            partial_fen is assumed formatted as WHITE rows, top-to-bottom:
            Example: "PPPPPPPP/RNBQKBNR"  (rank 2 / rank 1 for white)
            """
            standard_white_back = "RNBQKBNR"
            standard_white_pawns = "PPPPPPPP"
            standard_black_back = "rnbqkbnr"
            standard_black_pawns = "pppppppp"

            pawns_row, back_row = partial_fen.split("/")
            player_color = player_color.lower()

            if player_color == "white":
                return (
                    f"{standard_black_back}/{standard_black_pawns}/"
                    f"8/8/8/8/"
                    f"{pawns_row}/{back_row}"
                )

            elif player_color == "black":
                player_top = f"{back_row.lower()}/{pawns_row.lower()}"
                enemy_bottom = f"{standard_white_pawns}/{standard_white_back}"
                return f"{player_top}/8/8/8/8/{enemy_bottom}"

            else:
                raise ValueError("player_color must be 'white' or 'black'")

        full_fen = player_army_fen_to_color(g.player_army_fen, color)
        g.board.set_fen(full_fen + " w - - 0 1")

    # ─────────────────────────────────────────────────────────────
    # New-board setup
    # ─────────────────────────────────────────────────────────────
    def setup_new_board(self):
        g = self.g
        g.current_game_mode = "combat"

        g.current_state_wins = 0
        g.current_state_losses = 0

        g.completed_turns = 0 # Reset turn counter

        g.player_side = "white"
        if g.world.world_data[(g.world.player_pos)]["stage_id"] == 13:
            g.player_side = "black"
        world = g.world.world_data[(g.world.player_pos)]["stage_id"]

        g.board = chess.Board(None)
        self.apply_player_army_to_board(g.player_side)

        g.move_history.clear()
        g.lost_pieces = []
        g.enemy_lost_pieces = []
        g.frozen_squares.clear()
        g.shielded_squares.clear()
        g.magnet_square = None
        g.selected_square = None
        g.selected_power = None
        g.selected_spell = None
        g.wall_of_flame_active = False
        g.ENEMY_RAGE_QUITS = False

        g.spellbook = list(g.spellbook_master)
        g.quests.active_quests = []

        g.ui_state.show_enemy_dialog("Good luck", 4)
        print("SHOWING ENEMY DIALOG******************************")

        g.background_image = g.assets.load_background_image(world)
        if hasattr(g, "_bg_scaled"):
            del g._bg_scaled
        g.portrait_img = g.assets.load_portrait_image(world)

        g.selected_square = None
        self._relock_powers()
        g.main_game_screen = False

        g.PIECE_IMAGES = g.assets.load_piece_images()

        g.quests.setup_quest_selection()

        g.main_game_screen = True

        g.board_manager.sprinkle_gold_pieces()

    # ─────────────────────────────────────────────────────────────
    # Board reset pipeline
    # ─────────────────────────────────────────────────────────────
    def reset_board(self, preserve_gold=False):
        g = self.g
        g.current_game_mode = "combat"

        if getattr(g, "engine", None):
            try:
                g.engine.quit()
            except Exception:
                pass
            finally:
                g.engine = None

        try:
            g.engine = chess.engine.SimpleEngine.popen_uci(g.engine_path)
        except Exception as exc:
            print(f"[FATAL] Cannot launch engine: {exc}")
            g.ENEMY_RAGE_QUITS = True
            g.engine = None

        g.board = chess.Board()
        g.move_history = []
        g.lost_pieces = []
        g.enemy_lost_pieces = []
        g.frozen_squares = {}
        g.shielded_squares = {}
        g.magnet_square = None
        g.selected_square = None
        g.selected_power = None
        g.selected_spell = None
        g.wall_of_flame_active = False
        g.spellbook = list(g.spellbook_master)
        g._spell_cache_dirty = True
        g.ENEMY_RAGE_QUITS = False
        g.boulder_squares.clear()

        g.completed_turns = 0 # Reset turn counter

        g.quests.apply_overworld_quest_cards_for_current_board()
        g.quests.setup_quest_status_tracking()

        g.player_side = "black" if g.player_side == "white" else "white"
        if g.world.world_data[(g.world.player_pos)]["stage_id"] == 13:
            g.player_side = "black"
        elif g.world.world_data[(g.world.player_pos)]["stage_id"] == 4:
            g.player_side = "white"

        self._relock_powers()
        self.apply_player_army_to_board(g.player_side)

        g.PIECE_IMAGES = g.assets.load_piece_images()
        if preserve_gold:
            print("[INFO] Preserving existing gold after stalemate reset.")
        else:
            g.board_manager.sprinkle_gold_pieces()

        print(f"Brand-new game! You are now {g.player_side}.")

        if g.quests.enable_no_future_rooks:
            enemy_color = chess.BLACK if g.player_side == "white" else chess.WHITE
            for square in chess.SQUARES:
                piece = g.board.piece_at(square)
                if piece and piece.piece_type == chess.ROOK and piece.color == enemy_color:
                    g.board.remove_piece_at(square)
            print("[QUEST] Enemy rooks removed due to quest reward.")

        if g.quests.set_outer_pawns_as_rooks:
            player_color = chess.WHITE if g.player_side == "white" else chess.BLACK
            start_rank = 1 if player_color == chess.WHITE else 6
            a_file_sq = chess.square(0, start_rank)
            h_file_sq = chess.square(7, start_rank)

            for sq in (a_file_sq, h_file_sq):
                if g.board.piece_at(sq) and g.board.piece_at(sq).piece_type == chess.PAWN:
                    g.board.set_piece_at(sq, chess.Piece(chess.ROOK, player_color))

            g.quests.set_outer_pawns_as_rooks = False
            print("[QUEST] Player outer pawns converted to rooks.")

        if g.quests.enable_knightmare_mode:
            player_color = chess.WHITE if g.player_side == "white" else chess.BLACK
            for square in chess.SQUARES:
                piece = g.board.piece_at(square)
                if piece and piece.color == player_color and piece.piece_type != chess.KING:
                    g.board.set_piece_at(square, chess.Piece(chess.KNIGHT, player_color))

            print("[QUEST] Knightmare mode activated: all player pieces (except king) are knights.")
            g.quests.enable_knightmare_mode = False

        if g.player_side == "black" and g.engine:
            try:
                result = g.engine.play(g.board, chess.engine.Limit(time=0.1))
                move = result.move
                if move:
                    piece = g.board.piece_at(move.from_square)
                    g.board.push(move)
                    g.quests.update_quest_variables(piece=piece, move=move, player=False)
                    self._clear_king_protections()
            except Exception as exc:
                print(f"[RAGE-QUIT] Engine failed immediately: {exc}")
                g.ENEMY_RAGE_QUITS = True

    # ─────────────────────────────────────────────────────────────
    # King remove freeze/shield
    # ─────────────────────────────────────────────────────────────
    def _clear_king_protections(self):
        g = self.g
        for color in (chess.WHITE, chess.BLACK):
            ksq = g.board.king(color)
            if ksq is None:
                continue
            g.frozen_squares.pop(ksq, None)
            g.shielded_squares.pop(ksq, None)

    def _escape_moves_from(self, src_sq):
        g = self.g
        esc = []
        for m in self._legal_moves_from(src_sq):
            g.board.push(m)
            still_in_check = g.board.is_check()
            g.board.pop()
            if not still_in_check:
                esc.append(m)
        return esc

    # ─────────────────────────────────────────────────────────────
    # Board helpers
    # ─────────────────────────────────────────────────────────────
    def mirror_move(self, move):
        from_sq = move.from_square
        to_sq = move.to_square
        from_file = chess.square_file(from_sq)
        from_rank = chess.square_rank(from_sq)
        to_file = chess.square_file(to_sq)
        to_rank = chess.square_rank(to_sq)
        mirrored_from = chess.square(from_file, 7 - from_rank)
        mirrored_to = chess.square(to_file, 7 - to_rank)
        return chess.Move(mirrored_from, mirrored_to)

    def _legal_moves_from(self, src_sq):
        g = self.g
        return [m for m in g.board.legal_moves if m.from_square == src_sq]

    def _pruned_moves_from(self, src_sq):
        g = self.g
        raw = self._legal_moves_from(src_sq)
        piece = g.board.piece_at(src_sq)
        if not piece:
            return []

        if g.board.is_check():
            escapes = self._escape_moves_from(src_sq)
            if not escapes:
                return []
            pruned = g.map_challenges.prune_moves(escapes, piece=piece, from_sq=src_sq)
            return pruned or escapes

        return g.map_challenges.prune_moves(raw, piece=piece, from_sq=src_sq)

    def _after_player_push(self, piece, move):
        g = self.g
        g.quests.update_quest_variables(piece, move, player=True)
        g.quests.swap_used_this_turn = False
        self._clear_king_protections()
        g.selected_square = None
        g.board_manager.collect_gold()
        g.turns += 1

    def update_allowed_moves(self):
        g = self.g
        g.possible_moves = []
        if g.selected_square is None:
            return

        board = g.board
        piece = board.piece_at(g.selected_square)
        if piece is None:
            return

        base = [m for m in board.legal_moves if m.from_square == g.selected_square]
        pruned = g.map_challenges.prune_moves(base, piece=piece, from_sq=g.selected_square)
        extras = g.map_challenges.extra_stage_moves_for_highlight(board, piece, g.selected_square)

        seen = set()
        final = []
        for mv in pruned + extras:
            key = (mv.from_square, mv.to_square, mv.promotion)
            if key not in seen:
                seen.add(key)
                final.append(mv)

        g.possible_moves = [m.to_square for m in final]

    def _build_promotion_if_needed(self, piece, src_sq, dst_sq):
        g = self.g
        move = chess.Move(src_sq, dst_sq)
        if piece is None:
            return move

        if piece.piece_type == chess.PAWN:
            legal_promotions = self._legal_promotion_piece_types(src_sq, dst_sq)
            if legal_promotions:
                promotion_type = self._choose_promotion_piece_type(piece, src_sq, dst_sq, legal_promotions)
                if promotion_type is None:
                    return None
                move = chess.Move(src_sq, dst_sq, promotion=promotion_type)
        return move

    def _legal_promotion_piece_types(self, src_sq, dst_sq):
        g = self.g
        preferred = [piece_type for piece_type, _, _ in PROMOTION_OPTIONS]
        legal = {
            move.promotion
            for move in g.board.legal_moves
            if (
                move.from_square == src_sq and
                move.to_square == dst_sq and
                move.promotion is not None
            )
        }
        return [piece_type for piece_type in preferred if piece_type in legal]

    def _choose_promotion_piece_type(self, piece, src_sq, dst_sq, legal_promotions):
        g = self.g
        provider = getattr(g, "promotion_choice_provider", None)
        if provider:
            choice = provider(piece.color, src_sq, dst_sq, tuple(legal_promotions))
        else:
            choice = choose_promotion_piece_type(g, piece.color)

        if choice is None:
            return None

        if choice not in legal_promotions:
            print(f"[Promotion] Invalid promotion choice {choice}; defaulting to queen.")
            return legal_promotions[0]

        return choice

    def _validate_move_against_map(self, move, piece):
        g = self.g
        if move not in g.board.legal_moves:
            return False

        if g.board.is_check():
            g.board.push(move)
            escapes_check = not g.board.is_check()
            g.board.pop()
            if escapes_check:
                allowed = g.map_challenges.prune_moves([move], piece=piece, from_sq=move.from_square)
                return bool(allowed) or True

        allowed = g.map_challenges.prune_moves([move], piece=piece, from_sq=move.from_square)
        return bool(allowed)

    def _finalize_successful_player_move(self, piece, move, dest_square):
        g = self.g
        board = g.board

        if move in board.legal_moves:
            g.move_history.append(board.fen())
            g.renderer.animate_piece_move(piece.symbol(), move.from_square, move.to_square)
            board.push(move)

            if move.promotion:
                g.player_has_promoted = True

            g.quests.update_quest_variables(piece, move, player=True)
            self._clear_king_protections()
            g.selected_square = None
            g.board_manager.collect_gold()
            g.turns += 1
            g.map_challenges.maybe_apply_slip_after_player_move(piece, move)
            return True

        try:
            is_special = False
            if hasattr(g.map_challenges, "is_triple_pawn_move"):
                is_special = g.map_challenges.is_triple_pawn_move(move)
        except Exception:
            is_special = False

        if is_special:
            g.move_history.append(board.fen())
            g.renderer.animate_piece_move(piece.symbol(), move.from_square, move.to_square)

            if g.map_challenges.apply_special_move(move):
                if move.promotion:
                    g.player_has_promoted = True
                g.quests.update_quest_variables(piece, move, player=True)
                self._clear_king_protections()
                g.selected_square = None
                g.board_manager.collect_gold()
                g.turns += 1
                return True
            else:
                g.ui_state.send_feedback("That special pawn leap is blocked.")
                return False

        g.ui_state.send_feedback("That move is blocked by the land’s rules.")
        return False

    def _attempt_player_move_to(self, dest_square):
        g = self.g

        if g.selected_square is None:
            return False

        if g.selected_square in g.frozen_squares:
            g.selected_square = None
            g.ui_state.send_feedback("Target square is frozen!")
            return False

        if dest_square in g.shielded_squares and g.board.piece_at(dest_square):
            g.selected_square = None
            g.ui_state.send_feedback("Target square is shielded!")
            return False

        piece = g.board.piece_at(g.selected_square)
        if piece is None:
            g.selected_square = None
            g.ui_state.send_feedback("Illegal move. Try again.")
            return False

        move = self._build_promotion_if_needed(piece, g.selected_square, dest_square)
        if move is None:
            return False

        if move in g.board.legal_moves:
            pruned = g.map_challenges.prune_moves([move], piece=piece, from_sq=move.from_square)
            if pruned:
                return self._finalize_successful_player_move(piece, move, dest_square)
            else:
                extras = g.map_challenges.extra_stage_moves_for_highlight(g.board, piece, g.selected_square)
                if any((m.from_square == move.from_square and m.to_square == move.to_square and m.promotion == move.promotion) for m in extras):
                    return self._finalize_successful_player_move(piece, move, dest_square)

                g.selected_square = None
                g.ui_state.send_feedback("That move is blocked by the land’s rules.")
                return False

        extras = g.map_challenges.extra_stage_moves_for_highlight(g.board, piece, g.selected_square)
        is_extra = any((m.from_square == move.from_square and m.to_square == move.to_square and m.promotion == move.promotion) for m in extras)

        if is_extra:
            return self._finalize_successful_player_move(piece, move, dest_square)

        g.selected_square = None
        g.ui_state.send_feedback("Illegal move. Try again.")
        return False

    def swap_pieces(self, square1, square2):
        g = self.g
        piece1 = g.board.piece_at(square1)
        piece2 = g.board.piece_at(square2)
        g.board.set_piece_at(square1, piece2)
        g.board.set_piece_at(square2, piece1)
        g.audio.play_random("swap")
        print(f"Swapped pieces at {chess.square_name(square1)} and {chess.square_name(square2)}")

    def decrement_power_timers(self):
        g = self.g
        for square in list(g.shielded_squares.keys()):
            g.shielded_squares[square] -= 1
            if g.shielded_squares[square] <= 0:
                del g.shielded_squares[square]

        for square in list(g.frozen_squares.keys()):
            g.frozen_squares[square] -= 1
            if g.frozen_squares[square] <= 0:
                del g.frozen_squares[square]

        g.magnet_square = None

    def sprinkle_gold_pieces(self):
        g = self.g
        g.gold_pieces.clear()
        g.gold_icons.clear()
        g.landed_gold_pieces.clear()
        possible_ranks = [2, 3, 4, 5]

        placed = 0
        while placed < 5:
            file = random.randint(0, 7)
            rank = random.choice(possible_ranks)
            square = chess.square(file, rank)
            if square not in g.gold_pieces:
                g.gold_pieces.add(square)
                icon = random.choice(g.gold_coins)
                g.gold_icons[square] = icon
                g.renderer.animate_gold_drop(square, icon)
                g.landed_gold_pieces.add(square)
                placed += 1

        print(f"[INFO] Gold placed on: {[chess.square_name(sq) for sq in g.gold_pieces]}")

    def collect_gold(self):
        g = self.g
        for square, piece in g.board.piece_map().items():
            if piece.color == (chess.WHITE if g.player_side == "white" else chess.BLACK) and square in g.gold_pieces:
                g.gold_pieces.remove(square)
                g.landed_gold_pieces.discard(square)
                g.player_gold += 1
                print(f"[INFO] Player collected gold at {chess.square_name(square)}! Total: {g.player_gold}")
                g.audio.play_random("coin")

    def promote_back_rank_pawns_to_queens(self, board=None):
        board = board or self.g.board
        promoted = []

        for square, piece in list(board.piece_map().items()):
            if piece.piece_type != chess.PAWN:
                continue

            rank = chess.square_rank(square)
            if rank not in (0, 7):
                continue

            board.set_piece_at(square, chess.Piece(chess.QUEEN, piece.color))
            promoted.append(square)

        if promoted:
            print(
                "[Promotion] Auto-promoted back-rank pawn(s) to queen: "
                f"{[chess.square_name(sq) for sq in promoted]}"
            )

        return promoted

    def player_color(self):
        g = self.g
        return chess.WHITE if g.player_side == "white" else chess.BLACK
    
    def _relock_powers(self):
        g = self.g
        g.powers_unlocked = False
        g.selected_power = None

        renderer = getattr(g, "renderer", None)
        if renderer and hasattr(renderer, "reset_powers_unlock_animation"):
            renderer.reset_powers_unlock_animation()
