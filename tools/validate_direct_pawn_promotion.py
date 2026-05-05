from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import chess

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from board_manager import BoardManager
from quest_rewards import QuestRewardHandler


class _Audio:
    def play_random(self, *args, **kwargs):
        return None


class _Renderer:
    def animate_piece_move(self, *args, **kwargs):
        return None


class _Quests:
    def record_captured_piece(self, *args, **kwargs):
        return None


def _game(board, player_side="white"):
    game = SimpleNamespace()
    game.board = board
    game.player_side = player_side
    game.gold_pieces = set()
    game.gold_icons = {}
    game.landed_gold_pieces = set()
    game.player_gold = 0
    game.audio = _Audio()
    game.renderer = _Renderer()
    game.quests = _Quests()
    game.frozen_squares = {}
    game.shielded_squares = {}
    game.board_manager = BoardManager(game)
    return game


def _piece(board, square_name):
    return board.piece_at(chess.parse_square(square_name))


def validate_helper():
    board = chess.Board("4P3/8/8/8/8/8/8/4p3 w - - 0 1")
    game = _game(board)
    promoted = game.board_manager.promote_back_rank_pawns_to_queens()

    assert set(promoted) == {chess.E8, chess.E1}
    assert _piece(board, "e8").piece_type == chess.QUEEN
    assert _piece(board, "e1").piece_type == chess.QUEEN
    assert _piece(board, "e8").color == chess.WHITE
    assert _piece(board, "e1").color == chess.BLACK


def validate_advance_rows_promotes_white():
    board = chess.Board("7k/4P3/8/8/8/8/8/K7 w - - 0 1")
    game = _game(board, player_side="white")
    QuestRewardHandler(game).advance_all_pieces_one_row()

    piece = _piece(board, "e8")
    assert piece and piece.piece_type == chess.QUEEN and piece.color == chess.WHITE
    assert _piece(board, "e7") is None


def validate_advance_rows_promotes_black():
    board = chess.Board("k7/8/8/8/8/8/4p3/7K b - - 0 1")
    game = _game(board, player_side="black")
    QuestRewardHandler(game).advance_all_pieces_one_row()

    piece = _piece(board, "e1")
    assert piece and piece.piece_type == chess.QUEEN and piece.color == chess.BLACK
    assert _piece(board, "e2") is None


def main():
    validate_helper()
    validate_advance_rows_promotes_white()
    validate_advance_rows_promotes_black()
    print("[OK] Direct pawn promotion validation passed.")


if __name__ == "__main__":
    main()
