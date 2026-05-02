# Bug Triage Recommendations

## Executive Summary

The highest-value bugs are progression/reward bugs, not balance polish. The best first fix is the story reward path: the bug report says the Light spell was not awarded and likely all spells are affected, and the current code confirms that `StoryPlayer` stores `return_rewards` on `last_rewards` without returning them to `StoryMode`.

Several reported items appear already fixed or partially fixed in the current tree, especially the overworld crash traceback and magnet freeze/shield behavior. Those should be verified before changing code. Quest-condition bugs such as Wall of Fire are real but touch game logic, so they should be fixed in small, testable steps with explicit expected behavior.

## Top 5 Bugs to Address

### 1. Story Spell Rewards Are Not Applied

- Evidence: `bug_report.txt` says, "Took light spell but didnt' get it. Probably all spells won't work (probably didnt' get that part of the code working)".
- Likely root cause: `play_story.py` sets `StoryPlayer.last_rewards` when an option has `return_choice`, but `play_story()` returns only the target string. `story_mode.py` only applies rewards when the raw story result is a dict or tuple containing rewards, so modern story rewards in `data/frames.json` are silently skipped. Stone appears to work only because `StoryMode.handle_win_story()` has legacy hard-coded Stone reward logic.
- Relevant files/functions: `play_story.py::StoryPlayer.play_frame`, `play_story.py::StoryPlayer.play_story`, `story_mode.py::StoryMode._normalize_story_result_and_apply_rewards`, `story_mode.py::StoryMode.handle_win_story`, `data/frames.json`.
- Recommended fix: Make `StoryMode` consume `self.story_player.last_rewards` when `play_story()` returns a plain string, then clear `last_rewards` after applying. Add a tiny regression test or harness for a story option that returns `"One With Light"` through `return_rewards`. Be careful not to double-award Stone rewards, since Stone currently has both JSON rewards and legacy code.
- Difficulty: Medium
- Regression risk: Medium
- Player impact: High
- Confidence: High
- Fix now? Yes
- Notes: This is small and reversible, and it unlocks a core campaign reward path. The only tricky bit is preserving Stone behavior without awarding duplicate shields/promotions or duplicate `Summon Boulder`.

### 2. Overworld Progression / Story Advance Crash

- Evidence: `bug_report.txt` says, "moving on with the story is broken," followed by `[WARN] TerritoryWinScreen failed: 'GameWorld' object has no attribute 'game'` and a traceback ending in `game_world.py`, `overworld_move`, `NameError: name 'g' is not defined`.
- Likely root cause: The reported runtime had stale references to `g` inside `GameWorld.overworld_move()` and `TerritoryWinScreen` expected a `GameWorld.game` alias. In the current tree, `GameWorld.__init__` already sets both `self.g` and `self.game`, and `overworld_move()` now uses `game = self.g`, so this specific traceback may already be fixed.
- Relevant files/functions: `game_world.py::GameWorld.__init__`, `game_world.py::GameWorld.record_win`, `game_world.py::GameWorld.overworld_move`, `game_won.py::TerritoryWinScreen.__init__`, `game_result.py::GameResultManager.win_round`.
- Recommended fix: First run a focused manual/debug smoke test for winning a territory and entering `overworld_move()`. Only patch if the current tree still crashes. If it does, keep the fix limited to replacing stray `g` references with `self.g`/local `game` and ensuring `GameWorld.game` exists.
- Difficulty: Low if still present
- Regression risk: Low
- Player impact: High
- Confidence: Medium
- Fix now? Maybe
- Notes: This blocks campaign progression if live, but current code suggests it may already be resolved. Do not spend a large fix on this without reproducing it.

### 3. Wall of Fire Quest Triggers From Enemy Non-Pawn Moves, Not Blocked Pawns

- Evidence: `bug_report.txt` says, "Blocking pawns is really just looking at if a pawn hasn't moved. We need to see if it COULD move," and logs Quest #45 completing with `"Enemy Pawns Haven't Moved: 6 >= 5"` followed by `[QuestReward] Firewall cast`.
- Likely root cause: `quest_info.py` handles `"Enemy Pawns Haven't Moved"` by incrementing `enemy_non_pawn_streak` whenever the enemy moves a non-pawn. It does not inspect whether enemy pawns have legal moves available. It also adds the whole streak value each turn, which can inflate the stat faster than one per turn.
- Relevant files/functions: `quest_info.py::QuestInfo.update_quest_variables`, `data/quests.json` Quest #45 "Wall of Fire", likely `quest_rewards.py::QuestRewardHandler.trigger_firewall` once the condition is correct.
- Recommended fix: Define the intended condition explicitly: likely "all enemy pawns have zero legal pawn moves for 5 consecutive enemy turns." Implement a helper that scans enemy pawns and `board.legal_moves`, updates the quest stat to a consecutive-turn count, and resets when any enemy pawn can move. Add a board-position test for blocked vs merely unmoved pawns.
- Difficulty: Medium
- Regression risk: Medium
- Player impact: High
- Confidence: High
- Fix now? Yes, after story rewards
- Notes: This is game logic, so it needs explicit permission and a narrow test. The current reward `trigger_firewall()` is still a placeholder, so the condition fix and reward implementation should probably be separate changes.

### 4. Quest / Story Reward Presentation Queue May Be Incomplete or Misleading

- Evidence: `bug_report.txt` says Quest #44 completes, then notes "Animation doesn't do the exclude". It also says "possibly fixed... When winning multiple quests at the same time, let them fire one after the other (build a win queue)".
- Likely root cause: The current tree now has `QuestRewardHandler.reward_win_queue` and renderer-driven serialization, so the multiple-reward queue looks partially implemented. The remaining risk is presentation-state mismatch: `QuestInfo.win_quest()` removes the quest from `active_quests` immediately, while `RenderPipeline.start_quest_win_animation()` later reconstructs card position using `display_index`. If the index or candidate card lookup drifts, the animation can appear at the wrong slot or fail to exclude/redraw the right card.
- Relevant files/functions: `quest_info.py::QuestInfo.win_quest`, `quest_rewards.py::QuestRewardHandler.give_reward`, `quest_rewards.py::QuestRewardHandler.update_reward_queue`, `render.py::RenderPipeline.update_reward_presentation_queue`, `render.py::RenderPipeline.start_quest_win_animation`, `render.py::RenderPipeline.draw_current_quest_cards`.
- Recommended fix: Verify with two simultaneous quest completions before changing code. If still broken, make the queued reward card store the actual card image and original on-screen rect at completion time, rather than trying to reconstruct it later from mutable quest state.
- Difficulty: Medium
- Regression risk: Medium
- Player impact: Medium
- Confidence: Medium
- Fix now? Maybe
- Notes: This is mostly UX unless it blocks rewards. The reward application itself happens immediately, so fix after progression/reward correctness bugs.

### 5. Pawns Can End Up On Promotion Rank Without Promoting

- Evidence: `bug_report.txt` says, "Pawns don't promote when on the last File" near the Pawn Juggler quest log. The wording likely means last rank, not file.
- Likely root cause: Normal player moves promote through `BoardManager._build_promotion_if_needed()`, and `engine.py::sanitize_board_inplace()` promotes pawns on rank 1/8 before engine interaction. But board-mutating rewards and spells can set pieces directly, bypassing normal move promotion. `quest_rewards.py::QuestRewardHandler.juggle_pawns()` moves pawns to random empty squares and does not avoid or promote back-rank placements.
- Relevant files/functions: `quest_rewards.py::QuestRewardHandler.juggle_pawns`, `board_manager.py::BoardManager._build_promotion_if_needed`, `engine.py::sanitize_board_inplace`, possibly other board-editing rewards/spells.
- Recommended fix: Add a small shared helper for "safe direct pawn placement" or call a sanitizer immediately after reward/spell board mutations. For Pawn Juggler specifically, either exclude rank 1/8 from random targets or promote immediately if a pawn lands there, matching intended design.
- Difficulty: Low to Medium
- Regression risk: Medium
- Player impact: Medium
- Confidence: Medium
- Fix now? Maybe
- Notes: This is likely fixable, but it touches non-standard mechanics. Confirm whether Pawn Juggler should allow instant promotion before patching.

## Bugs Not Recommended Yet

- Magnet does not respect freezes and shields: not recommended immediately. The current `engine.py` already filters magnet moves by `frozen_squares` and `shielded_squares`, so this looks likely fixed. Verify only.
- One With Light piece reload issue: not recommended immediately. `cast_spells.py::cast_one_with_light()` reloads `PIECE_IMAGES`, so the reported issue may be fixed. Verify visually.
- Quest statuses after enemy move / Queen Count not firing: not recommended immediately. Enemy move code calls `QuestInfo.update_quest_variables()` after moves. The current report labels this likely fixed.
- Gold dropped twice on new level: under-specified. Could be animation duplication in `sprinkle_gold_pieces()`/`animate_gold_drop()` or an actual double reward. Needs reproduction and screenshot/log.
- Need to earn 3 gold per won quest card: unclear design change versus bug. Current quest rewards only grant gold when JSON says `"Gold"`, so this needs explicit design confirmation.
- Need to show the map when choosing colony square: UX improvement, not as urgent as reward/progression bugs.
- Need to add `$` to market/money elements and money not shown/oversized in army buy: UI polish, useful but lower priority.
- Story still earns boulder for sparing the Wizard of Stone: likely real, but it is tangled with legacy Stone behavior and JSON story data. Fix after the general story reward path is corrected.
- Hover enemy picture should show wins/losses/stalemates: feature request, not a bug blocking play.
- After stalemate, no coins: unclear whether this means quest reward, board gold, or baseline round payout. Needs expected economy rule.
- Need to build save system: feature-sized work, not a triage bug.
- Wizard of Light pieces appear in piece purchase screen after playing again: likely asset/state leakage, but needs reproduction and relevant screen path.
- Storm takes a pawn every turn; try every 5 turns: balance tuning, not first-pass bug fixing.
- Only allow pieces, not pawns, to be swapped / powers only on your side: report says likely fixed; verify only.

## Recommended Fix Order

1. Fix story reward delivery so learned spells and powerups from modern win stories are actually awarded.
2. Smoke-test overworld progression after a 3-win territory clear; patch only if the crash still reproduces.
3. Fix Wall of Fire quest tracking with a small legal-move-based blocked-pawn helper and tests.
4. Verify and tighten quest reward animation queue/indexing.
5. Decide intended Pawn Juggler promotion behavior, then add a narrow promotion-rank safeguard.

## Suggested Next Codex Prompt

Review the story reward flow and fix only the bug where `return_rewards` from story choices are not applied, especially learned spells like `One With Light`. Do not change unrelated game logic. Preserve existing Stone wizard behavior without double-awarding rewards. Add a small regression test or minimal harness if practical, and report exactly which files changed.
