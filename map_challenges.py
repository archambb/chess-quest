# map_challenges.py
import chess
import random

class MapChallenges:
    def __init__(self, game):
        self.g = game
        self.board_effects_active = True

        # Stage 2 (lava row countdown) state
        self._lava_row_active = False
        self._lava_row_index = None  # 0..7
        self._lava_row_counter = 0   # starts at 10, ticks down each full player-turn

        # Stage 4 (Stalker) state
        # _stalker_square: current square if active (int 0..63) or None
        # _stalker_cooldown: turns remaining before respawn when not active (only ticks on Stage 4)
        self._stalker_square = None
        self._stalker_cooldown = 0

        # Stage 10 (astral gate control)
        self.astral_gate_held = None  # "player" | "enemy" | None

    # ────────────────────────────────────────────────────────────────────
    # Utility helpers
    # ────────────────────────────────────────────────────────────────────
    def _player_color(self):
        return chess.WHITE if getattr(self.g, "player_side", "white") == "white" else chess.BLACK

    def _enemy_color(self):
        return not self._player_color()

    def _center_squares(self):
        # d4, e4, d5, e5  -> files 3,4 and ranks 3,4
        return [chess.D4, chess.E4, chess.D5, chess.E5]

    def _adjacent_squares_8(self, sq):
        out = []
        f0, r0 = chess.square_file(sq), chess.square_rank(sq)
        for df in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if df == 0 and dr == 0:
                    continue
                f, r = f0 + df, r0 + dr
                if 0 <= f <= 7 and 0 <= r <= 7:
                    out.append(chess.square(f, r))
        return out

    def _empty_squares_adjacent_to(self, sq):
        out = []
        for t in self._adjacent_squares_8(sq):
            if self.g.board.piece_at(t) is None:
                out.append(t)
        return out

    def _random_empty_on_side(self, color):
        """
        Return a random empty square on the given side of the board:
          - For WHITE side: ranks 0..3 are 'white side' (from white POV).
          - For BLACK side: ranks 4..7 are 'black side'.
        """
        empties = []
        for sq in chess.SQUARES:
            if self.g.board.piece_at(sq) is None:
                r = chess.square_rank(sq)
                if (color == chess.WHITE and r <= 3) or (color == chess.BLACK and r >= 4):
                    empties.append(sq)
        return random.choice(empties) if empties else None

    def _safe_place_piece(self, color, piece_type, square, avoid_checkmate=True, avoid_check=True):
        """
        Try placing a piece of (color, piece_type) on 'square' and reject if it would
        immediately produce an unwanted state. Returns True if applied on real board.
        """
        board = self.g.board
        if board.piece_at(square) is not None:
            return False

        tb = board.copy(stack=False)
        tb.set_piece_at(square, chess.Piece(piece_type, color))

        # Evaluate against current side-to-move
        wk = tb.king(chess.WHITE)
        bk = tb.king(chess.BLACK)
        w_attacked = bool(wk and tb.is_attacked_by(chess.BLACK, wk))
        b_attacked = bool(bk and tb.is_attacked_by(chess.WHITE, bk))

        if avoid_check and (w_attacked or b_attacked):
            return False

        if avoid_checkmate:
            # Test with White to move
            t1 = tb.copy(stack=False)
            t1.turn = chess.WHITE
            if t1.is_checkmate():
                return False
            # Test with Black to move
            t2 = tb.copy(stack=False)
            t2.turn = chess.BLACK
            if t2.is_checkmate():
                return False

        # Commit to real board
        board.set_piece_at(square, chess.Piece(piece_type, color))
        return True

    def _shield_square(self, sq, turns):
        # don't shield kings
        p = self.g.board.piece_at(sq)
        if p and p.piece_type == chess.KING:
            return False
        self.g.shielded_squares[sq] = turns
        return True

    def _freeze_square(self, sq, turns):
        # never freeze kings
        p = self.g.board.piece_at(sq)
        if p and p.piece_type == chess.KING:
            return False
        self.g.frozen_squares[sq] = turns
        return True

    # ────────────────────────────────────────────────────────────────────
    # Main hook (call this right before the AI moves)
    # ────────────────────────────────────────────────────────────────────
    def PreEngineMove(self):
        if not self.board_effects_active:
            return

        try:
            stage_id = self.g.world.world_data[self.g.world.player_pos]["stage_id"]
        except Exception:
            return

        # Hard gate: Astral Gate exists ONLY on Stage 10
        if stage_id != 10:
            self.disable_astral_hint()

        # Always keep central 4 squares shielded on Stage 9 (permanent refresh)
        if stage_id == 9:
            for c in self._center_squares():
                # Big number; also re-applied every turn so it never expires.
                self._shield_square(c, 10**9)

        # Stage-triggered periodic effects
        if stage_id == 0 and (self.g.turns % 15 == 0):
            self._resurrect_enemy_rooks()

        if stage_id == 2:
            self._stage2_lava_logic()

        # NEW: Stage 4 — Stalker
        if stage_id == 4:
            self._stage4_stalker_logic()

        if stage_id == 3:
            self._stage3_random_enemy_shield()

        if stage_id == 5:
            self._stage5_random_friendly_freeze()

        if stage_id == 6 and self.g.turns % 5 == 0 and self.g.turns != 0:
            self._stage6_tornado_remove_friendly_pawn()

        if stage_id == 7:
            self._stage7_resurrect_enemy_pawns_as_knights()

        if stage_id == 9:
            self._stage9_every_20th_enemy_pawn_promotes()

        if stage_id == 10:
            self._stage10_update_astral_gate_control()

        if stage_id == 11:
            self._stage11_enemy_pawn_resurrection_and_shields()

        if stage_id == 12:
            self._stage12_turn20_pawn_sacrifice_to_queen()

    # ────────────────────────────────────────────────────────────────────
    # Stage 4 — Stalker logic
    # ────────────────────────────────────────────────────────────────────
    def _stage4_stalker_logic(self):
        """
        A Stalker roams the enemy side. Each call:
          • If cooling down, decrement and return (respawn when 0).
          • If inactive and no cooldown, spawn on enemy-side middle (d-file or e-file),
            else random empty enemy-side square if blocked.
          • If active, try to move one step to a random adjacent square that does NOT
            contain an enemy (AI) piece. Empty or player piece is allowed.
            - If it steps onto a player piece, remove that piece and despawn for 10 turns.
            - If no legal adjacent moves exist, teleport to a random empty enemy-side square.
        """
        enemy = self._enemy_color()
        player = self._player_color()
        board = self.g.board

        # Handle cooldown (only tick while on Stage 4)
        if self._stalker_square is None and self._stalker_cooldown > 0:
            self._stalker_cooldown -= 1
            if self._stalker_cooldown == 0:
                # Respawn now on random empty enemy-side square
                spot = self._random_empty_on_side(enemy)
                if spot is not None:
                    self._stalker_square = spot
                    try:
                        self.g.audio.play_random("teleport")
                    except Exception:
                        pass
                    self._say("A Stalker returns on the far side...")
            return

        # If not active and no cooldown, try initial/enforced spawn
        if self._stalker_square is None and self._stalker_cooldown == 0:
            spawn = self._pick_stalker_spawn(enemy)
            # If preferred blocked, fall back to random empty on enemy side
            if board.piece_at(spawn) is not None:
                spawn = self._random_empty_on_side(enemy) or spawn
            # Only occupy if empty
            if board.piece_at(spawn) is None:
                self._stalker_square = spawn
                try:
                    self.g.audio.play_random("teleport")
                except Exception:
                    pass
                self._say("A Stalker prowls the enemy half...")
            return  # spawned this cycle; it will move on the next tick

        # Active: attempt to move
        if self._stalker_square is not None:
            curr = self._stalker_square
            # Adjacent candidates: cannot contain ENEMY (AI) piece
            neigh = self._adjacent_squares_8(curr)
            random.shuffle(neigh)

            legal = []
            for sq in neigh:
                p = board.piece_at(sq)
                # Can't step onto enemy (AI) piece
                if p and p.color == enemy:
                    continue
                # Allowed: empty or player piece
                legal.append(sq)

            if not legal:
                # Nowhere to go: teleport to random empty enemy-side square
                tele = self._random_empty_on_side(enemy)
                if tele is not None:
                    self._stalker_square = tele
                    try:
                        self.g.audio.play_random("teleport")
                    except Exception:
                        pass
                    self._say("The Stalker vanishes... and reappears afar.")
                return

            # Choose one step
            dst = random.choice(legal)
            victim = board.piece_at(dst)

            # (Optional) tiny animation hook for UI if you have one
            try:
                # Use a neutral symbol for animation (no board piece is tied to the Stalker)
                self.g.renderer.animate_piece_move("·", curr, dst)
            except Exception:
                pass

            # Resolve contact
            if victim and victim.color == player:
                # Remove the player's piece, despawn, start cooldown
                self.g.quests.record_captured_piece(victim, count_for_quests=True)
                board.remove_piece_at(dst)
                self._stalker_square = None
                self._stalker_cooldown = 10
                try:
                    self.g.audio.play_random("bomb")
                except Exception:
                    pass
                self._say("A Stalker strikes! It fades for 10 turns...")
            else:
                # Just move
                self._stalker_square = dst

    def _pick_stalker_spawn(self, enemy_color):
        """
        Preferred spawn squares: 'middle of the board enemy side', either left/right center.
        For enemy=BLACK -> prefer d6/e6 ; for enemy=WHITE -> prefer d3/e3.
        """
        if enemy_color == chess.BLACK:
            choices = [chess.D6, chess.E6]
        else:
            choices = [chess.D3, chess.E3]
        return random.choice(choices)

    def _say(self, text):
        try:
            self.g.renderer.enemy_dialog_text = text
            self.g.renderer.enemy_dialog_timer = 120
            self.g.renderer.enemy_dialog_alpha = 255
        except Exception:
            pass

    # ────────────────────────────────────────────────────────────────────
    # Stage 2 — Lava: 50% strike OR 50% row countdown (every 10 turns)
    # ────────────────────────────────────────────────────────────────────
    def _stage2_lava_logic(self):
        """
        Every 10 turns:
          • 50%: A lava strike hits a random square that does not contain a King or Queen.
                 If it is a PLAYER piece, it is removed.
          • 50%: Start (or continue) a 'countdown row'. It begins at 10 and ticks down
                 each player turn. When it reaches zero, that entire row is flooded with
                 lava and all PLAYER pieces on that row are destroyed.
        Notes:
          • If a countdown is active, we decrement its counter every time this hook runs.
          • Only one countdown can be active at a time. (We can choose to restart once finished.)
        """
        # Tick an active row if present
        if self._lava_row_active:
            if self._lava_row_counter > 0:
                self._lava_row_counter -= 1
                # Display a heads-up
                self.g.renderer.enemy_dialog_text = f"Lava rises on rank {self._lava_row_index + 1} in {self._lava_row_counter}..."
                self.g.renderer.enemy_dialog_timer = 90  # ~1.5s @60fps
                self.g.renderer.enemy_dialog_alpha = 255
            if self._lava_row_counter == 0:
                # Flood the row; destroy player's pieces on that rank
                player_color = self._player_color()
                for file_ in range(8):
                    sq = chess.square(file_, self._lava_row_index)
                    p = self.g.board.piece_at(sq)
                    if p and p.color == player_color:
                        self.g.quests.record_captured_piece(p, count_for_quests=True)
                        self.g.board.remove_piece_at(sq)
                self._lava_row_active = False
                self.g.audio.play_random("bomb")
                self.g.renderer.enemy_dialog_text = "The lava engulfs the rank!"
                self.g.renderer.enemy_dialog_timer = 120
                self.g.renderer.enemy_dialog_alpha = 255
                return  # lava event consumed this cycle

        # Only trigger a fresh event every 10 turns
        if self.g.turns % 10 != 0:
            return

        # Decide which branch: 0 = strike, 1 = countdown
        if random.random() < 0.5:
            # Single lava strike
            # Pick a random square that is NOT occupied by K or Q
            candidates = [sq for sq in chess.SQUARES
                          if not ( (p := self.g.board.piece_at(sq)) and p.piece_type in (chess.KING, chess.QUEEN) )]
            if not candidates:
                return
            target = random.choice(candidates)
            victim = self.g.board.piece_at(target)
            if victim and victim.color == self._player_color():
                self.g.quests.record_captured_piece(victim, count_for_quests=True)
                self.g.board.remove_piece_at(target)
                self.g.audio.play_random("bomb")
                self.g.renderer.enemy_dialog_text = f"Lava strikes {chess.square_name(target)}!"
                self.g.renderer.enemy_dialog_timer = 120
                self.g.renderer.enemy_dialog_alpha = 255
        else:
            # Start a countdown row if not already active
            if not self._lava_row_active:
                self._lava_row_active = True
                self._lava_row_index = random.randint(0, 7)
                self._lava_row_counter = 10
                self.g.renderer.enemy_dialog_text = f"Lava rises on rank {self._lava_row_index + 1} in 10..."
                self.g.renderer.enemy_dialog_timer = 120
                self.g.renderer.enemy_dialog_alpha = 255

    # ────────────────────────────────────────────────────────────────────
    # Stage 3 — Random enemy square gets a shield each turn
    # ────────────────────────────────────────────────────────────────────
    def _stage3_random_enemy_shield(self):
        enemy = self._enemy_color()
        enemy_squares = [sq for sq, p in self.g.board.piece_map().items() if p.color == enemy]
        if not enemy_squares:
            return
        sq = random.choice(enemy_squares)
        self._shield_square(sq, 2)
        self.g.audio.play_random("shields")

    # ────────────────────────────────────────────────────────────────────
    # Stage 5 — Random friendly non-king freezes
    # ────────────────────────────────────────────────────────────────────
    def _stage5_random_friendly_freeze(self):
        player = self._player_color()
        cand = [sq for sq, p in self.g.board.piece_map().items()
                if p.color == player and p.piece_type != chess.KING]
        if not cand:
            return
        sq = random.choice(cand)
        self._freeze_square(sq, 3)
        self.g.audio.play_random("freezes")

    # ────────────────────────────────────────────────────────────────────
    # Stage 6 — Tornado removes a random friendly pawn
    # ────────────────────────────────────────────────────
    def _stage6_tornado_remove_friendly_pawn(self):
        player = self._player_color()
        pawns = [sq for sq, p in self.g.board.piece_map().items()
                 if p.color == player and p.piece_type == chess.PAWN]
        if not pawns:
            return
        sq = random.choice(pawns)
        self.g.quests.record_captured_piece(self.g.board.piece_at(sq), count_for_quests=True)
        self.g.board.remove_piece_at(sq)
        self._stage6_tornado_vfx(sq)
        self.g.audio.play_random("bomb")
        self.g.renderer.enemy_dialog_text = "A tornado snatches a pawn!"
        self.g.renderer.enemy_dialog_timer = 120
        self.g.renderer.enemy_dialog_alpha = 255

    def _stage6_tornado_vfx(self, square):
        """Hook for tornado VFX/GFX when the storm removes a pawn."""
        pass

    # ────────────────────────────────────────────────────
    # Stage 7 — Enemy pawns resurrect as knights around the enemy queen
    # ────────────────────────────────────────────────────
    def _stage7_resurrect_enemy_pawns_as_knights(self):
        enemy = self._enemy_color()
        qsq = self.g.board.king(enemy)  # king != queen; we need the queen:
        # Find the enemy queen’s square instead:
        qsq = None
        for sq, p in self.g.board.piece_map().items():
            if p.color == enemy and p.piece_type == chess.QUEEN:
                qsq = sq
                break
        if qsq is None:
            return  # no enemy queen alive

        # Count enemy pawns that are missing (<= 8 minus on-board count)
        pawns_on_board = sum(1 for _, p in self.g.board.piece_map().items()
                             if p.color == enemy and p.piece_type == chess.PAWN)
        missing = max(0, 8 - pawns_on_board)
        if missing == 0:
            return

        spots = [sq for sq in self._empty_squares_adjacent_to(qsq)]
        random.shuffle(spots)

        resurrected = 0
        for spot in spots:
            if resurrected >= missing:
                break
            # Place a KNIGHT of enemy color (not a pawn)
            if self._safe_place_piece(enemy, chess.KNIGHT, spot, avoid_checkmate=False, avoid_check=False):
                resurrected += 1

        if resurrected:
            self.g.audio.play_random("promotion")
            self.g.renderer.enemy_dialog_text = "Knights rise at the queen’s side!"
            self.g.renderer.enemy_dialog_timer = 150
            self.g.renderer.enemy_dialog_alpha = 255

    # ────────────────────────────────────────────────────────────────────
    # Stage 9 — Every 20th turn: random enemy pawn promotes to N/B/R
    # ────────────────────────────────────────────────────────────────────
    def _stage9_every_20th_enemy_pawn_promotes(self):
        if self.g.turns % 20 != 0 or self.g.turns == 0:
            return

        enemy = self._enemy_color()
        pawns = [sq for sq, p in self.g.board.piece_map().items()
                 if p.color == enemy and p.piece_type == chess.PAWN]
        if not pawns:
            return

        sq = random.choice(pawns)
        promo_to = random.choice([chess.KNIGHT, chess.BISHOP, chess.ROOK])
        self.g.board.set_piece_at(sq, chess.Piece(promo_to, enemy))
        self.g.audio.play_random("promotion")
        self.g.renderer.enemy_dialog_text = "A pawn is elevated by the Rift."
        self.g.renderer.enemy_dialog_timer = 150
        self.g.renderer.enemy_dialog_alpha = 255

    # ────────────────────────────────────────────────────────────────────
    # Stage 10 — Control central 4; set astral_gate_held
    # ────────────────────────────────────────────────────────────────────
    def _stage10_update_astral_gate_control(self):
        """
        Stage 10 control of d4,e4,d5,e5.
        - astral_gate_held = "player" | "enemy" | None
        - If enemy holds:   g.current_stockfish_level = 20
        else:             g.current_stockfish_level = g.stockfish_level
        - Best-move hint: ONLY shown for the PLAYER when the PLAYER holds control.
        (Prevents confusion from showing the AI's move.)
        """
        centers = self._center_squares()
        player = self._player_color()
        enemy  = not player

        p_count = 0
        e_count = 0
        for c in centers:
            pc = self.g.board.piece_at(c)
            if not pc:
                continue
            if pc.color == player:
                p_count += 1
            elif pc.color == enemy:
                e_count += 1

        if p_count > e_count:
            self.astral_gate_held = "player"
        elif e_count > p_count:
            self.astral_gate_held = "enemy"
        else:
            self.astral_gate_held = None

        self.g.astral_gate_held = self.astral_gate_held

        # Difficulty bump only when ENEMY controls the gate
        try:
            if self.astral_gate_held == "enemy":
                self.g.current_stockfish_level = 20
            else:
                self.g.current_stockfish_level = getattr(self.g, "stockfish_level", 5)
        except Exception:
            pass

        # HINT POLICY: Only show hint for the PLAYER when PLAYER controls.
        if self.astral_gate_held == "player":
            self._update_best_move_hint_for(player, depth=20)
        else:
            self._set_best_move_hint(None, None)

    def get_stage_id(self):
        try:
            return self.g.world.world_data[self.g.world.player_pos]["stage_id"]
        except Exception:
            return None

    def disable_astral_hint(self):
        self.astral_gate_held = None
        self.g.astral_gate_held = None
        # hint to render (from_sq, to_sq)
        self.g.astral_best_hint = None
        # snap engine level back to base
        if hasattr(self.g, "stockfish_level"):
            self.g.current_stockfish_level = self.g.stockfish_level

    def refresh_astral_hint_only(self):
        """Recompute the purple 'best move' hint for Stage 10 only, and
        apply the level bump to the AI only when ENEMY holds the gate."""
        if not self.board_effects_active or self.get_stage_id() != 10:
            self.disable_astral_hint()
            return

        # Ensure held/owner is up to date
        self._stage10_update_astral_gate_control()
        held = self.astral_gate_held
        if held is None:
            self.disable_astral_hint()
            return

        board = self.g.board
        player = chess.WHITE if getattr(self.g, "player_side", "white") == "white" else chess.BLACK
        enemy  = not player

        # Who should get a hint? Only the side-to-move *and* that holds the gate.
        side_to_move = board.turn
        if (held == "player" and side_to_move != player) or (held == "enemy" and side_to_move != enemy):
            # Not that side's turn → no hint, but we still maintain level policy below.
            self.g.astral_best_hint = None
        else:
            # Compute a best move at top strength (depth 20) for the side-to-move.
            try:
                res = self.g.engine.play(board, chess.engine.Limit(depth=20))
                bm = res.move
                self.g.astral_best_hint = (bm.from_square, bm.to_square) if bm else None
            except Exception:
                self.g.astral_best_hint = None

        # Level policy: enemy gets boosted when THEY hold; otherwise revert.
        if held == "enemy":
            self.g.current_stockfish_level = 20
        else:
            if hasattr(self.g, "stockfish_level"):
                self.g.current_stockfish_level = self.g.stockfish_level


    def _set_best_move_hint(self, hint_tuple, color):
        """
        hint_tuple = (from_sq, to_sq) or None
        color      = chess.WHITE / chess.BLACK or None
        """
        self.g.best_move_hint = hint_tuple
        self.g.best_move_hint_color = color

    def _get_engine_for_hints(self):
        """
        Try to locate a usable python-chess engine object and a 'play' config.
        We don't change your main AI flow; this is only for hint calculation.
        Returns (engine, limit_or_time) or (None, None).
        """
        # Try a few common attributes you might be using
        cand = [
            getattr(self.g, "enemy_engine", None),
            getattr(self.g, "engine", None),
            getattr(self.g, "stockfish", None),
            getattr(self.g, "stockfish_engine", None),
        ]
        eng = next((e for e in cand if e is not None), None)
        if eng is None:
            return (None, None)

        # Depth-limited analysis is ideal for reproducible hints
        import chess.engine
        limit = chess.engine.Limit(depth=20)
        return (eng, limit)

    def _update_best_move_hint_for(self, color, depth=20):
        """
        Compute & cache a best-move hint for 'color' at current board FEN.
        We re-run only if (fen, color) changed since last time.
        """
        fen_now = self.g.board.fen()
        cache_key = (fen_now, color)
        if not hasattr(self, "_hint_cache_key"):
            self._hint_cache_key = None

        if self._hint_cache_key == cache_key:
            # Already have a valid hint for this exact position & side
            return

        eng, limit = self._get_engine_for_hints()
        if eng is None or limit is None:
            # No engine available; clear hint
            self._set_best_move_hint(None, None)
            self._hint_cache_key = cache_key
            return

        # Ensure the engine analyzes from 'color' perspective
        board = self.g.board
        if board.turn != color:
            # Temporarily flip turn in a copy for analysis to match the holder's color
            tmp = board.copy(stack=False)
            tmp.turn = color
            pos = tmp
        else:
            pos = board

        try:
            # Use depth 20 irrespective of difficulty; shallow fallback if needed
            import chess.engine
            limit = chess.engine.Limit(depth=depth)
            info = eng.analyse(pos, limit)
            move = info.get("pv", [None])[0] or info.get("bestmove")  # some engines return 'bestmove'
            if move is None:
                self._set_best_move_hint(None, None)
            else:
                self._set_best_move_hint((move.from_square, move.to_square), color)
            self._hint_cache_key = cache_key
        except Exception:
            # Defensive: never break the game if analysis fails
            self._set_best_move_hint(None, None)
            self._hint_cache_key = cache_key

    # ────────────────────────────────────────────────────────────────────
    # Stage 11 — Enemy pawn resurrections + periodic enemy shield
    # ────────────────────────────────────────────────────────────────────
    def _stage11_enemy_pawn_resurrection_and_shields(self):
        enemy = self._enemy_color()

        # Try to resurrect ONE missing enemy pawn per call in a random empty spot
        # on enemy side, as long as it doesn't immediately create a check or checkmate.
        pawns_on_board = sum(1 for _, p in self.g.board.piece_map().items()
                             if p.color == enemy and p.piece_type == chess.PAWN)
        missing = max(0, 8 - pawns_on_board)
        if missing > 0:
            for _ in range(20):  # up to 20 attempts to find a valid spot
                spot = self._random_empty_on_side(enemy)
                if not spot:
                    break
                if self._safe_place_piece(enemy, chess.PAWN, spot, avoid_checkmate=True, avoid_check=True):
                    self.g.audio.play_random("promotion")
                    break

        # Every 10 turns: random enemy gets a 5-turn shield
        if self.g.turns % 10 == 0 and self.g.turns != 0:
            enemy_squares = [sq for sq, p in self.g.board.piece_map().items() if p.color == enemy]
            if enemy_squares:
                sq = random.choice(enemy_squares)
                self._shield_square(sq, 5)
                self.g.audio.play_random("shields")

    # ────────────────────────────────────────────────────────────────────
    # Stage 12 — On turn 20: enemy sacrifices all pawns; one becomes a queen
    # ────────────────────────────────────────────────────────────────────
    def _stage12_turn20_pawn_sacrifice_to_queen(self):
        if self.g.turns != 20:
            return
        enemy = self._enemy_color()

        pawn_squares = [sq for sq, p in self.g.board.piece_map().items()
                        if p.color == enemy and p.piece_type == chess.PAWN]
        if not pawn_squares:
            return

        # Choose one square to become a queen, remove all other enemy pawns
        queen_square = random.choice(pawn_squares)
        for sq in pawn_squares:
            self.g.quests.record_captured_piece(self.g.board.piece_at(sq), count_for_quests=True)
            self.g.board.remove_piece_at(sq)
        self.g.board.set_piece_at(queen_square, chess.Piece(chess.QUEEN, enemy))
        self.g.audio.play_random("promotion")
        self.g.renderer.enemy_dialog_text = "A crimson rite: pawns for a queen!"
        self.g.renderer.enemy_dialog_timer = 180
        self.g.renderer.enemy_dialog_alpha = 255

    # ────────────────────────────────────────────────────────────────────
    # Existing: Rook resurrection (Stage 0 demo)
    # ────────────────────────────────────────────────────────────────────
    def _resurrect_enemy_rooks(self):
        board = self.g.board
        enemy = self._enemy_color()
        home_squares = (chess.A1, chess.H1) if enemy == chess.WHITE else (chess.A8, chess.H8)

        enemy_rook_count = sum(
            1 for sq in chess.SQUARES
            if (p := board.piece_at(sq)) and p.piece_type == chess.ROOK and p.color == enemy
        )

        resurrected_any = False
        for sq in home_squares:
            if enemy_rook_count >= 2:
                break
            if board.piece_at(sq) is None:
                board.set_piece_at(sq, chess.Piece(chess.ROOK, enemy))
                enemy_rook_count += 1
                resurrected_any = True

                lines = [
                    "Awaken, Stonebound Rooks of the Rift!",
                    "Rise, Granite Sentinels—take your posts!",
                    "Stone rooks, return to the battlefield!",
                    "By bedrock and oath—stand again, Rooks!",
                    "Rift-born rooks, reform from the granite!",
                    "From quiet stone, the rooks arise!",
                ]
                self.g.renderer.enemy_dialog_text = random.choice(lines)
                self.g.renderer.enemy_dialog_timer = 300
                self.g.renderer.enemy_dialog_alpha = 255
                print(f"[MapChallenges] Resurrected enemy rook at {chess.square_name(sq)}")

        if not resurrected_any:
            print("[MapChallenges] No rook resurrection occurred.")

    # ────────────────────────────────────────────────────────────────────
    # Pruning (Stage 1 & 8) — unchanged from your last version
    # ────────────────────────────────────────────────────────────────────
    def prune_moves(self, moves, *, piece=None, from_sq=None):
        if not self.board_effects_active:
            return list(moves)
        try:
            stage_id = self.g.world.world_data[self.g.world.player_pos]["stage_id"]
        except Exception:
            return list(moves)

        if stage_id not in (1, 8):
            return list(moves)

        board = self.g.board
        out = []
        for mv in moves:
            p = piece
            src = from_sq
            if p is None or src is None:
                src = mv.from_square
                p = board.piece_at(src)
                if p is None:
                    continue

            dst = mv.to_square
            df = abs(chess.square_file(dst) - chess.square_file(src))
            dr = abs(chess.square_rank(dst) - chess.square_rank(src))
            cheb = max(df, dr)

            if p.piece_type in (chess.QUEEN, chess.ROOK, chess.BISHOP) and cheb > 3:
                continue

            if stage_id == 1 and p.piece_type == chess.PAWN:
                if not board.is_capture(mv):
                    is_white = (p.color == chess.WHITE)
                    start_rank = 1 if is_white else 6
                    src_rank = chess.square_rank(src)
                    if df == 0 and dr == 2 and src_rank == start_rank:
                        continue

            out.append(mv)
        return out

    # ────────────────────────────────────────────────────────────────────
    # Stage 5 "slip" — unchanged from your last version
    # ────────────────────────────────────────────────────────────────────
    def maybe_apply_slip_after_player_move(self, piece_before_move, move):
        if not self.board_effects_active:
            return False
        try:
            stage_id = self.g.world.world_data[self.g.world.player_pos]["stage_id"]
        except Exception:
            return False
        if stage_id != 5:
            return False

        board = self.g.board
        player_color = self._player_color()

        mover_color = piece_before_move.color if piece_before_move else player_color
        if mover_color != player_color:
            return False

        if random.random() >= 0.25:
            return False

        src = move.from_square
        curr = move.to_square
        piece_now = board.piece_at(curr)
        if piece_now is None:
            return False

        if piece_now.piece_type in (chess.KING, chess.ROOK):
            return False

        ux, uy = self._unit_step_from_move(move)
        if ux is None:
            return False

        slip_dist = random.choices([1, 2, 3, 4], weights=[80, 10, 9, 1])[0]

        dst = self._nth_square_along(curr, ux, uy, slip_dist)
        if dst is None:
            return False

        for k in range(1, slip_dist + 1):
            sq = self._nth_square_along(curr, ux, uy, k)
            if sq is None or board.piece_at(sq) is not None:
                return False

        if not self._relocate_keeps_own_king_safe(board, curr, dst, piece_now.color):
            return False

        try:
            self.g.renderer.animate_piece_move(piece_now.symbol(), curr, dst)
        except Exception:
            pass

        board.remove_piece_at(curr)
        board.set_piece_at(dst, chess.Piece(piece_now.piece_type, piece_now.color))
        self.g.ui_state.send_feedback("The ground is slick—your piece slides!")
        return True

    # geometry/safety helpers for slip
    def _unit_step_from_move(self, move):
        fx, fy = chess.square_file(move.from_square), chess.square_rank(move.from_square)
        tx, ty = chess.square_file(move.to_square), chess.square_rank(move.to_square)
        dx, dy = tx - fx, ty - fy
        adx, ady = abs(dx), abs(dy)
        if dx == 0 and dy == 0:
            return (None, None)
        if dx == 0:
            return (0, 1 if dy > 0 else -1)
        if dy == 0:
            return (1 if dx > 0 else -1, 0)
        if adx == ady:
            return (1 if dx > 0 else -1, 1 if dy > 0 else -1)
        return (None, None)

    def _nth_square_along(self, start_sq, ux, uy, n):
        x0, y0 = chess.square_file(start_sq), chess.square_rank(start_sq)
        x = x0 + ux * n
        y = y0 + uy * n
        if 0 <= x <= 7 and 0 <= y <= 7:
            return chess.square(x, y)
        return None

    def _relocate_keeps_own_king_safe(self, board, src, dst, color):
        test = board.copy(stack=False)
        piece = test.piece_at(src)
        if piece is None or piece.color != color:
            return False
        test.remove_piece_at(src)
        test.remove_piece_at(dst)
        test.set_piece_at(dst, piece)
        ksq = test.king(color)
        if ksq is None:
            return False
        opp = not color
        return not test.is_attacked_by(opp, ksq)

    # compatibility with main (no extra highlights needed right now)
    def extra_stage_moves_for_highlight(self, board, piece, from_sq):
        return []
