# turn_controller.py
from __future__ import annotations


class TurnController:
    """
    Owns enemy-turn progression & per-move post-processing.
    """

    def __init__(self, game):
        self.g = game
        self._engine_moved = False

    def tick(self):
        g = self.g

        # If menu is open, do nothing
        if getattr(g, "menu", None) and getattr(g.menu, "is_open", False):
            return

        board = getattr(g, "board", None)
        if not board:
            return

        if self._engine_moved:
            # after enemy moved, tick timers once
            try:
                g.board_manager.decrement_power_timers()
            except Exception as e:
                print(f"[WARN] decrement_power_timers failed: {e}")
            self._engine_moved = False
            return

        if board.is_game_over():
            return

        # only act on enemy turn
        if board.turn == (getattr(g, "player_side", "white") == "white"):
            return

        enemy_engine = getattr(g, "enemy_move_engine", None)
        if not enemy_engine:
            return

        try:
            self._engine_moved = bool(enemy_engine.engine_move())

            # post-move events hook
            qrh = getattr(g, "quest_reward_handler", None)
            if qrh and hasattr(qrh, "post_piece_move_events"):
                qrh.post_piece_move_events()

        except Exception as e:
            print(f"[ERROR] Engine move failed: {e}")
            # An unexpected problem has occurred. Have the enemy get mad and quit and reset the game.
            setattr(g, "ENEMY_RAGE_QUITS", True)
            try:
                g.win_round("rage_quit")
            except Exception as e2:
                print(f"[WARN] win_round('rage_quit') failed: {e2}")
            self._engine_moved = False
