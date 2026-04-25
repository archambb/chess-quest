# cast_spells.py
import random
import itertools

import pygame                 # uses pygame.time.get_ticks()
import chess                  # chess.Board, chess.Piece, chess.square, etc.
import chess.engine           # needed for chess.engine.Limit(...) -- TODO: We'll pull this one out later
import config                 # MFX_* constants, sizes, etc.


class CastSpells:
    def __init__(self, game):
        self.g = game

    def cast_flood(self, centre_square: chess.Square) -> bool:
        """
        Flood:
            • Kills pawns on the target square and the four orthogonal neighbours.
            • Freezes every non-pawn piece on those same squares (friend or foe).
            • Plays a dark-blue “wave” overlay that fades in, then out.
        """
        if not self.g.powers.is_on_player_side(centre_square):
            return False
        
        row = chess.square_rank(centre_square)

        if (self.g.player_side == "white" and row > 3) or (self.g.player_side == "black" and row < 4):
            print("Flood can only be cast on your half of the board.")
            self.g.ui_state.send_feedback("You can only flood your half!")
            return False
        # --- 1. determine affected squares --------------------------------------
        offsets = [(0, 0), (1, 0), (-1, 0), (0, 1), (0, -1)]
        cx, cy = chess.square_file(centre_square), chess.square_rank(centre_square)

        affected = []
        for dx, dy in offsets:
            x, y = cx + dx, cy + dy
            if 0 <= x < 8 and 0 <= y < 8:
                affected.append(chess.square(x, y))

        # --- 2. apply the effects ----------------------------------------------
        FREEZE_TURNS = 2            # tweak to taste (uses your normal decrementer)
        for sq in affected:
            piece = self.g.board.piece_at(sq)
            if piece is None:
                continue

            if piece.piece_type == chess.PAWN:
                self.g.quests.record_captured_piece(piece, count_for_quests=True)
                self.g.board.remove_piece_at(sq)                     # drown the pawn
                # optional: play splash SFX here
            else:
                # freeze : store turn counter in the same dict you use elsewhere
                self.g.frozen_squares[sq] = FREEZE_TURNS
                # optional: play ice-crack SFX here

        # --- 3. queue the blue overlay animation -------------------------------
        # Keep it simple: just record a transient animation state; your main
        # draw() loop can fade alpha from 0→180→0 over, say, 30 frames.
        self.g.flood_animations.append(
            {
                "squares": affected,
                "alpha":   0,
                "direction": 1   # 1 = fade-in, −1 = fade-out
            }
        )

        if "Flood" in self.g.spellbook:
            self.g.spellbook.remove("Flood")
        self.g.selected_spell = None
        self.g.flood_spell_active = False
        return True

    def cast_summon_elf(self) -> None:
        """
        Summons a friendly bishop adjacent to your king, but ONLY if doing so
        does not put the opponent's king in check. If no safe square exists the
        spell fails and no power is consumed.
        """

        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        enemy_color  = not player_color

        king_sq = self.g.board.king(player_color)
        if king_sq is None:
            self.g.ui_state.send_feedback("Your king is missing!")
            return

        # All empty squares around the king (8-neighbourhood)
        candidate_squares = []
        k_file, k_rank = chess.square_file(king_sq), chess.square_rank(king_sq)
        if not self.g.powers.is_on_player_side(chess.square(k_file, k_rank)):
            self.g.ui_state.send_feedback("Your king is too far away.")
            return
        
        for df in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if df == 0 and dr == 0:
                    continue
                f, r = k_file + df, k_rank + dr
                if 0 <= f < 8 and 0 <= r < 8:
                    sq = chess.square(f, r)
                    if self.g.board.piece_at(sq) is None:
                        candidate_squares.append(sq)

        random.shuffle(candidate_squares)        # randomise landing order
        safe_square = None

        for sq in candidate_squares:
            test_board = self.g.board.copy(stack=False)
            test_board.set_piece_at(sq, chess.Piece(chess.BISHOP, player_color))

            enemy_king_sq = test_board.king(enemy_color)
            # Will the bishop (or any other piece) give check?
            if enemy_king_sq and test_board.is_attacked_by(player_color, enemy_king_sq):
                continue  # unsafe - try next square
            safe_square = sq
            break

        if safe_square is None:
            # Spell fails
            self.g.ui_state.send_feedback(
                "You cannot summon an elf now because it would put the opponent into an immediate check."
            )
            print("[Summon Elf] No safe square found - spell aborted.")
            return

        # --- Commit the summon on the real board -----------------------
        self.g.board.set_piece_at(safe_square, chess.Piece(chess.BISHOP, player_color))
        print(f"Summoned elf (bishop) at {chess.square_name(safe_square)}.")

        # Remove spell from spellbook and reset selection
        if "Summon Elf" in self.g.spellbook:
            self.g.spellbook.remove("Summon Elf")
        self.g.selected_spell = None
        self.g.selected_power = None
        return True
        self.g.board_manager.collect_gold()


    def cast_summon_undead_elves(self) -> bool:
        """
        Summon Undead Elves:
            • Restores missing friendly bishops (up to 2 total bishops).
            • Places them on empty squares adjacent to your king.
            • Never places a bishop if doing so would introduce a NEW check.
            • Consumes the spell only if at least one bishop is summoned.
        """
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        king_sq = self.g.board.king(player_color)

        if king_sq is None:
            self.g.ui_state.send_feedback("Your king is missing!")
            return False

        if not self.g.powers.is_on_player_side(king_sq):
            self.g.ui_state.send_feedback("Your king is too far away.")
            return False

        current_bishops = self._piece_squares(self.g.board, player_color, chess.BISHOP)
        missing_bishops = 2 - len(current_bishops)

        if missing_bishops <= 0:
            self.g.ui_state.send_feedback("Your bishops still stand—no undead elves to summon.")
            return False

        empty_adjacent = self._empty_adjacent_squares(king_sq)
        if not empty_adjacent:
            self.g.ui_state.send_feedback("No empty space adjacent to your king.")
            return False

        random.shuffle(empty_adjacent)

        working_board = self.g.board.copy(stack=False)
        summoned = 0

        for sq in empty_adjacent:
            if summoned >= missing_bishops:
                break

            test_board = working_board.copy(stack=False)
            test_board.set_piece_at(sq, chess.Piece(chess.BISHOP, player_color))

            if self._would_introduce_new_check(test_board, baseline_board=working_board):
                continue

            working_board = test_board
            summoned += 1
            print(f"[Summon Undead Elves] Bishop summoned at {chess.square_name(sq)}")

        if summoned == 0:
            self.g.ui_state.send_feedback(
                "You cannot summon undead elves now—it would put a king in check."
            )
            print("[Summon Undead Elves] No safe squares found.")
            return False

        self.g.board = working_board

        if "Summon Undead Elves" in self.g.spellbook:
            self.g.spellbook.remove("Summon Undead Elves")
            self.g._spell_cache_dirty = True

        self.g.selected_spell = None
        self.g.selected_power = None
        self.g.board_manager.collect_gold()
        self.g.ui_state.send_feedback(f"Summoned {summoned} undead elf{'ves' if summoned != 1 else ''}.")
        return True


    def cast_ice_blast(self, target_square, duration=3) -> bool:
        """
        Freeze an entire file (column) for `duration` full turns.
        `target_square` is any square in the column the player clicked.
        """
        if not self.g.powers.is_on_player_side(target_square):
            return False
        
        file_idx = chess.square_file(target_square)
        frozen_now = []

        for rank in range(8):                      # ranks 0..7
            sq = chess.square(file_idx, rank)
            # You can skip pawns if you only want to freeze non-pawns:
            # piece = self.g.board.piece_at(sq)
            # if piece and piece.piece_type == chess.PAWN:
            #     continue
            self.g.frozen_squares[sq] = duration
            frozen_now.append(chess.square_name(sq))

        print(f"[CAST] Ice Blast: froze file {chr(file_idx + ord('a'))} "
            f"for {duration} turn(s): {', '.join(frozen_now)}")

        # remove spell from book & clear targeting
        if "Ice Blast" in self.g.spellbook:
            self.g.spellbook.remove("Ice Blast")
        self.g.selected_spell = None
        self.g.selected_power = None
        return True

    def cast_wind_storm(self):
        moved = []
        for rank in range(8):
            for file in reversed(range(7)):  # right to left, avoid file 7
                from_sq = chess.square(file, rank)
                to_sq = chess.square(file + 1, rank)

                piece = self.g.board.piece_at(from_sq)
                if piece is None:
                    continue

                if self.g.board.piece_at(to_sq) is None:
                    self.g.board.set_piece_at(to_sq, piece)
                    self.g.board.remove_piece_at(from_sq)
                    moved.append((chess.square_name(from_sq), chess.square_name(to_sq)))

        print(f"[CAST] Wind Storm moved {len(moved)} pieces:")
        for f, t in moved:
            print(f" - {f} → {t}")
        self.g.board_manager.collect_gold()
        # Optionally remove from spellbook or limit uses
        if "Wind Storm" in self.g.spellbook:
            self.g.spellbook.remove("Wind Storm")
        self.g.selected_spell = None
        
    def cast_desert_sun(self):
        if not self.g.frozen_squares:
            print("[CAST] Desert Sun: No frozen pieces to thaw.")
            return

        thawed = list(self.g.frozen_squares.keys())
        self.g.frozen_squares.clear()

        print(f"[CAST] Desert Sun thawed {len(thawed)} square(s):")
        for sq in thawed:
            print(f" - {chess.square_name(sq)}")

        # Optional: Remove spell or reset state
        if "Desert Sun" in self.g.spellbook:
            self.g.spellbook.remove("Desert Sun")
        self.g.selected_spell = None


    def cast_inspire_soldier(self, target_square) -> bool:
        if not self.g.powers.is_on_player_side(target_square):
            return False
        piece = self.g.board.piece_at(target_square)
        if not piece:
            print(f"[CAST] Inspire Soldier failed: No piece at {chess.square_name(target_square)}")
            self.g.ui_state.send_feedback("Choose one of your pawns.")
            return False

        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK

        if piece.piece_type != chess.PAWN or piece.color != player_color:
            print(f"[CAST] Inspire Soldier failed: Invalid target at {chess.square_name(target_square)}")
            self.g.ui_state.send_feedback("Choose one of your pawns.")
            return False

        self.g.board.remove_piece_at(target_square)
        self.g.board.set_piece_at(target_square, chess.Piece(chess.KNIGHT, player_color))
        print(f"[CAST] Inspire Soldier: Promoted pawn at {chess.square_name(target_square)} to knight.")

        if "Inspire Soldier" in self.g.spellbook:
            self.g.spellbook.remove("Inspire Soldier")
        self.g.selected_spell = None
        self.g.selected_power = None
        return True

    def cast_orb_of_premonition(self):
        try:
            result = self.g.engine.analyse(self.g.board, chess.engine.Limit(time=0.5))
            best_move = result.get("pv", [None])[0]

            if best_move:
                move_uci = best_move.uci()
                move_san = self.g.board.san(best_move)
                self.g.ui_state.send_feedback(f"The Orb reveals: {move_san} ({move_uci})")
                self.g.orb_highlight_squares = [best_move.from_square, best_move.to_square]
                self.g.orb_pulse_alpha = 60
                self.g.orb_pulse_direction = 1
            else:
                self.g.ui_state.send_feedback("The Orb sees no future… no legal moves found.")
                self.g.orb_highlight_squares = []
        except Exception as e:
            print(f"[ERROR] Orb of Premonition failed: {e}")
            self.g.ui_state.send_feedback("The Orb flickers in confusion. Something went wrong.")
            self.g.orb_highlight_squares = []
        
        if "Orb of Premonition" in self.g.spellbook:
            self.g.spellbook.remove("Orb of Premonition")
        self.g.selected_spell = None
        self.g.selected_power = None
        return True


    def cast_heal_pawns(self):
        """
        Restores missing pawns for the current player,
        but never places one that would put either king in check.
        Only spends the spell if at least one pawn is successfully placed.
        """
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        pawn_rank = 1 if player_color == chess.WHITE else 6
        pawn_type = chess.PAWN

        # Count how many pawns we already have
        current_pawns = [
            sq for sq, piece in self.g.board.piece_map().items()
            if piece.color == player_color and piece.piece_type == pawn_type
        ]
        pawns_needed = 8 - len(current_pawns)
        if pawns_needed <= 0:
            print("Heal Pawns: Already at max pawns.")
            self.g.ui_state.send_feedback("Heal Pawns: You already have all of your pawns.")
            return False

        preferred_files = [3, 4, 2, 5, 1, 6, 0, 7]  # d, e, c, f, b, g, a, h
        placed = 0

        for file in preferred_files:
            if placed >= pawns_needed:
                break

            sq = chess.square(file, pawn_rank)
            if self.g.board.piece_at(sq):
                continue

            # Simulate on a test board
            test_board = self.g.board.copy(stack=False)
            test_board.set_piece_at(sq, chess.Piece(pawn_type, player_color))

            white_king = test_board.king(chess.WHITE)
            black_king = test_board.king(chess.BLACK)

            white_safe = (
                white_king is None or
                not test_board.is_attacked_by(chess.BLACK, white_king)
            )
            black_safe = (
                black_king is None or
                not test_board.is_attacked_by(chess.WHITE, black_king)
            )

            if white_safe and black_safe:
                self.g.board.set_piece_at(sq, chess.Piece(pawn_type, player_color))
                placed += 1
                print(f"Healed pawn placed at {chess.square_name(sq)}")
            else:
                print(f"Skipped {chess.square_name(sq)} - unsafe for king(s).")

        if placed == 0:
            self.g.ui_state.send_feedback("Heal Pawns: No safe squares to place pawns.")
            return False

        if "Heal Pawns" in self.g.spellbook:
            self.g.spellbook.remove("Heal Pawns")
            self.g._spell_cache_dirty = True

        self.g.selected_spell = None
        self.g.selected_power = None
        self.g.ui_state.send_feedback(f"Heal Pawns: Placed {placed} pawn(s).")
        self.g.board_manager.collect_gold()
        return True


    def cast_sacrifice(self):
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        for square, piece in self.g.board.piece_map().items():
            if piece.piece_type == chess.QUEEN and piece.color == player_color:
                self.g.quests.record_captured_piece(piece, count_for_quests=True)
                self.g.board.remove_piece_at(square)
                self.g.powerups["promotions"] += 2
                if "Sacrifice" in self.g.spellbook:
                    self.g.spellbook.remove("Sacrifice")
                    self.g._spell_cache_dirty = True
                print(f"Sacrifice: Queen removed from {chess.square_name(square)}. +2 promotion points.")
                return True

        self.g.ui_state.send_feedback("Sacrifice failed: No queen found.")
        print("Sacrifice failed: No queen found.")
        return False


    def cast_one_with_light(self):
        if self.g.player_side != "white":
            print("Casting One With Light: switching to white side.")
            self.g.player_side = "white"

            # If it's black's turn, let black (AI) move before giving control to white
            if self.g.board.turn == chess.BLACK:
                print("Forcing black (AI) move before switching.")
                try:
                    result = self.g.engine.play(self.g.board, chess.engine.Limit(time=0.1))
                    move = result.move
                    if move:
                        piece = self.g.board.piece_at(move.from_square)
                        self.g.board.push(move)
                        self.g.quests.update_quest_variables(piece=piece, move=move, player=False)
                        self.g._clear_king_protections()
                except Exception as e:
                    print(f"[ERROR] Failed to let black move before switch: {e}")

            # Regardless, ensure it's now white’s turn
            self.g.board.turn = chess.WHITE
            self.g.PIECE_IMAGES = self.g.assets.load_piece_images()
            self.g.selected_square = None
            self.g.board_manager.update_allowed_moves()
            print("Player is now white.")
            self.g.ui_state.send_feedback("You are now One With Light.")

            if "One With Light" in self.g.spellbook:
                self.g.spellbook.remove("One With Light")
            self.g.selected_spell = None
            self.g.board_manager.collect_gold()
        else:
            print("Player is already white. Spell has no effect.")


    def cast_greed(self):
        if not self.g.gold_pieces:
            self.g.ui_state.send_feedback("No gold to covet!")
            return
        self.g.greed_active = True
        self.g.ui_state.send_feedback("Greed: the foe will chase gold…")
        if "Greed" in self.g.spellbook:
            self.g.spellbook.remove("Greed")
        self.g.selected_spell = None

    # Random meteors fall that will not hit the king or cause a check situation
    def cast_meteor_shower(self, square: chess.Square) -> bool:
        """
        Call this when the player selects a board square to choose the quadrant
        for Meteor Shower. The meteors will:
        • avoid kings
        • not introduce NEW checks
        """
        if not self.g.powers.is_on_player_side(square):
            return False
        # ------------------------------------------------------------
        # 1.  Quadrant bookkeeping
        # ------------------------------------------------------------
        col, row = chess.square_file(square), chess.square_rank(square)
        qx, qy   = col // 4, row // 4                 # 0‒1 each
        self.g.meteor_quadrant = qy * 2 + qx
        self.g.selected_spell  = None
        self.g.meteor_active   = False

        files  = range(qx * 4, qx * 4 + 4)
        ranks  = range(qy * 4, qy * 4 + 4)
        pool   = [chess.square(f, r) for f, r in itertools.product(files, ranks)]
        random.shuffle(pool)

        # ------------------------------------------------------------
        # 2.  Baseline check status BEFORE any meteors
        # ------------------------------------------------------------
        w_king_sq = self.g.board.king(chess.WHITE)
        b_king_sq = self.g.board.king(chess.BLACK)

        white_in_check_initial = (
            w_king_sq is not None and
            self.g.board.is_attacked_by(chess.BLACK, w_king_sq)
        )
        black_in_check_initial = (
            b_king_sq is not None and
            self.g.board.is_attacked_by(chess.WHITE, b_king_sq)
        )

        # We'll iteratively build up a working copy with accepted strikes
        working_board = self.g.board.copy(stack=False)
        targets       = []

        # ------------------------------------------------------
    
        # 3.  Select up to four safe target squares
        # ------------------------------------------------------------
        for sq in pool:
            if len(targets) >= 4:
                break

            piece = working_board.piece_at(sq)
            if piece and piece.piece_type == chess.KING:
                continue  # never drop on a king

            # Simulate strike on a fresh copy of the current working board
            test_board = working_board.copy(stack=False)
            test_board.remove_piece_at(sq)

            # Post-strike check status
            w_in_check_after = (
                w_king_sq is not None and
                test_board.is_attacked_by(chess.BLACK, w_king_sq)
            )
            b_in_check_after = (
                b_king_sq is not None and
                test_board.is_attacked_by(chess.WHITE, b_king_sq)
            )

            illegal = (
                (not white_in_check_initial and w_in_check_after) or
                (not black_in_check_initial and b_in_check_after)
            )
            if illegal:
                continue  # this square would introduce a NEW check

            # Accept the target
            targets.append(sq)
            working_board = test_board  # accumulate removal for next iterations

        # ------------------------------------------------------------
        # 4.  Abort if no valid squares
        # ------------------------------------------------------------
        if not targets:
            self.g.ui_state.send_feedback(
                "The meteor shower fizzles—no safe places to strike!"
            )
            print("[Meteor Shower] No valid targets; spell failed.")
            return False

        # ------------------------------------------------------------
        # 5.  Spawn meteors on each approved square
        # ------------------------------------------------------------
        for sq in targets:
            file  = chess.square_file(sq)
            rank  = chess.square_rank(sq)

            square_x = self.g.board_origin_x + file * config.SQUARE_SIZE
            square_y = self.g.board_origin_y + (7 - rank) * config.SQUARE_SIZE

            # centre the sprite
            fw, fh  = self.g.magic_library[config.MFX_METEOR]["frames"][0].get_size()
            dest_x  = square_x + (config.SQUARE_SIZE - fw) // 2
            dest_y  = square_y + (config.SQUARE_SIZE - fh) // 2

            start_x = dest_x + random.randint(-20, 20)
            start_y = -fh
            eid     = f"meteor_{sq}_{pygame.time.get_ticks()}"

            self.g.renderer.display_magic_effect(
                eid, config.MFX_METEOR,
                start_x, start_y,
                dest_x, dest_y,
                duration=30
            )
            self.g.meteor_target_queue.append((eid, 30, sq))

        # ------------------------------------------------------------
        # 6.  Consume the spell
        # ------------------------------------------------------------
        if "Meteor Shower" in self.g.spellbook:
            self.g.spellbook.remove("Meteor Shower")
        self.g.selected_spell = None
        return True


    def cast_granite_elf(self, target_square: chess.Square) -> bool:
        """
        Granite Elf:
            • Target one of your bishops.
            • Turns that bishop into a rook.
            • Fails if that transformation would introduce a NEW check.
        """
        if not self.g.powers.is_on_player_side(target_square):
            return False

        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        piece = self.g.board.piece_at(target_square)

        if piece is None:
            self.g.ui_state.send_feedback("Choose one of your bishops.")
            return False

        if piece.color != player_color or piece.piece_type != chess.BISHOP:
            self.g.ui_state.send_feedback("Granite Elf must target one of your bishops.")
            return False

        test_board = self.g.board.copy(stack=False)
        test_board.set_piece_at(target_square, chess.Piece(chess.ROOK, player_color))

        if self._would_introduce_new_check(test_board):
            self.g.ui_state.send_feedback(
                "Granite Elf cannot be cast there because it would put a king in check."
            )
            return False

        self.g.board.set_piece_at(target_square, chess.Piece(chess.ROOK, player_color))
        print(f"[CAST] Granite Elf: bishop at {chess.square_name(target_square)} became a rook.")

        if "Granite Elf" in self.g.spellbook:
            self.g.spellbook.remove("Granite Elf")
            self.g._spell_cache_dirty = True

        self.g.selected_spell = None
        self.g.selected_power = None
        self.g.board_manager.collect_gold()
        return True

    def cast_mirror_armies(self) -> bool:
        """
        Mirror Armies:
            • Makes white and black have the same counts of each non-king piece type.
            • Never adds pieces, only removes extras.
            • Extra pieces are removed randomly.
            • If a candidate removal would introduce a NEW check, it is skipped.
            • Piece types handled: pawn, knight, bishop, rook, queen.
        """
        piece_types = [
            chess.PAWN,
            chess.KNIGHT,
            chess.BISHOP,
            chess.ROOK,
            chess.QUEEN,
        ]

        type_names = {
            chess.PAWN: "pawn",
            chess.KNIGHT: "knight",
            chess.BISHOP: "bishop",
            chess.ROOK: "rook",
            chess.QUEEN: "queen",
        }

        working_board = self.g.board.copy(stack=False)
        removed_summary = []
        removed_pieces = []

        for piece_type in piece_types:
            white_squares = self._piece_squares(working_board, chess.WHITE, piece_type)
            black_squares = self._piece_squares(working_board, chess.BLACK, piece_type)

            white_count = len(white_squares)
            black_count = len(black_squares)

            if white_count == black_count:
                continue

            if white_count > black_count:
                side_to_trim = chess.WHITE
                trim_count = white_count - black_count
                candidate_squares = white_squares[:]
            else:
                side_to_trim = chess.BLACK
                trim_count = black_count - white_count
                candidate_squares = black_squares[:]

            random.shuffle(candidate_squares)

            removed_this_type = 0
            attempted = set()

            # Keep trying until we either remove enough or run out of candidates
            while removed_this_type < trim_count and len(attempted) < len(candidate_squares):
                remaining_candidates = [sq for sq in candidate_squares if sq not in attempted]
                if not remaining_candidates:
                    break

                sq = random.choice(remaining_candidates)
                attempted.add(sq)

                removed_piece = working_board.piece_at(sq)
                test_board = working_board.copy(stack=False)
                test_board.remove_piece_at(sq)

                if self._would_introduce_new_check(test_board, baseline_board=working_board):
                    continue

                working_board = test_board
                removed_this_type += 1
                if removed_piece:
                    removed_pieces.append(removed_piece)
                removed_summary.append(
                    f"{'White' if side_to_trim == chess.WHITE else 'Black'} "
                    f"{type_names[piece_type]} removed from {chess.square_name(sq)}"
                )

            if removed_this_type < trim_count:
                print(
                    f"[Mirror Armies] Could not safely remove all extra "
                    f"{type_names[piece_type]}s "
                    f"({removed_this_type}/{trim_count} removed)."
                )

        # Did anything actually change?
        if working_board.board_fen() == self.g.board.board_fen():
            self.g.ui_state.send_feedback("Mirror Armies found no safe changes to make.")
            print("[Mirror Armies] No safe removals performed.")
            return False

        self.g.board = working_board
        for removed_piece in removed_pieces:
            self.g.quests.record_captured_piece(removed_piece, count_for_quests=True)

        print("[CAST] Mirror Armies results:")
        for line in removed_summary:
            print(" -", line)

        if "Force Mirror" in self.g.spellbook:
            self.g.spellbook.remove("Force Mirror")
            self.g._spell_cache_dirty = True

        self.g.selected_spell = None
        self.g.selected_power = None
        self.g.board_manager.collect_gold()

        if removed_summary:
            self.g.ui_state.send_feedback(f"Mirror Armies removed {len(removed_summary)} piece(s).")
        else:
            self.g.ui_state.send_feedback("Mirror Armies completed, but no pieces were removed.")

        return True

    def _would_introduce_new_check(self, test_board: chess.Board, baseline_board: chess.Board | None = None) -> bool:
        """
        Returns True if test_board introduces a NEW check for either side
        compared to baseline_board. Existing checks are tolerated.
        """
        base = baseline_board or self.g.board

        w_king_base = base.king(chess.WHITE)
        b_king_base = base.king(chess.BLACK)
        w_king_test = test_board.king(chess.WHITE)
        b_king_test = test_board.king(chess.BLACK)

        white_in_check_before = (
            w_king_base is not None and
            base.is_attacked_by(chess.BLACK, w_king_base)
        )
        black_in_check_before = (
            b_king_base is not None and
            base.is_attacked_by(chess.WHITE, b_king_base)
        )

        white_in_check_after = (
            w_king_test is not None and
            test_board.is_attacked_by(chess.BLACK, w_king_test)
        )
        black_in_check_after = (
            b_king_test is not None and
            test_board.is_attacked_by(chess.WHITE, b_king_test)
        )

        return (
            (not white_in_check_before and white_in_check_after) or
            (not black_in_check_before and black_in_check_after)
        )

    def _empty_adjacent_squares(self, square: chess.Square) -> list[chess.Square]:
        """Return empty squares in the 8-neighbourhood around `square`."""
        result = []
        file_ = chess.square_file(square)
        rank_ = chess.square_rank(square)

        for df in (-1, 0, 1):
            for dr in (-1, 0, 1):
                if df == 0 and dr == 0:
                    continue
                f = file_ + df
                r = rank_ + dr
                if 0 <= f < 8 and 0 <= r < 8:
                    sq = chess.square(f, r)
                    if self.g.board.piece_at(sq) is None:
                        result.append(sq)
        return result

    def _piece_squares(self, board: chess.Board, color: chess.Color, piece_type: chess.PieceType) -> list[chess.Square]:
        return [
            sq for sq, piece in board.piece_map().items()
            if piece.color == color and piece.piece_type == piece_type
        ]            
