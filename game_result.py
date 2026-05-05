# game_result.py
from __future__ import annotations

import chess


class GameResultManager:
    """
    Handles end-of-round / end-of-game logic for Chess Quest.

    Designed to be owned by ChessScreen as:
        self.game_result = GameResultManager(self)

    Public helpers:
        - process_terminal_state_if_needed()
        - win_round(dialog_option="lose")
        - lose_round(win_status=False)
        - stalemate_round(win_status=False)
        - between_rounds_quest_activity(win_status=False)
    """

    def __init__(self, game):
        self.g = game  # ChessScreen instance

    # ─────────────────────────────────────────────────────────────
    # Terminal state (board.is_game_over / rage quit)
    # ─────────────────────────────────────────────────────────────
    def process_terminal_state_if_needed(self) -> bool:
        """
        Returns True if a terminal state was processed and the caller should `continue`
        the main loop, False if no terminal state exists.
        """
        g = self.g

        if not g.main_game_screen:
            return False

        if not (g.board.is_game_over() or g.ENEMY_RAGE_QUITS):
            return False

        result = g.board.result()

        if g.ENEMY_RAGE_QUITS:
            print("The enemy wizard rage quits!")
            self.win_round("rage_quit")

        elif result == "1-0":
            if g.player_side == "white":
                print("You (White) won!")
                self.win_round()
            else:
                print("AI (White) won!")
                self.lose_round()

        elif result == "0-1":
            if g.player_side == "black":
                print("You (Black) won!")
                self.win_round()
            else:
                print("AI (Black) won!")
                self.lose_round()

        else:
            print("Draw! Board resets.")
            self.stalemate_round()

        print(f"Current score: {g.player_wins} wins, {g.player_losses} losses")
        g.ENEMY_RAGE_QUITS = False
        return True

    # ─────────────────────────────────────────────────────────────
    # Between-round quest activity
    # ─────────────────────────────────────────────────────────────
    def between_rounds_quest_activity(self, win_status: bool = False):
        g = self.g

        # Turn off round-lasting effects
        if g.quests.enable_poisoned_pawns is True:
            g.quests.enable_poisoned_pawns = False

        g.quests.update_quest_variables(piece=None, player=False, move=None, power_used=None)
        g.quests.check_for_quest_win()
        g.turns = 0

    # ─────────────────────────────────────────────────────────────
    # Round lifecycle
    # ─────────────────────────────────────────────────────────────
    def win_round(self, dialog_option: str = "lose"):
        g = self.g

        g.renderer.trigger_gamestate_display(dialog_option)
        g.ui_state.hard_pause()

        if "Win Game" in g.quests.quest_status:
            g.quests.update_quest_stat("Win Game", equal_to=1)
            g.quests.check_for_quest_win()

        self.between_rounds_quest_activity(win_status=True)
        g.player_wins += 1

        if g.player_wins >= 3:
            # Reset board wins
            g.player_wins = 0
            g.player_losses = 0
            g.player_stalemates = 0
            g.player_side = "white"

            # Reset quest-related board variables
            g.quests.reset_quest_variables()

            # Stage-specific win story BEFORE leaving this tile
            if hasattr(g, "story_mode") and hasattr(g, "world") and g.world:
                g.story_mode.handle_win_story()

            # Mark this world as beaten
            g.world.record_win(g.world.player_pos[0], g.world.player_pos[1])

            # ── Final boss placeholder ─────────────────────────────
            if g.world.all_wizards_defeated():
                print("[INFO] All wizards defeated - Final Boss sequence placeholder.")
                # TODO: hook up final boss flow here later

            # Move to the next location
            g.world.overworld_move()

            # Story for arriving at the new location (first visit vs return)
            if hasattr(g, "story_mode") and hasattr(g, "world") and g.world:
                g.story_mode.handle_new_level_story()

            wd = self.g.world.world_data
            stage = wd.get(self.g.world.player_pos, {}).get("stage_id", 1)

            g.assets.load_portrait_image(stage)
            g.setup_new_board()

            # Reset spellbook (last; player may earn spells in the win story)
            g.spellbook = list(g.spellbook_master)

        else:
            g.ui_state.show_enemy_dialog(dialog_option)
            g.reset_board()

    def lose_round(self, win_status: bool = False):
        g = self.g

        print("[INFO] Player lost a round!]")
        print("[INFO] Updating quest variables...]")

        if g.quests.enable_checkmate_teleport is True:
            g.quests.enable_checkmate_teleport = False
            g.quest_reward_handler.checkmate_teleport()
            return

        if win_status is False:
            g.renderer.trigger_gamestate_display("checkmate")
        else:
            # preserve existing behavior
            win_status = False
            g.renderer.trigger_gamestate_display("concede")

        g.ui_state.hard_pause()

        if "Lost Game" in g.quests.quest_status:
            g.quests.update_quest_stat("Lost Game", equal_to=1)
            g.quests.check_for_quest_win()

        self.between_rounds_quest_activity(win_status)
        g.player_losses += 1

        if g.player_losses >= 3:
            g.player_wins = 0
            g.player_losses = 0
            g.player_stalemates = 0

            # Stage-specific failure story BEFORE leaving this tile
            if hasattr(g, "story_mode") and hasattr(g, "world") and g.world:
                g.story_mode.handle_lose_story()

            # Record the loss on the current world
            g.world.record_loss(g.world.player_pos[0], g.world.player_pos[1])

            # Move to the next location
            g.world.overworld_move()

            # Story for arriving at the new world (first visit vs return)
            if hasattr(g, "story_mode") and hasattr(g, "world") and g.world:
                g.story_mode.handle_new_level_story()

            wd = self.g.world.world_data
            stage = wd.get(self.g.world.player_pos, {}).get("stage_id", 1)

            g.assets.load_portrait_image(stage)
            g.setup_new_board()
        else:
            g.reset_board()

    def stalemate_round(self, win_status: bool = False):
        g = self.g

        print("[INFO] Player lost a round!]")
        print("[INFO] Updating quest variables...]")

        g.renderer.trigger_gamestate_display("stalemate")
        g.ui_state.hard_pause()

        g.quests.update_quest_variables(piece=None, player=False, move=None, power_used=None)

        # Can't get the Stalemate quest to fire and can't figure out why
        # Adding this to make it work
        if "Stalemate" in g.quests.quest_status:
            g.quests.update_quest_stat("Stalemate", equal_to=1)

        g.quests.check_for_quest_win()
        self.between_rounds_quest_activity(win_status)
        g.player_stalemates = getattr(g, "player_stalemates", 0) + 1
        g.reset_board(preserve_gold=True)

