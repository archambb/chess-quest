# ui_state.py
from __future__ import annotations

import os
import json
import random
import pygame
import chess
import config


class UIState:
    """
    Owns transient UI state & timing:
      - hard_pause timing + callback
      - feedback scroll trigger
      - game-state overlay trigger ("check", etc.)
      - enemy dialog helper
    """

    def __init__(self, game):
        self.g = game

        # ---- hard pause ----
        self.g.hard_pause_start_time = None
        self.g.hard_pause_callback = None
        self.g.click_pause_active = False
        self.g.click_pause_callback = None
        self.g.hard_pause_duration = getattr(self.g, "hard_pause_duration", int(0.9 * config.FPS * (1000 / config.FPS)))
        # Prefer ms duration if already used elsewhere; otherwise default ~900ms
        if isinstance(self.g.hard_pause_duration, float):
            self.g.hard_pause_duration = int(self.g.hard_pause_duration)

        self.g.hard_pause_clock = pygame.time.Clock()

        # ---- check overlay bookkeeping ----
        self.g.in_check_overlay_active = getattr(self.g, "in_check_overlay_active", False)

    # ─────────────────────────────────────────────────────────────
    # Hard pause
    # ─────────────────────────────────────────────────────────────
    def hard_pause(self, callback=None):
        self.g.hard_pause_start_time = pygame.time.get_ticks()
        self.g.hard_pause_callback = callback

    def click_pause(self, callback=None):
        self.g.click_pause_active = True
        self.g.click_pause_callback = callback

    def tick_hard_pause(self, renderer) -> bool:
        """
        Returns True if we are still in hard-pause and consumed the frame
        (i.e., caller should 'continue' main loop).
        """
        if getattr(self.g, "click_pause_active", False):
            clicked = False
            try:
                for event in pygame.event.get():
                    if event.type == pygame.QUIT:
                        pygame.quit()
                        raise SystemExit
                    if event.type == pygame.MOUSEBUTTONDOWN:
                        clicked = True

                renderer.draw()
                pygame.display.flip()
                self.g.hard_pause_clock.tick(config.FPS)
            except SystemExit:
                raise
            except Exception:
                pass

            if not clicked:
                return True

            self.g.click_pause_active = False
            cb = self.g.click_pause_callback
            self.g.click_pause_callback = None
            if cb:
                try:
                    cb()
                except Exception as e:
                    print(f"[WARN] click_pause callback failed: {e}")
            return True

        if not self.g.hard_pause_start_time:
            return False

        now = pygame.time.get_ticks()

        # duration is in ms; if someone stored frames, try to interpret safely
        duration = getattr(self.g, "hard_pause_duration", 0)
        if duration <= 0:
            # if duration was configured as frames somewhere, approximate to ms
            duration = int(0.9 * 1000)

        if now - self.g.hard_pause_start_time < duration:
            # draw a frame during pause
            try:
                renderer.draw()
                pygame.display.flip()
                self.g.hard_pause_clock.tick(config.FPS)
            except Exception:
                # If display not ready, don't hard-crash here.
                pass
            return True

        # pause complete
        self.g.hard_pause_start_time = None

        cb = self.g.hard_pause_callback
        self.g.hard_pause_callback = None
        if cb:
            try:
                cb()
            except Exception as e:
                print(f"[WARN] hard_pause callback failed: {e}")

        return False

    # ─────────────────────────────────────────────────────────────
    # Feedback scroll trigger ad graphic feedback
    # ─────────────────────────────────────────────────────────────
    def send_feedback(self, message: str):
        unfold_frames = int(0.25 * config.FPS)
        hold_frames = 600

        r = getattr(self.g, "renderer", None)
        if not r:
            print("[WARN] send_feedback called before renderer exists")
            return

        r.feedback_text = message
        r.feedback_alpha = 255
        r.feedback_unfold_frames = unfold_frames
        r.feedback_timer_hold = hold_frames
        r.feedback_total_duration = unfold_frames + hold_frames + unfold_frames
        r.feedback_frame_counter = 0
        r.feedback_waiting_for_click = True
        r.feedback_collapse_early = False

    def trigger_inventory_lock_wiggle():
        pass

    # ─────────────────────────────────────────────────────────────
    # Game state overlay updater
    # ─────────────────────────────────────────────────────────────
    def update_game_state(self):
        # Just in case we get here before board exists
        board = getattr(self.g, "board", None)
        if not board:
            return

        if board.is_game_over():
            self.g.in_check_overlay_active = False
            return

        board_in_check = board.is_check()

        renderer = getattr(self.g, "renderer", None)
        if not renderer:
            self.g.in_check_overlay_active = board_in_check
            return

        if board_in_check and not self.g.in_check_overlay_active:
            renderer.trigger_gamestate_display("check")
            self.hard_pause()

        elif not board_in_check and self.g.in_check_overlay_active:
            renderer.gamestate_display_active = False

        self.g.in_check_overlay_active = board_in_check

    # ─────────────────────────────────────────────────────────────
    # Enemy dialog helper
    # ─────────────────────────────────────────────────────────────
    def show_enemy_dialog(self, dialog, duration_sec=14):
        renderer = getattr(self.g, "renderer", None)
        if not renderer:
            print("[WARN] show_enemy_dialog called before renderer exists")
            return

        if dialog in ("surrender", "rage_quit", "lose"):
            filepath = os.path.join("data", f"{dialog}.json")
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    options = json.load(f)
                dialog_text = random.choice(options)["dialog"]
            except Exception as e:
                print(f"[Error loading dialog {dialog}]:", e)
                dialog_text = "[Missing dialog]"
        else:
            dialog_text = dialog

        renderer.enemy_dialog_text = dialog_text
        renderer.enemy_dialog_timer = duration_sec * config.FPS
        renderer.enemy_dialog_alpha = 255
