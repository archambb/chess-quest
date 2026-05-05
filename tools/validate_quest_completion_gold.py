from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from quest_info import QuestInfo


class _RewardHandler:
    def __init__(self, game):
        self.g = game
        self.calls = []

    def give_reward(self, quest_num, reward, display_index=None):
        self.calls.append((quest_num, reward, display_index))
        for key, value in reward.items():
            if key == "gold":
                self.g.player_gold += value
            elif key == "double_gold":
                self.g.player_gold *= 2


def _quest_info(active_quests, starting_gold=0):
    game = SimpleNamespace()
    game.player_gold = starting_gold
    game.quest_reward_handler = _RewardHandler(game)

    quests = QuestInfo.__new__(QuestInfo)
    quests.g = game
    quests.active_quests = list(active_quests)
    return quests, game


def validate_completion_gold_stacks_with_gold_reward():
    quests, game = _quest_info([7], starting_gold=10)
    quests.win_quest(7, {"gold": 5})

    assert game.player_gold == 18, game.player_gold
    assert quests.active_quests == []
    assert game.quest_reward_handler.calls == [(7, {"gold": 5}, 0)]


def validate_completion_gold_only_once():
    quests, game = _quest_info([9], starting_gold=0)
    quests.win_quest(9, {})
    quests.win_quest(9, {})

    assert game.player_gold == 3, game.player_gold
    assert len(game.quest_reward_handler.calls) == 1


def validate_completion_gold_after_double_reward():
    quests, game = _quest_info([12], starting_gold=10)
    quests.win_quest(12, {"double_gold": 1})

    assert game.player_gold == 23, game.player_gold


def main():
    validate_completion_gold_stacks_with_gold_reward()
    validate_completion_gold_only_once()
    validate_completion_gold_after_double_reward()
    print("[OK] Quest completion gold validation passed.")


if __name__ == "__main__":
    main()
