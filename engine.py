# engine.py
import chess
import chess.engine
import traceback
import random

# Base caps; actual values are scaled by difficulty each turn
THINK_TIME_MIN = 0.02
THINK_TIME_MAX = 0.12
EVAL_DEPTH_MIN = 1
EVAL_DEPTH_MAX = 10

RECOVERY_ANALYSIS_BASE = 6
GREED_ANALYSIS_BASE    = 5
MIRROR_LOG = True


# ─────────────────────────────────────────────────────────────
# FEN / BOARD SANITIZATION
# ─────────────────────────────────────────────────────────────
def sanitize_board_inplace(board: chess.Board) -> bool:
    """
    Best-effort board sanitizer to prevent common 'illegal but tolerated elsewhere' states
    from breaking your game/engine.

    Currently:
      - Any pawn on rank 1 or 8 is auto-promoted to a queen of same color.

    Returns True if any changes were made.
    """
    changed = False
    for sq, p in list(board.piece_map().items()):
        if p.piece_type == chess.PAWN:
            r = chess.square_rank(sq)  # 0..7
            if r == 0 or r == 7:
                board.set_piece_at(sq, chess.Piece(chess.QUEEN, p.color))
                changed = True
    return changed


def clean_fen(fen: str) -> str:
    """
    Clean/repair a FEN string so it is less likely to break downstream logic.

    Fixes include:
      - Ensure 6 FEN fields exist (pad defaults if missing)
      - Normalize side-to-move (w/b)
      - Auto-promote pawns on rank 1/8 to queens
      - Repair castling rights if impossible based on piece placement
      - Repair en passant square if nonsensical
      - Clamp halfmove/fullmove to valid ints

    If the FEN is too malformed to parse meaningfully, returns the original FEN.
    """
    try:
        parts = (fen or "").strip().split()
        if len(parts) < 1:
            return fen

        # Pad missing fields (common in hand-written FENs)
        while len(parts) < 6:
            if len(parts) == 1:
                parts.append("w")
            elif len(parts) == 2:
                parts.append("-")
            elif len(parts) == 3:
                parts.append("-")
            elif len(parts) == 4:
                parts.append("0")
            elif len(parts) == 5:
                parts.append("1")

        placement, stm, castling, ep, halfmove, fullmove = parts[:6]

        # Side to move
        stm = stm.lower()
        if stm not in ("w", "b"):
            stm = "w"

        # Halfmove / fullmove
        try:
            halfmove_i = int(halfmove)
        except Exception:
            halfmove_i = 0
        halfmove_i = max(0, halfmove_i)

        try:
            fullmove_i = int(fullmove)
        except Exception:
            fullmove_i = 1
        fullmove_i = max(1, fullmove_i)

        # --- placement repair + pawn auto-promotion ---
        ranks = placement.split("/")
        # If ranks count is off, best-effort normalize to 8 ranks
        if len(ranks) != 8:
            # If fewer, pad empty ranks; if more, truncate
            if len(ranks) < 8:
                ranks = ranks + ["8"] * (8 - len(ranks))
            else:
                ranks = ranks[:8]

        def expand_rank(r: str) -> list[str]:
            out = []
            for ch in r:
                if ch.isdigit():
                    out.extend(["."] * int(ch))
                else:
                    out.append(ch)
            # normalize to 8
            if len(out) < 8:
                out.extend(["."] * (8 - len(out)))
            elif len(out) > 8:
                out = out[:8]
            return out

        def compress_rank(cells: list[str]) -> str:
            s = []
            empties = 0
            for ch in cells:
                if ch == ".":
                    empties += 1
                else:
                    if empties:
                        s.append(str(empties))
                        empties = 0
                    s.append(ch)
            if empties:
                s.append(str(empties))
            return "".join(s) or "8"

        board_rows = [expand_rank(r) for r in ranks]

        # Pawn auto-promotion: rank 8 (row 0) and rank 1 (row 7)
        for col in range(8):
            if board_rows[0][col] == "p":
                board_rows[0][col] = "q"
            if board_rows[0][col] == "P":
                board_rows[0][col] = "Q"
            if board_rows[7][col] == "p":
                board_rows[7][col] = "q"
            if board_rows[7][col] == "P":
                board_rows[7][col] = "Q"

        placement_fixed = "/".join(compress_rank(row) for row in board_rows)

        # Build a board to validate castling/en-passant
        board = chess.Board(f"{placement_fixed} {stm} - - 0 1")

        # --- castling repair: only keep rights that are actually possible ---
        def has_piece(square_name: str, piece_symbol: str) -> bool:
            sq = chess.parse_square(square_name)
            p = board.piece_at(sq)
            return p is not None and p.symbol() == piece_symbol

        castling = castling if castling != "" else "-"
        allowed = []

        if has_piece("e1", "K") and has_piece("h1", "R"):
            allowed.append("K")
        if has_piece("e1", "K") and has_piece("a1", "R"):
            allowed.append("Q")
        if has_piece("e8", "k") and has_piece("h8", "r"):
            allowed.append("k")
        if has_piece("e8", "k") and has_piece("a8", "r"):
            allowed.append("q")

        castling_fixed = "".join([c for c in "KQkq" if c in allowed]) or "-"

        # --- en passant repair: must be "-" or a valid square; also must be plausible ---
        ep_fixed = ep
        if ep_fixed != "-":
            try:
                ep_sq = chess.parse_square(ep_fixed)
                # Plausibility: ep target must be on rank 3 (for black to capture) or rank 6 (for white to capture)
                r = chess.square_rank(ep_sq)  # 0..7
                if r not in (2, 5):  # ranks 3 or 6 in 1-based terms
                    ep_fixed = "-"
                else:
                    # More plausibility: there must exist an adjacent pawn of side-to-move that could capture
                    # and the square behind ep must have an opponent pawn that just "could have" advanced.
                    # If this is too strict, just keep the rank check.
                    ep_file = chess.square_file(ep_sq)
                    mover = chess.WHITE if stm == "w" else chess.BLACK

                    def pawn_at(file_i: int, rank_i: int, color: bool) -> bool:
                        if not (0 <= file_i <= 7 and 0 <= rank_i <= 7):
                            return False
                        s = chess.square(file_i, rank_i)
                        p = board.piece_at(s)
                        return p is not None and p.piece_type == chess.PAWN and p.color == color

                    # Capturing pawns sit one rank behind ep (from capturer perspective)
                    if mover == chess.WHITE:
                        capt_rank = chess.square_rank(ep_sq) - 1
                        victim_rank = chess.square_rank(ep_sq) - 1
                    else:
                        capt_rank = chess.square_rank(ep_sq) + 1
                        victim_rank = chess.square_rank(ep_sq) + 1

                    can_cap = (
                        pawn_at(ep_file - 1, capt_rank, mover) or
                        pawn_at(ep_file + 1, capt_rank, mover)
                    )
                    if not can_cap:
                        ep_fixed = "-"
            except Exception:
                ep_fixed = "-"

        return f"{placement_fixed} {stm} {castling_fixed} {ep_fixed} {halfmove_i} {fullmove_i}"

    except Exception:
        # If anything goes sideways, return original.
        return fen

class EnemyMoveEngine:
    def __init__(self, game):
        self.g = game
        self._last_selector = "engine"  # for logging/tagging

    # ─────────────────────────────────────────────────────────────
    # Public entry
    # ─────────────────────────────────────────────────────────────
    def engine_move(self) -> bool:
        level = self._ensure_level_for_turn()

        self.g.map_challenges.PreEngineMove()
        self.g.compass_hint = None
        self.g.in_check_overlay_active = False

        if self._should_skip_enemy_turn():
            return False

        board = self.g.board

        # NEW: sanitize board state before any engine interaction
        try:
            if sanitize_board_inplace(board):
                print("[FEN/Sanitize] Promoting pawn(s) on rank 1/8 before engine move.")
        except Exception:
            pass

        base_move = self._safe_engine_play(board, level)

        if base_move is None:
            self.g.ENEMY_RAGE_QUITS = True
            return False

        legal_moves = list(board.legal_moves)

        # Choose move by priority of overrides
        move = None
        self._last_selector = "engine"

        # Scale override analysis depths by difficulty
        rec_depth  = self._scaled_depth(level, base=RECOVERY_ANALYSIS_BASE)
        greed_depth = self._scaled_depth(level, base=GREED_ANALYSIS_BASE)

        # 1) Greed (only if no magnet target)
        if getattr(self.g, "greed_active", False) and self.g.magnet_square is None:
            move = self._select_greed_move(legal_moves, depth=greed_depth)
            if move:
                self._last_selector = "greed"

        # 2) Magnet (must land on magnet square; also respect freeze/shield)
        if move is None and self.g.magnet_square is not None:
            move = self._select_magnet_move(legal_moves, depth=rec_depth)
            if move:
                self._last_selector = "magnet"

        # 3) Freeze/Shield recovery if base move is blocked
        if move is None and self._move_hits_freeze_or_shield(base_move):
            move = self._select_recovery_move(legal_moves, depth=rec_depth)
            if move:
                self._last_selector = "recovery"

        # 4) Mirror
        if move is None and getattr(self.g, "force_mirror_active", False):
            move = self._select_mirror_move(legal_moves)
            if move:
                self._last_selector = "mirror"

        # 5) Default to base engine move (with difficulty-based softening)
        if move is None:
            move = self._maybe_soften_move(base_move, legal_moves, level)
            self._last_selector = "engine" if move == base_move else "softened"

        # Execute selected move with shared path
        return self._execute_move(move, source_tag=self._last_selector)

    # ─────────────────────────────────────────────────────────────
    # Difficulty helpers
    # ─────────────────────────────────────────────────────────────
    def _ensure_level_for_turn(self) -> int:
        """
        Get the current skill level for this turn.
        Prefer g.current_stockfish_level (already set by your DifficultyManager).
        If missing, compute TEMP so we don't play at full strength by accident.
        """
        lvl = getattr(self.g, "current_stockfish_level", None)
        if isinstance(lvl, int) and 0 <= lvl <= 20:
            return lvl or 1
        # Fallback: try to compute via your DifficultyManager if it exists
        try:
            if hasattr(self.g, "difficulty_manager"):
                return int(self.g.difficulty_manager.SetEngineDifficultyTemp()) or 1
            if hasattr(self.g, "difficulty"):
                # In some builds you stored it as .difficulty
                return int(self.g.difficulty.SetEngineDifficultyTemp()) or 1
        except Exception:
            pass
        return 1

    def _think_time_for(self, level: int) -> float:
        """Lower level → less think time. Range THINK_TIME_MIN..THINK_TIME_MAX."""
        level = max(1, min(20, int(level)))
        return THINK_TIME_MIN + (THINK_TIME_MAX - THINK_TIME_MIN) * (level - 1) / 19.0

    def _scaled_depth(self, level: int, base: int) -> int:
        """
        Scale an analysis base depth by difficulty.
        Low levels: shallow; high levels: deeper, capped at EVAL_DEPTH_MAX.
        """
        level = max(1, min(20, int(level)))
        # Map level 1→EVAL_DEPTH_MIN .. 20→min(EVAL_DEPTH_MAX, base+something)
        target = EVAL_DEPTH_MIN + int((EVAL_DEPTH_MAX - EVAL_DEPTH_MIN) * (level - 1) / 19.0)
        return max(EVAL_DEPTH_MIN, min(EVAL_DEPTH_MAX, max(1, min(base, target))))

    def _soften_chance(self, level: int) -> float:
        """
        Probability to pick a 'merely decent' move instead of the top move.
        1.0 at level 1 → 0.0 by ~level 12+ (tweak to taste).
        """
        level = max(1, min(20, int(level)))
        # Linear dropoff; clamp at 0
        p = max(0.0, 1.0 - (level - 1) / 11.0)  # L1=1.0, L12≈0.0, L20=0.0
        return p

    # ─────────────────────────────────────────────────────────────
    # Selection helpers (override choosing)
    # ─────────────────────────────────────────────────────────────
    def _select_greed_move(self, legal_moves, depth: int):
        """Pick best-scoring legal move that lands on a gold square."""
        gold = getattr(self.g, "gold_pieces", set())
        candidates = [m for m in legal_moves if m.to_square in gold]
        if not candidates:
            return None

        best_move, best_score = None, None
        for mv in candidates:
            score = self._evaluate_resulting_position(mv, depth=depth)
            if score is None:
                continue
            best_move, best_score = self._choose_by_side(best_move, best_score, mv, score)

        if best_move:
            print(f"[Greed] AI grabs gold: {best_move.uci()}  (score={best_score}, depth={depth})")
            # Greed is single-shot
            self.g.greed_active = False
        return best_move

    def _select_magnet_move(self, legal_moves, depth: int):
        """Pick best-scoring move that lands on magnet square; respect freeze/shield."""
        magnet_sq = self.g.magnet_square
        if magnet_sq is None:
            return None

        on_magnet = [
            m for m in legal_moves
            if m.to_square == magnet_sq
            and (m.from_square not in self.g.frozen_squares)
            and (m.to_square   not in self.g.shielded_squares)
        ]
        if not on_magnet:
            return None

        best_move, best_score = None, None
        for mv in on_magnet:
            score = self._evaluate_resulting_position(mv, depth=depth)
            if score is None:
                continue
            best_move, best_score = self._choose_by_side(best_move, best_score, mv, score)

        if best_move:
            print(f"[Magnet] Engine pulled to {chess.square_name(magnet_sq)}: {best_move.uci()} (depth={depth})")
        return best_move

    def _select_recovery_move(self, legal_moves, depth: int):
        """If base move is blocked by freeze/shield, pick best legal alternative."""
        allowed = [
            m for m in legal_moves
            if (m.from_square not in self.g.frozen_squares)
            and (m.to_square   not in self.g.shielded_squares)
        ]
        if not allowed:
            print("[Blocked] No legal alternative due to freeze/shield.")
            return None

        best_move, best_score = None, None
        for mv in allowed:
            score = self._evaluate_resulting_position(mv, depth=depth)
            if score is None:
                continue
            best_move, best_score = self._choose_by_side(best_move, best_score, mv, score)

        if best_move:
            print(f"[Recovery] Engine retries with: {best_move.uci()}  (score={best_score}, depth={depth})")
        return best_move

    def _select_mirror_move(self, legal_moves):
        """Mirror the player's last move if legal."""
        if not self.g.board.move_stack:
            return None
        last_move = self.g.board.move_stack[-1]
        mirror = self.g.board_manager.mirror_move(last_move)
        if mirror in legal_moves:
            if MIRROR_LOG:
                print(f"[Mirror] AI mirrors: {mirror.uci()}")
            return mirror
        return None

    # ─────────────────────────────────────────────────────────────
    # Execution (shared path)
    # ─────────────────────────────────────────────────────────────
    def _execute_move(self, move: chess.Move, source_tag: str) -> bool:
        """Animate, push, apply post-effects (incl. Poisoned Pawns & Greedland), quests, cleanup."""
        board = self.g.board

        # BEFORE push: who is moving?
        mover_piece = board.piece_at(move.from_square)

        # Animate if we know the sprite
        if mover_piece:
            self._animate(mover_piece, move)

        # BEFORE push: capture snapshot (handles en passant)
        cap_piece, _ = self._prepush_capture_snapshot(board, move)

        try:
            self._record_position_to_history()
            board.push(move)
        except Exception as e:
            print(f"[ERROR] Engine move failed: {e}")
            traceback.print_exc()
            self.g.ENEMY_RAGE_QUITS = True
            return False

        # Post-push effects
        self._apply_poisoned_pawns(move, cap_piece)
        self._post_magnet_cleanup()

        # --- Stage 14: Greedland coin & purchase logic on capture ---
        try:
            self._greed_on_enemy_capture(cap_piece)
        except Exception:
            pass

        # Quest hooks / board cleanup
        try:
            self.g.quests.update_quest_variables(mover_piece, move, player=False)
        except Exception as e:
            print(f"[WARN] Quest update failed: {e}")
            traceback.print_exc()

        self.g._clear_king_protections()

        print(f"Engine moves ({source_tag}): {move.uci()}")

        # Keep Astral Gate hint accurate for the upcoming turn (Stage 10 only)
        try:
            if hasattr(self.g, "map_challenges"):
                self.g.map_challenges.refresh_astral_hint_only()
        except Exception:
            pass

        self.g.completed_turns += 1

        # Auto-unlock powers after 10 completed turns
        if self.g.completed_turns >= 10:
            if not getattr(self.g, "powers_unlocked", False):
                renderer = getattr(self.g, "renderer", None)
                if renderer and hasattr(renderer, "unlock_powers_area"):
                    renderer.unlock_powers_area()

        return True

    # ─────────────────────────────────────────────────────────────
    # Rule effects / post-processing
    # ─────────────────────────────────────────────────────────────
    def _apply_poisoned_pawns(self, move: chess.Move, captured_piece: chess.Piece | None):
        """
        Poisoned Pawns:
          If self.g.quests.enable_poisoned_pawns is True
          AND the engine's move captured a pawn (normal or en passant),
          remove the capturing engine piece from move.to_square AFTER the push.
        """
        quests = getattr(self.g, "quests", None)
        if not (quests and getattr(quests, "enable_poisoned_pawns", False)):
            return
        if not (captured_piece and captured_piece.piece_type == chess.PAWN):
            return

        # Capturing piece stands on move.to_square after push (incl. en passant)
        self.g.board.remove_piece_at(move.to_square)
        print(f"[PoisonedPawns] Captured pawn → capturing piece at {chess.square_name(move.to_square)} is removed.")

    def _post_magnet_cleanup(self):
        """Clear magnet if its square is now empty (effect resolved)."""
        msq = getattr(self.g, "magnet_square", None)
        if msq is not None and not self.g.board.piece_at(msq):
            self.g.magnet_square = None

    # ─────────────────────────────────────────────────────────────
    # Utilities
    # ─────────────────────────────────────────────────────────────
    def _should_skip_enemy_turn(self) -> bool:
        """True if game is over or it is the player's turn."""
        if self.g.board.is_game_over():
            return True
        players_turn_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        return self.g.board.turn == players_turn_color

    def _safe_engine_play(self, board, level: int) -> chess.Move | None:
        try:
            # NEW: sanitize again (cheap + safe)
            try:
                sanitize_board_inplace(board)
            except Exception:
                pass

            t = self._think_time_for(level)
            result = self.g.engine.play(
                board,
                chess.engine.Limit(time=t),
                info=chess.engine.INFO_ALL
            )
            return result.move
        except chess.engine.EngineTerminatedError as e:
            print(f"Engine error: {e}. Skipping engine turn.")
            traceback.print_exc()
            return None
        except Exception as e:
            print(f"Engine unknown error: {e}")
            traceback.print_exc()
            return None

    def _move_hits_freeze_or_shield(self, move: chess.Move) -> bool:
        """Check if a move is blocked by freeze/shield rules."""
        return (move.from_square in self.g.frozen_squares) or (move.to_square in self.g.shielded_squares)

    def _evaluate_resulting_position(self, move: chess.Move, depth: int) -> int | None:
        board = self.g.board.copy()
        try:
            board.push(move)
        except Exception:
            return None

        # NEW: after push, ensure no pawn is sitting on a promotion rank
        try:
            sanitize_board_inplace(board)
        except Exception:
            pass

        try:
            info = self.g.engine.analyse(board, chess.engine.Limit(depth=depth))
            return info["score"].white().score(mate_score=10000)
        except Exception as e:
            print(f"[Eval] analyse failed on {move.uci()}: {e}")
            return None

    def _choose_by_side(self, best_move, best_score, cand_move, cand_score):
        """Pick better (max for White-to-move, min for Black-to-move)."""
        if best_move is None:
            return cand_move, cand_score
        if self.g.board.turn == chess.WHITE:
            if cand_score is not None and cand_score > best_score:
                return cand_move, cand_score
        else:
            if cand_score is not None and cand_score < best_score:
                return cand_move, cand_score
        return best_move, best_score

    def _maybe_soften_move(self, best_move: chess.Move, legal_moves, level: int) -> chess.Move:
        """
        At low levels, occasionally pick a decent-but-not-best move.
        Implementation: shallow-evaluate up to N random legal moves, sort by score,
        then pick from lower-ranked candidates with probability set by difficulty.
        """
        p = self._soften_chance(level)
        if p <= 0.0 or len(legal_moves) <= 1:
            return best_move

        # Sample a subset to keep it fast
        sample_size = min(8, len(legal_moves))
        sampled = random.sample(legal_moves, sample_size) if len(legal_moves) > sample_size else list(legal_moves)

        depth = max(1, min(3, self._scaled_depth(level, base=2)))  # very shallow
        scored = []
        for mv in sampled:
            sc = self._evaluate_resulting_position(mv, depth=depth)
            if sc is None:
                continue
            # Score always from White POV; invert if it's Black to move now (before push)
            s = sc if self.g.board.turn == chess.WHITE else -sc
            scored.append((s, mv))

        if not scored:
            return best_move

        # Sort best→worst from side-to-move perspective
        scored.sort(key=lambda t: t[0], reverse=True)

        # With probability p, choose a move from the bottom half (but still legal and sane)
        if random.random() < p:
            bottom = scored[len(scored)//2:]
            # Avoid the absolute worst if possible
            if len(bottom) > 1:
                _, choice = random.choice(bottom[1:])
            else:
                _, choice = bottom[0]
            return choice

        return best_move

    def _animate(self, piece: chess.Piece, move: chess.Move):
        """Fire your animation; swallow errors to avoid breaking the turn."""
        try:
            self.g.renderer.animate_piece_move(piece.symbol(), move.from_square, move.to_square)
        except Exception:
            pass

    def _record_position_to_history(self):
        """Append FEN BEFORE pushing the move."""
        try:
            self.g.move_history.append(self.g.board.fen())
        except Exception:
            pass

    def _prepush_capture_snapshot(self, board: chess.Board, move: chess.Move):
        """
        Return (captured_piece, captured_square) BEFORE pushing.
        En passant: captured pawn is behind move.to_square relative to the mover.
        """
        if not board.is_capture(move):
            return None, None
        if board.is_en_passant(move):
            # Before push, board.turn is the mover color.
            cap_sq = move.to_square - 8 if board.turn == chess.WHITE else move.to_square + 8
        else:
            cap_sq = move.to_square
        return board.piece_at(cap_sq), cap_sq

    # ─────────────────────────────────────────────────────────────
    # Stage 14: Greedland helpers
    # ─────────────────────────────────────────────────────────────
    def _current_stage_id(self):
        try:
            return self.g.world.world_data[self.g.world.player_pos]["stage_id"]
        except Exception:
            return None

    def _ensure_greed_counters(self):
        # Persistent coin counter on game
        if not hasattr(self.g, "enemy_greed_coins"):
            self.g.enemy_greed_coins = 0

    def _greed_on_enemy_capture(self, captured_piece: chess.Piece | None):
        """
        When the AI captures a player's piece on Stage 14:
          • +1 coin and taunt
          • Every 6 coins: buy the player's best non-king piece (convert color)
        """
        if captured_piece is None:
            return
        if not getattr(self.g, "map_challenges", None) or not self.g.map_challenges.board_effects_active:
            return
        if self._current_stage_id() != 14:
            return

        # Captured piece must belong to PLAYER
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        if captured_piece.color != player_color:
            return

        self._ensure_greed_counters()
        self.g.enemy_greed_coins += 1

        # Taunt
        coins = self.g.enemy_greed_coins
        to_next = 6 - (coins % 6) if (coins % 6) != 0 else 0
        if to_next:
            msg = f"I have {coins} coin{'s' if coins != 1 else ''}! Just {to_next} left to go!"
        else:
            msg = f"Six coins! Time to buy something nice…"

        # Show dialog; swallow any UI/audio errors
        try:
            self.g.renderer.enemy_dialog_text = msg
            self.g.renderer.enemy_dialog_timer = 150
            self.g.renderer.enemy_dialog_alpha = 255
            if hasattr(self.g, "audio"):
                self.g.audio.play_random("gold")
        except Exception:
            pass

        # Purchase at every multiple of 6
        while self.g.enemy_greed_coins >= 6:
            # Spend exactly 6 (keeps overflow safe if you ever award >1 coin)
            self.g.enemy_greed_coins -= 6
            bought = self._greed_buy_best_player_piece()
            # Feedback for the purchase
            try:
                if bought is not None:
                    sq_name = chess.square_name(bought)
                    self.g.renderer.enemy_dialog_text = f"Your finest—now mine at {sq_name}."
                    self.g.renderer.enemy_dialog_timer = 180
                    self.g.renderer.enemy_dialog_alpha = 255
                    if hasattr(self.g, "audio"):
                        self.g.audio.play_random("promotion")
                else:
                    # Nothing to buy; refund 6 so coin math isn't confusing
                    self.g.enemy_greed_coins += 6
                    break
            except Exception:
                pass

    def _greed_buy_best_player_piece(self) -> int | None:
        """
        Flip the player's best non-king piece in-place to the enemy's color.
        Returns the square index if a piece was converted, else None.
        """
        board = self.g.board
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        enemy_color = not player_color

        # Gather all player pieces except king
        plist = []
        for sq, p in board.piece_map().items():
            if p.color == player_color and p.piece_type != chess.KING:
                plist.append((sq, p))

        if not plist:
            return None

        # Piece values (queen > rook > bishop/knight > pawn)
        values = {
            chess.QUEEN: 900,
            chess.ROOK: 500,
            chess.BISHOP: 330,
            chess.KNIGHT: 320,
            chess.PAWN: 100,
        }

        # Choose the highest value; break ties by random or by “forwardness”
        best_sq, best_piece, best_score = None, None, -10**9
        for sq, p in plist:
            val = values.get(p.piece_type, 0)

            # Optional tie-break: prefer pieces more advanced toward enemy side
            rank = chess.square_rank(sq)
            # If player is white, higher rank is more advanced; if black, lower rank is more advanced
            forward = rank if player_color == chess.WHITE else (7 - rank)

            score = val * 1000 + forward  # weight value >> position
            if score > best_score:
                best_sq, best_piece, best_score = sq, p, score

        if best_sq is None:
            return None

        # Convert ownership: same piece type, enemy color
        board.set_piece_at(best_sq, chess.Piece(best_piece.piece_type, enemy_color))
        return best_sq
