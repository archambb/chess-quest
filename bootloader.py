# bootloader.py
from __future__ import annotations

import os
import random

import pygame
import chess
import chess.engine

import config

from cast_spells import CastSpells
from spell_targeting import SpellTargeting
from quest_info import QuestInfo
from quest_rewards import QuestRewardHandler
from render import RenderPipeline
from audio import AudioManager
from effects import EffectsManager
from assetmanager import AssetManager
from powers import Powers
from map_challenges import MapChallenges
from difficulty import DifficultyManager
from story_mode import StoryMode
from gear import Gear
from menu import GameMenu
from board_manager import BoardManager
from spell_rules import SpellRules
from ui_state import UIState
from turn_controller import TurnController
from debug_controller import DebugController
from game_result import GameResultManager
from input_controller import InputController

class BootLoader:
    """
    Boots the ChessScreen instance with the exact same variables as before,
    but moved out of main.py.

    IMPORTANT:
    - Does NOT rename any self.* variables.
    - Assumes pygame is already initialized and self.screen exists.
    """

    def __init__(self, game):
        self.g = game

    def boot(self):
        g = self.g

        # ─────────────────────────────────────────────
        # Loading screen helpers
        # ─────────────────────────────────────────────
        loading_font = pygame.font.SysFont(None, 36)
        small_font = pygame.font.SysFont(None, 24)
        clock = pygame.time.Clock()
        total_steps = 7
        step = 0

        # ─────────────────────────────────────────────────────────────
        # CRITICAL: provide attrs used by other modules BEFORE BootLoader
        # (QuestInfo / QuestRewards may reference these during boot)
        # ─────────────────────────────────────────────────────────────
        g.SQUARE_SIZE = getattr(config, "SQUARE_SIZE", 80)

        # ─────────────────────────────────────────────────────────────
        # Boot-safe defaults to prevent early AttributeErrors during boot
        # NOTE: Remove these if having boot issues to ID the boot issue
        # ─────────────────────────────────────────────────────────────
        g.player_side = getattr(g, "player_side", "white")
        g.board = getattr(g, "board", chess.Board())
        g.board_origin_x = getattr(g, "board_origin_x", 0)
        g.board_origin_y = getattr(g, "board_origin_y", 0)
        g.active_effects = getattr(g, "active_effects", {})
        g.meteor_target_queue = getattr(g, "meteor_target_queue", [])
        g.main_game_screen = getattr(g, "main_game_screen", False)

        def _draw_loading(current_step, total_steps, headline, detail):
            """
            Simple blocking loading screen with a progress bar and two lines of text.
            Call this between heavy init steps.
            """
            progress = max(0.0, min(1.0, current_step / float(total_steps)))

            # Allow window close while loading
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    pygame.quit()
                    raise SystemExit

            g.screen.fill((5, 10, 25))

            bar_w = int(config.WIDTH * 0.6)
            bar_h = 26
            bar_x = (config.WIDTH - bar_w) // 2
            bar_y = (config.HEIGHT - bar_h) // 2

            # Bar background
            pygame.draw.rect(
                g.screen,
                (40, 60, 110),
                (bar_x, bar_y, bar_w, bar_h),
                border_radius=10
            )

            # Bar fill
            fill_w = int(bar_w * progress)
            pygame.draw.rect(
                g.screen,
                (90, 160, 255),
                (bar_x, bar_y, fill_w, bar_h),
                border_radius=10
            )

            # Percent text
            pct_txt = small_font.render(f"{int(progress * 100)}%", True, (230, 235, 255))
            pct_rect = pct_txt.get_rect(center=(config.WIDTH // 2, bar_y + bar_h // 2))
            g.screen.blit(pct_txt, pct_rect)

            # Title
            title_txt = loading_font.render("Loading Chess Quest...", True, (235, 240, 255))
            title_rect = title_txt.get_rect(center=(config.WIDTH // 2, bar_y - 40))
            g.screen.blit(title_txt, title_rect)

            # Headline
            head_txt = small_font.render(headline, True, (220, 225, 245))
            head_rect = head_txt.get_rect(center=(config.WIDTH // 2, bar_y + bar_h + 30))
            g.screen.blit(head_txt, head_rect)

            # Detail line
            if detail:
                detail_txt = small_font.render(detail, True, (190, 195, 215))
                detail_rect = detail_txt.get_rect(center=(config.WIDTH // 2, bar_y + bar_h + 60))
                g.screen.blit(detail_txt, detail_rect)

            pygame.display.flip()
            clock.tick(60)

        # ─────────────────────────────────────────────
        # Core state setup (cheap)
        # ─────────────────────────────────────────────

        g.story_mode = StoryMode(g)

        # Each opponent's variables
        g.player_wins = 0
        g.player_losses = 0
        g.player_side = "white"  # or black -- can change with certain boards

        # Defaults (unset until a save/new-game applies real values)
        g.stockfish_level = None
        g.current_stockfish_level = None

        g.difficulty = DifficultyManager(g)

        # Colors...
        g.WHITE = config.WHITE_COLOR
        g.BLACK = config.BLACK_COLOR
        g.LIGHT_BLUE = config.LIGHT_BLUE
        g.DARKER_BLUE = config.DARKER_BLUE
        g.BLUE_OUTLINE = config.BLUE_OUTLINE

        # Initialize chess board and engine
        g.board = chess.Board()
        g.engine_path = os.path.join("engine", "stockfish", "stockfish-windows-x86-64-avx2.exe")
        g.engine = chess.engine.SimpleEngine.popen_uci(g.engine_path)

        # === PLAYER ARMY INITIAL STATE ===
        g.player_army_fen = "PPPPPPPP/RNBQKBNR"

        # ── Placeholder difficulty so the engine is usable right now ──
        _PLACEHOLDER_SKILL = 7  # safe middle-ground; change if you prefer
        g.current_stockfish_level = _PLACEHOLDER_SKILL
        g.engine.configure({"Skill Level": _PLACEHOLDER_SKILL})
        print(f"[Difficulty] Bootstrapped placeholder Skill Level → {_PLACEHOLDER_SKILL}")

        # Step 1: engine + rules core
        step += 1
        _draw_loading(
            step,
            total_steps,
            "Awakening the chess engine...",
            "Summoning Stockfish and core rules..."
        )

        # Icon locations (set each loop of rendering)
        g.power_icon_rects = {}

        # Board origin shifted to center of middle area
        g.board_origin_x = config.PORTRAIT_WIDTH + (config.BOARD_WIDTH - 640) // 2
        g.board_origin_y = (config.HEIGHT - 640) // 2

        # Board management
        g.selected_square = None
        g.selected_power = None  # None or the power name like "bombs"
        g.shielded_squares = {}  # square: turns remaining
        g.frozen_squares = {}    # square: turns remaining
        g.move_history = []      # for undo/time warp
        g.possible_moves = []    # visualization of possible moves (list of to_squares)
        g.swap_selected_square = None  # Swap mode
        g.magnet_square = None  # Tracks the square where the magnet is placed
        g.spellbook_open = False
        g._spell_cache_dirty = True
        g.selected_spell = None
        g.gold_pieces = set()   # Set of squares that have gold
        g.gold_icons = {}       # maps square to gold icon
        g.landed_gold_pieces = set()  # For gold animation
        g.powerups = {}
        g.turns = 0

        # --- Gear / gear inventory ---
        g.gear_owned: list[str] = []  # type: ignore # What the player actually owns
        g.gear_slots: dict[str, str | None] = {}  # type: ignore # active gear loaded into slots

        # Powers UI lock overlay gate
        g.powers_unlocked = False

        # Powers
        g.powers = Powers(g)

        # Step 2: spells & powers
        step += 1
        _draw_loading(
            step,
            total_steps,
            "Preparing spells and powers...",
            "Equipping bombs, shields, and strange magics..."
        )

        # Load assets
        g.assets = AssetManager(g)

        # Step 3: core visual assets via AssetManager
        step += 1
        _draw_loading(
            step,
            total_steps,
            "Loading core visuals...",
            "Heroes, enemies, and board backdrops..."
        )
        g.assets.load_game_state_images()

        # Gear / gear
        g.gear = Gear(g)
        g.compass_hint = None

        # Pause variables for the hard pause
        g.hard_pause_start_time = None
        g.hard_pause_duration = config.check_notification_duration  # /1000 seconds
        g.hard_pause_callback = None
        g.hard_pause_clock = pygame.time.Clock()

        # Lost Pieces for quest tracking and may use for additional graphics
        g.lost_pieces = []
        g.enemy_lost_pieces = []

        # Normal spellbook (empty for starting game)
        g.spellbook_master = []
        g.spellbook = []

        # Spellbook UI variables
        g._hover_spell = None   # currently hovered name or None
        g._hover_start_ms = 0   # pygame.time.get_ticks() stamp
        g._HOVER_DELAY_MS = 2000  # 2 seconds
        g.spell_info = {}

        # Spell variables
        g.cached_spell_availability = {}
        g._spell_cache_dirty = True

        g.flood_animations = []
        g.flood_spell_active = False
        g.flood_pulse_alpha = 0
        g.flood_pulse_direction = 1

        g.shadow_step_active = False
        g.selected_power = None
        g.shadow_pulse_alpha = 60
        g.shadow_pulse_direction = 1

        g.orb_highlight_squares = []
        g.orb_pulse_alpha = 60
        g.orb_pulse_direction = 1

        g.force_mirror_active = False
        g.greed_active = False

        g.meteor_target_queue = []   # list of (dest_x, dest_y, board_square)
        g.meteor_active = False
        g.meteor_quadrant = None
        g.meteor_flash_timer = 0

        g.boulder_squares = set()

        g.cast_spells = CastSpells(g)
        g.spell_targeting = SpellTargeting(g)

        # ****************************************************************************************
        # Build Quest Information
        g.quests = QuestInfo(g)
        g.quest_reward_handler = QuestRewardHandler(g)

        # Background image, portraits
        g.background_image = None
        g.enemy_portrait_y_actual = None
        g.hero_portrait_y_actual = None

        g.in_check_overlay_active = False  # This is used to determine when to show the check overlay
        g.main_game_screen = True

        g.magic_library = []  # indexed list of effect-prototypes (frames + meta)
        g.active_effects = {}  # id → runtime-state dict

        # Step 4: audio manager + SFX
        g.audio = AudioManager()
        step += 1
        _draw_loading(
            step,
            total_steps,
            "Loading sound effects...",
            "Clanks, crashes, spells and coin jingles..."
        )
        g.audio._load_all_sounds()

        # Step 5: music
        step += 1
        _draw_loading(
            step,
            total_steps,
            "Loading music...",
            "Hiring bards to score your adventure..."
        )
        g.audio.load_initial_music()

        # Load graphics
        g.power_icons = {}
        g.powers.initialize_empty_powerups()

        # Step 6: UI artwork (icons, spellbook, effects, gear)
        step += 1
        _draw_loading(
            step,
            total_steps,
            "Loading UI artwork...",
            "Spellbook, gold coins, magic effects, gear icons..."
        )
        g.spellbook_icon = g.assets.load_spellbook_gfx()
        g.spellbook_bg = g.assets.load_spellbook_background()
        g.gold_coins = g.assets.load_gold_coins()
        g.assets.load_magic_effects()
        g.gear_icons = g.assets.load_gear_icons()
        g.assets.load_lock_ui_gfx()

        g.ENEMY_RAGE_QUITS = False

        # Player gold
        g.player_gold = 0

        # Step 7: renderer / effects / map rules
        step += 1
        _draw_loading(
            step,
            total_steps,
            "Warming up renderer...",
            "Particles, overlays, and map challenges..."
        )
        # Build rendering system
        g.renderer = RenderPipeline(g)

        # Build effects engine
        g.effects = EffectsManager(g)

        # Prepare the map challenges engine
        g.map_challenges = MapChallenges(g)

        # ─────────────────────────────────────────────
        # NEW: Game result manager
        # ─────────────────────────────────────────────
        g.game_result = GameResultManager(g)

        # Board manager (extracted board setup/reset + helpers)
        g.board_manager = BoardManager(g)

        # Spell rules manager (extracted spell availability checks)
        g.spell_rules = SpellRules(g)

        # UI state manager (feedback/pause/overlay/dialog)
        g.ui_state = UIState(g)

        # Input controller (created AFTER menu exists)
        g.input = InputController(g)

        # Turn + Debug controllers (keep run() thin)
        g.turn_controller = TurnController(g)

        g.debug_controller = DebugController(g)

        # ─────────────────────────────────────────────
        # In-game menu (ESC / X closes back to game)
        # ─────────────────────────────────────────────
        g.menu = GameMenu(
            g,
            on_save=g.save_game,
            on_load=g.load_game,
            on_exit_to_main=g.exit_to_main_screen,
            on_exit_os=g.exit_to_os,
        )


