# input_controller.py
from __future__ import annotations

import pygame
import chess
import config


class InputController:
    """
    Owns all player input handling for ChessScreen.

    Responsibilities:
      - Hover detection (board square, power icon, spellbook hover spell)
      - Menu interception & ESC to open menu
      - Mouse click handling:
          * feedback dismiss
          * gear pending targeting resolution
          * power icon selection + time warp immediate
          * board clicks (swap power, board-targeted powers, spell targeting, normal select/move)
          * spellbook open/close + spell selection
          * gear UI clicks via renderer.handle_gear_click

    Contract:
      - update_hover(mouse_pos) returns (hovered_square, hovered_power)
      - handle_event(event, hovered_square, hovered_power, mouse_pos) returns dict:
            {"quit": bool}
    """

    def __init__(self, game):
        self.g = game

    # ─────────────────────────────────────────────────────────────
    # Hover updates
    # ─────────────────────────────────────────────────────────────
    def _update_spellbook_hover(self, mouse_x: int, mouse_y: int) -> None:
        """Updates hover spell + hover timer bookkeeping while spellbook is open."""
        if not self.g.spellbook_open:
            return

        icon_height = 36
        mx, my = mouse_x, mouse_y
        hovered_now = None

        sorted_spells = sorted(self.g.spellbook)

        # page 1
        x, y = 323, 118
        for name in sorted_spells[:8]:
            if pygame.Rect(x, y, 300, icon_height).collidepoint(mx, my):
                hovered_now = name
                break
            y += icon_height

        # page 2
        if hovered_now is None:
            x, y = 683, 105
            for name in sorted_spells[8:]:
                if pygame.Rect(x, y, 300, icon_height).collidepoint(mx, my):
                    hovered_now = name
                    break
                y += icon_height

        if hovered_now != self.g._hover_spell:
            self.g._hover_spell = hovered_now
            self.g._hover_start_ms = pygame.time.get_ticks()

    def _hovered_power_icon(self, mouse_x: int, mouse_y: int):
        """Mirror draw_powerups grid math to determine hovered power key, or None."""
        if not self.g.main_game_screen:
            return None

        if not getattr(self.g, "powers_unlocked", False):
            return None

        hovered_power = None
        icon_size = 72
        padding = 8
        inventory_rect_x = config.WIDTH - config.POWER_WIDTH + 10
        inventory_rect_y = 10
        start_x = inventory_rect_x + padding
        start_y = inventory_rect_y + 30
        col_count = 2

        index = 0
        for power in self.g.powerups:
            row = index // col_count
            col = index % col_count
            icon_x = start_x + col * (icon_size + padding)
            icon_y = start_y + row * (icon_size + padding)
            icon_rect = pygame.Rect(icon_x, icon_y, icon_size, icon_size)
            if icon_rect.collidepoint(mouse_x, mouse_y):
                hovered_power = power
                break
            index += 1

        return hovered_power

    def _hovered_board_square(self, mouse_x: int, mouse_y: int):
        """Mirror board draw layout to determine hovered chess square, or None."""
        if not self.g.main_game_screen:
            return None

        col = (mouse_x - self.g.board_origin_x) // config.SQUARE_SIZE
        row = 7 - (mouse_y - self.g.board_origin_y) // config.SQUARE_SIZE
        if 0 <= col < 8 and 0 <= row < 8:
            return chess.square(col, row)
        return None

    def update_hover(self, mouse_pos):
        """Call once per frame. Updates spellbook hover timer and returns (hovered_square, hovered_power)."""
        mouse_x, mouse_y = mouse_pos

        # spellbook hover tracking
        self._update_spellbook_hover(mouse_x, mouse_y)

        # main-screen hovers
        if self.g.main_game_screen:
            hovered_power = self._hovered_power_icon(mouse_x, mouse_y)
            hovered_square = self._hovered_board_square(mouse_x, mouse_y)
            return hovered_square, hovered_power

        # not on main game screen
        self.g.selected_square = None
        return None, None

    # ─────────────────────────────────────────────────────────────
    # Event handling
    # ─────────────────────────────────────────────────────────────
    def handle_event(self, event, hovered_square, hovered_power, mouse_pos):
        """
        Returns {"quit": bool}
        """
        g = self.g
        mouse_x, mouse_y = mouse_pos

        # window close
        if event.type == pygame.QUIT:
            return {"quit": True}

        # ─────────────────────────────────────────────
        # Menu interception (when open, it owns input)
        # ─────────────────────────────────────────────
        if g.menu.is_open:
            closed = g.menu.handle_event(event)
            if closed:
                pass
            return {"quit": False}

        # ESC opens menu (avoid hard pause / spellbook)
        if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
            if not g.hard_pause_start_time and not g.spellbook_open:
                g.menu.open()
            return {"quit": False}

        # Mouse click handling
        if event.type == pygame.MOUSEBUTTONDOWN:
            # Dismiss feedback if showing
            if g.renderer.feedback_text and g.renderer.feedback_frame_counter >= g.renderer.feedback_min_display_frames:
                g.renderer.feedback_collapse_early = True

            # prefer click position over stale mouse_pos
            if hasattr(event, "pos"):
                mouse_x, mouse_y = event.pos

            if g.main_game_screen:
                self._handle_main_game_click(event, hovered_square, hovered_power, mouse_x, mouse_y)
            elif g.spellbook_open:
                self._handle_spellbook_click(mouse_x, mouse_y)

        return {"quit": False}

    # ─────────────────────────────────────────────────────────────
    # Click sub-handlers
    # ─────────────────────────────────────────────────────────────
    def _handle_main_game_click(self, event, hovered_square, hovered_power, mouse_x, mouse_y):
        g = self.g

        # Gear targeting resolution has top priority
        if getattr(g.gear, "pending_action", None):
            if g.renderer.is_click_on_board(mouse_x, mouse_y):
                col = (mouse_x - g.board_origin_x) // config.SQUARE_SIZE
                row = 7 - (mouse_y - g.board_origin_y) // config.SQUARE_SIZE
                if 0 <= col < 8 and 0 <= row < 8:
                    sq = chess.square(col, row)
                    if g.gear.resolve_pending_click(sq):
                        return  # consume click fully

        if getattr(g, "wall_of_flame_active", False):
            if g.renderer.is_click_on_board(mouse_x, mouse_y):
                col = (mouse_x - g.board_origin_x) // config.SQUARE_SIZE
                row = 7 - (mouse_y - g.board_origin_y) // config.SQUARE_SIZE
                if 0 <= col < 8 and 0 <= row < 8:
                    sq = chess.square(col, row)
                    handler = getattr(g, "quest_reward_handler", None)
                    if handler and handler.resolve_wall_of_flame_row(sq):
                        g.possible_moves = []
                        return
            g.ui_state.send_feedback("Choose a board row for Wall of Flame.")
            return

        # Power icon click?
        if hovered_power:
            self._handle_power_icon_click(hovered_power)
            # note: we still allow board click to occur below if you want that behavior.

        # Compute board cell from click
        col = (mouse_x - g.board_origin_x) // config.SQUARE_SIZE
        row = 7 - (mouse_y - g.board_origin_y) // config.SQUARE_SIZE

        # Collect any click-based gold first (as before)
        g.board_manager.collect_gold()

        if 0 <= col < 8 and 0 <= row < 8:
            self._handle_board_click(col, row, hovered_square)

        # Spellbook open click region (same rect as before)
        book_icon_rect = pygame.Rect(
            config.WIDTH - config.POWER_WIDTH + 10,
            config.HEIGHT // 2 + 10,
            config.POWER_WIDTH - 20,
            (config.HEIGHT // 2) - 20
        )
        if book_icon_rect.collidepoint(mouse_x, mouse_y):
            g.spellbook_open = True
            g._spell_cache_dirty = True
            g.spell_rules.evaluate_spell_availability()
            g.main_game_screen = False
            print("Spellbook opened!")
            g.selected_square = None
            return

        # Gear UI click (bottom-right area) after other interactions
        if hasattr(event, "pos"):
            mouse_pos = event.pos
            if g.renderer.handle_gear_click(mouse_pos):
                return

    def _handle_power_icon_click(self, hovered_power: str):
        g = self.g
        count = g.powerups.get(hovered_power, 0)

        # Ensure swap helper attrs exist (so cleanup doesn't throw)
        if not hasattr(g, "swap_selected_square"):
            g.swap_selected_square = None
        if not hasattr(g, "swap_highlight_squares"):
            g.swap_highlight_squares = set()

        if count <= 0:
            if g.selected_power is not None:
                print(f"No uses left for {hovered_power}, deselecting all powers.")
                g.selected_power = None
                if hovered_power == "swaps":
                    g.swap_selected_square = None
                    g.swap_highlight_squares = set()
            return

        # toggle selection
        if g.selected_power == hovered_power:
            g.selected_power = None
            if hovered_power == "swaps":
                g.swap_selected_square = None
                g.swap_highlight_squares = set()
            print(f"Unselected power: {hovered_power}")
            return

        # switching to a new power
        g.selected_power = hovered_power
        print(f"Selected power: {hovered_power}")

        # If changing away from swaps, clear any partial swap state
        if hovered_power != "swaps":
            if g.swap_selected_square is not None:
                g.swap_selected_square = None
            if g.swap_highlight_squares:
                g.swap_highlight_squares = set()

        if g.selected_power == "bombs":
            g.ui_state.send_feedback("Bomb a pawn in the highlighted area.")

        # Immediate activation: time warp
        if hovered_power == "time_warps":
            if g.move_history:
                turns_to_rewind = 2
                for _ in range(turns_to_rewind):
                    if g.move_history:
                        last_state = g.move_history.pop()
                        g.board.set_fen(last_state)
                g.powerups["time_warps"] -= 1
                g.audio.play_random("time_warp")
                print(f"Time warp activated! Rewound {turns_to_rewind} turn(s).")
            g.selected_power = None

    def _handle_board_click(self, col: int, row: int, hovered_square):
        g = self.g
        square = chess.square(col, row)

        if getattr(g, "wall_of_flame_active", False):
            handler = getattr(g, "quest_reward_handler", None)
            if handler and handler.resolve_wall_of_flame_row(square):
                g.possible_moves = []
                return

        # ------------------------------------------------------------------
        # SPELL TARGETING: if a spell is armed, it gets first dibs on the click
        # ------------------------------------------------------------------
        st = getattr(g, "spell_targeting", None)
        if st is not None:
            try:
                if st.handle_board_click(square):
                    # Ensure we don’t “also” treat this as a piece selection / move
                    g.selected_square = None
                    g.possible_moves = []
                    return
            except Exception as e:
                print(f"[ERROR] spell_targeting.handle_board_click failed: {e}")
                # fall through to normal logic if something goes wrong


        # Ensure swap helper attrs exist
        if not hasattr(g, "swap_selected_square"):
            g.swap_selected_square = None
        if not hasattr(g, "swap_highlight_squares"):
            g.swap_highlight_squares = set()

        # -------------------- Swap power --------------------
        if g.selected_power == "swaps":
            player_color = chess.WHITE if g.player_side == "white" else chess.BLACK
            enemy_color = not player_color

            def is_on_player_side(sq: chess.Square) -> bool:
                r = chess.square_rank(sq)
                if g.player_side == "white":
                    return r <= 3
                return r >= 4

            def build_swap_highlights(from_sq: chess.Square) -> set[chess.Square]:
                """Squares on player side that contain an opposite-color piece (not king)."""
                p_from = g.board.piece_at(from_sq)
                if not p_from:
                    return set()
                want_color = enemy_color if p_from.color == player_color else player_color

                out = set()
                for sq in chess.SQUARES:
                    if not is_on_player_side(sq):
                        continue
                    if sq == from_sq:
                        continue
                    p = g.board.piece_at(sq)
                    if not p:
                        continue
                    if p.piece_type == chess.KING:
                        continue
                    if p.color == want_color:
                        out.add(sq)
                return out

            # Click must be on player side (both clicks)
            if not is_on_player_side(square):
                g.ui_state.send_feedback("Swaps can only be used on your side of the board.")
                return

            # FIRST CLICK
            if g.swap_selected_square is None:
                p1 = g.board.piece_at(square)
                if not p1:
                    g.ui_state.send_feedback("Select a piece to swap (not an empty square).")
                    return
                if p1.piece_type == chess.KING:
                    g.ui_state.send_feedback("You cannot swap kings.")
                    return
                if p1.piece_type == chess.PAWN:
                    g.ui_state.send_feedback("Pawns cannot be swapped.")
                    return

                g.swap_selected_square = square
                g.swap_highlight_squares = build_swap_highlights(square)
                print(f"Selected first square for swap: {chess.square_name(square)}")

                # Swap UI fix: if no valid targets, auto-cancel (prevents sticky state)
                if not g.swap_highlight_squares:
                    g.ui_state.send_feedback("No valid swap targets on your side.")
                    g.swap_selected_square = None
                    g.swap_highlight_squares = set()
                    g.selected_power = None
                return

            # SECOND CLICK
            sq1 = g.swap_selected_square
            sq2 = square

            # Clicking same square cancels
            if sq2 == sq1:
                g.swap_selected_square = None
                g.swap_highlight_squares = set()
                g.selected_power = None
                g.ui_state.send_feedback("Swap cancelled.")
                return

            piece1 = g.board.piece_at(sq1)
            piece2 = g.board.piece_at(sq2)

            # Require both squares to be occupied
            if not piece1 or not piece2:
                g.ui_state.send_feedback("Swaps must be between two pieces (no empty squares).")
                return

            # No kings
            if piece1.piece_type == chess.KING or piece2.piece_type == chess.KING:
                g.ui_state.send_feedback("You cannot swap kings.")
                return
            if piece1.piece_type == chess.PAWN or piece2.piece_type == chess.PAWN:
                g.ui_state.send_feedback("Pawns cannot be swapped.")
                return

            # Must be opposite colors (player <-> enemy)
            if piece1.color == piece2.color:
                g.ui_state.send_feedback("Swaps must be between your piece and an enemy piece.")
                return

            # Enforce second click must be in the computed highlight set
            if g.swap_highlight_squares and (sq2 not in g.swap_highlight_squares):
                g.ui_state.send_feedback("That is not a valid swap target.")
                return

            # Simulate swap on a temp board to ensure no instant checks shenanigans
            test_board = g.board.copy(stack=False)
            test_board.remove_piece_at(sq1)
            test_board.remove_piece_at(sq2)
            test_board.set_piece_at(sq2, piece1)
            test_board.set_piece_at(sq1, piece2)

            # 1) Would this leave side-to-move in check?
            test_board.turn = g.board.turn
            if test_board.is_check():
                g.ui_state.send_feedback("This swap would leave your king in check. Choose other squares.")
                print("[Swap] Cancelled: leaves player in check.")
                return

            # 2) Would this place opponent in check immediately?
            test_board.turn = not g.board.turn
            if test_board.is_check():
                g.ui_state.send_feedback("This swap would place the opponent in check. Choose other squares.")
                print("[Swap] Cancelled: checks opponent.")
                return

            # Perform real swap
            g.board.remove_piece_at(sq1)
            g.board.remove_piece_at(sq2)
            g.board.set_piece_at(sq2, piece1)
            g.board.set_piece_at(sq1, piece2)

            print(f"[Swap] Swapped {chess.square_name(sq1)} and {chess.square_name(sq2)}.")
            g.powerups["swaps"] -= 1
            g.quests.swap_used_this_turn = True

            # Clear swap state
            g.swap_selected_square = None
            g.swap_highlight_squares = set()
            g.selected_power = None
            g.board_manager.collect_gold()
            g.board_manager.update_allowed_moves()
            return

        # -------------------- Board-targeted powers --------------------
        if g.selected_power:
            piece = g.board.piece_at(square)
            used = (g.powers.activate_power(g.selected_power, square) is True)
            if used:
                g.quests.update_quest_variables(piece, move=None, player=True, power_used=g.selected_power)
                g.selected_power = None
            return

        # -------------------- Normal selection & move --------------------
        if g.selected_square is None and hovered_square is not None:
            piece = g.board.piece_at(hovered_square)
            player_color = chess.WHITE if g.player_side == "white" else chess.BLACK
            if piece and piece.color == player_color:
                g.selected_square = hovered_square
                g.board_manager.update_allowed_moves()
            return

        # Unselect piece (clicking same square)
        if g.selected_square == hovered_square:
            g.selected_square = None
            g.possible_moves = []
            return

        # Attempt to move to target
        g.board_manager._attempt_player_move_to(square)

    def _handle_spellbook_click(self, mouse_x: int, mouse_y: int):
        g = self.g

        icon_height = 36
        sorted_spells = sorted(g.spellbook)

        # Page 1
        x = 323
        y = 118
        for spell_name in sorted_spells[:8]:
            text_rect = pygame.Rect(x, y, 300, icon_height)
            if text_rect.collidepoint(mouse_x, mouse_y):
                print(f"Selected spell: {spell_name}")
                g.selected_spell = spell_name
                g.spellbook_open = False
                g._spell_cache_dirty = True
                g.main_game_screen = True
                g.spell_targeting.arm_from_spellbook(g.selected_spell)
                return
            y += icon_height
            if y > 550:
                break

        # Page 2
        x2 = 683
        y2 = 105
        for spell_name in sorted_spells[8:]:
            text_rect = pygame.Rect(x2, y2, 300, icon_height)
            if text_rect.collidepoint(mouse_x, mouse_y):
                print(f"Selected spell: {spell_name}")
                g.selected_spell = spell_name
                g.spellbook_open = False
                g.main_game_screen = True
                g.spell_targeting.arm_from_spellbook(g.selected_spell)
                return
            y2 += icon_height
            if y2 > 550:
                break

        # Click outside closes book
        book_rect = pygame.Rect(300, 100, 680, 450)
        if not book_rect.collidepoint(mouse_x, mouse_y):
            g.spellbook_open = False
            g._spell_cache_dirty = True
            g.main_game_screen = True
