#quest_info.py
import chess
import operator
import config
from quest_cards import CreateQuestCard
import pygame
import random
import json
import operator


class QuestInfo:
    def __init__(self,game):

        # Debugging Only -- this will setup default quest choices
        self.debug_quest_choices = None
        self.debug_quest_choices = [37, 39, 40, 41, 42] # Must be count of 5
        #self.debug_quest_choices = random.sample(range(1, 50), 5)

        self.g = game
        self.quest_lookup = {}
        self.injected_quest_lookup = {}
        self.injected_quest_ids = []
        
        # Quest tracking
        self.quest_status = {} # id → runtime-state dict

        self.load_all_quests()
        self.quest_max = len(self.all_quests)

        self.hovered_card_index = None
        self.card_hover_scales = [config.CARD_SCALE] * 5
        self.quest_card_hovered = False
        self.checked_files_seen = set()
        self.last_piece_moved_square = None
        self.same_piece_move_streak = 0
        self.enemy_non_pawn_streak = 0
        self.last_captured_piece_type = None
        self.rank_8_race_status = None # This measures who gets to their last rank first
        self.king_adjacent_streak = 0
        self.moved_pawn_squares = set()
        self.moved_knight_squares = set()
        self.moved_bishop_squares = set()
        self.moved_rook_squares = set()
        self.moved_queen_squares = set()
        self.moved_king_squares = set()
        self.player_has_promoted = False
        self.last_player_move_was_capture = False
        self.unbroken_diagonals = {}  # key: frozenset of squares, value: current streak
        self.longest_unbroken_diagonal_streak = 0
        self.same_piece_move_streak = 0
        self.last_moved_to_square = None
        self.same_piece_type_streak = 0
        self.last_piece_type = None
        self.swap_used_this_turn = False
        self.last_enemy_capture_type = None  # stores the type of piece enemy captured on their last move
        self.eye_for_eye_pending = False
        self.eye_for_eye_target_square = None
        self.eye_for_eye_attacker_type = None
        self.eye_for_eye_victim_type = None

        # Variables for managing quest results, powers, etc
        self.enable_checkmate_teleport = False
        self.enable_reflective_shield = False
        self.enable_empowered_freeze = False
        self.set_outer_pawns_as_rooks = False
        self.enable_knightmare_mode = False
        self.end_board_effects = False
        self.enable_poisoned_pawns = False
        self.enable_no_future_rooks = False

        self.original_card_size = (0, 0)

        # quest-selection UI state
        self.card_rects = []
        self.continue_rect = None
        self.quest_selection_done = False
        self.show_continue_button = False
        
        # For counting unmoved player pieces
        # TODO: This will need to be refreshed for levels that have different starting positions
        self.player_starting_squares = set()
        for square in chess.SQUARES:
            p = self.g.board.piece_at(square)
            if p and p.color == self.g.player_color():
                self.player_starting_squares.add((square, p.piece_type))

        # Used for render.py -- passing the quest card building size to the renderer
        self.original_card_size = (0,0)


    def load_all_quests(self):
        with open("data/quests.json", "r", encoding="utf-8") as f:
            self.all_quests = json.load(f)
        self.quest_lookup = {q["quest_number"]: q for q in self.all_quests}

    def _quest_by_id(self, quest_id):
        if quest_id in self.injected_quest_lookup:
            return self.injected_quest_lookup[quest_id]
        return self.quest_lookup.get(quest_id)

    def apply_overworld_quest_cards_for_current_board(self):
        manager = getattr(self.g, "overworld_quests", None)
        if manager is None:
            return

        for quest in manager.get_board_quest_definitions():
            qid = quest.get("quest_number")
            if qid is None or qid in getattr(self, "active_quests", []):
                continue

            self.injected_quest_lookup[qid] = quest
            self.injected_quest_ids.append(qid)
            self.active_quests.append(qid)

            if not hasattr(self, "quest_candidates"):
                self.quest_candidates = []
            if not hasattr(self, "quest_cards"):
                self.quest_cards = []

            self.quest_candidates.append(qid)
            card = CreateQuestCard(qid, quest_data=quest)
            w, h = card.get_size()
            self.original_card_size = (w, h)
            scaled = pygame.transform.smoothscale(
                card,
                (int(w * config.CARD_SCALE_EXPAND), int(h * config.CARD_SCALE_EXPAND)),
            )
            self.quest_cards.append(scaled)
            self.card_hover_scales.append(config.CARD_SCALE)

    def setup_quest_selection(self):
        all_quest_ids = list(range(1, self.quest_max+1))
        selected_ids = random.sample(all_quest_ids, 5)
        if self.g.debug and self.debug_quest_choices is not None:
            selected_ids = self.debug_quest_choices
        self.quest_candidates = selected_ids # TO DO: I'm not sure we're using this class variable anymore
        self.active_quests = []
        self.quest_cards = []
        self.injected_quest_lookup = {}
        self.injected_quest_ids = []

        for qid in selected_ids:
            print("Quest ID:", qid)
            card = CreateQuestCard(qid)
            w, h = card.get_size()
            self.original_card_size = (w, h)
            scaled = pygame.transform.smoothscale(card, (int(w * config.CARD_SCALE_EXPAND), int(h * config.CARD_SCALE_EXPAND)))
            self.quest_cards.append(scaled)

        self.card_rects = []          # updated every frame for clicking
        self.continue_rect = None     # will be set by renderer once drawn
        self.quest_selection_done = False
        self.show_continue_button = False

        selecting = True
        while selecting:
            for event in pygame.event.get():
                #TODO: Build a unified quit handler -- put it in the renderer
                if event.type == pygame.QUIT:
                    pygame.quit()
                self.handle_quest_selection_event(event)

            if self.quest_selection_done:
                selecting = False
                break
        
            self.g.renderer.draw("quest_selection")


    def handle_quest_selection_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            pos = event.pos

            # Card clicks
            for rect, qid in self.card_rects:
                if rect.collidepoint(pos):
                    if qid in self.active_quests:
                        self.active_quests.remove(qid)
                    elif len(self.active_quests) < 3:
                        self.active_quests.append(qid)

            # Continue button
            if self.continue_rect is not None and self.continue_rect.collidepoint(pos):
                self.apply_overworld_quest_cards_for_current_board()
                self.setup_quest_status_tracking()
                self.quest_selection_done = True


    def setup_quest_status_tracking(self):
        self.quest_status = {}

        for quest_num in self.active_quests:
            quest = self._quest_by_id(quest_num)
            if not quest:
                continue

            for pair in quest.get("win_reward_pairs", []):
                to_win = pair.get("to_win", {})
                for key in to_win.keys():
                    if key not in self.quest_status:
                        self.update_quest_stat(key, zero=True)


    def update_quest_stat(self, key=None, amount=0, zero=False, clear=False, equal_to=None):
        if clear:
            self.quest_status.clear()
            return

        if key is None:
            return  # No key to update

        if zero:
            self.quest_status[key] = 0
            return

        if equal_to is not None:
            self.quest_status[key] = equal_to
            return

        print("quest_status: ", self.quest_status)
        if key in self.quest_status:
            self.quest_status[key] += amount
        else:
            # Initialize if not present and amount is non-zero
            if amount != 0:
                self.quest_status[key] = amount
        


    def update_quest_variables(self, piece=None, move=None, player=False, power_used=None):
        print ("[INFO] Updating quest variables...")
        print ("[INFO] Piece: ", piece)
        print ("[INFO] Move: ", move)
        print ("[INFO] Player: ", player)
        print ("[INFO] Power used: ", power_used)
        
        board_before_move = None

        if move and self.g.board.move_stack:
            board_before_move = self.g.board.copy()
            board_before_move.pop()

            if move not in board_before_move.pseudo_legal_moves:
                move = None
                piece = None
        
        # Build variables
        if move:
            captured_piece = self.get_captured_piece(board_before_move, move)
            print("[Move] Setting Captured piece: ", captured_piece)
        else:
            captured_piece = None
            print("[No move] setting captured piece: None")

        if self.g.player_side == "white":
            player_color = chess.WHITE
            enemy_color = chess.BLACK
        else:
            player_color = chess.BLACK 
            enemy_color = chess.WHITE

        if captured_piece:
            self.record_captured_piece(captured_piece, count_for_quests=False)

        # Pieceless checks (state checks)
        if piece == None:
            for key in self.quest_status.keys():
                if player == True:
                    if key == "Win Game":
                        if self.g.board.is_checkmate() or self.g.ENEMY_RAGE_QUITS:
                            self.update_quest_stat(key, equal_to=1)
                        else:
                            self.update_quest_stat(key, zero=True)
                elif player == False:
                    if key == "Lost Game":
                        print("Checking Lost Game")
                        if self.g.board.is_checkmate():
                            self.update_quest_stat(key, equal_to=1)
                            print("Lost Game = 1")
                        else:
                            self.update_quest_stat(key, zero=True)
                            print("Lost Game = 0")
                
                if key == "Stalemate":
                    if self.g.board.is_stalemate():
                        self.update_quest_stat(key, equal_to=1)
                    else:
                        self.update_quest_stat(key, zero=True)
            return
        # NOTE: Do not early return if piece is None — some quests like "Lost Game" rely only on game state.
        # Use `if piece:` inside quest-specific checks where needed.

        print("Keys: ", self.quest_status.keys())
        for key in self.quest_status.keys():
            # ───── Univseral Checks ─────
            if key == "Eye for an Eye":
                # ENEMY TURN: track if they captured one of our non-pawn pieces
                if player is False and move and captured_piece:
                    if captured_piece.piece_type != chess.PAWN:
                        attacker = self.g.board.piece_at(move.to_square)
                        if attacker and attacker.piece_type != chess.PAWN:
                            self.eye_for_eye_target_square = move.to_square  # where attacker landed
                            self.eye_for_eye_attacker_type = attacker.piece_type
                            self.eye_for_eye_victim_type = captured_piece.piece_type
                            self.eye_for_eye_pending = True
                    else:
                        # Clear any pending revenge if the captured piece was a pawn
                        self.eye_for_eye_pending = False
                        self.eye_for_eye_target_square = None
                        self.eye_for_eye_attacker_type = None
                        self.eye_for_eye_victim_type = None

                # PLAYER TURN: check if revenge conditions are satisfied
                elif player is True and self.eye_for_eye_pending:
                    if move and captured_piece:
                        if (
                            move.to_square == self.eye_for_eye_target_square and
                            captured_piece.piece_type == self.eye_for_eye_attacker_type and
                            piece and piece.piece_type == self.eye_for_eye_victim_type and
                            piece.piece_type != chess.PAWN
                        ):
                            self.update_quest_stat(key, amount=1)

                    # Always reset after player's move
                    self.eye_for_eye_pending = False
                    self.eye_for_eye_target_square = None
                    self.eye_for_eye_attacker_type = None
                    self.eye_for_eye_victim_type = None

            elif key == "Regicide" and board_before_move:
                only_kings_and_queens = True

                for square in chess.SQUARES:
                    p = board_before_move.piece_at(square)
                    if p and p.piece_type not in (chess.KING, chess.QUEEN):
                        only_kings_and_queens = False
                        break

                if only_kings_and_queens:
                    self.update_quest_stat(key, equal_to=1)

            elif key == "Piece Ratio":
                player_count = 0
                enemy_count = 0
                for square in chess.SQUARES:
                    p = self.g.board.piece_at(square)
                    if p:
                        if p.color == player_color:
                            player_count += 1
                        else:
                            enemy_count += 1
                
                # Avoid division by zero
                ratio = player_count / enemy_count if enemy_count > 0 else float('inf')
                print("Piece Ratio: ", ratio, "player_count: ", player_count, "enemy_count: ", enemy_count)
                self.update_quest_stat(key, zero=True)
                self.update_quest_stat(key, amount=round(ratio, 2))

            # Pawn Count is the lowest number of pawns on a side for Last Man Standing Quest
            elif key == "Pawn Count":
                count_w = 0
                count_b = 0
                count = 0
                for square in chess.SQUARES:
                    p = self.g.board.piece_at(square)
                    if p and p.piece_type == chess.PAWN and p.color == chess.WHITE:
                        count_w += 1
                    elif p and p.piece_type == chess.PAWN and p.color == chess.BLACK:
                        count_b += 1
                count = min(count_w, count_b)
                self.update_quest_stat(key, equal_to=count)

            elif key == "Queen Count":
                count = 0
                for square in chess.SQUARES:
                    p = self.g.board.piece_at(square)
                    if p and p.piece_type == chess.QUEEN and p.color == player_color:
                        count += 1
                self.update_quest_stat(key, equal_to=count)

            elif key == "Lost Pawns" and move:
                if captured_piece and captured_piece.piece_type == chess.PAWN and captured_piece.color == player_color:
                    self.update_quest_stat(key, amount=1)
                    
            elif key == "Piece Count":
                count = 0
                for square in chess.SQUARES:
                    p = self.g.board.piece_at(square)
                    if p and p.color == player_color:
                        count += 1
                self.update_quest_stat(key, equal_to=count)

            elif key == "Frozen Pieces":
                # Skip if in checkmate
                if self.g.board.is_checkmate():
                    continue

                # the freezes live on game, not self
                frozen_squares = getattr(self.g, "frozen_squares", {})

                enemy_color = not (chess.WHITE if self.g.player_side == "white" else chess.BLACK)

                # count enemy pieces whose square is frozen
                immobile_count = sum(
                    1
                    for sq in chess.SQUARES
                    for piece in [self.g.board.piece_at(sq)]
                    if piece and piece.color == enemy_color and sq in frozen_squares
                )

                self.update_quest_stat(key, equal_to=immobile_count)

            
            # ───── Enemy-only checks ─────
            if player == False:
                if key == "Consecutive Enemy Knight Moves":
                    if piece.piece_type == chess.KNIGHT:
                        print("Consecutive Enemy Knight Moves + 1")
                        self.update_quest_stat(key, amount=1)
                        
                    else:
                        print("Consecutive Enemy Knight Moves reset")
                        self.update_quest_stat(key, zero=True)

                elif key == "Queen Sacrifice" and move:
                    if captured_piece and captured_piece.piece_type == chess.QUEEN:
                        self.update_quest_stat(key, amount=1)

                elif key == "Enemy First on Rank 8" and move and piece:
                    # Enemy reached the PLAYER's back rank
                    if self.g.player_side == "white":
                        target_rank = 0   # enemy (black) reaching rank 1
                    else:
                        target_rank = 7   # enemy (white) reaching rank 8

                    to_rank = chess.square_rank(move.to_square)
                    already_triggered = self.quest_status.get(key, 0) >= 1

                    if (
                        not already_triggered and
                        piece.color == enemy_color and
                        piece.piece_type != chess.KING and
                        to_rank == target_rank
                    ):
                        print(f"[Quest] Enemy First on Rank 8 triggered by {piece.symbol()} at {chess.square_name(move.to_square)}")
                        self.update_quest_stat(key, equal_to=1)
                    else:
                        if not already_triggered:
                            self.update_quest_stat(key, zero=True)


                elif key == "Blood Mirror" and move:
                    if captured_piece:
                        if getattr(self, "enemy_lost_piece_last_turn", False):
                            self.update_quest_stat(key, amount=1)
                            self.enemy_lost_piece_last_turn = False
                        else:
                            self.player_lost_piece_last_turn = True
                            self.update_quest_stat(key, zero=True)

                # If enemy checks you
                elif key == "Checked" and move:
                    if board_before_move.gives_check(move):
                        self.update_quest_stat(key, amount=1)

                # To do: evaluted
                elif key == "Checked Unique Files" and move:
                    if board_before_move.gives_check(move):
                        # Find player's king square

                        player_king_square = self.g.board.king(self.g.player_color())
                        if player_king_square is not None:
                            file = chess.square_file(player_king_square)
                            if file not in self.checked_files_seen:
                                self.checked_files_seen.add(file)
                                self.update_quest_stat(key, amount=1)
                                
                elif key == "Consecutively Lost Pieces" and move:
                    captured = board_before_move.piece_at(move.to_square)
                    if captured:
                        self.update_quest_stat(key, amount=1)
                    else:
                        if self.quest_status[key] < 4:
                            self.update_quest_stat(key, zero=True)

                elif key == "Enemy Pawns Haven't Moved" and move:
                    check_board = board_before_move or self.g.board
                    blocked_pawns = self._count_enemy_pawns_without_legal_moves(check_board, enemy_color)
                    if blocked_pawns >= 4:
                        self.enemy_non_pawn_streak += 1
                        self.update_quest_stat(key, equal_to=self.enemy_non_pawn_streak)
                    else:
                        self.enemy_non_pawn_streak = 0
                        self.update_quest_stat(key, equal_to=0)

                elif key == "Lost Elves" and move:
                    if captured_piece and captured_piece.piece_type == chess.BISHOP and captured_piece.color == player_color:
                        self.update_quest_stat(key, amount=1)

                elif key == "Lost Pawns" and move:
                    if captured_piece and captured_piece.piece_type == chess.PAWN and captured_piece.color == player_color:
                        self.update_quest_stat(key, amount=1)

                elif key == "Lost Pieces" and move:
                    if captured_piece and captured_piece.color == player_color:
                        self.update_quest_stat(key, amount=1)

                elif key == "Promoted Enemy" and move:
                    if (
                        piece.piece_type == chess.PAWN and
                        move.promotion and
                        not getattr(self, "player_has_promoted", False) and
                        not getattr(self, "used_promotion_power", False)
                    ):
                        self.update_quest_stat(key, equal_to=1)

            # ───── Player-only checks ─────
            else:
                if key == "Moved Pawns":
                    if piece.piece_type == chess.PAWN:
                        self.update_quest_stat(key, amount=1)

                elif key == "Rook Captures" and move:
                    if captured_piece and captured_piece.piece_type == chess.ROOK and captured_piece.color == enemy_color:
                        self.update_quest_stat(key, amount=1)
                
                elif key == "Turns" and move:
                    self.update_quest_stat(key, amount=1)

                elif key == "Blood Mirror" and move:
                    if captured_piece:
                        if getattr(self, "player_lost_piece_last_turn", False):
                            self.update_quest_stat(key, amount=1)
                            self.player_lost_piece_last_turn = False
                        else:
                            self.enemy_lost_piece_last_turn = True

                elif key == "Backline Captures" and move:
                    if captured_piece:
                        rank = chess.square_rank(move.to_square)
                        if (self.g.player_side == "white" and rank == 7) or (self.g.player_side == "black" and rank == 0):
                            self.update_quest_stat(key, amount=1)

                # This only checks if a PLAYER'S piece is bombed for the quest "title": "Fire in the Hole",
                elif key == "Bombed Pawn":
                    if (
                        power_used == "bombs" and
                        piece.piece_type == chess.PAWN and
                        piece.color == (chess.WHITE if self.g.player_side == "white" else chess.BLACK)
                    ):
                        # Bomb was used successfully on a player's own pawn
                        self.update_quest_stat(key, amount=1)

                elif key == "Captured Pieces" and move:
                    if captured_piece:
                        self.update_quest_stat(key, amount=1)

                elif key == "Castle" and move:
                    last_move = self.g.board.peek()
                    moved_piece = self.g.board.piece_at(last_move.to_square)

                    # Determine which color just moved (opposite of current turn)
                    color_just_moved = not self.g.board.turn  # True for white, False for black

                    # Ensure it was the player who moved
                    if color_just_moved == player_color:
                        # Ensure the moved piece is a king
                        if moved_piece and moved_piece.piece_type == chess.KING:
                            from_file = chess.square_file(last_move.from_square)
                            to_file = chess.square_file(last_move.to_square)

                            # Check if king moved from e-file to c- or g-file (castling)
                            if from_file == 4 and to_file in (2, 6):
                                self.update_quest_stat(key, amount=1)

                # Concurrent Shields
                elif key == "Concurrent Enemy Shields" and power_used in ("shields", "advanced_shields"):
                    count = 0
                    for sq in self.g.shielded_squares:
                        piece = self.g.board.piece_at(sq)
                        if piece and piece.color == enemy_color:  # enemy piece
                            count += 1

                    self.update_quest_stat(key, equal_to=count)

                elif key == "Consecutive Moves" and move:
                    # Determine the moving piece safely (prefer pre-move board if you have it)
                    moving_piece = piece
                    if moving_piece is None:
                        moving_piece = self.g.board.piece_at(move.from_square)

                    if self.last_moved_to_square == move.from_square:
                        self.same_piece_move_streak += 1
                    else:
                        self.same_piece_move_streak = 1

                    self.last_moved_to_square = move.to_square
                    self.update_quest_stat("Consecutive Moves", equal_to=self.same_piece_move_streak)

                elif key == "Consecutive Pawn Moves" and move:
                    # Piece-type streaks (e.g., "Consecutive Pawn Moves")
                    moving_piece = piece
                    if moving_piece:
                        piece_name = chess.piece_name(moving_piece.piece_type).capitalize()
                        if self.last_piece_type == piece_name:
                            self.same_piece_type_streak += 1
                        else:
                            self.same_piece_type_streak = 1
                        self.last_piece_type = piece_name

                        type_key = f"Consecutive {piece_name} Moves"
                        if type_key in self.quest_status:
                            self.update_quest_stat(type_key, equal_to=self.same_piece_type_streak)

                        # Zero the other type keys (but NOT the generic one)
                        for other in ("Pawn","Knight","Bishop","Rook","Queen","King"):
                            ok = f"Consecutive {other} Moves"
                            if ok != type_key and ok in self.quest_status:
                                self.update_quest_stat(ok, zero=True)

                elif key == "Divide and Conquer":
                    # Only check if the quest hasn't been disqualified yet
                    if self.quest_status[key] != -1:
                        all_pieces_in_own_half = True

                        for square in chess.SQUARES:
                            piece_at_square = self.g.board.piece_at(square)
                            if piece_at_square and piece_at_square.color == player_color:
                                rank = chess.square_rank(square)

                                if (self.g.player_side == "white" and rank > 3) or \
                                   (self.g.player_side == "black" and rank < 4):
                                    all_pieces_in_own_half = False
                                    break

                        if all_pieces_in_own_half:
                            self.update_quest_stat(key, equal_to=1)
                        else:
                            self.update_quest_stat(key, equal_to=-1)  # Disqualify permanently until reset

                elif key == "King Adjacent to Enemy":
                    king_square = self.g.board.king(player_color)
                    if king_square is not None:
                        king_rank = chess.square_rank(king_square)
                        king_file = chess.square_file(king_square)

                        adjacent_enemy_found = False
                        for df in [-1, 0, 1]:
                            for dr in [-1, 0, 1]:
                                if df == 0 and dr == 0:
                                    continue
                                f = king_file + df
                                r = king_rank + dr
                                if 0 <= f < 8 and 0 <= r < 8:
                                    adj_sq = chess.square(f, r)
                                    piece = self.g.board.piece_at(adj_sq)
                                    if piece and piece.color == enemy_color:
                                        adjacent_enemy_found = True
                                        break
                            if adjacent_enemy_found:
                                break

                        if adjacent_enemy_found:
                            self.king_adjacent_streak += 1
                            self.update_quest_stat(key, amount=self.king_adjacent_streak)
                        else:
                            self.king_adjacent_streak = 0

                elif key == "King Moves" and move and piece:
                    if piece.piece_type == chess.KING:
                        self.update_quest_stat(key, amount=1)

                elif key == "Knight Moves" and move and piece:
                    if piece.piece_type == chess.KNIGHT:
                        self.update_quest_stat(key, amount=1)

                elif key == "King and Queen Fork" and move:
                    # Require a pre-move snapshot
                    if board_before_move is None:
                        continue

                    # Make a post-move board so attacks reflect the new position
                    board_after = board_before_move.copy()
                    try:
                        board_after.push(move)
                    except Exception:
                        continue  # malformed/illegal move safeguard

                    player_color = self.g.player_color()
                    enemy_color  = not player_color

                    # The piece that just moved (post-move)
                    mover = board_after.piece_at(move.to_square)
                    if not mover or mover.color != player_color:
                        continue

                    # Attacks from the mover's new square
                    attacks = board_after.attacks(move.to_square)

                    # Find enemy king & queen in the post-move position
                    enemy_king_sq = board_after.king(enemy_color)

                    enemy_queen_sq = None
                    for sq in chess.SQUARES:
                        p = board_after.piece_at(sq)
                        if p and p.color == enemy_color and p.piece_type == chess.QUEEN:
                            enemy_queen_sq = sq
                            break

                    # Count only if BOTH pieces are present and attacked
                    if (
                        enemy_king_sq is not None and
                        enemy_queen_sq is not None and
                        enemy_king_sq in attacks and
                        enemy_queen_sq in attacks
                    ):
                        self.update_quest_stat(key, amount=1)


                elif key == "King's Rank":
                    king_sq = self.g.board.king(player_color)
                    if king_sq is None:
                        self.update_quest_stat(key, zero=True)
                    else:
                        r0 = chess.square_rank(king_sq)  # 0..7 (0 = rank 1)
                        normalized = (r0 + 1) if player_color == chess.WHITE else (8 - r0)
                        self.update_quest_stat(key, equal_to=normalized)


                elif key == "Mirror Kill":
                    if self.g.board.is_checkmate():
                        king_start_square = config.STARTING_KING_SQUARES["white" if enemy_color == chess.WHITE else "black"]

                        # Check if any player-controlled piece is standing on that square
                        piece = self.g.board.piece_at(king_start_square)
                        if piece and piece.color == player_color:
                            self.update_quest_stat(key, equal_to=1)

                elif key == "Moved Pawns" and move:
                    if piece.piece_type == chess.PAWN:
                        if move.from_square not in self.moved_pawn_squares:
                            self.moved_pawn_squares.add(move.from_square)
                            self.update_quest_stat(key, amount=1)
                elif key == "Moved Knights" and move:
                    if piece.piece_type == chess.KNIGHT:
                        if move.from_square not in self.moved_knight_squares:
                            self.moved_knight_squares.add(move.from_square)
                            self.update_quest_stat(key, amount=1)

                elif key == "Moved Bishops" and move:
                    if piece.piece_type == chess.BISHOP:
                        if move.from_square not in self.moved_bishop_squares:
                            self.moved_bishop_squares.add(move.from_square)
                            self.update_quest_stat(key, amount=1)

                elif key == "Moved Rooks" and move:
                    if piece.piece_type == chess.ROOK:
                        if move.from_square not in self.moved_rook_squares:
                            self.moved_rook_squares.add(move.from_square)
                            self.update_quest_stat(key, amount=1)

                elif key == "Moved Queens" and move:
                    if piece.piece_type == chess.QUEEN:
                        if move.from_square not in self.moved_queen_squares:
                            self.moved_queen_squares.add(move.from_square)
                            self.update_quest_stat(key, amount=1)

                elif key == "Moved Kings" and move:
                    if piece.piece_type == chess.KING:
                        if move.from_square not in self.moved_king_squares:
                            self.moved_king_squares.add(move.from_square)
                            self.update_quest_stat(key, amount=1)

                elif key == "Promoted Pawn" and move:
                    if piece.piece_type == chess.PAWN and move.promotion:
                        self.update_quest_stat(key, amount=1)
                        self.player_has_promoted = True  # for use in other quests like "Promoted Enemy"

                elif key == "Rook Captures" and move:
                    if captured_piece and captured_piece.piece_type == chess.ROOK and captured.color != player_color:
                        self.update_quest_stat(key, amount=1)

                elif key == "Swap and Kill":
                    print("[INFO] swap_used_this_turn: ", self.swap_used_this_turn)
                    print("[INFO] captured_piece: ", captured_piece)
                    if self.swap_used_this_turn == True and captured_piece:
                        self.update_quest_stat(key, amount=1)
                    else:
                        self.update_quest_stat(key, zero=True)


                elif key == "The Gauntlet Turns":
                    piece_count = 0
                    for square in chess.SQUARES:
                        p = self.g.board.piece_at(square)
                        if p and p.color ==player_color:
                            piece_count += 1

                    if piece_count <= 3:
                        self.update_quest_stat(key, amount=1)
                    else:
                        self.update_quest_stat(key, zero=True)

                elif key == "Unbroken 5-Piece Diagonal":
                    new_groups = {}

                    # Group diagonals by `/` and `\`
                    for direction in ("forward", "backward"):
                        diagonals = {}

                        for square in chess.SQUARES:
                            piece = self.g.board.piece_at(square)
                            if not piece:
                                continue

                            key_val = chess.square_file(square) + chess.square_rank(square) if direction == "forward" else chess.square_file(square) - chess.square_rank(square)
                            diagonals.setdefault(key_val, []).append(square)

                    # Process each diagonal
                    for squares in diagonals.values():
                        # Sort by rank *and* file to be safe across both diagonal directions
                        squares.sort(key=lambda sq: (chess.square_rank(sq), chess.square_file(sq)))

                        current_group = []
                        last_color = None

                        for sq in squares:
                            p = self.g.board.piece_at(sq)
                            if not p:
                                current_group = []
                                last_color = None
                                continue

                            if p.color == last_color:
                                current_group.append(sq)
                            else:
                                current_group = [sq]
                                last_color = p.color

                            # ✅ Need 5-in-a-row; slide a 5-wide window
                            if len(current_group) >= 5:
                                # e.g., len=7 yields windows [0..4], [1..5], [2..6]
                                for i in range(len(current_group) - 5 + 1):
                                    window = current_group[i:i+5]

                                    # Use an ordered tuple as key (easier to debug than frozenset)
                                    group_key = tuple(window)

                                    prev = self.unbroken_diagonals.get(group_key, 0)
                                    streak = prev + 1
                                    new_groups[group_key] = streak

                                    if streak > self.longest_unbroken_diagonal_streak:
                                        self.longest_unbroken_diagonal_streak = streak
                                        self.update_quest_stat(key, equal_to=streak)

                    # Replace old groups with only surviving ones
                    self.unbroken_diagonals = new_groups


                elif key == "Unmoved Pieces":
                    count = 0
                    for square, original_type in self.player_starting_squares:
                        p = self.g.board.piece_at(square)
                        if p and p.piece_type == original_type and p.color == player_color:
                            count += 1
                    self.update_quest_stat(key, zero=True)
                    self.update_quest_stat(key, amount=count)

                elif key == "Vulnerable Queen":
                    queen_square = None

                    # Find the player's queen
                    for square in chess.SQUARES:
                        p = self.g.board.piece_at(square)
                        if p and p.piece_type == chess.QUEEN and p.color == player_color:
                            queen_square = square
                            break

                    if queen_square is None:
                        # Queen is gone → reset
                        self.update_quest_stat(key, zero=True)
                    else:
                        vulnerable = False
                        for move in self.g.board.legal_moves:
                            if move.to_square == queen_square and self.g.board.piece_at(move.from_square).color != player_color:
                                vulnerable = True
                                break

                        if vulnerable:
                            self.update_quest_stat(key, amount=1)
    
                elif key == "Checkmate Elves and Pawns":
                    # Attacker is the opposite of whoever's turn it is now (since board.turn flips after a move)
                    attacker_color = player_color
                    victim_color = enemy_color

                    # Always validate king square first
                    king_square = self.g.board.king(victim_color)
                    if king_square is None:
                        return

                    # Checkmate status (this is our gatekeeper)
                    if self.g.board.is_checkmate():
                        # Find attackers of the king
                        attackers = self.g.board.attackers(attacker_color, king_square)

                        # Evaluate all attackers
                        valid = True
                        for sq in attackers:
                            piece = self.g.board.piece_at(sq)
                            if piece:
                                if piece.piece_type not in (chess.BISHOP, chess.PAWN):
                                    valid = False
                                    break

                        if valid and attackers:
                            self.update_quest_stat(key, equal_to=1)


                elif key == "Pacifist's Pact":
                    disqualified = False

                    if power_used == "bombs":
                        disqualified = True

                    elif move:
                        if captured_piece and captured_piece.color == enemy_color:
                            disqualified = True

                    if disqualified:
                        if self.quest_status["Turns"] < 10:
                            self.update_quest_stat(key, equal_to=-1)  # Failed
                        elif self.quest_status["Turns"] < 15:
                            self.update_quest_stat(key, equal_to=10)   # 10-turn success
                        elif self.quest_status["Turns"] < 20:
                            self.update_quest_stat(key, equal_to=15)   # 15-turn success
                        else:
                            self.update_quest_stat(key, equal_to=20)   # Full 20-turn success
                    else:
                        # Auto-lock if full success achieved
                        if self.quest_status["Turns"] == 20:
                            self.update_quest_stat(key, equal_to=20)
  
        self.update_injected_board_objectives()
        self.check_for_quest_win()
    # We also need to check if the quest is indeed won

    def update_injected_board_objectives(self):
        if not self.injected_quest_lookup:
            return

        player_color = self.g.player_color()
        for qid in list(self.active_quests):
            quest = self.injected_quest_lookup.get(qid)
            if not quest:
                continue
            objective = quest.get("objective", {})
            if objective.get("type") != "hold_piece_on_squares":
                continue
            key = objective.get("stat_key")
            if not key or key not in self.quest_status:
                continue

            squares = []
            for square_name in objective.get("squares", []):
                try:
                    squares.append(chess.parse_square(square_name))
                except Exception:
                    pass

            piece_type = None
            piece_type_name = objective.get("piece_type")
            if piece_type_name:
                piece_type = getattr(chess, str(piece_type_name).upper(), None)

            matched = False
            for square in squares:
                piece = self.g.board.piece_at(square)
                if not piece or piece.color != player_color:
                    continue
                if piece_type is not None and piece.piece_type != piece_type:
                    continue
                matched = True
                break

            if matched:
                self.update_quest_stat(key, amount=1)
            else:
                self.update_quest_stat(key, zero=True)

    def check_for_quest_win(self):
        ops = {
            "==": operator.eq,
            "!=": operator.ne,
            ">=": operator.ge,
            "<=": operator.le,
            ">": operator.gt,
            "<": operator.lt,
        }

        print("\n[QUEST CHECK] Starting check_for_quest_win...")
        for quest_num in self.active_quests:
            print(f"\n→ Checking Quest #{quest_num}")
            quest = self._quest_by_id(quest_num)

            if not quest:
                print(f"  ✖ Quest #{quest_num} not found in all_quests!")
                continue

            title = quest.get("title", "Unnamed")
            print(f"  Title: {title}")

            win_pairs = quest.get("win_reward_pairs", [])
            if not win_pairs:
                print("  ✖ No win_reward_pairs defined!")
                continue

            for i, pair in enumerate(win_pairs):
                print(f"  → Checking win condition group #{i + 1}")
                win_conditions = pair.get("to_win", {})
                all_met = True

                for key, cond in win_conditions.items():
                    stat_value = self.quest_status.get(key, 0)

                    if isinstance(cond, int):
                        print(f"    • {key}: {stat_value} == {cond}? ", end="")
                        if stat_value == cond:
                            print("✅ Yes")
                        else:
                            print("❌ No")
                            all_met = False
                            break

                    elif isinstance(cond, dict):
                        op_str = cond.get("op", "==")
                        value = cond.get("value", 0)
                        op_func = ops.get(op_str)

                        if not op_func:
                            print(f"    ✖ Unsupported operator '{op_str}' for key '{key}'")
                            all_met = False
                            break

                        result = op_func(stat_value, value)
                        print(f"    • {key}: {stat_value} {op_str} {value}? {'✅ Yes' if result else '❌ No'}")

                        if not result:
                            all_met = False
                            break
                    else:
                        print(f"    ✖ Invalid condition format for key '{key}': {cond}")
                        all_met = False
                        break

                if all_met:
                    print(f"  ✅ Quest #{quest_num} COMPLETE! Calling win_quest()...")
                    reward = pair.get("reward", {})
                    self.win_quest(quest_num, reward)
                    break
                else:
                    print(f"  ➖ Quest #{quest_num} not yet complete.")


    def win_quest(self, quest_num, reward=None):
        print(f"[Quest] win_quest({quest_num}) called")
        if quest_num not in self.active_quests:
            print(f"[QuestReward] Quest #{quest_num} is not active; skipping duplicate reward.")
            return

        display_index = self.active_quests.index(quest_num)

        if quest_num in self.injected_quest_lookup:
            self.g.quest_reward_handler.enqueue_reward_card(
                quest_num,
                reward or {},
                display_index=display_index,
            )
            manager = getattr(self.g, "overworld_quests", None)
            if manager is not None:
                manager.complete_board_objective(quest_num)
            self.active_quests.remove(quest_num)
            return
        
        self.g.quest_reward_handler.give_reward(
            quest_num,
            reward or {},
            display_index=display_index,
        )
        
        self.g.player_gold += 3
        print(f"[QuestReward] Quest completion gold: +3 (Total: {self.g.player_gold})")

        self.active_quests.remove(quest_num)

    
    def get_captured_piece(self, board_before_move: chess.Board, move: chess.Move):
        """Return the captured piece (a chess.Piece) or None, given the board
        state *before* the move is played."""
        if board_before_move is None or move is None:
            return None

        # En passant - captured pawn is not on move.to_square yet
        if board_before_move.is_en_passant(move):
            cap_sq = chess.square(
                chess.square_file(move.to_square),
                chess.square_rank(move.from_square)
            )
            return board_before_move.piece_at(cap_sq)

        # Normal capture (or None if it’s not a capture)
        return board_before_move.piece_at(move.to_square)

    def _count_enemy_pawns_without_legal_moves(self, board: chess.Board, enemy_color: chess.Color) -> int:
        """Return the number of remaining enemy pawns that cannot legally move now."""
        if board is None:
            return 0

        test_board = board.copy(stack=False)
        test_board.turn = enemy_color
        enemy_pawn_squares = {
            square
            for square, piece in test_board.piece_map().items()
            if piece.color == enemy_color and piece.piece_type == chess.PAWN
        }

        movable_pawns = set()
        for move in test_board.legal_moves:
            piece = test_board.piece_at(move.from_square)
            if piece and piece.color == enemy_color and piece.piece_type == chess.PAWN:
                movable_pawns.add(move.from_square)

        return len(enemy_pawn_squares - movable_pawns)

    def record_captured_piece(self, captured_piece, count_for_quests=False):
        """Track captured/destroyed pieces for revive rewards and non-move capture stats."""
        if captured_piece is None:
            return

        if self.g.player_side == "white":
            player_color = chess.WHITE
            enemy_color = chess.BLACK
        else:
            player_color = chess.BLACK
            enemy_color = chess.WHITE

        piece_copy = chess.Piece(captured_piece.piece_type, captured_piece.color)

        if captured_piece.color == player_color:
            if not hasattr(self.g, "lost_pieces"):
                self.g.lost_pieces = []
            self.g.lost_pieces.append(piece_copy)

            if count_for_quests:
                self.update_quest_stat("Lost Pieces", amount=1)
                if captured_piece.piece_type == chess.PAWN:
                    self.update_quest_stat("Lost Pawns", amount=1)
                elif captured_piece.piece_type == chess.BISHOP:
                    self.update_quest_stat("Lost Elves", amount=1)

        elif captured_piece.color == enemy_color:
            if not hasattr(self.g, "enemy_lost_pieces"):
                self.g.enemy_lost_pieces = []
            self.g.enemy_lost_pieces.append(piece_copy)

            if count_for_quests:
                self.update_quest_stat("Captured Pieces", amount=1)
                if captured_piece.piece_type == chess.ROOK:
                    self.update_quest_stat("Rook Captures", amount=1)

    def reset_quest_variables(self):
        """
        Resets all quest-related runtime variables to their default state,
        except persistent powers like reflective shield and empowered freeze.
        Call this when starting a new quest level or upon full board refresh.
        """

        # ───── Reset quest effects and powers (except persistent buffs) ─────
        self.enable_checkmate_teleport = False
        self.set_outer_pawns_as_rooks = False
        self.enable_knightmare_mode = False
        self.end_board_effects = False
        self.enable_poisoned_pawns = False
        self.enable_no_future_rooks = False

        # ───── Runtime quest state ─────
        self.quest_max = len(self.all_quests)
        self.hovered_card_index = None
        self.card_hover_scales = [config.CARD_SCALE] * 5
        self.quest_card_hovered = False
        self.checked_files_seen = set()
        self.last_piece_moved_square = None
        self.same_piece_move_streak = 0
        self.enemy_non_pawn_streak = 0
        self.last_captured_piece_type = None
        self.rank_8_race_status = None
        self.king_adjacent_streak = 0
        self.moved_pawn_squares = set()
        self.moved_knight_squares = set()
        self.moved_bishop_squares = set()
        self.moved_rook_squares = set()
        self.moved_queen_squares = set()
        self.moved_king_squares = set()
        self.player_has_promoted = False
        self.last_player_move_was_capture = False
        self.unbroken_diagonals = {}
        self.longest_unbroken_diagonal_streak = 0
        self.last_moved_to_square = None
        self.same_piece_type_streak = 0
        self.last_piece_type = None
        self.swap_used_this_turn = False
        self.last_enemy_capture_type = None
        self.eye_for_eye_pending = False
        self.eye_for_eye_target_square = None
        self.eye_for_eye_attacker_type = None
        self.eye_for_eye_victim_type = None

        print("[QUEST] All quest variables reset (persistent powers preserved).")
