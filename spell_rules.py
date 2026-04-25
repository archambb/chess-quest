# spell_rules.py
from __future__ import annotations

import chess


class SpellRules:
    """
    Centralized spell availability logic extracted from main.py.

    Design goals:
    - Do NOT rename any g.self.* variables
    - Keep identical behavior/prints as the old main.py logic
    - main.py keeps is_spell_available() name via wrapper
    """

    def __init__(self, game):
        self.g = game

    def is_spell_available(self, spell_name: str) -> bool:
        g = self.g

        if spell_name == "Summon Elf":
            player_colour = chess.WHITE if g.player_side == "white" else chess.BLACK

            # Count surviving bishops of the player
            bishops_alive = sum(
                1 for _, p in g.board.piece_map().items()
                if p.piece_type == chess.BISHOP and p.color == player_colour
            )

            if bishops_alive > 1:
                # Bishop is still on the board. Cannot cast.
                return False

            king_sq = g.board.king(player_colour)
            if king_sq is None:
                print("Summon Elf not available: player's king is missing.")
                return False

            print(f"King found at {chess.square_name(king_sq)}")
            k_file, k_rank = chess.square_file(king_sq), chess.square_rank(king_sq)

            for df in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    if df == 0 and dr == 0:
                        continue
                    f, r = k_file + df, k_rank + dr
                    if 0 <= f < 8 and 0 <= r < 8:
                        test_sq = chess.square(f, r)
                        if g.board.piece_at(test_sq) is None:
                            print(f"Found empty square adjacent to king: {chess.square_name(test_sq)}")
                            return True
            print("Summon Elf not available: no empty adjacent square to king.")
            return False

        elif spell_name == "Summon Undead Elves":
            player_colour = chess.WHITE if g.player_side == "white" else chess.BLACK

            bishops_alive = sum(
                1 for _, p in g.board.piece_map().items()
                if p.piece_type == chess.BISHOP and p.color == player_colour
            )

            if bishops_alive > 1:
                print("Summon Undead Elves not available: more than one bishop is still alive.")
                return False

            king_sq = g.board.king(player_colour)
            if king_sq is None:
                print("Summon Undead Elves not available: player's king is missing.")
                return False

            print(f"King found at {chess.square_name(king_sq)}")
            k_file, k_rank = chess.square_file(king_sq), chess.square_rank(king_sq)

            for df in (-1, 0, 1):
                for dr in (-1, 0, 1):
                    if df == 0 and dr == 0:
                        continue
                    f, r = k_file + df, k_rank + dr
                    if 0 <= f < 8 and 0 <= r < 8:
                        test_sq = chess.square(f, r)
                        if g.board.piece_at(test_sq) is None:
                            print(f"Found empty square adjacent to king: {chess.square_name(test_sq)}")
                            return True

            print("Summon Undead Elves not available: no empty adjacent square to king.")
            return False

        elif spell_name == "Granite Elf":
            player_colour = chess.WHITE if g.player_side == "white" else chess.BLACK

            for sq, piece in g.board.piece_map().items():
                if piece.piece_type != chess.BISHOP:
                    continue
                if piece.color != player_colour:
                    continue
                if not g.powers.is_on_player_side(sq):
                    continue

                print(f"Granite Elf available: bishop found on player side at {chess.square_name(sq)}")
                return True

            print("Granite Elf not available: no bishop on the player's side of the board.")
            return False

        elif spell_name == "Mirror Armies":
            piece_types = (
                chess.PAWN,
                chess.KNIGHT,
                chess.BISHOP,
                chess.ROOK,
                chess.QUEEN,
            )

            for piece_type in piece_types:
                white_count = sum(
                    1 for _, p in g.board.piece_map().items()
                    if p.piece_type == piece_type and p.color == chess.WHITE
                )
                black_count = sum(
                    1 for _, p in g.board.piece_map().items()
                    if p.piece_type == piece_type and p.color == chess.BLACK
                )

                if white_count != black_count:
                    print(
                        f"Mirror Armies available: mismatch found for piece type {piece_type} "
                        f"(white={white_count}, black={black_count})"
                    )
                    return True

            print("Mirror Armies not available: both armies already match.")
            return False

        elif spell_name == "Shadow Step":
            player_color = chess.WHITE if g.player_side == "white" else chess.BLACK
            king_sq = g.board.king(player_color)
            if king_sq is None:
                print("Shadow Step not available: king is missing.")
                return False
            print("Shadow Step available.")
            return True

        elif spell_name == "Desert Sun":
            result = bool(g.frozen_squares)
            print(f"Desert Sun {'available' if result else 'not available'}: frozen squares = {len(g.frozen_squares)}")
            return result

        elif spell_name == "Ice Blast":
            print("Ice Blast is always available.")
            return True

        elif spell_name == "Inspire Soldier":
            player_color = chess.WHITE if g.player_side == "white" else chess.BLACK
            for piece in g.board.piece_map().values():
                if piece.piece_type == chess.PAWN and piece.color == player_color:
                    return True
            print("Inspire Soldier not available: no pawns found.")
            return False

        elif spell_name == "Heal Pawns":
            player_colour = chess.WHITE if g.player_side == "white" else chess.BLACK
            pawns_alive = sum(
                1 for _, p in g.board.piece_map().items()
                if p.piece_type == chess.PAWN and p.color == player_colour
            )
            pawns_missing = 8 - pawns_alive
            if pawns_missing == 0:
                print("Heal Pawns not available: all pawns are already alive.")
                return False
            return True

        elif spell_name == "Sacrifice":
            player_color = chess.WHITE if g.player_side == "white" else chess.BLACK
            for square, piece in g.board.piece_map().items():
                if piece.piece_type == chess.QUEEN and piece.color == player_color:
                    print("Sacrifice is available: Queen is present.")
                    return True
            print("Sacrifice not available: No queen to sacrifice.")
            return False

        elif spell_name == "One With Light":
            if g.player_side == "white":
                print("One With Light unavailable: already white.")
                return False
            return True

        elif spell_name == "Greed":
            if g.gold_pieces:
                return True
            print("Greed unavailable: no gold on the board.")
            return False

        elif spell_name == "Meteor Shower":
            return True   # always castable

        print(f"{spell_name} is assumed available (no special rules).")
        return True

    def evaluate_spell_availability(self):
        self.cached_spell_availability = {
            spell: self.is_spell_available(spell)
            for spell in self.g.spellbook
        }
        self._spell_cache_dirty = False
        print("[SPELLBOOK] spell availability cache rebuilt")