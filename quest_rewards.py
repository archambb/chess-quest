# quest_rewards.py

import random
import pygame
import chess
import math
from collections import deque


class QuestRewardHandler:
    def __init__(self, game):
        self.g = game

        # --- Reward presentation queue ---
        self.reward_win_queue = deque()
        self.active_reward_card = None
        self.active_reward_started_ms = 0

        # Tune these as needed
        self.reward_card_duration_ms = 2200
        self.reward_card_gap_ms = 250

    def give_reward(self, quest_num, reward, display_index=None):
        # 1) Apply gameplay effect immediately
        self._apply_reward(reward)

        # 2) Queue presentation so multiple rewards serialize nicely
        self.enqueue_reward_card(quest_num, reward, display_index=display_index)

    # ------------------------------------------------------------------
    # REWARD CARD QUEUE
    # ------------------------------------------------------------------

    def enqueue_reward_card(self, quest_num, reward, display_index=None):
        """
        Queue a reward presentation card instead of showing it immediately.
        """
        self.reward_win_queue.append({
            "quest_num": quest_num,
            "reward": reward,
            "display_index": display_index,
        })

    def update_reward_queue(self):
        """
        Call once per frame from your main update/tick loop.
        Controls when reward cards start/end and advances the queue.
        """
        now = pygame.time.get_ticks()

        # If a card is currently active, see whether it's done
        if self.active_reward_card is not None:
            elapsed = now - self.active_reward_started_ms

            # If you have renderer/effects state that can tell you animation is done,
            # you can also check that here instead of only using time.
            if elapsed >= self.reward_card_duration_ms:
                self.active_reward_card = None
                self.active_reward_started_ms = now + self.reward_card_gap_ms
            return

        # Optional small delay between cards
        if self.active_reward_started_ms and now < self.active_reward_started_ms:
            return

        # Start next queued reward
        if self.reward_win_queue:
            self.active_reward_card = self.reward_win_queue.popleft()
            self.active_reward_started_ms = now
            self._start_reward_card_animation(self.active_reward_card)

    def _start_reward_card_animation(self, card_data):
        """
        Trigger sound / particles / animation setup for the active reward card.
        Keep this lightweight: it should START the presentation, not block.
        """
        quest_num = card_data["quest_num"]
        reward = card_data["reward"]

        print(f"[QuestReward] Showing queued reward card for quest {quest_num}: {reward}")

        # Example sound hook
        try:
            if hasattr(self.g, "audio"):
                self.g.audio.play_random("quest_win")
        except Exception:
            pass

        # Optional: kick off a UI/effect animation if you already have one
        # Example:
        # try:
        #     self.g.effects.start_reward_card_animation(quest_num, reward)
        # except Exception:
        #     pass

    def has_active_reward_card(self):
        return self.active_reward_card is not None

    def get_active_reward_card(self):
        return self.active_reward_card

    def clear_reward_queue(self):
        self.reward_win_queue.clear()
        self.active_reward_card = None
        self.active_reward_started_ms = 0

    def format_reward_text(self, reward):
        """
        Convert reward dict into user-facing text lines for the reward card UI.
        """
        lines = []
        for key, value in reward.items():
            label = key.replace("_", " ").title()
            if value is None or value == "":
                lines.append(label)
            elif value is True:
                lines.append(label)
            else:
                lines.append(f"{label}: {value}")
        return lines

    # ------------------------------------------------------------------
    # REWARD APPLICATION
    # ------------------------------------------------------------------

    def _apply_reward(self, reward):
        for key, value in reward.items():
            method = getattr(self, f"_reward_{key.lower().replace(' ', '_')}", None)
            if method:
                method(value)
            else:
                print(f"[QuestReward] ⚠️ Unknown reward type: {key}")

    # ───── REWARD ACTIONS ─────

    def _reward_gold(self, amount):
        self.g.player_gold += amount

    def _reward_promotions(self, count):
        self._grant_power("promotions", count)

    def _reward_time_warps(self, count):
        self._grant_power("time_warps", count)

    def _reward_swaps(self, count):
        self._grant_power("swaps", count)

    def _reward_shields(self, count):
        self._grant_power("shields", count)

    def _reward_freezes(self, count):
        self._grant_power("freezes", count)

    def _reward_advanced_shields(self, count):
        self._grant_power("advanced_shields", count)

    def _reward_bombs(self, count):
        self._grant_power("bombs", count)

    def _reward_magnets(self, count):
        self._grant_power("magnets", count)

    def _reward_spell_refresh(self, _):
        self.g.spellbook = list(self.g.spellbook_master)

    def _reward_double_gold(self, _):
        self.g.player_gold *= 2
        print(f"[QuestReward] Gold doubled to {self.g.player_gold}")

    def _reward_pawns_to_knights(self, _):
        self.transform_pawns_to_knights()
        print("[QuestReward] Player pawns transformed to knights")

    def _reward_steal_promotion(self, _):
        self.steal_promotion()
        print("[QuestReward] Enemy promotion stolen")

    def _reward_chain_lightning(self, _):
        self.trigger_chain_lightning()
        print("[QuestReward] Chain lightning triggered")

    def _reward_firewall(self, _):
        self.trigger_firewall()
        print("[QuestReward] Firewall cast")

    def _reward_total_freeze(self, turns):
        self.freeze_all_enemy(turns)
        print(f"[QuestReward] Total freeze for {turns} turns")

    def _reward_checkmate_teleport(self, _):
        self.g.quests.enable_checkmate_teleport = True
        print("[QuestReward] Checkmate teleport enabled")

    def _reward_reflective_shield(self, turns):
        self.g.quests.enable_reflective_shield = turns
        print(f"[QuestReward] Reflective shield for {turns} turns")

    def _reward_outer_pawns_start_as_rooks(self, _):
        self.g.quests.set_outer_pawns_as_rooks = True
        print("[QuestReward] Outer pawns will start as rooks next game")

    def _reward_knightmare(self, _):
        self.g.quests.enable_knightmare_mode = True
        print("[QuestReward] Knightmare mode activated")

    def _reward_end_board_effects(self, _):
        self.g.quests.end_board_effects = True
        print("[QuestReward] Ending board effects")

    def _reward_early_graves(self, _):
        self.respawn_lost_pieces_randomly()
        print("[QuestReward] Lost pieces respawned")

    def _reward_poisoned_pawns(self, _):
        self.g.quests.enable_poisoned_pawns = True
        print("[QuestReward] Poisoned pawns enabled")

    def _reward_pawn_storm(self, _):
        self.trigger_pawn_storm()
        print("[QuestReward] Pawn storm triggered")

    def _reward_steal_first_on_rank_8(self, _):
        self.steal_first_piece_on_rank_8()
        print("[QuestReward] First enemy to rank 8 is stolen")

    def _reward_random_pawn_to_rook(self, _):
        self.upgrade_random_pawn_to_rook()
        print("[QuestReward] Random pawn upgraded to rook")

    def _reward_lightning_strikes_the_tallest_piece(self, _):
        self.zap_tallest_piece()
        print("[QuestReward] Lightning zaps tallest piece")

    def _reward_advance_rows(self, _):
        self.advance_all_pieces_one_row()
        print("[QuestReward] Troops advance one row")

    def _reward_continue(self, label):
        print(f"[QuestReward] Conditional continue marker: {label}")

    def _grant_power(self, name, count):
        if name in self.g.powerups:
            self.g.powerups[name] += count
        else:
            self.g.powerups[name] = count
        print(f"[QuestReward] +{count} {name} (Total: {self.g.powerups[name]})")

        # This is okay if it is the ON-BOARD reward effect.
        # But if this also spawns the reward CARD, move that part into the queue path instead.
        self.g.effects.play_reward_effect(name, count)

    def _reward_pawn_juggler(self, _):
        self.juggle_pawns()

    def _reward_freeze_knights(self, turns):
        board = self.g.board
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        enemy_color = not player_color

        frozen = 0
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == enemy_color and piece.piece_type == chess.KNIGHT:
                self.g.frozen_squares[square] = self.g.frozen_squares.get(square, 0) + turns
                frozen += 1
                print(f"[FreezeKnights] Knight at {chess.square_name(square)} frozen for {turns} turns")

        if frozen > 0:
            print(f"[FreezeKnights] {frozen} enemy knights frozen for {turns} turns.")
            self.g.audio.play_random("freezes")

    def _reward_advanced_shield_kit_3x3(self, _):
        self.g.advanced_shield_kit = True
        print("[QuestReward] Advanced Shield Kit acquired! Shields now cover 3×3.")
        try:
            self.g.effects.play_reward_effect("advanced_shields", 1)
            self.g.audio.play_random("advanced_shields")
        except Exception:
            pass

    def _reward_central_blast(self, _):
        self.blast_away_center()

    def _reward_empowered_freeze(self, _):
        self.g.quests.enable_empowered_freeze = True

      ### The more complex rewards: ###

    def juggle_pawns(self):
        print("[QuestReward] Pawn Juggler activated! Shuffling pawns...")

        board = self.g.board
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK

        # 1. Collect pawns and empty squares
        pawns = [sq for sq in chess.SQUARES
                if (piece := board.piece_at(sq)) and piece.piece_type == chess.PAWN and piece.color == player_color]
        empties = [sq for sq in chess.SQUARES if board.piece_at(sq) is None]

        if not pawns or not empties:
            print("[PawnJuggler] No pawns or no empty squares available.")
            return

        random.shuffle(empties)
        new_positions = {}

        # 2. Try placing each pawn in a random safe square
        for pawn_sq in pawns:
            placed = False
            random.shuffle(empties)  # reshuffle for extra chaos

            for target in empties:
                tb = board.copy(stack=False)
                tb.remove_piece_at(pawn_sq)
                tb.set_piece_at(target, chess.Piece(chess.PAWN, player_color))

                # Check if move leaves us in check
                tb.turn = not player_color  # enemy's turn
                if tb.is_check():
                    continue  # unsafe, skip

                new_positions[pawn_sq] = target
                empties.remove(target)
                placed = True
                break

            if not placed:
                print(f"[PawnJuggler] Could not safely move pawn from {chess.square_name(pawn_sq)}.")

        # 3. Apply placements on the real board
        for from_sq, to_sq in new_positions.items():
            pawn = board.piece_at(from_sq)
            if pawn:
                board.remove_piece_at(from_sq)
                board.set_piece_at(to_sq, pawn)
                print(f"[PawnJuggler] Pawn moved {chess.square_name(from_sq)} → {chess.square_name(to_sq)}")
                # Optional animations / effects
                try:
                    self.g.renderer.animate_piece_move(pawn.symbol(), from_sq, to_sq)
                except Exception:
                    pass

        if new_positions:
            self.g.audio.play_random("teleport")
            self.g.board_manager.collect_gold()
            print(f"[PawnJuggler] {len(new_positions)} pawns juggled!")
        else:
            print("[PawnJuggler] No pawns were relocated.")

    def transform_pawns_to_knights(self):
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        board = self.g.board

        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.piece_type == chess.PAWN and piece.color == player_color:
                board.set_piece_at(square, chess.Piece(chess.KNIGHT, player_color))

    def steal_promotion(self):
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        enemy_color = not player_color
        board = self.g.board

        promotion_rank = 0 if enemy_color == chess.BLACK else 7

        print(f"[QuestReward] Searching for promoted enemy piece on rank {promotion_rank + 1}...")

        for file in range(8):  # Files a-h → 0-7
            square = chess.square(file, promotion_rank)
            piece = board.piece_at(square)

            if piece and piece.color == enemy_color and piece.piece_type != chess.PAWN and piece.piece_type != chess.KING:
                print(f"[QuestReward] Stolen promotion at {chess.square_name(square)} ({piece.symbol()})")
                new_piece = chess.Piece(piece.piece_type, player_color)
                board.set_piece_at(square, new_piece)

                # TODO: Add visual and sound feedback
                # self.g.renderer.play_magic_flash("steal_promotion")
                # self.g.audio.play_random("transform")
                return  # Done once we’ve found one
            

    def trigger_chain_lightning(self):
        board = self.g.board
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        enemy_color = not player_color

        def _is_enemy(piece):      return piece and piece.color == enemy_color
        def _is_king(piece):       return _is_enemy(piece) and piece.piece_type == chess.KING
        def _is_killable(piece):   return _is_enemy(piece) and piece.piece_type != chess.KING

        # Pull a valid tracked diagonal; fall back if needed
        diagonals = getattr(self.g.quests, "unbroken_diagonals", {})
        try:
            longest = None
            if isinstance(diagonals, dict) and diagonals:
                candidates = []
                for k, streak in diagonals.items():
                    if isinstance(k, (list, tuple, set, frozenset)) and all(isinstance(s, int) for s in k):
                        if len(k) >= 5:
                            candidates.append((streak, k))
                if candidates:
                    candidates.sort(key=lambda t: (t[0], len(t[1])), reverse=True)
                    longest = candidates[0][1]
        except Exception:
            longest = None

        if not longest or len(longest) < 5:
            print("[ChainLightning] No valid diagonal found!")
            return 0

        diagonal_squares = set(longest)
        print(f"[ChainLightning] Using diagonal (len={len(diagonal_squares)}): "
            f"{[chess.square_name(sq) for sq in diagonal_squares]}")

        # Seed: any enemy (including kings) adjacent to the diagonal
        zap_queue, visited = set(), set()
        for sq in diagonal_squares:
            for n in self.get_adjacent_squares(sq):
                p = board.piece_at(n)
                if _is_enemy(p):  # include kings here → conductors
                    zap_queue.add(n)

        if not zap_queue:
            print("[ChainLightning] No adjacent enemies to start chain.")
            return 0

        # BFS: propagate through all enemies (kings conduct), but only mark non-kings for kill
        zapped = set()
        while zap_queue:
            sq = zap_queue.pop()
            if sq in visited:
                continue
            visited.add(sq)

            p = board.piece_at(sq)
            if not _is_enemy(p):
                continue

            if _is_killable(p):
                zapped.add(sq)

            # Propagate from ANY enemy here, including kings
            for n in self.get_adjacent_squares(sq):
                if n not in visited:
                    np = board.piece_at(n)
                    if _is_enemy(np):
                        zap_queue.add(n)

        if not zapped:
            print("[ChainLightning] Nothing eligible for zapping.")
            return 0

        print(f"[ChainLightning] Final zapped ({len(zapped)}): {[chess.square_name(sq) for sq in zapped]}")

        removed = 0
        for sq in zapped:
            p = board.piece_at(sq)
            # Double-check killable and enemy (never remove a king)
            if _is_killable(p):
                self.g.quests.record_captured_piece(p, count_for_quests=True)
                board.remove_piece_at(sq)
                removed += 1
                try:
                    self.g.renderer.play_zap_effect(sq)
                except Exception as e:
                    print(f"[ChainLightning] VFX fail at {chess.square_name(sq)}: {e!r}")

        if removed > 0:
            try:
                self.g.audio.play_random("chain_lightning")
            except Exception:
                pass

        return removed


    def get_adjacent_squares(self, square):
        rank = chess.square_rank(square)
        file = chess.square_file(square)
        deltas = [(-1, -1), (-1, 0), (-1, 1),
                ( 0, -1),         ( 0, 1),
                ( 1, -1), ( 1, 0), ( 1, 1)]

        adjacent = []
        for dr, df in deltas:
            r, f = rank + dr, file + df
            if 0 <= r < 8 and 0 <= f < 8:
                adjacent.append(chess.square(f, r))
        return adjacent

    def trigger_firewall(self):
        pass
        # TODO: We will pass this like a spell

    def freeze_all_enemy(self, turns):
        board = self.g.board
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        enemy_color = not player_color

        freeze_count = 0

        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.color == enemy_color and piece.piece_type != chess.KING:
                self.g.frozen_squares[square] = turns
                freeze_count += 1
                print(f"[Freeze] {chess.square_name(square)} frozen for {turns} turns")

        if freeze_count > 0:
            self.g.audio.play_random("freeze")
            print(f"[FreezeAllEnemy] {freeze_count} enemy pieces frozen for {turns} turns.")
        else:
            print("[FreezeAllEnemy] No enemy pieces found to freeze.")

    def respawn_lost_pieces_randomly(self):
        board = self.g.board
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        enemy_color = not player_color

        # You’re referencing self.g.lost_pieces (make sure you actually maintain this list)
        lost_pieces = list(getattr(self.g, "lost_pieces", []))
        if not lost_pieces:
            print("[Respawn] No pieces to respawn.")
            return

        currently_in_check = board.is_check()
        empties = [sq for sq in chess.SQUARES if board.piece_at(sq) is None]
        random.shuffle(empties)

        placed = 0
        consumed = []

        for piece in lost_pieces:
            for sq in list(empties):
                tb = board.copy(stack=False)
                tb.set_piece_at(sq, piece)

                # After placing, whose turn is it? This is a board edit outside move flow.
                # We only care about the *state* relative to the player's king.
                # Ensure it's NOT checkmate either way:
                tb.turn = enemy_color
                becomes_mate = tb.is_checkmate()

                # Also ensure "no check" if we are NOT currently in check
                tb.turn = player_color
                becomes_check = tb.is_check()

                if becomes_mate:           # always disallow
                    continue
                if not currently_in_check and becomes_check:
                    continue

                # Accept placement
                board.set_piece_at(sq, piece)
                empties.remove(sq)
                placed += 1
                consumed.append(piece)
                print(f"[Respawn] {piece.symbol()} placed at {chess.square_name(sq)}")
                break

        # remove consumed pieces from your tracking if you keep a list
        if hasattr(self.g, "lost_pieces") and consumed:
            for p in consumed:
                try: self.g.lost_pieces.remove(p)
                except ValueError: pass

        print(f"[Respawn] {placed}/{len(lost_pieces)} pieces successfully placed.")
        if placed > 0:
            # TODO: swap to real SFX/VFX
            self.g.audio.play_random("resurrect")
            if hasattr(self.g.renderer, "play_respawn_flash"):
                self.g.renderer.play_respawn_flash()



    def trigger_pawn_storm(self):
        board = self.g.board
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        enemy_color = not player_color
        step = 8 if player_color == chess.WHITE else -8  # 1 rank per step
        direction = step * 2                              # move 2 ranks total

        storm_moves = []

        # 1. Find all player pawns
        for square in chess.SQUARES:
            piece = board.piece_at(square)
            if piece and piece.piece_type == chess.PAWN and piece.color == player_color:
                mid_square = square + step
                target_square = square + direction

                # Skip off-board squares
                if not (0 <= mid_square < 64 and 0 <= target_square < 64):
                    continue

                mid_piece = board.piece_at(mid_square)
                target_piece = board.piece_at(target_square)

                # Pawns cannot move through kings or friendly pieces
                if (mid_piece and mid_piece.color == player_color) or \
                (target_piece and target_piece.color == player_color):
                    continue

                # Add to move list if path not blocked by friendly units
                storm_moves.append((square, mid_square, target_square))

        print(f"[PawnStorm] Found {len(storm_moves)} pawns to move.")

        # 2. Execute storm
        for from_sq, mid_sq, to_sq in storm_moves:
            piece = board.piece_at(from_sq)
            board.remove_piece_at(from_sq)

            # Collect captures (both mid and target squares)
            captured_squares = []
            for sq in (mid_sq, to_sq):
                captured_piece = board.piece_at(sq)
                if captured_piece and captured_piece.color != piece.color and captured_piece.piece_type != chess.KING:
                    captured_squares.append(sq)
                    print(f"[PawnStorm] {chess.square_name(from_sq)} captures {chess.square_name(sq)}")
                    self.g.quests.record_captured_piece(captured_piece, count_for_quests=True)
                    board.remove_piece_at(sq)

            # Promotion check
            rank = chess.square_rank(to_sq)
            if (player_color == chess.WHITE and rank == 7) or (player_color == chess.BLACK and rank == 0):
                promoted_piece = chess.Piece(chess.QUEEN, player_color)
                board.set_piece_at(to_sq, promoted_piece)
                print(f"[PawnStorm] {chess.square_name(from_sq)} -> {chess.square_name(to_sq)} (Promoted to Queen!)")
                self.g.renderer.animate_piece_move(promoted_piece.symbol(), from_sq, to_sq)
            else:
                board.set_piece_at(to_sq, piece)
                print(f"[PawnStorm] {chess.square_name(from_sq)} storms to {chess.square_name(to_sq)}")
                self.g.renderer.animate_piece_move(piece.symbol(), from_sq, to_sq)

        self.g.audio.play_random("pawn_storm")

        


    def steal_first_piece_on_rank_8(self):
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        enemy_color = not player_color

        # Player's back rank index (0 for white, 7 for black)
        back_rank = 0 if player_color == chess.WHITE else 7

        human_rank = back_rank + 1  # for printing (1..8)
        print(f"[StealRank8] Checking player's back rank ({human_rank}) for enemy pieces...")

        for file in range(8):  # files a..h (0..7)
            square = chess.square(file, back_rank)
            piece = self.g.board.piece_at(square)

            if piece and piece.color == enemy_color and piece.piece_type != chess.KING:
                # Convert that piece to the player's color at the same square
                new_piece = chess.Piece(piece.piece_type, player_color)
                self.g.board.set_piece_at(square, new_piece)

                print(f"[StealRank8] Stole {piece.symbol()} at {chess.square_name(square)} "
                    f"→ now {new_piece.symbol()} for player.")
                # TODO: self.g.renderer.play_magic_flash("steal_rank8")
                # TODO: self.g.audio.play_random("transform")
                return  # Only steal one

        print("[StealRank8] No enemy piece found to steal on the back rank.")



    def upgrade_random_pawn_to_rook(self):
        board = self.g.board
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK

        # Find all player pawns
        player_pawns = [
            square for square in chess.SQUARES
            if (piece := board.piece_at(square)) and piece.piece_type == chess.PAWN and piece.color == player_color
        ]

        if not player_pawns:
            print("[UpgradePawn] No pawns available to upgrade.")
            return

        # Pick one at random
        target_square = random.choice(player_pawns)
        board.set_piece_at(target_square, chess.Piece(chess.ROOK, player_color))

        print(f"[UpgradePawn] Pawn at {chess.square_name(target_square)} upgraded to Rook.")

        # TODO:self.g.audio.play_random("transform")
        # TODO:self.g.renderer.play_magic_flash("pawn_to_rook", target_square)

    def zap_tallest_piece(self):
        board = self.g.board
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        enemy_color = not player_color

        # Order of "tallest" priority: Queen > Rook > Bishop > Knight > Pawn
        priority = [chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]

        target_square = None
        target_piece = None

        for ptype in priority:
            for square in chess.SQUARES:
                piece = board.piece_at(square)
                if piece and piece.color == enemy_color and piece.piece_type == ptype:
                    target_square = square
                    target_piece = piece
                    break
            if target_piece:
                break

        if not target_piece:
            print("[ZapTallest] No enemy piece available to zap.")
            return

        # Remove the piece from the board
        self.g.quests.record_captured_piece(target_piece, count_for_quests=True)
        board.remove_piece_at(target_square)
        print(f"[ZapTallest] Zapped enemy {target_piece.symbol()} at {chess.square_name(target_square)}")

        # ⚡ Lightning strike visual
        file = chess.square_file(target_square)
        rank = chess.square_rank(target_square)
        sx = self.g.board_origin_x + file * self.g.SQUARE_SIZE
        sy = self.g.board_origin_y + (7 - rank) * self.g.SQUARE_SIZE

        eid = f"lightning_{target_square}_{pygame.time.get_ticks()}"
        self.g.renderer.display_magic_effect(
            eid,
            3,           # ⚡ lightning effect index (magic_effects_003)
            sx, sy,
            duration=180, 
            complete_attr="lightning_done"
        )

        # ⚡ Optional sound cue
        if hasattr(self.g, "audio"):
            self.g.audio.play_random("lightning")

        # You can trigger post-zap logic after it finishes:
        # if getattr(self.g, "lightning_done", False):
        #     self.g.effects.spawn_smoke_at(target_square)

    def advance_all_pieces_one_row(self):
        board = self.g.board
        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        enemy_color = not player_color
        direction = 1 if player_color == chess.WHITE else -1

        moved_squares = set()
        moves_made = []

        while True:
            move_found = False

            rank_order = range(7, -1, -1) if player_color == chess.WHITE else range(0, 8)

            for r in rank_order:
                for f in range(8):
                    from_sq = chess.square(f, r)
                    if from_sq in moved_squares:
                        continue

                    piece = board.piece_at(from_sq)
                    if not piece or piece.color != player_color:
                        continue

                    # Skip if frozen
                    if hasattr(self.g, "frozen_squares") and self.g.frozen_squares.get(from_sq, 0) > 0:
                        continue

                    target_rank = r + direction
                    if not (0 <= target_rank <= 7):
                        continue  # would move off-board

                    to_sq = chess.square(f, target_rank)

                    # Blocked by friendly piece
                    target_piece = board.piece_at(to_sq)
                    if target_piece and target_piece.color == player_color:
                        continue

                    # Cannot capture enemy king
                    if target_piece and target_piece.color == enemy_color and target_piece.piece_type == chess.KING:
                        continue

                    # Shielded square blocks movement (treat as occupied)
                    if hasattr(self.g, "shielded_squares") and to_sq in self.g.shielded_squares:
                        continue

                    # Legal move found — apply
                    board.remove_piece_at(from_sq)
                    if target_piece:
                        self.g.quests.record_captured_piece(target_piece, count_for_quests=True)
                        board.remove_piece_at(to_sq)
                    board.set_piece_at(to_sq, piece)

                    try:
                        self.g.renderer.animate_piece_move(piece.symbol(), from_sq, to_sq)
                    except Exception:
                        pass

                    moved_squares.add(from_sq)
                    moved_squares.add(to_sq)
                    moves_made.append(to_sq)
                    move_found = True
                    break  # restart loop with updated board
                if move_found:
                    break

            if not move_found:
                break  # no more moves possible


    def blast_away_center(self):
        """
        Blasts away all pieces (both colors) on files c-f (2..5),
        leaving kings in place. Plays magic effect #4 on each removed square.
        """
        board = self.g.board
        blast_files = (2, 3, 4, 5)

        magic_lib = getattr(self.g, "magic_library", None)
        FX = 4  # <<< use magic effect index 4
        if not magic_lib or FX < 0 or FX >= len(magic_lib):
            print("[central_blast] Effect #4 not available; skipping VFX.")
            effect_proto = None
        else:
            effect_proto = magic_lib[FX]

        removed = []

        # 1) Collect targets
        for f in blast_files:
            for r in range(8):
                sq = chess.square(f, r)
                piece = board.piece_at(sq)
                if not piece:
                    continue
                if piece.piece_type == chess.KING:     # keep kings
                    continue
                removed.append((sq, piece))

        # 2) Remove them
        for sq, _piece in removed:
            self.g.quests.record_captured_piece(_piece, count_for_quests=True)
            board.remove_piece_at(sq)

        # 3) Visuals: play effect #4 on each impacted square
        if effect_proto:
            frames0 = effect_proto["frames"][0]
            fw, fh = frames0.get_size()
            fps = effect_proto.get("fps", 12)
            tpf = max(1, 60 // max(1, fps))
            life = len(effect_proto["frames"]) * tpf  # one clean pass

            for sq, _piece in removed:
                file = chess.square_file(sq)
                rank = chess.square_rank(sq)

                sx = self.g.board_origin_x + file * self.g.SQUARE_SIZE
                sy = self.g.board_origin_y + (7 - rank) * self.g.SQUARE_SIZE

                x = sx + (self.g.SQUARE_SIZE - fw) // 2
                y = sy + (self.g.SQUARE_SIZE - fh) // 2

                eid = f"blast_fx4_{sq}_{pygame.time.get_ticks()}"
                self.g.renderer.display_magic_effect(
                    eid, FX, x, y,
                    duration=life
                )

        # 4) Boom (optional)
        if hasattr(self.g, "audio"):
            try:
                self.g.audio.play("explosion_heavy")
            except Exception:
                pass

        # 5) Log
        if removed:
            algebraic = ", ".join(chess.square_name(sq) for sq, _ in removed)
            print(f"[central_blast] Removed {len(removed)} pieces from files c-f: {algebraic}")
        else:
            print("[central_blast] No removable pieces on files c-f.")

    def post_piece_move_events(self):
        # Only trigger Reflective Shield on player's turn
        if self.g.quests.enable_reflective_shield > 0 and self.g.is_it_players_turn():
            self.g.quests.enable_reflective_shield -= 1

            board = self.g.board
            if board.is_check():
                player_color = self.g.player_color()
                king_square = board.king(player_color)

                if king_square is None:
                    return  # Safety check — don't proceed if king is not on board

                enemy_color = not player_color
                attackers = board.attackers(enemy_color, king_square)

                for square in attackers:
                    piece = board.piece_at(square)
                    if piece:
                        self.g.renderer.destroy_piece(square)
                        self.g.quests.record_captured_piece(piece, count_for_quests=True)
                        self.g.board.remove_piece_at(square)

    def checkmate_teleport(self):

        board = self.g.board

        # Determine colors based on whose turn it is: enemy just moved and it's still their turn (per your note)
        them = board.turn                   # enemy color (it's currently their turn)
        us = not them                       # our color (the side being rescued)

        king_sq = board.king(us)
        if king_sq is None:
            # No king found; nothing we can do
            return

        enemy_king_sq = board.king(them)
        enemy_squares = [sq for sq in chess.SQUARES
                         if (p := board.piece_at(sq)) and p.color == them]

        # Heuristic: prefer squares far from enemies, corners slightly favored, away from center slightly favored
        def _safety_score(sq: chess.Square) -> float:
            dmin = min(chess.square_distance(sq, e) for e in enemy_squares) if enemy_squares else 7
            corners = {chess.A1, chess.H1, chess.A8, chess.H8}
            corner_bonus = 0.25 if sq in corners else 0.0
            file_ = chess.square_file(sq)
            rank_ = chess.square_rank(sq)
            center_bonus = 0.05 * (abs(file_ - 3.5) + abs(rank_ - 3.5))
            return dmin + corner_bonus + center_bonus

        candidates = []

        # Primary pass: empty, not adjacent to enemy king, and not attacked after sim
        for sq in chess.SQUARES:
            if board.piece_at(sq) is not None:
                continue
            if enemy_king_sq is not None and chess.square_distance(sq, enemy_king_sq) <= 1:
                continue
            if board.is_attacked_by(them, sq):
                continue

            # Simulate our king on target to double-check safety in resulting position
            b = board.copy(stack=False)
            b.remove_piece_at(king_sq)
            b.set_piece_at(sq, chess.Piece(chess.KING, us))
            b.turn = board.turn  # keep enemy's turn in the simulation too
            if not b.is_attacked_by(them, sq):
                candidates.append((_safety_score(sq), sq))

        # Fallback: if nothing passes adjacency filter, allow squares that are merely unattacked after sim
        if not candidates:
            for sq in chess.SQUARES:
                if board.piece_at(sq) is not None:
                    continue
                b = board.copy(stack=False)
                b.remove_piece_at(king_sq)
                b.set_piece_at(sq, chess.Piece(chess.KING, us))
                b.turn = board.turn
                if not b.is_attacked_by(them, sq):
                    candidates.append((_safety_score(sq) - 0.5, sq))  # small penalty

        if not candidates:
            # Nowhere safe—just bail quietly
            if hasattr(self.g, "send_feedback"):
                self.g.ui_state.send_feedback("Teleport failed: no safe square available.")
            return

        candidates.sort(key=lambda t: t[0], reverse=True)
        best_sq = candidates[0][1]

        # Commit teleport on the REAL board (do NOT change board.turn)
        board.remove_piece_at(king_sq)
        board.set_piece_at(best_sq, chess.Piece(chess.KING, us))

        # UX polish TODO: Flashing VFX, build out the audio
        if hasattr(self.g, "gamestate") and self.g.gamestate in ("checkmate", "stalemate"):
            self.g.gamestate = "normal"
        try:
            if hasattr(self.g, "audio"):
                self.g.audio.play_random("teleport")
        except Exception:
            pass
  
