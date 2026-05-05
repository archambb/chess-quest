import os
import sys

import chess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from quest_info import QuestInfo


def _quest_info_for_validation():
    quest_info = QuestInfo.__new__(QuestInfo)
    quest_info.enemy_non_pawn_streak = 0
    quest_info.quest_status = {"Enemy Pawns Haven't Moved": 0}
    return quest_info


def _apply_wall_of_fire_check(quest_info, board, enemy_color):
    key = "Enemy Pawns Haven't Moved"
    if quest_info._count_enemy_pawns_without_legal_moves(board, enemy_color) >= 4:
        quest_info.enemy_non_pawn_streak += 1
        quest_info.quest_status[key] = quest_info.enemy_non_pawn_streak
    else:
        quest_info.enemy_non_pawn_streak = 0
        quest_info.quest_status[key] = 0
    return quest_info.quest_status[key]


def main():
    quest_info = _quest_info_for_validation()

    # Fewer than 4 blocked pawns should not progress Wall of Fire.
    open_pawn_board = chess.Board("4k3/pppp4/nn6/8/8/8/8/4K3 b - - 0 1")
    assert quest_info._count_enemy_pawns_without_legal_moves(open_pawn_board, chess.BLACK) == 2
    assert _apply_wall_of_fire_check(quest_info, open_pawn_board, chess.BLACK) == 0

    # At least 4 blocked enemy pawns should progress the streak.
    blocked_pawn_board = chess.Board("4k3/pppp4/nnnn4/8/8/8/8/4K3 b - - 0 1")
    assert quest_info._count_enemy_pawns_without_legal_moves(blocked_pawn_board, chess.BLACK) == 4
    assert _apply_wall_of_fire_check(quest_info, blocked_pawn_board, chess.BLACK) == 1
    assert _apply_wall_of_fire_check(quest_info, blocked_pawn_board, chess.BLACK) == 2

    # If the blocked count falls below 4, the streak resets.
    assert _apply_wall_of_fire_check(quest_info, open_pawn_board, chess.BLACK) == 0

    # A pawn blocked directly ahead but with a legal capture still counts as movable.
    capture_board = chess.Board("4k3/pppp4/nnnnP3/8/8/8/8/4K3 b - - 0 1")
    assert quest_info._count_enemy_pawns_without_legal_moves(capture_board, chess.BLACK) == 3

    print("Wall of Fire trigger validation passed.")


if __name__ == "__main__":
    main()
