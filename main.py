# main.py
import pygame
import chess
import config
from intro_screen import BeginningScreens
from game_world import GameWorld
from debug import Debug_GiveAllPowerups, Debug_GiveAllSpells
from engine import EnemyMoveEngine
from bootloader import BootLoader


# This software is GPLv3 (or newest). This software uses copyrighted assets, so assets need to be generated to use this g.


class ChessScreen:
    def __init__(self):
        debug_options = config.load_debug_options()
        self.debug = debug_options["debug"]
        self.debug_overlay_enabled = debug_options["debug_overlay_enabled"]
        self.player_set = 0  # This is for the player's piece images. This will be set by the player in the final g.

        pygame.init()
        pygame.mixer.init()
        self.font = pygame.font.SysFont(None, 28)
        self.screen = pygame.display.set_mode((config.WIDTH, config.HEIGHT))
        pygame.display.set_caption("Chess Quest")

        # Boot everything heavy (no variable renames; same self.* names)
        BootLoader(self).boot()

        # ─────────────────────────────────────────────
        # Start the game (unchanged)
        # ─────────────────────────────────────────────
        if self.debug:
            self.spellbook = Debug_GiveAllSpells()
            self.powerups = Debug_GiveAllPowerups()
            self.spellbook_master = Debug_GiveAllSpells()
            self.gear_owned = list(config.GEAR_ORDER)
            self.active_stage = "fire"
            self.current_state_wins = 0
            self.world = GameWorld(self)

            # Load images that require a world number
            self.world.world_data[(self.world.player_pos)]["stage_id"] = 0
            self.setup_new_board()
        else:
            beginning_screen = BeginningScreens()
            beginning_screen.intro_screen()
            game_type = beginning_screen.show_main_menu()

            if game_type == "New Game":
                self.game_start_new_game()
            elif game_type == "Continue":
                pass
                # self.g_start_continue()
            elif game_type == "Options":
                pass
                # self.options_menu()

    # IMPORTANT: this MUST NOT depend on board_manager during boot
    def player_color(self):
        return chess.WHITE if self.player_side == "white" else chess.BLACK

    # ─────────────────────────────────────────────
    # Menu callbacks (unchanged)
    # ─────────────────────────────────────────────
    def save_game(self):
        print("[MENU] Save requested")
        self.send_feedback("Save not implemented yet.")

    def load_game(self):
        print("[MENU] Load requested")
        self.send_feedback("Load not implemented yet.")

    def exit_to_main_screen(self):
        print("[MENU] Exit to Main Screen requested")
        self.send_feedback("Exit to Main Screen not implemented yet.")

    def exit_to_os(self):
        print("[MENU] Exit to OS requested")
        pygame.quit()
        raise SystemExit

    # ────────────────────────────────────────────────────────────────────
    # Board pipeline wrappers (already delegated)
    # ────────────────────────────────────────────────────────────────────
    def setup_new_board(self):
        return self.board_manager.setup_new_board()

    def reset_board(self):
        return self.board_manager.reset_board()

    def apply_player_army_to_board(self, color):
        return self.board_manager.apply_player_army_to_board(color)

    def _clear_king_protections(self):
        return self.board_manager._clear_king_protections()

    def _escape_moves_from(self, src_sq):
        return self.board_manager._escape_moves_from(src_sq)

    # ────────────────────────────────────────────────────────────────────
    # Misc helpers / thin wrappers
    # ────────────────────────────────────────────────────────────────────
    def between_rounds_quest_activity(self, win_status=False):
        return self.game_result.between_rounds_quest_activity(win_status=win_status)

    def win_round(self, dialog_option="lose"):
        return self.game_result.win_round(dialog_option=dialog_option)

    def lose_round(self, win_status=False):
        return self.game_result.lose_round(win_status=win_status)

    def stalemate_round(self, win_status=False):
        return self.game_result.stalemate_round(win_status=win_status)

    # ────────────────────────────────────────────────────────────────────
    # Setup & story
    # ────────────────────────────────────────────────────────────────────
    def game_start_new_game(self):
        self.world = GameWorld(self)
        print("Built the game world.")

        if hasattr(self, "story_mode"):
            self.story_mode.play_intro_and_tutorial()

        self.setup_new_board()
        self.run()

    def is_it_players_turn(self) -> bool:
        return self.board.turn == (self.player_side == "white")

    # ────────────────────────────────────────────────────────────────────
    # Main loop
    # ────────────────────────────────────────────────────────────────────
    def run(self):
        # Keep engine wrapper creation where it always was
        self.enemy_move_engine = EnemyMoveEngine(self)

        running = True
        hovered_square = None
        hovered_power = None

        while running:
            # Centralized hard pause tick (renders + delays + callback)
            if self.ui_state.tick_hard_pause(self.renderer):
                continue

            mouse_pos = pygame.mouse.get_pos()
            debug_overlay_open = self.debug_controller.is_overlay_open()
            if debug_overlay_open:
                hovered_square, hovered_power = None, None
            else:
                hovered_square, hovered_power = self.input.update_hover(mouse_pos)

            if self.main_game_screen and not debug_overlay_open:
                if self.game_result.process_terminal_state_if_needed():
                    continue

            for event in pygame.event.get():
                # Debug hotkeys (only acts if self.debug True inside controller)
                consumed = self.debug_controller.handle_event(event)
                if consumed:
                    continue

                out = self.input.handle_event(
                    event,
                    hovered_square=hovered_square,
                    hovered_power=hovered_power,
                    mouse_pos=getattr(event, "pos", mouse_pos),
                )
                if out.get("quit"):
                    running = False
                    break

            # Centralized enemy-turn progression + post-move hooks + ragequit handling
            debug_overlay_open = self.debug_controller.is_overlay_open()
            if not debug_overlay_open:
                self.turn_controller.tick()
                self.ui_state.update_game_state()
            self.renderer.draw("main", hovered_square=hovered_square, hovered_power=hovered_power)

        # Shutdown
        try:
            self.engine.quit()
        except Exception:
            pass
        pygame.quit()



if __name__ == "__main__":
    game_screen = ChessScreen()
    game_screen.run()
