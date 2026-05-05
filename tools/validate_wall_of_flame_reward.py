import os
import sys
from types import SimpleNamespace

import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quest_rewards import QuestRewardHandler


class DummyQuests:
    def __init__(self):
        self.captured = []

    def record_captured_piece(self, captured_piece, count_for_quests=False):
        if count_for_quests:
            self.captured.append(captured_piece)


class DummyBoardManager:
    def __init__(self):
        self.updated = False

    def update_allowed_moves(self):
        self.updated = True


class TestRewardHandler(QuestRewardHandler):
    def __init__(self, game):
        self.g = game
        self.effects_called = False

    def play_wall_of_flame_effects(self, row_squares, removed):
        self.effects_called = True
        self.effect_row = list(row_squares)
        self.effect_removed = list(removed)


def main():
    board = chess.Board(None)
    board.set_piece_at(chess.E1, chess.Piece(chess.KING, chess.WHITE))
    board.set_piece_at(chess.E8, chess.Piece(chess.KING, chess.BLACK))
    board.set_piece_at(chess.A4, chess.Piece(chess.ROOK, chess.BLACK))
    board.set_piece_at(chess.C4, chess.Piece(chess.BISHOP, chess.BLACK))
    board.set_piece_at(chess.E4, chess.Piece(chess.KNIGHT, chess.WHITE))
    board.set_piece_at(chess.H4, chess.Piece(chess.KING, chess.BLACK))

    game = SimpleNamespace(
        board=board,
        player_side="white",
        wall_of_flame_active=False,
        selected_square=chess.E4,
        selected_power="bombs",
        selected_spell="Flood",
        quests=DummyQuests(),
        board_manager=DummyBoardManager(),
    )

    handler = TestRewardHandler(game)
    handler.trigger_firewall()

    assert game.wall_of_flame_active is True
    assert game.selected_square is None
    assert game.selected_power is None
    assert game.selected_spell is None

    used = handler.resolve_wall_of_flame_row(chess.D4)
    assert used is True
    assert game.wall_of_flame_active is False
    assert game.board.piece_at(chess.A4) is None
    assert game.board.piece_at(chess.C4) is None
    assert game.board.piece_at(chess.E4).color == chess.WHITE
    assert game.board.piece_at(chess.H4).piece_type == chess.KING
    assert len(game.quests.captured) == 2
    assert handler.effects_called is True
    assert game.board_manager.updated is True

    print("Wall of Flame reward validation passed.")


if __name__ == "__main__":
    main()
