# render.py
import pygame
import math
import chess
import config
import math, random
import numpy as np
from pygame import gfxdraw

from render_board import BoardRenderer
from render_ui import UIRenderMixin


class RenderPipeline(BoardRenderer, UIRenderMixin):
    def __init__(self, g):
        self.g = g  # Reference to main game state for data access
        UIRenderMixin._ui_init(self)

        self.hover_timer = 0
        self.clock = pygame.time.Clock()
        self.current_quest_hover_offset = 0.0  # Ranges from 0.0 (hidden) to 1.0 (fully raised)

        # ───────── Gear / Gear UI state ─────────
        # Rectangles for hit-testing gear icons
        self.gear_rects = {}           # gear_id -> pygame.Rect
        # Hover tracking (for 2s tooltip)
        self.gear_hover_id = None      # current hovered gear_id or None
        self.gear_hover_start_ms = 0   # pygame.time.get_ticks() when hover began
        self._gear_hover_tooltip_fired = False  # prevent spam during a single hover

        # Descriptions for gear scroll messages (pulled from config)
        self.gear_descriptions = getattr(config, "GEAR_DESCRIPTIONS", {})

        # For quest animation
        self.quest_win_animations = []  # Each entry: {"qid": int, "pieces": [...], "frame": float}
        self.quest_anim_config = {
            "rise_duration": 0.75,
            "hold_duration": 1.8,
            "shake_duration": 1.2,
            "explode_duration": 2.0,
        }


    ########################################################################
    #                         🎨 CORE RENDER ENTRY                         #
    ########################################################################
    def draw(self, mode="main", **kwargs):
        self.hover_timer = (self.hover_timer + 1) % 628
        hover_alpha = int(128 + 127 * (0.5 + 0.5 * math.sin(self.hover_timer * 0.1)))
        dt = self.clock.tick(config.FPS) / 1000

        # Update particles each frame
        if hasattr(self.g, "effects"):
            self.g.effects.update(dt)

         # Dialog timer
        if self.enemy_dialog_timer > 0:
            self.enemy_dialog_timer -= 1
            if self.enemy_dialog_timer > config.FPS:
                self.enemy_dialog_alpha = 255           # fully visible
            else:
                # fade out over the last 1 second
                self.enemy_dialog_alpha = int(255 * self.enemy_dialog_timer / config.FPS)
        else:
            self.enemy_dialog_text = ""
            self.enemy_dialog_alpha = 0


        hovered_square = kwargs.get("hovered_square")

        self.draw_background()
        self.draw_board(hovered_square, hover_alpha)

        if mode == "main":
            self.draw_flood_animations()
            self.draw_gold()
            self.draw_pieces(hovered_square=hovered_square, hover_alpha=hover_alpha)
            self.draw_powers_area(kwargs.get("hovered_power"))
            self.draw_gold_counter()
            self.draw_portrait_area()
            self.draw_gear_bar()
            self.draw_current_quest_cards()
            self.update_reward_presentation_queue()
            self.update_quest_win_animations(dt)
            self.draw_quest_win_animations()
            # Draw particle/effects layer
            if hasattr(self.g, "effects"):
                self.g.effects.draw(self.g.screen)
            self.update_and_draw_magic_effects()
            if self.g.spellbook_open:
                self.draw_spellbook()
                self.draw_spell_tooltip()


        elif mode == "quest_selection":
            self.draw_portrait_area()
            self.draw_gear_bar()
            self.draw_pieces()
            self.draw_powers_area()
            self.draw_gold_counter()
            self.draw_quest_selection()

        elif mode == "animate_piece":
            self.draw_portrait_area()
            self.draw_gear_bar()
            self.draw_gold_counter()
            self.draw_flood_animations()
            self.draw_gold()
            self.draw_current_quest_cards()
            self.draw_pieces_exclude(kwargs["exclude_square"])
            self.update_and_draw_magic_effects()

        elif mode == "gold_drop":
            self.draw_portrait_area()
            self.draw_gear_bar()
            self.draw_gold_counter()
            self.draw_pieces()
            self.draw_powers_area()
            self.draw_gold()

        if self.g.show_quest_status:
            self.draw_quest_status_scroll()

        self.draw_feedback() # Keep feedback always on the top
        # Menu is always the top-most overlay
        self._draw_game_menu_overlay_if_open()
        self._draw_debug_overlay_if_open()
        if kwargs.get("flip", True):
            pygame.display.flip()

    def _draw_debug_overlay_if_open(self):
        controller = getattr(self.g, "debug_controller", None)
        overlay = getattr(controller, "overlay", None)
        if overlay and getattr(overlay, "is_open", False):
            overlay.draw(self.g.screen)


    ########################################################################
    #                           📜 UI                                      #
    ########################################################################

    ########################################################################
    #                             ♟️ PIECE DRAWING                         #
    ########################################################################
    def draw_pieces(self, hovered_square=None, hover_alpha=128):
        squares_sorted = sorted(chess.SQUARES, key=lambda s: -(s // 8))  # Top row to bottom

        # Detect stalker presence (Stage 4 only)
        stalker_sq = None
        stalker_img = getattr(self.g, "stalker_image", None)
        if stalker_img is not None and hasattr(self.g, "map_challenges"):
            try:
                wd = self.g.world.world_data
                stage = wd.get(self.g.world.player_pos, {}).get("stage_id", 1)
                if stage == 4:
                    stalker_sq = getattr(self.g.map_challenges, "_stalker_square", None)
            except Exception:
                stalker_sq = None

        for square in squares_sorted:
            piece = self.g.board.piece_at(square)

            # NEW: treat Stalker like a piece for draw if it’s on this square
            is_stalker_here = (stalker_img is not None and stalker_sq == square)

            if (piece or is_stalker_here) and square not in self.g.boulder_squares:
                row = 7 - (square // 8)
                col = square % 8

                x = self.g.board_origin_x + col * config.SQUARE_SIZE
                base_y = self.g.board_origin_y + row * config.SQUARE_SIZE
                height_px = int(config.SQUARE_SIZE * config.PIECE_HEIGHT)
                y = base_y - height_px + config.SQUARE_SIZE  # Align bottom of piece to top of square

                # Decide which image to blit
                if piece:
                    piece_image = self.g.PIECE_IMAGES[piece.symbol()]
                else:
                    piece_image = stalker_img

                # Base blit
                self.g.screen.blit(piece_image, (x, y))

                # Poison tint only applies to player's pawns
                if piece:
                    self._blit_green_tint_if_poisoned_pawn(piece, piece_image, x, y)

                # Square overlays (freeze/shield) still based on board state
                if square in self.g.frozen_squares:
                    overlay = pygame.Surface((config.SQUARE_SIZE, config.SQUARE_SIZE), pygame.SRCALPHA)
                    overlay.fill((0, 0, 255, 100))
                    self.g.screen.blit(overlay, (x, base_y))

                if square in self.g.shielded_squares:
                    overlay = pygame.Surface((config.SQUARE_SIZE, config.SQUARE_SIZE), pygame.SRCALPHA)
                    overlay.fill((128, 128, 128, 100))
                    self.g.screen.blit(overlay, (x, base_y))

                # Hover glow (apply to either real piece or stalker)
                if square == hovered_square:
                    pulse_norm = hover_alpha / 255.0
                    glow_strength = config.BASE + config.AMP * (pulse_norm ** config.GAMMA)

                    glowing_piece = piece_image.copy()
                    arr   = pygame.surfarray.pixels3d(glowing_piece).astype(np.float32)
                    alpha = pygame.surfarray.pixels_alpha(glowing_piece).astype(np.float32) / 255.0

                    lum = (0.2126*arr[:, :, 0] + 0.7152*arr[:, :, 1] + 0.0722*arr[:, :, 2]) / 255.0

                    L_LO, L_HI = 0.05, 0.95
                    mid = np.clip((lum - L_LO) / (L_HI - L_LO), 0.0, 1.0)

                    w = (alpha * mid * glow_strength)[:, :, None]
                    arr += (255.0 - arr) * w
                    arr = np.clip(arr, 0, 255)

                    arr_u8 = arr.astype(np.uint8)
                    pygame.surfarray.pixels3d(glowing_piece)[:, :, :] = arr_u8
                    del arr, arr_u8, alpha

                    self.g.screen.blit(glowing_piece, (x, y))

            # Boulder draw (unchanged)
            if hasattr(self, "boulder_squares") and square in self.g.boulder_squares and getattr(self, "boulder_done", False):
                row = 7 - (square // 8)
                col = square % 8
                x = self.g.board_origin_x + col * config.SQUARE_SIZE
                y = self.g.board_origin_y + row * config.SQUARE_SIZE

                if len(self.g.magic_library) > 2:
                    boulder_sprite = self.g.magic_library[config.MFX_BOULDER]["frames"][0]
                    self.g.screen.blit(boulder_sprite, (x, y))


    def draw_pieces_exclude(self, exclude_square):
        squares_sorted = sorted(chess.SQUARES, key=lambda s: -(s // 8))

        # Detect stalker presence (Stage 4 only)
        stalker_sq = None
        stalker_img = getattr(self.g, "stalker_image", None)
        if stalker_img is not None and hasattr(self.g, "map_challenges"):
            try:
                wd = self.g.world.world_data
                stage = wd.get(self.g.world.player_pos, {}).get("stage_id", 1)
                if stage == 4:
                    stalker_sq = getattr(self.g.map_challenges, "_stalker_square", None)
            except Exception:
                stalker_sq = None

        for square in squares_sorted:
            if square == exclude_square:
                continue

            piece = self.g.board.piece_at(square)
            is_stalker_here = (stalker_img is not None and stalker_sq == square)

            if (piece or is_stalker_here) and square not in self.g.boulder_squares:
                row = 7 - (square // 8)
                col = square % 8
                x = self.g.board_origin_x + col * config.SQUARE_SIZE
                base_y = self.g.board_origin_y + row * config.SQUARE_SIZE
                height_px = int(config.SQUARE_SIZE * config.PIECE_HEIGHT)
                y = base_y - height_px + config.SQUARE_SIZE

                if piece:
                    piece_image = self.g.PIECE_IMAGES[piece.symbol()]
                else:
                    piece_image = stalker_img

                self.g.screen.blit(piece_image, (x, y))

                if piece:
                    self._blit_green_tint_if_poisoned_pawn(piece, piece_image, x, y)

                if square in self.g.frozen_squares:
                    overlay = pygame.Surface((config.SQUARE_SIZE, config.SQUARE_SIZE), pygame.SRCALPHA)
                    overlay.fill((0, 0, 255, 100))
                    self.g.screen.blit(overlay, (x, base_y))
                if square in self.g.shielded_squares:
                    overlay = pygame.Surface((config.SQUARE_SIZE, config.SQUARE_SIZE), pygame.SRCALPHA)
                    overlay.fill((128, 128, 128, 100))
                    self.g.screen.blit(overlay, (x, base_y))

            if hasattr(self, "boulder_squares") and square in self.g.boulder_squares and getattr(self, "boulder_done", False):
                row = 7 - (square // 8)
                col = square % 8
                x = self.g.board_origin_x + col * config.SQUARE_SIZE
                y = self.g.board_origin_y + row * config.SQUARE_SIZE

                if len(self.g.magic_library) > 2:
                    boulder_sprite = self.g.magic_library[config.MFX_BOULDER]["frames"][0]
                    self.g.screen.blit(boulder_sprite, (x, y))


    def _blit_green_tint_if_poisoned_pawn(self, piece, piece_image, x, y):
        quests = getattr(self.g, "quests", None)
        if not (quests and getattr(quests, "enable_poisoned_pawns", False)):
            return

        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        if piece.piece_type == chess.PAWN and piece.color == player_color:
            tinted = piece_image.copy()
            tinted.fill((0, 220, 0, 0), special_flags=pygame.BLEND_RGBA_ADD)
            tinted.fill((200, 255, 200, 0), special_flags=pygame.BLEND_RGBA_MULT)
            self.g.screen.blit(tinted, (x, y))

    def animate_piece_move(self, piece_symbol, start_square, end_square):
        self.g.possible_moves = []
        self.g.orb_highlight_squares = []
        piece_char = piece_symbol.lower()
        self.g.audio.play("move_" + piece_char)

        clock = pygame.time.Clock()

        start_col = chess.square_file(start_square)
        start_row = 7 - chess.square_rank(start_square)
        end_col = chess.square_file(end_square)
        end_row = 7 - chess.square_rank(end_square)

        distance_squares = abs(end_col - start_col) + abs(end_row - start_row)
        distance_squares = max(1, distance_squares)

        frames_per_square = 8
        frames = distance_squares * frames_per_square

        height_px = int(config.SQUARE_SIZE * config.PIECE_HEIGHT)

        # Note: base_y is where the square starts; final y aligns bottom of sprite to top of square
        start_base_y = self.g.board_origin_y + start_row * config.SQUARE_SIZE
        start_y = start_base_y - height_px + config.SQUARE_SIZE
        start_x = self.g.board_origin_x + start_col * config.SQUARE_SIZE

        end_base_y = self.g.board_origin_y + end_row * config.SQUARE_SIZE
        end_y = end_base_y - height_px + config.SQUARE_SIZE
        end_x = self.g.board_origin_x + end_col * config.SQUARE_SIZE

        piece_image = self.g.PIECE_IMAGES[piece_symbol]

        for frame in range(frames):
            t = frame / frames
            current_x = start_x + (end_x - start_x) * t
            current_y = start_y + (end_y - start_y) * t

            self.draw("animate_piece", exclude_square=start_square, flip=False)
            self.g.screen.blit(piece_image, (current_x, current_y))
            pygame.display.flip()
            clock.tick(config.FPS)

        # At the end of animate_piece_move
        if self.g.world.world_data[(self.g.world.player_pos)]["stage_id"] == 0:
            player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
            enemy_color = not player_color

            # Determine color directly from the symbol
            is_white = piece_symbol.isupper()
            piece_color = chess.WHITE if is_white else chess.BLACK

            if piece_color == enemy_color:
                self.spawn_particles_from_piece(end_square, start_square)


    ########################################################################
    #                            🪄 SPELL EFFECTS                          #
    ########################################################################
    def draw_spellbook(self):
        # (Re-)build the cache only if needed -------------
        if getattr(self, "_spell_cache_dirty", True) or \
        not hasattr(self, "cached_spell_availability"):
            self.g.spell_rules.evaluate_spell_availability()

        # Background -------------------------------------
        if self.g.spellbook_bg:
            bg = pygame.transform.scale(self.g.spellbook_bg, (config.WIDTH, config.HEIGHT))
            self.g.screen.blit(bg, (0, 0))

        # Pre-compute common values -----------------------
        sorted_spells = sorted(self.g.spellbook)
        gold, bronze   = (160, 140, 0), (120, 80, 40)
        font           = pygame.font.SysFont(None, 32)
        line_height    = 36
        mx, my         = pygame.mouse.get_pos()

        # helper: rainbow/sparkle text --------------------
        def draw_text_with_sparkle(text, x, y, hover=False):
            for idx, ch in enumerate(text):
                phase = idx * 0.3
                t     = (math.sin(self.hover_timer * 0.2 + phase) + 1) / 2
                if hover:
                    dark, bright = (120, 0, 0), (255, 0, 0)
                    color = [int(dark[i]*(1-t) + bright[i]*t) for i in range(3)]
                else:
                    color = [int(gold[i]*(1-t) + bronze[i]*t) for i in range(3)]
                sfc = font.render(ch, True, color)
                self.g.screen.blit(sfc, (x, y))
                x += sfc.get_width()

        # drawing routine for a single column -------------
        def draw_column(spells, start_x, start_y):
            y = start_y
            for spell in spells:
                spell_def = self.g.spell_info.get(spell, {})
                display_name = spell_def.get("name", spell)

                available = self.g.cached_spell_availability.get(spell, True)
                txt_rect  = pygame.Rect(start_x, y, 300, line_height)

                if txt_rect.collidepoint(mx, my) and available:
                    draw_text_with_sparkle(display_name, start_x, y, hover=True)
                else:
                    if available:
                        draw_text_with_sparkle(display_name, start_x, y, hover=False)
                    else:
                        grey = font.render(display_name, True, (128, 128, 128))
                        self.g.screen.blit(grey, (start_x, y))
                y += line_height
                if y > 550:
                    break
        # Page-1 (left)  ---------------------------------
        draw_column(sorted_spells[:8], 323, 118)
        # Page-2 (right) ---------------------------------
        draw_column(sorted_spells[8:], 683, 105)
    def draw_spell_tooltip(self):
        # Draw parchment + wrapped spell description (bottom right).
        if not self.g.spellbook_open or self.g._hover_spell is None:
            return
        if pygame.time.get_ticks() - self.g._hover_start_ms < self.g._HOVER_DELAY_MS:
            return

        spell_def = self.g.spell_info.get(self.g._hover_spell, {})
        title = spell_def.get("name", self.g._hover_spell)
        desc = spell_def.get("description", "(no description)")

        # ---- position / scale scroll ----
        scroll = pygame.transform.smoothscale(self.g.spell_scroll, (600, 400))
        sx = config.WIDTH - 10 - scroll.get_width()
        sy = config.HEIGHT - 10 - scroll.get_height()
        self.g.screen.blit(scroll, (sx, sy))

        # ---- destination area inside scroll ----
        text_x = sx + 150
        text_y = sy + 85
        max_w = scroll.get_width() - 300
        max_h = scroll.get_height() - 150

        text_color = (20, 10, 0)

        def wrap_text(text: str, font: pygame.font.Font, width: int) -> list[str]:
            words = text.split()
            if not words:
                return []

            lines = []
            line = words[0]

            for word in words[1:]:
                test = f"{line} {word}"
                if font.size(test)[0] <= width:
                    line = test
                else:
                    lines.append(line)
                    line = word

            if line:
                lines.append(line)
            return lines

        # Start large, shrink until it fits
        title_size = 46
        body_size = 40
        min_title_size = 24
        min_body_size = 20

        fitted = False

        while title_size >= min_title_size and body_size >= min_body_size:
            title_font = pygame.font.SysFont(None, title_size, bold=True)
            body_font = pygame.font.SysFont(None, body_size)

            title_lines = wrap_text(title, title_font, max_w)
            body_lines = wrap_text(desc, body_font, max_w)

            title_line_h = title_font.get_height()
            body_line_h = body_font.get_height()

            title_height = len(title_lines) * title_line_h
            gap_after_title = 12
            body_height = len(body_lines) * body_line_h

            total_height = title_height + gap_after_title + body_height

            if total_height <= max_h:
                fitted = True
                break

            title_size -= 2
            body_size -= 2

        # Final fallback fonts if somehow still not fitted
        title_font = pygame.font.SysFont(None, max(title_size, min_title_size), bold=True)
        body_font = pygame.font.SysFont(None, max(body_size, min_body_size))

        title_lines = wrap_text(title, title_font, max_w)
        body_lines = wrap_text(desc, body_font, max_w)

        y = text_y

        # Draw title
        for line in title_lines:
            img = title_font.render(line, True, text_color)
            self.g.screen.blit(img, (text_x, y))
            y += title_font.get_height()

        y += 12

        # Draw body
        for line in body_lines:
            img = body_font.render(line, True, text_color)
            self.g.screen.blit(img, (text_x, y))
            y += body_font.get_height()

    # ────────────────────────────────────────────────────────────────────
    # Magic effects (moved from main.py)
    # ────────────────────────────────────────────────────────────────────
    def display_magic_effect(
        self, eid, effect_idx,
        start_x, start_y,
        end_x=None, end_y=None,
        duration=0,
        speed=None,
        acceleration=None,
        complete_attr=None
    ):
        g = self.g

        if effect_idx >= len(g.magic_library):
            print(f"[WARN] Effect #{effect_idx} does not exist.")
            return

        if complete_attr:
            setattr(g, complete_attr, False)

        if speed is not None:
            vx, vy = speed
        elif end_x is not None and end_y is not None and duration:
            vx = (end_x - start_x) / duration
            vy = (end_y - start_y) / duration
        else:
            vx = vy = 0

        ax, ay = acceleration if acceleration else (0, 0)

        g.active_effects[eid] = {
            "proto": g.magic_library[effect_idx],
            "frame": 0,
            "tick": 0,
            "x": start_x,
            "y": start_y,
            "vx": vx,
            "vy": vy,
            "ax": ax,
            "ay": ay,
            "life": duration,
            "target_y": end_y,
            "complete_attr": complete_attr,
            "dx": vx,  # legacy compat
            "dy": vy,  # legacy compat
        }

    def remove_magic_effect(self, eid):
        g = self.g
        eff = g.active_effects.pop(eid, None)
        if eff and eff.get("complete_attr"):
            setattr(g, eff["complete_attr"], True)

    def update_and_draw_magic_effects(self):
        to_remove = []

        for eid, eff in self.g.active_effects.items():
            proto = eff["proto"]

            #  1) advance animation frames 
            eff["tick"] += 1
            if eff["tick"] >= (60 // proto["fps"]):
                eff["tick"] = 0
                eff["frame"] = (eff["frame"] + 1) % len(proto["frames"])

            #  2) kinematics  (v += a ;  x += v) 
            if "vx" in eff:                       # new-style effect
                eff["vx"] += eff.get("ax", 0)
                eff["vy"] += eff.get("ay", 0)
                eff["x"]  += eff["vx"]
                eff["y"]  += eff["vy"]

                # Auto-stop when Y falls past target_y (if defined)
                target_y = eff.get("target_y")
                if target_y is not None and eff["y"] >= target_y:
                    eff["y"] = target_y
                    eff["vx"] = eff["vy"] = eff["ax"] = eff["ay"] = 0
                    to_remove.append(eid)
            else:                                 # legacy dx/dy fallback
                eff["x"] += eff["dx"]
                eff["y"] += eff["dy"]

            #  3) lifetime countdown 
            if eff["life"] > 0:
                eff["life"] -= 1
                if eff["life"] == 0:
                    to_remove.append(eid)

            #  4) blit current frame 
            frame_surf = proto["frames"][eff["frame"]]
            self.g.screen.blit(frame_surf, (int(eff["x"]), int(eff["y"])))

        #  5) cleanup finished effects 
        for eid in to_remove:
            self.remove_magic_effect(eid)

        #  6) meteor bookkeeping (unchanged) 
        new_queue = []
        for eid, frames_left, sq in self.g.meteor_target_queue:
            frames_left -= 1
            if frames_left <= 0:
                # spawn explosion at target square
                file  = chess.square_file(sq)
                rank  = chess.square_rank(sq)
                sx    = self.g.board_origin_x + file * config.SQUARE_SIZE
                sy    = self.g.board_origin_y + (7 - rank) * config.SQUARE_SIZE
                fw, fh = self.g.magic_library[config.MFX_EXPLODE]["frames"][0].get_size()
                ex_id  = f"boom_{sq}_{pygame.time.get_ticks()}"

                self.display_magic_effect(
                    ex_id, config.MFX_EXPLODE,
                    sx + (config.SQUARE_SIZE - fw)//2,
                    sy + (config.SQUARE_SIZE - fh)//2,
                    duration=24
                )

                self.g.quests.record_captured_piece(self.g.board.piece_at(sq), count_for_quests=True)
                self.g.board.remove_piece_at(sq)
                self.remove_magic_effect(eid)      # erase falling meteor
            else:
                new_queue.append((eid, frames_left, sq))
        self.g.meteor_target_queue = new_queue

    def draw_flood_animations(self):
        finished_animations = []

        for animation in self.g.flood_animations:
            alpha = animation["alpha"]
            direction = animation["direction"]

            # Adjust alpha
            if direction == 1:
                alpha += 3
                if alpha >= 150:
                    alpha = 150
                    animation["direction"] = -1  # switch to fade-out
            else:
                alpha -= 5
                if alpha <= 0:
                    finished_animations.append(animation)
                    continue  # don't draw anymore

            animation["alpha"] = alpha

            # Draw the overlay
            overlay = pygame.Surface((config.SQUARE_SIZE, config.SQUARE_SIZE), pygame.SRCALPHA)
            overlay.fill((0, 0, 180, alpha))  # dark blue with alpha

            for square in animation["squares"]:
                col = chess.square_file(square)
                row = chess.square_rank(square)
                x = self.g.board_origin_x + col * config.SQUARE_SIZE
                y = self.g.board_origin_y + (7 - row) * config.SQUARE_SIZE
                self.g.screen.blit(overlay, (x, y))

        # Remove finished animations
        for animation in finished_animations:
            self.g.flood_animations.remove(animation)

    ########################################################################
    #                          ⚙️  GEAR / GEAR UI                      #
    ########################################################################
    def draw_gear_bar(self):
        """
        Draws owned gear along the bottom of the board. Gear is drawn
        'behind' quest cards (we call this before draw_current_quest_cards).

        Behavior:
        - Only gear in self.g.gear_owned is drawn.
        - If ANY active quests remain, gear is dim + non-interactive.
        - Once ALL quest cards are completed, hovering a gear for 2 seconds
          shows a scroll description, and its gamma/brightness is boosted.
        """
        # If no gear system or owned list, nothing to do
        gear_owned = getattr(self.g, "gear_owned", None)
        if not gear_owned:
            self.gear_rects.clear()
            self.gear_hover_id = None
            return

        # Where to place the bar: horizontally centered under the board
        S = config.SQUARE_SIZE
        board_left = self.g.board_origin_x
        board_top = self.g.board_origin_y
        board_width = 8 * S
        board_bottom = board_top + 8 * S

        icon_size = int(S * 0.8)
        padding = int(S * 0.15)
        total_width = len(gear_owned) * icon_size + (len(gear_owned) - 1) * padding

        start_x = board_left + (board_width - total_width) // 2
        y = board_bottom + int(S * 0.1)  # slight gap under board

        # Make sure we don't draw off the screen
        if y + icon_size > config.HEIGHT:
            y = config.HEIGHT - icon_size - 10

        # Quest completion check: gear only usable once ALL quest cards are done
        quests_done = not getattr(self.g.quests, "active_quests", [])

        mx, my = pygame.mouse.get_pos()
        now_ms = pygame.time.get_ticks()

        self.gear_rects.clear()
        hovered_id = None

        for i, gear_id in enumerate(gear_owned):
            x = start_x + i * (icon_size + padding)

            rect = pygame.Rect(x, y, icon_size, icon_size)
            self.gear_rects[gear_id] = rect

            # Get icon surface
            icon = None
            if hasattr(self.g, "gear_icons"):
                icon = self.g.gear_icons.get(gear_id)

            if icon is None:
                # Fallback: simple colored placeholder with letter
                icon = pygame.Surface((icon_size, icon_size), pygame.SRCALPHA)
                icon.fill((60, 60, 60, 255))
                pygame.draw.rect(icon, (180, 180, 180), icon.get_rect(), 2)
                label = gear_id[:2].upper()
                font = pygame.font.SysFont(None, 24)
                txt = font.render(label, True, (255, 255, 255))
                self.g.screen.blit(icon, rect.topleft)
                self.g.screen.blit(
                    txt, txt.get_rect(center=rect.center)
                )
                continue

            # Scale icon to slot
            scaled_icon = pygame.transform.smoothscale(icon, (icon_size, icon_size))

            # Dim if quests not done yet
            if quests_done:
                # Interactive: full alpha, maybe boosted on hover
                if rect.collidepoint(mx, my):
                    hovered_id = gear_id
                    # Apply a gamma/brightness boost ~ +30%
                    boosted = self._apply_gamma_boost(scaled_icon, factor=1.3)
                    self.g.screen.blit(boosted, rect.topleft)
                else:
                    self.g.screen.blit(scaled_icon, rect.topleft)
            else:
                # Not yet usable; draw slightly dimmed and ignore hover logic
                dim = scaled_icon.copy()
                dim.fill((0, 0, 0, 120), special_flags=pygame.BLEND_RGBA_SUB)
                self.g.screen.blit(dim, rect.topleft)

        # ───── Hover timer + 2s tooltip logic (only if all quests done) ─────
        if not quests_done or hovered_id is None:
            # Reset hover tracking if no valid hover
            self.gear_hover_id = None
            self._gear_hover_tooltip_fired = False
            return

        # New hover started?
        if hovered_id != self.gear_hover_id:
            self.gear_hover_id = hovered_id
            self.gear_hover_start_ms = now_ms
            self._gear_hover_tooltip_fired = False
        else:
            # Same gear still hovered
            elapsed = now_ms - self.gear_hover_start_ms
            if elapsed >= 2000 and not self._gear_hover_tooltip_fired:
                self._gear_hover_tooltip_fired = True
                self._show_gear_scroll(hovered_id)

    def _apply_gamma_boost(self, surf: pygame.Surface, factor: float = 1.3) -> pygame.Surface:
        """
        Approximate 'gamma increase' by boosting brightness.
        factor ~1.3 means +30% brightness, with clipping.
        """
        boosted = surf.copy()
        try:
            arr = pygame.surfarray.pixels3d(boosted).astype("float32")
            arr *= factor
            arr[arr > 255] = 255
            pygame.surfarray.pixels3d(boosted)[:, :, :] = arr.astype("uint8")
        except Exception:
            # Fallback: simple additive tint if surfarray isn't available
            boosted.fill((40, 40, 40, 0), special_flags=pygame.BLEND_RGBA_ADD)
        return boosted

    def _show_gear_scroll(self, gear_id: str):
        """
        Trigger the feedback scroll with the gear's description.
        Uses existing feedback scroll rendering in draw_feedback().
        """
        desc = self.gear_descriptions.get(gear_id)
        if not desc:
            return

        # You can tweak the wording / title here
        # e.g., include a nice title prefix
        title = gear_id.replace("_", " ").title()
        self.feedback_text = f"{title}\n\n{desc}"

        # Basic animation parameters - aligned with your draw_feedback logic
        self.feedback_alpha = 255
        self.feedback_unfold_frames = int(0.6 * config.FPS)  # unfold over ~0.6s
        self.feedback_frame_counter = 0
        self.feedback_collapse_early = False  # let normal lifecycle handle closing

    def handle_gear_click(self, pos) -> bool:
        """
        To be called from main.py on MOUSEBUTTONDOWN.
        If a gear icon is clicked (and gear is usable), call gear.use_gear(gear_id)
        and return True. Otherwise return False.
        """
        # Must have gear and no active quests to be usable
        quests_done = not getattr(self.g.quests, "active_quests", [])
        if not quests_done:
            return False

        if not self.gear_rects:
            return False

        x, y = pos
        for gear_id, rect in self.gear_rects.items():
            if rect.collidepoint(x, y):
                # Call into gear system if present
                equip = getattr(self.g, "gear", None)
                if equip and hasattr(equip, "use_gear"):
                    equip.use_gear(gear_id)
                return True
        return False

    def is_click_on_board(self, x: int, y: int) -> bool:
        """
        Return True if the given screen coordinates (x, y)
        are inside the 8x8 chessboard area.
        """
        S = config.SQUARE_SIZE
        board_rect = pygame.Rect(
            self.g.board_origin_x,
            self.g.board_origin_y,
            8 * S,
            8 * S,
        )
        return board_rect.collidepoint(x, y)

    ########################################################################
    #                         🧩 QUEST & REWARDS UI                         #
    ########################################################################
    def draw_current_quest_cards(self):
        if not self.g.quests.active_quests:
            return

        mouse_x, mouse_y = pygame.mouse.get_pos()
        screen_w = config.WIDTH
        screen_h = config.HEIGHT

        # Determine if hovering over the "peek" area
        peek_height = 60
        if mouse_y > screen_h - peek_height:
            self.g.quests.quest_card_hovered = True
        else:
            self.g.quests.quest_card_hovered = False

        # Animate offset for sliding up/down (0.0 to 1.0)
        target_offset = 1.0 if self.g.quests.quest_card_hovered else 0.0
        speed = 0.1
        self.current_quest_hover_offset += (target_offset - self.current_quest_hover_offset) * speed

        # Base card size and scaling
        base_w, base_h = self.g.quests.original_card_size
        scale_start = config.CARD_SCALE
        scale_end = config.CARD_SCALE_EXPAND
        current_scale = scale_start + (scale_end - scale_start) * self.current_quest_hover_offset

        scaled_w = int(base_w * current_scale)
        scaled_h = int(base_h * current_scale)

        # Vertical positioning
        y_start = screen_h - peek_height
        y_end = screen_h // 2 - scaled_h // 2
        current_y = int(y_start + (y_end - y_start) * self.current_quest_hover_offset)

        active_count = len(self.g.quests.active_quests)
        positions = self._quest_card_hand_positions(active_count, scaled_w, scaled_h, current_y)

        for i, qid in enumerate(self.g.quests.active_quests):
            if qid not in self.g.quests.quest_candidates:
                continue
            index = self.g.quests.quest_candidates.index(qid)
            card = self.g.quests.quest_cards[index]

            # Scale card from full-res
            card_scaled = pygame.transform.smoothscale(card, (scaled_w, scaled_h))
            x, y = positions[i]
            self.g.screen.blit(card_scaled, (x, y))

    def _quest_card_hand_positions(self, count, card_w, card_h, y):
        if count <= 0:
            return []
        screen_w = self.g.screen.get_width()
        max_width = int(screen_w * 0.92)
        if count == 1:
            return [((screen_w - card_w) // 2, y)]

        natural_step = card_w + config.CARD_MARGIN
        total_width = card_w + natural_step * (count - 1)
        if total_width <= max_width:
            step = natural_step
        else:
            step = max(36, (max_width - card_w) // max(1, count - 1))
            total_width = card_w + step * (count - 1)

        start_x = (screen_w - total_width) // 2
        center = (count - 1) / 2
        positions = []
        for i in range(count):
            offset = abs(i - center)
            arc_y = int(y + offset * 8)
            positions.append((int(start_x + i * step), arc_y))
        return positions

    def update_reward_presentation_queue(self):
        """
        Start the next queued quest win animation only if no win animation
        is currently running.
        """
        # If something is already animating, do nothing
        if self.quest_win_animations:
            return

        qrh = getattr(self.g, "quest_reward_handler", None)
        if not qrh:
            return

        qrh.update_reward_queue()

        # QuestRewardHandler owns queued reward-card presentation state.
        active = getattr(qrh, "active_reward_card", None)
        if not active:
            return

        qid = active.get("quest_num")
        if qid is None:
            return

        self.start_quest_win_animation(qid, display_index=active.get("display_index"))

    def draw_quest_selection(self):
        self.g.screen.fill((20, 20, 20))
        self.draw_background()
        self.draw_board()
        self.draw_pieces()

        # Title
        text = "Pick 3 Quests"
        title_shadow = self.pick_3_font.render(text, True, (0, 0, 0))
        title_text = self.pick_3_font.render(text, True, (255, 255, 255))
        center_x = self.g.screen.get_width() // 2 - title_text.get_width() // 2
        self.g.screen.blit(title_shadow, (center_x + 2, 32 + 2))
        self.g.screen.blit(title_text, (center_x, 32))

        # Update scales & compute total width
        mouse_pos = pygame.mouse.get_pos()
        self.g.quests.hovered_card_index = None
        card_y = 270
        base_card_w, base_card_h = self.g.quests.original_card_size
        card_scales = []

        # First pass: calculate scales and hover
        for i in range(len(self.g.quests.quest_cards)):
            rect_estimate = pygame.Rect(0, 0, int(base_card_w * config.CARD_SCALE), int(base_card_h * config.CARD_SCALE))
            rect_estimate.x = i * (rect_estimate.width + config.CARD_MARGIN)
            rect_estimate.y = card_y
            if rect_estimate.collidepoint(mouse_pos):
                self.g.quests.hovered_card_index = i

            # Animate scale
            target = config.CARD_SCALE_EXPAND if i == self.g.quests.hovered_card_index else config.CARD_SCALE
            current = self.g.quests.card_hover_scales[i]
            self.g.quests.card_hover_scales[i] = current + (target - current) * 0.2
            card_scales.append(self.g.quests.card_hover_scales[i])

        # Compute total width based on animated scale
        total_width = sum(int(base_card_w * s) for s in card_scales) + config.CARD_MARGIN * (len(card_scales) - 1)
        start_x = (self.g.screen.get_width() - total_width) // 2

        # Draw cards
        self.g.quests.card_rects = []
        x_cursor = start_x
        for i, card in enumerate(self.g.quests.quest_cards):
            qid = self.g.quests.quest_candidates[i]
            scale = card_scales[i]
            scaled_w = int(base_card_w * scale)
            scaled_h = int(base_card_h * scale)
            scaled_card = pygame.transform.smoothscale(card, (scaled_w, scaled_h))
            y = card_y - (scaled_h - int(base_card_h * config.CARD_SCALE)) // 2

            rect = pygame.Rect(x_cursor, y, scaled_w, scaled_h)
            self.g.screen.blit(scaled_card, rect.topleft)
            # Yellow selection glow
            if qid in self.g.quests.active_quests:
                highlight = pygame.Surface((scaled_w, scaled_h), pygame.SRCALPHA)
                highlight.fill(config.CARD_SELECTED_TINT)
                self.g.screen.blit(highlight, rect.topleft)

            self.g.quests.card_rects.append((rect, qid))
            x_cursor += scaled_w + config.CARD_MARGIN

        # Continue button
        if len(self.g.quests.active_quests) == 3:
            self.g.quests.show_continue_button = True
            btn_text = self.btn_font.render("Continue", True, (255, 255, 255))
            btn_bg = pygame.Surface((btn_text.get_width()+40, btn_text.get_height()+20))
            btn_bg.fill((50, 150, 50))
            self.g.quests.continue_rect = btn_bg.get_rect(center=(self.g.screen.get_width() // 2, card_y + int(base_card_h * config.CARD_SCALE) + 80))
            self.g.screen.blit(btn_bg, self.g.quests.continue_rect.topleft)
            self.g.screen.blit(btn_text, btn_text.get_rect(center=self.g.quests.continue_rect.center))
        else:
            self.g.quests.continue_rect = None

    def draw_quest_win_animations(self):
        for anim in self.quest_win_animations:
            state = anim["state"]
            t = anim["frame"] / 60

            cfg = self.quest_anim_config

            if state in ["rising", "holding", "shaking"]:
                img = anim["image"]
                x0, y0 = anim["start_pos"]
                x1, y1 = anim["end_pos"]

                if state == "rising":
                    p = min(1.0, t / cfg["rise_duration"])
                    ease_p = p * p * (3 - 2 * p)
                    y = y0 + (y1 - y0) * ease_p
                else:
                    y = y1

                x = x1
                if state == "shaking":
                    shake_mag = 6
                    x += random.randint(-shake_mag, shake_mag)
                    y += random.randint(-shake_mag, shake_mag)

                self.g.screen.blit(img, (x, y))

            elif state == "exploding":
                for piece in anim["pieces"]:
                    explosion_frame = anim.get("explosion_started_frame", anim["frame"])
                    explosion_elapsed = max(0, anim["frame"] - explosion_frame) / 60
                    fade_p = min(1.0, explosion_elapsed / cfg["explode_duration"])
                    alpha = int((1.0 - fade_p) * 255)

                    img = pygame.transform.rotozoom(piece["image"], piece["angle"], piece["scale"])
                    img.fill((255, 255, 255, alpha), special_flags=pygame.BLEND_RGBA_MULT)
                    img = img.convert_alpha()
                    self.g.screen.blit(img, piece["pos"])
                    piece["angle"] += piece["rotation_speed"]

    def slice_image_into_jagged_pieces(self, image, origin=(0, 0), rows=6, cols=6):
        origin_x, origin_y = origin
        def generate_jagged_polygon(w, h, points=8, jaggedness=0.25):
            poly = []
            for i in range(points):
                angle = 2 * math.pi * i / points
                radius = 1 + random.uniform(-jaggedness, jaggedness)
                x = int(w / 2 + math.cos(angle) * w / 2 * radius)
                y = int(h / 2 + math.sin(angle) * h / 2 * radius)
                poly.append((x, y))
            return poly

        w, h = image.get_size()
        piece_w = w // cols
        piece_h = h // rows
        pieces = []

        pad = 8  # extra space to prevent rotozoom edge artifacts

        # Build scaling, screen information for position of the pieces
        base_w, base_h = self.g.quests.original_card_size
        # Use current scale
        current_scale = config.CARD_SCALE_EXPAND
        scaled_w = int(base_w * current_scale)
        scaled_h = int(base_h * current_scale)

        for row in range(rows):
            for col in range(cols):
                x = col * piece_w
                y = row * piece_h

                # 1. Extract image fragment
                fragment = pygame.Surface((piece_w, piece_h), pygame.SRCALPHA)
                fragment.fill((0, 0, 0, 0))
                fragment.blit(image, (0, 0), (x, y, piece_w, piece_h))

                # 2. Create jagged mask
                jagged_polygon = generate_jagged_polygon(piece_w, piece_h)
                mask_surface = pygame.Surface((piece_w, piece_h), pygame.SRCALPHA)
                pygame.gfxdraw.filled_polygon(mask_surface, jagged_polygon, (255, 255, 255, 255))
                jagged_mask = pygame.mask.from_surface(mask_surface)

                # 3. Apply mask
                for px in range(piece_w):
                    for py in range(piece_h):
                        if not jagged_mask.get_at((px, py)):
                            fragment.set_at((px, py), (0, 0, 0, 0))

                # 4. Pad fragment to avoid rotation black edges
                padded = pygame.Surface((piece_w + 2 * pad, piece_h + 2 * pad), pygame.SRCALPHA)
                padded.fill((0, 0, 0, 0))
                padded.blit(fragment, (pad, pad))

                # 5. Store physics
                dx = col - cols // 2
                dy = row - rows // 2
                speed = random.uniform(3, 6.0)

                pieces.append({
                    "image": padded,
                    "pos": [origin_x + x, origin_y + y],
                    "vel": [random.uniform(dx, dx + 0.5) * speed, random.uniform(dy, dy + 0.5) * speed],
                    "alpha": 255,
                    "angle": 0,
                    "rotation_speed": random.uniform(-2, 2),
                    "scale": 1.0
                })

        return pieces


    def update_quest_win_animations(self, dt):
        anim_config = self.quest_anim_config
        finished = []

        for anim in self.quest_win_animations:
            anim["frame"] += 1
            t = anim["frame"] / 60  # convert frame count to seconds

            if anim["state"] == "rising" and t >= anim_config["rise_duration"]:
                anim["state"] = "holding"
            elif anim["state"] == "holding" and t >= anim_config["rise_duration"] + anim_config["hold_duration"]:
                anim["state"] = "shaking"
            elif anim["state"] == "shaking" and t >= anim_config["rise_duration"] + anim_config["hold_duration"] + anim_config["shake_duration"]:
                anim["state"] = "exploding"
                anim["explosion_started_frame"] = anim["frame"]
                card_rect = anim.get("card_rect")
                origin = card_rect.topleft if card_rect else anim["end_pos"]
                anim["pieces"] = self.slice_image_into_jagged_pieces(
                    anim["image"],
                    origin=origin
                )

            if anim["state"] == "exploding":
                for piece in anim["pieces"]:
                    piece["pos"][0] += piece["vel"][0]
                    piece["pos"][1] += piece["vel"][1]
                    piece["alpha"] = max(0, piece["alpha"] - 4)

                explosion_elapsed = (anim["frame"] - anim.get("explosion_started_frame", anim["frame"])) / 60
                if explosion_elapsed >= anim_config["explode_duration"]:
                    finished.append(anim)

        for anim in finished:
            if anim in self.quest_win_animations:
                self.quest_win_animations.remove(anim)

            # Notify the queue owner that the current reward presentation is done.
            qrh = getattr(self.g, "quest_reward_handler", None)
            if qrh and getattr(qrh, "active_reward_card", None):
                active = qrh.active_reward_card
                if active.get("quest_num") == anim.get("qid"):
                    qrh.active_reward_card = None

    def start_quest_win_animation(self, qid, display_index=None):
        print("Calling start_quest_win_animation: ", qid)
        if self.quest_win_animations:
            return False
        if qid not in self.g.quests.quest_candidates:
            return False

        index = self.g.quests.quest_candidates.index(qid)
        base_w, base_h = self.g.quests.original_card_size

        # Use current scale
        current_scale = config.CARD_SCALE_EXPAND
        scaled_w = int(base_w * current_scale)
        scaled_h = int(base_h * current_scale)

        # Rebuild the card at the scaled size
        full_card_img = self.g.quests.quest_cards[index]
        card_scaled = pygame.transform.smoothscale(full_card_img, (scaled_w, scaled_h))

        screen_w = self.g.screen.get_width()
        screen_h = self.g.screen.get_height()
        card_rect = card_scaled.get_rect(center=(screen_w // 2, screen_h // 2))

        if display_index is None:
            if qid not in self.g.quests.active_quests:
                return False
            display_index = self.g.quests.active_quests.index(qid)
        active_count = max(1, len(self.g.quests.active_quests))
        display_index = max(0, min(active_count - 1, int(display_index)))

        y = screen_h - 60  # initial peek zone
        positions = self._quest_card_hand_positions(active_count, scaled_w, scaled_h, y)
        x, y = positions[display_index]

        self.quest_win_animations.append({
            "qid": qid,
            "image": card_scaled,
            "frame": 0,
            "state": "rising",
            "pos": [x, y],
            "start_pos": [x, y],
            "end_pos": [card_rect.x, card_rect.y],
            "card_rect": card_rect,
            "explosion_started_frame": None,
            "pieces": None
        })
        return True


    ########################################################################
    #                           💰 GOLD & EFFECTS                          #
    ########################################################################
    def draw_gold(self):
        for square in self.g.landed_gold_pieces:
            if square in self.g.gold_icons:
                icon = self.g.gold_icons[square]
                row = 7 - chess.square_rank(square)
                col = chess.square_file(square)
                icon_size = int(config.SQUARE_SIZE * 0.5)
                scaled_icon = pygame.transform.scale(icon, (icon_size, icon_size))
                x = self.g.board_origin_x + col * config.SQUARE_SIZE + (config.SQUARE_SIZE - icon_size) // 2
                y = self.g.board_origin_y + row * config.SQUARE_SIZE + (config.SQUARE_SIZE - icon_size) // 2
                self.g.screen.blit(scaled_icon, (x, y))

    def animate_gold_drop(self, square, icon):
        clock = pygame.time.Clock()

        # Board destination
        row = 7 - chess.square_rank(square)
        col = chess.square_file(square)
        dest_x = self.g.board_origin_x + col * config.SQUARE_SIZE
        dest_y = self.g.board_origin_y + row * config.SQUARE_SIZE

        # Icon scaling
        icon_size = int(config.SQUARE_SIZE * 0.5)
        icon = pygame.transform.scale(icon, (icon_size, icon_size))

        # Start above the screen
        y = -icon_size
        speed = 40  # pixels per frame

        while y < dest_y:
            # Render pipeline
            self.draw("gold_drop", flip=False)
            self.g.screen.blit(icon, (dest_x + (config.SQUARE_SIZE - icon_size) // 2, y))
            pygame.display.flip()
            y += speed
            clock.tick(config.FPS)


    def destroy_piece(self, square):
        piece = self.g.board.piece_at(square)
        if not piece:
            return

        image = self.g.PIECE_IMAGES.get(piece.symbol())
        if image is None:
            return

        

        # Calculate board-relative coordinates
        row = 7 - (square // 8)
        col = square % 8
        x = self.g.board_origin_x + col * config.SQUARE_SIZE
        base_y = self.g.board_origin_y + row * config.SQUARE_SIZE
        height_px = int(config.SQUARE_SIZE * config.PIECE_HEIGHT)
        y = base_y - height_px + config.SQUARE_SIZE  # Align bottom of piece to top of square
        explosion_pieces = self.slice_image_into_jagged_pieces(image, origin=(x,y))

        self.quest_win_animations.append({
            "qid": None,
            "image": image,
            "frame": 0,
            "state": "exploding",
            "pos": [x, y],
            "start_pos": [x, y],
            "end_pos": [x, y],
            "pieces": explosion_pieces
        })
