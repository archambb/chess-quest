from __future__ import annotations

import sys
from types import SimpleNamespace
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from board_manager import BoardManager


class _MapChallenges:
    def prune_moves(self, moves, **kwargs):
        return list(moves)

    def extra_stage_moves_for_highlight(self, *args, **kwargs):
        return []

    def maybe_apply_slip_after_player_move(self, *args, **kwargs):
        return None


class _Renderer:
    def animate_piece_move(self, *args, **kwargs):
        return None


class _Quests:
    def __init__(self):
        self.moves = []

    def update_quest_variables(self, piece=None, move=None, player=False, **kwargs):
        self.moves.append((piece, move, player))


class _UIState:
    def send_feedback(self, message):
        raise AssertionError(f"Unexpected feedback: {message}")


def _game(board, choice):
    game = SimpleNamespace()
    game.board = board
    game.selected_square = None
    game.frozen_squares = {}
    game.shielded_squares = {}
    game.move_history = []
    game.renderer = _Renderer()
    game.map_challenges = _MapChallenges()
    game.quests = _Quests()
    game.ui_state = _UIState()
    game.turns = 0
    game.player_side = "white" if board.turn == chess.WHITE else "black"
    game.player_has_promoted = False
    game.board_manager = None
    game.promotion_choice_provider = lambda color, src, dst, legal: choice
    manager = BoardManager(game)
    game.board_manager = manager
    game._clear_king_protections = manager._clear_king_protections
    game.gold_pieces = set()
    game.landed_gold_pieces = set()
    game.player_gold = 0
    return game, manager


def _assert_move(fen, src, dst, choice, expected_uci, expected_piece):
    board = chess.Board(fen)
    game, manager = _game(board, choice)
    game.selected_square = chess.parse_square(src)
    assert manager._attempt_player_move_to(chess.parse_square(dst))
    move = board.move_stack[-1]
    assert move.uci() == expected_uci, move.uci()
    piece = board.piece_at(chess.parse_square(dst))
    assert piece and piece.piece_type == expected_piece, piece
    assert game.player_has_promoted is True


def main():
    _assert_move("k7/4P3/8/8/8/8/8/K7 w - - 0 1", "e7", "e8", chess.KNIGHT, "e7e8n", chess.KNIGHT)
    _assert_move("k7/8/8/8/8/8/4p3/7K b - - 0 1", "e2", "e1", chess.ROOK, "e2e1r", chess.ROOK)
    _assert_move("5r1k/4P3/8/8/8/8/8/K7 w - - 0 1", "e7", "f8", chess.BISHOP, "e7f8b", chess.BISHOP)

    board = chess.Board("4k3/8/8/8/8/8/4P3/4K3 w - - 0 1")
    game, manager = _game(board, chess.ROOK)
    game.selected_square = chess.E2
    assert manager._attempt_player_move_to(chess.E3)
    assert board.move_stack[-1].uci() == "e2e3"
    assert game.player_has_promoted is False

    board = chess.Board("k7/4P3/8/8/8/8/8/K7 w - - 0 1")
    game, manager = _game(board, chess.KING)
    game.selected_square = chess.E7
    assert manager._attempt_player_move_to(chess.E8)
    assert board.move_stack[-1].uci() == "e7e8q"

    print("[OK] Promotion choice validation passed.")


if __name__ == "__main__":
    main()
