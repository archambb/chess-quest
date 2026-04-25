# gear.py
import chess
import random
from typing import Dict, List

import config
from debug import Debug_GiveAllGear

# TODO: Key, wand of stupidity, compass seems to work but isn't rendering right, boots don't detect forked pieces appropriately

class Gear:
    """
    Central gear/gear system.

    - Inventory data is tracked in self.gear: {name: count}.
    - Canonical order & descriptions live in config:
        * config.GEAR_ORDER
        * config.GEAR_DESCRIPTIONS

    RenderPipeline calls `g.gear.use_gear(gear_id)` when the
    player clicks a gear icon.
    """

    def __init__(self, game):
        self.g = game          # ChessScreen
        # IMPORTANT: do NOT cache board; always use self.g.board
        self.pending_action = None  # e.g. "ice_pick_target", "hatchet_target"

        # Base gear layout uses canonical order from config
        self.gear: Dict[str, int] = {
            name: 0 for name in config.GEAR_ORDER
        }

        # Example global gear state
        self.gear_key_unlocked: bool = False

        # DEBUG: give all gear if debug flag is set
        if getattr(self.g, "debug", False):
            self.gear = Debug_GiveAllGear(config.GEAR_ORDER)
            print("[DEBUG] All gear granted:", self.gear)

    # ─────────────────────────────────────────────
    # Inventory helpers
    # ─────────────────────────────────────────────
    def has(self, name: str) -> bool:
        """Return True if the player currently owns this gear."""
        return self.gear.get(name, 0) > 0

    def grant(self, name: str, amount: int = 1) -> None:
        """Grant gear (used by shops, quest rewards, etc.)."""
        if name not in self.gear:
            print(f"[EQUIP] Unknown gear '{name}' - not granting.")
            return
        self.gear[name] += amount
        print(f"[EQUIP] Granted {amount}x {name}. New total: {self.gear[name]}")

    def use(self, name: str) -> bool:
        """
        Legacy "consume" call. You said gear is NEVER consumed,
        so this is left here for compatibility but should not be used.
        """
        if not self.has(name):
            print(f"[EQUIP] Tried to use '{name}' but none are owned.")
            return False

        # If you ever decide some gear is consumable, uncomment this:
        # self.gear[name] -= 1
        # print(f"[EQUIP] Used 1x {name}. Remaining: {self.gear[name]}")
        print(f"[EQUIP] use('{name}') called, but gear is non-consumable.")
        return True

    def all_owned(self) -> List[str]:
        """Return a list of gear names you currently own (value > 0)."""
        return [name for name, value in self.gear.items() if value > 0]

    # ─────────────────────────────────────────────
    # Descriptions (from config)
    # ─────────────────────────────────────────────
    def get_description(self, name: str) -> str:
        return config.GEAR_DESCRIPTIONS.get(name, "[Unknown gear]")

    def get_display_name(self, name: str) -> str:
        desc = self.get_description(name)
        for sep in ("-", "-"):
            if sep in desc:
                return desc.split(sep, 1)[0].strip()
        return desc.strip()

    # ─────────────────────────────────────────────
    # Top-level use entry point (called by RenderPipeline)
    # ─────────────────────────────────────────────
    def use_gear(self, gear_id: str) -> bool:
        """
        Entry point for UI clicks on a gear icon.

        - Checks that the player owns the gear.
        - Dispatches to a handler named _use_<gear_id>.
        - Gear is NEVER consumed here (handlers just perform effects).

        Returns True if the click was handled (even if no effect),
        False only if the gear is unknown or we don't own it.
        """
        if gear_id not in self.gear:
            print(f"[EQUIP] use_gear called with unknown id '{gear_id}'.")
            return False

        if not self.has(gear_id):
            print(f"[EQUIP] Player tried to use '{gear_id}' but owns none.")
            return False

        handler_name = f"_use_{gear_id}"
        handler = getattr(self, handler_name, None)

        if handler is None:
            print(f"[EQUIP] No handler {handler_name} implemented yet.")
            return True  # click handled, but nothing happens

        try:
            result = handler()
            print(f"[EQUIP] Handler {handler_name} executed; result={result}")
        except Exception as e:
            print(f"[EQUIP] Error while using '{gear_id}': {e}")

        # IMPORTANT: gear is never consumed here
        return True

    # ─────────────────────────────────────────────
    # Convenience: player color
    # ─────────────────────────────────────────────
    @property
    def player_color(self) -> chess.Color:
        if hasattr(self.g, "player_color"):
            return self.g.player_color()
        return chess.WHITE if getattr(self.g, "player_side", "white") == "white" else chess.BLACK

    # ─────────────────────────────────────────────
    # Per-item handlers (1-12)
    # ─────────────────────────────────────────────

    # 1.png
    def _use_hatchet(self) -> bool:
        """
        Hatchet - Shatter an enemy shield.
        Enter a click-target mode; the next board click is handled
        in resolve_pending_click().
        """
        self.pending_action = "hatchet_target"
        print("[EQUIP] Hatchet armed: awaiting click on a shielded square.")
        return True

    # 2.png
    def _use_mace(self) -> bool:
        """
        Mace - Turn all enemy rooks into pawns.
        """
        board = self.g.board
        player_color = self.player_color
        enemy_color = not player_color

        enemy_rooks = [
            sq for sq in chess.SQUARES
            if (piece := board.piece_at(sq))
            and piece.color == enemy_color
            and piece.piece_type == chess.ROOK
        ]

        if not enemy_rooks:
            print("[EQUIP] Mace: no enemy rooks found.")
            return False

        for sq in enemy_rooks:
            board.set_piece_at(sq, chess.Piece(chess.PAWN, enemy_color))

        if hasattr(self.g.board_manager, "update_allowed_moves"):
            self.g.board_manager.update_allowed_moves()

        print(f"[EQUIP] Mace: converted {len(enemy_rooks)} enemy rooks to pawns.")
        return True

    # 3.png
    def _use_crossbow(self) -> bool:
        """
        Crossbow - Fire straight down your king's file, destroying
        the first enemy pawn hit (if any).
        """
        board = self.g.board
        player_color = self.player_color
        enemy_color = not player_color

        king_sq = board.king(player_color)
        if king_sq is None:
            print("[EQUIP] Crossbow: king not found.")
            return False

        k_file = chess.square_file(king_sq)
        k_rank = chess.square_rank(king_sq)
        direction = 1 if player_color == chess.WHITE else -1

        target_sq = None
        r = k_rank + direction
        while 0 <= r <= 7:
            sq = chess.square(k_file, r)
            piece = board.piece_at(sq)
            if piece is None:
                r += direction
                continue

            if piece.color == enemy_color and piece.piece_type == chess.PAWN:
                target_sq = sq
            break

        if target_sq is None:
            print("[EQUIP] Crossbow: no enemy pawn on king's file.")
            return False

        board.remove_piece_at(target_sq)
        if hasattr(self.g, "audio"):
            try:
                self.g.audio.play_random("crossbow")
            except Exception:
                pass

        if hasattr(self.g.board_manager, "update_allowed_moves"):
            self.g.board_manager.update_allowed_moves()

        print(f"[EQUIP] Crossbow: destroyed pawn on {chess.square_name(target_sq)}.")
        return True

    # 4.png
    def _use_sling(self) -> bool:
        """
        Sling - If any of your pawns share a rank with the enemy queen
        and the path is clear horizontally, remove that queen.
        """
        board = self.g.board
        player_color = self.player_color
        enemy_color = not player_color

        # Find enemy queen (first one only)
        queen_sq = None
        for sq, piece in board.piece_map().items():
            if piece and piece.color == enemy_color and piece.piece_type == chess.QUEEN:
                queen_sq = sq
                break

        if queen_sq is None:
            print("[EQUIP] Sling: no enemy queen present.")
            return False

        queen_rank = chess.square_rank(queen_sq)
        queen_file = chess.square_file(queen_sq)

        pawns = [
            sq for sq, piece in board.piece_map().items()
            if piece and piece.color == player_color and piece.piece_type == chess.PAWN
        ]

        for pawn_sq in pawns:
            if chess.square_rank(pawn_sq) != queen_rank:
                continue

            pawn_file = chess.square_file(pawn_sq)
            if pawn_file == queen_file:
                continue  # same square is impossible, but guard anyway

            if pawn_file < queen_file:
                between_files = range(pawn_file + 1, queen_file)
            else:
                between_files = range(queen_file + 1, pawn_file)

            clear = True
            for f in between_files:
                sq = chess.square(f, queen_rank)
                if board.piece_at(sq) is not None:
                    clear = False
                    break

            if not clear:
                continue

            # Success: remove queen
            board.remove_piece_at(queen_sq)
            if hasattr(self.g.board_manager, "update_allowed_moves"):
                self.g.board_manager.update_allowed_moves()

            print(
                f"[EQUIP] Sling: pawn at {chess.square_name(pawn_sq)} "
                f"sniped queen at {chess.square_name(queen_sq)}."
            )
            return True

        print("[EQUIP] Sling: no pawn had a clear line to the queen.")
        return False

    # 5.png
    def _use_torch(self) -> bool:
        """
        Torch - On stage 4 only, remove all enemy pawns ("Pawns of Darkness").
        """
        try:
            stage_id = self.g.world.world_data[self.g.world.player_pos]["stage_id"]
        except Exception:
            stage_id = None

        if stage_id != 4:
            print("[EQUIP] Torch: wrong stage (needs stage_id 4).")
            return False

        board = self.g.board
        player_color = self.player_color
        enemy_color = not player_color

        to_remove = [
            sq for sq, piece in board.piece_map().items()
            if piece and piece.color == enemy_color and piece.piece_type == chess.PAWN
        ]

        if not to_remove:
            print("[EQUIP] Torch: no enemy pawns to burn.")
            return False

        for sq in to_remove:
            board.remove_piece_at(sq)

        if hasattr(self.g.board_manager, "update_allowed_moves"):
            self.g.board_manager.update_allowed_moves()

        print(f"[EQUIP] Torch: removed {len(to_remove)} enemy pawns.")
        return True

    # 6.png
    def _use_crystal_staff(self) -> bool:
        """
        Transform all your pawns into N/B/R with:
            50% Knight, 30% Bishop, 20% Rook.
        """
        board = self.g.board
        player_color = self.player_color

        pawn_squares = [
            sq for sq, piece in board.piece_map().items()
            if piece and piece.color == player_color and piece.piece_type == chess.PAWN
        ]

        if not pawn_squares:
            print("[EQUIP] Crystal Staff: no pawns to transmute.")
            return False

        for sq in pawn_squares:
            roll = random.random()
            if roll < 0.50:
                new_type = chess.KNIGHT
            elif roll < 0.80:
                new_type = chess.BISHOP
            else:
                new_type = chess.ROOK

            board.set_piece_at(sq, chess.Piece(new_type, player_color))

        if hasattr(self.g.board_manager, "update_allowed_moves"):
            self.g.board_manager.update_allowed_moves()

        print(f"[EQUIP] Crystal Staff: transmuted {len(pawn_squares)} pawns.")
        return True

    # 7.png
    def _use_wand_of_stupidity(self) -> bool:
        """
        Placeholder: reduce enemy AI strength (to be implemented).
        """
        print("[EQUIP] Wand of Stupidity: not implemented yet.")
        return False

    # 8.png
    def _use_gear_key(self) -> bool:
        """
        Gear Key — unlocks the Powers UI (chain / lock / shackle).

        This triggers the renderer animation. The renderer is responsible
        for eventually setting `self.g.powers_unlocked = True`.

        Gear is NOT consumed.
        """

        # Already unlocked → nothing to do
        if getattr(self.g, "powers_unlocked", False):
            print("[EQUIP] Gear Key: powers already unlocked.")
            return False

        renderer = getattr(self.g, "renderer", None)
        if renderer and hasattr(renderer, "unlock_powers_area"):
            renderer.unlock_powers_area()
            print("[EQUIP] Gear Key: triggered powers unlock animation.")
            return True

        # Safety fallback (should never happen in normal gameplay)
        self.g.powers_unlocked = True
        print("[EQUIP] Gear Key: renderer missing — powers unlocked immediately.")
        return True


    # 9.png
    def _use_compass(self) -> bool:
        """
        Compass - store a checkmating move (if one exists) in self.g.compass_hint.
        """
        board = self.g.board

        mating_move = None
        for move in board.legal_moves:
            test = board.copy(stack=False)
            test.push(move)
            if test.is_checkmate():
                mating_move = move
                break

        if mating_move is None:
            print("[EQUIP] Compass: no mating move found.")
            return False

        self.g.compass_hint = (mating_move.from_square, mating_move.to_square)
        print(
            f"[EQUIP] Compass: mate hint {board.san(mating_move)} "
            f"({chess.square_name(mating_move.from_square)} -> "
            f"{chess.square_name(mating_move.to_square)})."
        )
        return True

    # 10.png
    def _use_boots(self) -> bool:
        """
        Boots - move forked non-king pieces to random adjacent safe squares.
        """
        board = self.g.board
        player_color = self.player_color
        enemy_color = not player_color

        forked = []
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if not piece or piece.color != player_color or piece.piece_type == chess.KING:
                continue
            attackers = board.attackers(enemy_color, sq)
            if len(attackers) >= 2:
                forked.append(sq)

        if not forked:
            print("[EQUIP] Boots: no forked pieces found.")
            return False

        moved_any = False
        rng = getattr(self.g, "random", random)

        for sq in forked:
            piece = board.piece_at(sq)
            if piece is None:
                continue

            f0 = chess.square_file(sq)
            r0 = chess.square_rank(sq)

            candidates = []
            for df in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    if df == 0 and dr == 0:
                        continue
                    f, r = f0 + df, r0 + dr
                    if 0 <= f < 8 and 0 <= r < 8:
                        dest = chess.square(f, r)
                        if board.piece_at(dest) is None and not board.is_attacked_by(enemy_color, dest):
                            candidates.append(dest)

            if not candidates:
                continue

            dest = rng.choice(candidates)
            board.remove_piece_at(sq)
            board.set_piece_at(dest, piece)
            moved_any = True

        if moved_any and hasattr(self.g, "update_allowed_moves"):
            self.g.board_manager.update_allowed_moves()

        print(f"[EQUIP] Boots: moved forked pieces, success={moved_any}.")
        return moved_any

    # 11.png
    def _use_ice_pick(self) -> bool:
        """
        Ice Pick - Thaw one frozen square using the SAME pattern as Hatchet:
        set self.pending_action and let resolve_pending_click handle the square.
        """
        if not getattr(self.g, "frozen_squares", None):
            print("[EQUIP] Ice Pick: no frozen squares to thaw.")
            return False

        self.pending_action = "ice_pick_target"
        print("[EQUIP] Ice Pick armed: awaiting click on a frozen square.")
        return True  # armed; effect happens on click

    # 12.png
    def _use_sword_of_regicide(self) -> bool:
        """
        Sword of Regicide - remove all enemy queens.
        """
        board = self.g.board
        player_color = self.player_color
        enemy_color = not player_color

        removed = 0
        for sq in chess.SQUARES:
            piece = board.piece_at(sq)
            if piece and piece.color == enemy_color and piece.piece_type == chess.QUEEN:
                board.remove_piece_at(sq)
                removed += 1

        if removed == 0:
            print("[EQUIP] Sword of Regicide: no enemy queens found.")
            return False

        if hasattr(self.g.board_manager, "update_allowed_moves"):
            self.g.board_manager.update_allowed_moves()

        print(f"[EQUIP] Sword of Regicide: removed {removed} enemy queen(s).")
        return True

    # ─────────────────────────────────────────────
    # Board-click resolution for targeting gear
    # ─────────────────────────────────────────────
    def resolve_pending_click(self, square: int) -> bool:
        """
        Called from main.py when the player clicks a square WHILE a gear
        targeting mode is active (Hatchet, Ice Pick, etc.).
        """
        action = self.pending_action
        if not action:
            return False

        # ICE PICK TARGET
        if action == "ice_pick_target":
            self.pending_action = None
            if square in self.g.frozen_squares:
                del self.g.frozen_squares[square]
                print(f"[EQUIP] Ice Pick: thawed {chess.square_name(square)}.")
                return True

            print("[EQUIP] Ice Pick: clicked square is not frozen.")
            return False

        # HATCHET TARGET
        if action == "hatchet_target":
            self.pending_action = None
            if square in self.g.shielded_squares:
                del self.g.shielded_squares[square]
                print(f"[EQUIP] Hatchet: broke shield on {chess.square_name(square)}.")
                return True

            print("[EQUIP] Hatchet: no shield on that square.")
            return False

        # Unknown / no-op action
        print(f"[EQUIP] resolve_pending_click: unknown action '{action}'.")
        self.pending_action = None
        return False
