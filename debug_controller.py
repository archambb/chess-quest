# debug_controller.py
from __future__ import annotations

import pygame

from debug_overlay import DebugOverlay


class DebugController:
    """
    Keeps debug hotkeys out of main loop.
    """

    def __init__(self, game):
        self.g = game
        self.overlay = DebugOverlay(game)

    def handle_event(self, event):
        g = self.g

        if event.type == pygame.KEYDOWN and event.key == pygame.K_BACKQUOTE:
            if getattr(g, "debug_overlay_enabled", False):
                self.overlay.toggle()
                return True

        if self.is_overlay_open():
            if event.type == pygame.QUIT:
                return False
            return self.overlay.handle_event(event)

        if event.type != pygame.KEYDOWN:
            return False

        if not getattr(g, "debug", False):
            return False

        # Match your existing hotkeys
        if event.key in (pygame.K_PLUS, pygame.K_EQUALS):
            g.win_round()
            print(f"[DEBUG] Incremented wins: {getattr(g, 'player_wins', '?')}")
            return True

        if event.key == pygame.K_MINUS:
            g.lose_round()
            print(f"[DEBUG] Incremented losses: {getattr(g, 'player_losses', '?')}")
            return True

        if event.key == pygame.K_w and getattr(getattr(g, "quests", None), "active_quests", []):
            g.quests.win_quest(g.quests.active_quests[0])
            return True

        if event.key == pygame.K_1:
            import debug
            debug.Debug_CompleteQuest(g, 0)
            return True

        if event.key == pygame.K_2:
            import debug
            debug.Debug_CompleteQuest(g, 1)
            return True

        if event.key == pygame.K_3:
            import debug
            debug.Debug_CompleteQuest(g, 2)
            return True

        return False

    def is_overlay_open(self) -> bool:
        return bool(getattr(self.overlay, "is_open", False))
