# powers.py
import chess
import random


class Powers:
    def __init__(self, game):
        self.g = game

    # --------------- small helpers ---------------
    def _effects_active(self) -> bool:
        mc = getattr(self.g, "map_challenges", None)
        return bool(getattr(mc, "board_effects_active", True)) if mc else True

    def _stage_id(self):
        try:
            return self.g.world.world_data[self.g.world.player_pos]["stage_id"]
        except Exception:
            return None

    def _square_name(self, sq):
        try:
            return chess.square_name(sq)
        except Exception:
            return "?"

    def _chebyshev_move_len(self, move: chess.Move) -> int:
        f0, r0 = chess.square_file(move.from_square), chess.square_rank(move.from_square)
        f1, r1 = chess.square_file(move.to_square), chess.square_rank(move.to_square)
        return max(abs(f1 - f0), abs(r1 - r0))

    def _removal_is_safe(self, squares_to_remove):
        """
        Return True iff removing all pieces on squares_to_remove does not
        newly put a king in check (for either side).
        """
        board = self.g.board
        test = board.copy(stack=False)

        # Explicitly compute original king-attack states (both sides)
        w_king = test.king(chess.WHITE)
        b_king = test.king(chess.BLACK)
        w_attacked_orig = bool(w_king and test.is_attacked_by(chess.BLACK, w_king))
        b_attacked_orig = bool(b_king and test.is_attacked_by(chess.WHITE, b_king))

        # Apply removals
        for sq in squares_to_remove:
            test.remove_piece_at(sq)

        # Re-evaluate
        w_king = test.king(chess.WHITE)
        b_king = test.king(chess.BLACK)
        w_attacked_after = bool(w_king and test.is_attacked_by(chess.BLACK, w_king))
        b_attacked_after = bool(b_king and test.is_attacked_by(chess.WHITE, b_king))

        # Do not allow a new check to appear for either side
        if (not w_attacked_orig and w_attacked_after) or (not b_attacked_orig and b_attacked_after):
            return False
        return True

    def _adjacent_squares_8(self, square):
        f, r = chess.square_file(square), chess.square_rank(square)
        for df in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if df == 0 and dr == 0:
                    continue
                nf, nr = f + df, r + dr
                if 0 <= nf <= 7 and 0 <= nr <= 7:
                    yield chess.square(nf, nr)

    # Helper
    def is_on_player_side(self, sq: chess.Square) -> bool:
        r = chess.square_rank(sq)  # 0..7
        if self.g.player_side == "white":
            return r <= 3
        return r >= 4

    def _player_color(self) -> bool:
        return chess.WHITE if self.g.player_side == "white" else chess.BLACK

    def _enemy_color(self) -> bool:
        return not self._player_color()

    def _is_player_owned_piece(self, sq: chess.Square) -> bool:
        p = self.g.board.piece_at(sq)
        return bool(p and p.color == self._player_color())

    def _is_enemy_piece(self, sq: chess.Square) -> bool:
        p = self.g.board.piece_at(sq)
        return bool(p and p.color == self._enemy_color())

    # Swap validation helpers (call these from your InputController swap logic)
    def is_valid_swap_first(self, square: chess.Square) -> bool:
        """First swap click: must be a player-owned piece on player side (not king)."""
        if not self.is_on_player_side(square):
            return False
        p = self.g.board.piece_at(square)
        if not p:
            return False
        if p.piece_type in (chess.KING, chess.PAWN):
            return False
        return p.color == self._player_color()

    def is_valid_swap_second(self, square: chess.Square) -> bool:
        """Second swap click: must be an enemy piece on player side (not king)."""
        if not self.is_on_player_side(square):
            return False
        p = self.g.board.piece_at(square)
        if not p:
            return False
        if p.piece_type in (chess.KING, chess.PAWN):
            return False
        return p.color == self._enemy_color()

    

    # --------------- main entry ---------------
    def activate_power(self, power, square, *, allow_spellbook=False):
        stage_id = self._stage_id()
        effects_on = self._effects_active()
        spellbook_spell_powers = {"Ice Blast", "Inspire Soldier", "Shadow Step", "Meteor Shower"}

        # Global gate: only inventory / toolbar powers are locked behind powers_unlocked.
        # Spell powers always pass through this gate, even though they reuse this executor.
        if not getattr(self.g, "powers_unlocked", False) and power not in spellbook_spell_powers:
            self.g.ui_state.send_feedback("Your powers are sealed.")
            return False

        # ---------------- bombs ----------------
        if power == "bombs":
            # Stage 1: bombs do not work (only if effects are active)
            if effects_on and stage_id == 1:
                self.g.ui_state.send_feedback("Bombs are inert on this map.")
                return False

            piece = self.g.board.piece_at(square)
            if not (piece and piece.piece_type == chess.PAWN):
                self.g.ui_state.send_feedback("No pawn to bomb here.")
                return False

            # Only bomb your side
            if not self.is_on_player_side(square):
                self.g.ui_state.send_feedback("You can only bomb on your side of the board.")
                return False

            # Primary blast safety: remove that pawn only
            if not self._removal_is_safe([square]):
                self.g.ui_state.send_feedback("This bomb is not allowed.")
                print("Bomb blocked - would cause a check.")
                return False

            # Commit primary bomb
            self.g.board.remove_piece_at(square)
            self.g.powerups["bombs"] -= 1
            self.g.audio.play_random("bomb")

            # Stage 2: splash damage to one random adjacent square as well
            if effects_on and stage_id == 2:
                candidates = list(self._adjacent_squares_8(square))
                random.shuffle(candidates)

                # pick the first safe adjacent square that contains a piece (not a king)
                picked = None
                for adj in candidates:
                    p = self.g.board.piece_at(adj)
                    if not p:
                        continue
                    if p.piece_type == chess.KING:
                        continue
                    if self._removal_is_safe([adj]):
                        picked = adj
                        break

                if picked is not None:
                    self.g.board.remove_piece_at(picked)
                    self.g.audio.play_random("bomb")
                    print(f"[Bomb Splash] Also destroyed at {self._square_name(picked)}")
                else:
                    print("[Bomb Splash] No safe adjacent target found; splash skipped.")

            self.g.board_manager.update_allowed_moves()
            return True

        # ---------------- freezes ----------------
        if power == "freezes":
            # Stage 5 and 8: freeze does not work
            if effects_on and stage_id in (5, 8):
                self.g.ui_state.send_feedback("The frost fizzles on this map.")
                return False

            # Stage 1 special: “Freezes last double”
            if effects_on and stage_id == 1 and self.g.board.move_stack:
                last = self.g.board.move_stack[-1]
                if self._chebyshev_move_len(last) == 2:
                    target_sq = last.to_square
                    target_pc = self.g.board.piece_at(target_sq)
                    if target_pc:
                        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
                        enemy_color = not player_color
                        if target_pc.color == enemy_color and target_pc.piece_type != chess.KING:
                            square = target_sq
                            print(f"[Freeze L1] Overriding target to last double at {self._square_name(square)}")

            # Player-side targeting rule
            if not self.is_on_player_side(square):
                self.g.ui_state.send_feedback("You can only target freezes on your side of the board.")
                return False

            piece = self.g.board.piece_at(square)
            if not piece:
                self.g.ui_state.send_feedback("No piece to freeze here.")
                return False

            if piece.piece_type == chess.KING:
                self.g.ui_state.send_feedback("Kings cannot be frozen!")
                print("[Freeze] Blocked - king target.")
                return False  # DO NOT consume

            player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
            enemy_color = not player_color

            if piece.color != enemy_color:
                self.g.ui_state.send_feedback("Cannot freeze your own units!")
                return False

            # Commit freeze
            self.g.frozen_squares[square] = 3
            self.g.powerups["freezes"] -= 1
            self.g.audio.play_random("freezes")

            # Empowered freeze: spill region can include EMPTY squares too
            if getattr(self.g.quests, "enable_empowered_freeze", False) is True and random.random() < (1.0 / 3.0):
                rank = chess.square_rank(square)
                file = chess.square_file(square)

                player_color = self._player_color()
                enemy_color = not player_color

                candidates = []
                for df in (-1, 0, 1):
                    for dr in (-1, 0, 1):
                        if df == 0 and dr == 0:
                            continue
                        nf, nr = file + df, rank + dr
                        if not (0 <= nf <= 7 and 0 <= nr <= 7):
                            continue
                        adj_sq = chess.square(nf, nr)

                        # Keep global "player-side-only" even for spill
                        if not self.is_on_player_side(adj_sq):
                            continue

                        p = self.g.board.piece_at(adj_sq)

                        # If occupied: must be enemy and not king
                        if p:
                            if p.piece_type == chess.KING:
                                continue
                            if p.color != enemy_color:
                                continue
                            candidates.append(adj_sq)
                        else:
                            # Empty squares allowed in spill
                            candidates.append(adj_sq)

                if candidates:
                    bonus_sq = random.choice(candidates)
                    self.g.frozen_squares[bonus_sq] = 3
                    self.g.audio.play_random("freezes")
                    print(f"[Freeze] Empowered: also froze {self._square_name(bonus_sq)} (3 turns).")
                else:
                    print("[Freeze] Empowered proc but no eligible adjacent targets.")


            self.g.board_manager.update_allowed_moves()
            return True

        # ---------------- shields ----------------
        if power == "shields":
            # Player-side targeting rule
            if not self.is_on_player_side(square):
                self.g.ui_state.send_feedback("You can only place shields on your side of the board.")
                return False

            piece = self.g.board.piece_at(square)
            if not piece:
                self.g.ui_state.send_feedback("You must shield one of your units.")
                return False

            player_color = self._player_color()
            if piece.color != player_color:
                self.g.ui_state.send_feedback("You can only shield your own units.")
                return False

            if piece.piece_type == chess.KING:
                self.g.ui_state.send_feedback("Kings cannot be shielded!")
                return False

            # Commit shield (selection must be a piece; the effect itself is square-based)
            self.g.shielded_squares[square] = 2
            self.g.powerups["shields"] -= 1
            self.g.audio.play_random("shields")

            self.g.board_manager.update_allowed_moves()
            return True


        # ---------------- advanced shields ----------------
        if power == "advanced_shields":
            # Player-side targeting rule (message should say "shields")
            if not self.is_on_player_side(square):
                self.g.ui_state.send_feedback("You can only place shields on your side of the board.")
                return False

            piece0 = self.g.board.piece_at(square)
            if not piece0:
                self.g.ui_state.send_feedback("You must shield one of your units.")
                return False

            player_color = self._player_color()
            if piece0.color != player_color:
                self.g.ui_state.send_feedback("You can only shield your own units.")
                return False

            if piece0.piece_type == chess.KING:
                self.g.ui_state.send_feedback("Kings cannot be shielded!")
                return False

            rank = chess.square_rank(square)
            file = chess.square_file(square)

            if getattr(self.g, "advanced_shield_kit", False):
                # Full 3×3 block
                offsets = [
                    (-1, -1), (0, -1), (1, -1),
                    (-1,  0), (0,  0), (1,  0),
                    (-1,  1), (0,  1), (1,  1),
                ]
            else:
                # Default = plus sign
                offsets = [(0, 0), (0, 1), (0, -1), (-1, 0), (1, 0)]

            applied = 0
            for df, dr in offsets:
                f, r = file + df, rank + dr
                if not (0 <= f < 8 and 0 <= r < 8):
                    continue
                sq = chess.square(f, r)

                # Keep your global “player side only” policy for applied spill squares too
                if not self.is_on_player_side(sq):
                    continue

                # Spill can include empty squares, but never kings
                p = self.g.board.piece_at(sq)
                if p and p.piece_type == chess.KING:
                    continue

                self.g.shielded_squares[sq] = 4
                applied += 1

            if not applied:
                self.g.ui_state.send_feedback("No valid squares to shield.")
                return False

            self.g.powerups["advanced_shields"] -= 1
            self.g.audio.play_random("advanced_shields")

            self.g.board_manager.update_allowed_moves()
            return True


        # ---------------- swaps ----------------
        if power == "swaps":
            # Swap logic requires 2 squares: handled in InputController
            return False

        # ---------------- promotions ----------------
        if power == "promotions":
            piece = self.g.board.piece_at(square)
            if not piece or piece.piece_type != chess.PAWN:
                self.g.ui_state.send_feedback("No pawn to promote here.")
                return False

            # Player-side restriction
            if not self.is_on_player_side(square):
                self.g.ui_state.send_feedback("You can only promote on your side of the board.")
                return False

            player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
            if piece.color != player_color:
                self.g.ui_state.send_feedback("You can only promote your own pawn.")
                return False

            # Safety: simulate promotion and ensure it doesn't newly create check
            test_board = self.g.board.copy(stack=False)
            test_board.set_piece_at(square, chess.Piece(chess.QUEEN, piece.color))

            w_king = test_board.king(chess.WHITE)
            b_king = test_board.king(chess.BLACK)
            white_check_after = bool(w_king and test_board.is_attacked_by(chess.BLACK, w_king))
            black_check_after = bool(b_king and test_board.is_attacked_by(chess.WHITE, b_king))

            base = self.g.board
            w_king0 = base.king(chess.WHITE)
            b_king0 = base.king(chess.BLACK)
            white_check_before = bool(w_king0 and base.is_attacked_by(chess.BLACK, w_king0))
            black_check_before = bool(b_king0 and base.is_attacked_by(chess.WHITE, b_king0))

            if (not white_check_before and white_check_after) or (not black_check_before and black_check_after):
                self.g.ui_state.send_feedback("This promotion is not allowed.")
                print("Promotion blocked - would cause a check.")
                return False

            # Commit promotion
            self.g.board.set_piece_at(square, chess.Piece(chess.QUEEN, piece.color))
            self.g.powerups["promotions"] -= 1
            self.g.used_promotion_power = True
            self.g.audio.play_random("promotion")
            print("Promotion performed!")

            self.g.board_manager.update_allowed_moves()
            return True

        # ---------------- magnets ----------------
        if power == "magnets":
            if not self.is_on_player_side(square):
                self.g.ui_state.send_feedback("You can only place magnets on your side of the board.")
                return False
            if square in self.g.frozen_squares or square in self.g.shielded_squares:
                self.g.ui_state.send_feedback("Magnets cannot be placed on frozen or shielded squares.")
                return False

            self.g.magnet_square = square
            self.g.powerups["magnets"] -= 1
            self.g.audio.play_random("magnet")
            print(f"Magnet activated at {self._square_name(square)}!")

            self.g.board_manager.update_allowed_moves()
            return True

        # ---------------- Shadow Step + spell-powers ----------------
        if power == "Shadow Step" and (
            getattr(self.g, "shadow_step_active", False)
            or getattr(self.g, "selected_power", None) == "Shadow Step"
            or allow_spellbook
        ):
            if self.g.board.piece_at(square) is not None:
                print(f"Shadow Step failed: {self._square_name(square)} is occupied.")
                self.g.ui_state.send_feedback("That square is occupied.")
                return False

            player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
            enemy_color = not player_color
            king_sq = self.g.board.king(player_color)
            if king_sq is None:
                self.g.ui_state.send_feedback("Your king is missing!")
                print("Shadow Step failed: player king not found.")
                return False

            def shadow_step_legal(dest_sq: chess.Square) -> bool:
                # 1) cannot jump next to enemy king
                enemy_king = self.g.board.king(enemy_color)
                if enemy_king is not None:
                    df = abs(chess.square_file(dest_sq) - chess.square_file(enemy_king))
                    dr = abs(chess.square_rank(dest_sq) - chess.square_rank(enemy_king))
                    if max(df, dr) == 1:
                        return False
                # 2) cannot leave own king in check
                test_board = self.g.board.copy(stack=False)
                test_board.remove_piece_at(king_sq)
                test_board.set_piece_at(dest_sq, chess.Piece(chess.KING, player_color))
                return not test_board.is_attacked_by(enemy_color, dest_sq)

            if not shadow_step_legal(square):
                self.g.ui_state.send_feedback("That shadow step is not allowed.")
                print("Shadow Step blocked - unsafe destination.")
                return False

            # perform teleport
            piece = self.g.board.remove_piece_at(king_sq)
            self.g.board.set_piece_at(square, piece)
            self.g.board.turn = not self.g.board.turn

            print(f"Shadow Step: King teleported to {self._square_name(square)}")

            self.g.shadow_step_active = False
            self.g.selected_power = None
            self.g.selected_spell = None
            self.g.board_manager.collect_gold()
            if "Shadow Step" in self.g.spellbook:
                self.g.spellbook.remove("Shadow Step")
                self.g._spell_cache_dirty = True

            self.g.board_manager.update_allowed_moves()
            return True

        if power == "Ice Blast":
            used = bool(self.g.cast_spells.cast_ice_blast(square))
            if used:
                self.g.board_manager.update_allowed_moves()
            return used

        if power == "Inspire Soldier":
            used = bool(self.g.cast_spells.cast_inspire_soldier(square))
            if used:
                self.g.board_manager.update_allowed_moves()
            return used

        if power == "Meteor Shower" and getattr(self.g, "meteor_active", False):
            used = bool(self.g.cast_spells.cast_meteor_shower(square))
            if used:
                self.g.board_manager.update_allowed_moves()
            return used

        # Unknown / not handled here
        return False


    def initialize_empty_powerups(self):
        powerup_names = [
            "bombs",
            "freezes",
            "swaps",
            "shields",
            "advanced_shields",
            "promotions",
            "time_warps",
            "magnets",
        ]
        self.g.powerups = {name: 0 for name in powerup_names}
        self.g.power_icons = self.g.assets.load_power_icons()
        self.g.advanced_shield_kit = False
