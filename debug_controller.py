# debug_controller.py
from __future__ import annotations

import pygame


class DebugController:
    """
    Keeps debug hotkeys out of main loop.
    """

    def __init__(self, game):
        self.g = game

    def handle_event(self, event):
        if event.type != pygame.KEYDOWN:
            return

        g = self.g

        if not getattr(g, "debug", False):
            return

        # Match your existing hotkeys
        if event.key in (pygame.K_PLUS, pygame.K_EQUALS):
            g.win_round()
            print(f"[DEBUG] Incremented wins: {getattr(g, 'player_wins', '?')}")
            return

        if event.key == pygame.K_MINUS:
            g.lose_round()
            print(f"[DEBUG] Incremented losses: {getattr(g, 'player_losses', '?')}")
            return

        if event.key == pygame.K_w and getattr(getattr(g, "quests", None), "active_quests", []):
            g.quests.win_quest(g.quests.active_quests[0])
            return

        if event.key == pygame.K_1:
            import debug
            debug.Debug_CompleteQuest(g, 0)
            return

        if event.key == pygame.K_2:
            import debug
            debug.Debug_CompleteQuest(g, 1)
            return

        if event.key == pygame.K_3:
            import debug
            debug.Debug_CompleteQuest(g, 2)
            return
