# render_ui.py
import pygame
import math
import config


class UIRenderMixin:
    """
    UI rendering chunk pulled out of render.py.

    Assumes the main renderer provides:
      - self.g
      - self.hover_timer (for sparkle text timing)
    """

    def _ui_init(self):
        # Dialog
        self.enemy_dialog_text = ""
        self.enemy_dialog_alpha = 0
        self.enemy_dialog_timer = 0  # frames to stay fully visible

        # Feedback variables
        self.feedback_text = ""
        self.feedback_alpha = 0
        self.feedback_unfold_frames = 0
        self.feedback_timer_hold = 0
        self.feedback_total_duration = 0

        self.feedback_min_display_frames = int(0.5 * config.FPS)
        self.feedback_frame_counter = 0
        self.feedback_waiting_for_click = False
        self.feedback_collapse_early = False

        # Fonts used by UI
        self.btn_font = pygame.font.SysFont("arial", 32, bold=True)
        self.pick_3_font = pygame.font.SysFont("georgia", 48, bold=True)

        # Gamestate render controls
        self.gstate_display_active = False
        self.gstate_display_start_time = 0
        self.gstate_display_max_time = 5000  # 5 seconds
        self.gstate_display_anim_duration = 200  # 200ms grow effect
        self.gstate_display_type = None  # "checkmate", "stalemate", etc.

        # ───────── Powers area lock overlay animation ─────────
        # When powers_unlocked is False, we draw chain/lock/shackle.
        # When unlocking is triggered: shackle rises, then all fade out, then powers_unlocked=True.
        self._powers_unlock_anim_active = False
        self._powers_unlock_anim_start_ms = 0

        # Timings (ms)
        self._powers_unlock_shackle_rise_ms = 650
        self._powers_unlock_fade_ms = 650

        # Motion tuning
        self._powers_unlock_shackle_margin_top = 8  # px from top of lock_ui_box

    ########################################################################
    #                           📜 UI                                      #
    ########################################################################
    def draw_background(self):
        # Full background fill
        self.g.screen.fill((20, 20, 20))
        # Apply background image
        self.draw_background_image()
        # Draw the powers area
        self.draw_powers_area()

    def draw_background_image(self) -> None:
        if self.g.background_image is None:
            return  # nothing to draw

        # (keeping your current behavior as-is)
        if not hasattr(self, "_bg_scaled"):
            scale_factor = config.HEIGHT / self.g.background_image.get_height()
            new_w = int(self.g.background_image.get_width() * scale_factor)
            new_h = config.HEIGHT
            self._bg_scaled = pygame.transform.smoothscale(
                self.g.background_image, (new_w, new_h)
            )

        self.g.screen.blit(self._bg_scaled, (0, 0))

    def draw_gold_counter(self):
        """Draw a static gold counter (coin icon + = + amount) in the top-left corner."""
        x, y = 60, 20
        font = pygame.font.SysFont(None, 48)

        if getattr(self.g, "gold_coins", None) and len(self.g.gold_coins) > 0:
            coin_img = self.g.gold_coins[0]
        else:
            coin_img = pygame.Surface((40, 40), pygame.SRCALPHA)
            pygame.draw.circle(coin_img, (212, 175, 55), (20, 20), 18)
            pygame.draw.circle(coin_img, (120, 90, 20), (20, 20), 18, 3)

        COIN_SIZE = 48
        coin_img = pygame.transform.smoothscale(coin_img, (COIN_SIZE, COIN_SIZE))

        gold_amount = getattr(self.g, "player_gold", 0)
        text = f"= {gold_amount}"
        text_surface = font.render(text, True, (255, 255, 255))
        shadow_surface = font.render(text, True, (0, 0, 0))

        coin_y = y
        text_y = y + (COIN_SIZE // 2 - text_surface.get_height() // 2)

        self.g.screen.blit(shadow_surface, (x + COIN_SIZE + 10 + 2, text_y + 2))
        self.g.screen.blit(coin_img, (x, coin_y))
        self.g.screen.blit(text_surface, (x + COIN_SIZE + 10, text_y))

    def draw_powers_area(self, hovered_power=None):
        power_rect = pygame.Rect(config.WIDTH - config.POWER_WIDTH, 0, config.POWER_WIDTH, config.HEIGHT)
        pygame.draw.rect(self.g.screen, (30, 30, 30), power_rect)

        outline_color = (0, 191, 255)
        outline_width = 3
        corner_radius = 12

        inventory_rect = pygame.Rect(
            config.WIDTH - config.POWER_WIDTH + 10, 10,
            config.POWER_WIDTH - 20, (config.HEIGHT // 2) - 20
        )
        pygame.draw.rect(self.g.screen, outline_color, inventory_rect, outline_width, border_radius=corner_radius)

        font = pygame.font.SysFont(None, 24)
        text_surface = font.render("Inventory", True, outline_color)
        text_rect = text_surface.get_rect(center=(inventory_rect.centerx, inventory_rect.y + 15))
        self.g.screen.blit(text_surface, text_rect)

        locked = not getattr(self.g, "powers_unlocked", False)

        icon_size = 72
        padding = 8
        start_x = inventory_rect.x + padding
        start_y = inventory_rect.y + 30

        col_count = 2
        index = 0

        for power, count in self.g.powerups.items():
            row = index // col_count
            col = index % col_count
            icon_x = start_x + col * (icon_size + padding)
            icon_y = start_y + row * (icon_size + padding)

            icon = self.g.power_icons.get(power)
            if icon:
                rect = pygame.Rect(icon_x, icon_y, icon_size, icon_size)
                self.g.power_icon_rects[power] = rect
                self.g.screen.blit(icon, rect.topleft)

                if (not locked) and hovered_power == power:
                    hover_rect = pygame.Rect(icon_x - 1, icon_y - 1, icon_size + 2, icon_size + 2)
                    pygame.draw.rect(self.g.screen, (200, 200, 200), hover_rect, 2)

                if (not locked) and self.g.selected_power == power:
                    highlight_rect = pygame.Rect(icon_x - 2, icon_y - 2, icon_size + 4, icon_size + 4)
                    pygame.draw.rect(self.g.screen, (255, 255, 0), highlight_rect, 3)

                count_surface = font.render(str(count), True, (255, 255, 255))
                count_rect = count_surface.get_rect(bottomright=(icon_x + icon_size - 2, icon_y + icon_size - 2))
                bg_rect = count_rect.inflate(4, 4)
                pygame.draw.rect(self.g.screen, (0, 0, 0, 180), bg_rect)
                self.g.screen.blit(count_surface, count_rect)

            index += 1

        spells_rect = pygame.Rect(inventory_rect.x, config.HEIGHT // 2 + 10, inventory_rect.width, inventory_rect.height)
        pygame.draw.rect(self.g.screen, outline_color, spells_rect, outline_width, border_radius=corner_radius)

        text_surface = font.render("Spells", True, outline_color)
        text_rect = text_surface.get_rect(center=(spells_rect.centerx, spells_rect.y + 15))
        self.g.screen.blit(text_surface, text_rect)

        if self.g.spellbook_icon:
            book_icon_size = spells_rect.width - 2 * padding
            book_icon = pygame.transform.scale(self.g.spellbook_icon, (book_icon_size, book_icon_size))
            book_x = spells_rect.x + (spells_rect.width - book_icon_size) // 2
            book_y = spells_rect.y + (spells_rect.height - book_icon_size) // 2 + 10
            self.g.screen.blit(book_icon, (book_x, book_y))

        # Locked overlay on top of powers area
        if not getattr(self.g, "powers_unlocked", False):
            self._draw_powers_lock_overlay()

    def _draw_powers_lock_overlay(self):
        """
        Draw chain/lock/shackle overlay.

        REQUIRED DRAW ORDER:
            chain (back) -> shackle (middle) -> lock (front)

        Visual fix:
            The lock should occlude the lower portion of the shackle so it appears
            "inserted" into the lock body. We do this by clipping the shackle draw
            to only the region ABOVE a cutoff line (approx mouth line).

        If unlock animation is active:
          - shackle rises to top of lock_ui_box
          - then all fade out
          - then powers_unlocked=True
        """
        chain = getattr(self.g, "chain_image", None)
        lock = getattr(self.g, "lock_image", None)
        shackle = getattr(self.g, "shackle_image", None)
        box = getattr(self.g, "lock_ui_box", None)

        # If assets aren't loaded, fail quietly
        if not (chain and lock and shackle and box):
            return

        now = pygame.time.get_ticks()

        # Base alpha
        alpha = 255

        # Use the stored centered rects from AssetManager as baseline
        chain_rect = getattr(self.g, "chain_rect", pygame.Rect(box))
        lock_rect_base = getattr(self.g, "lock_rect", None)
        shackle_rect_base = getattr(self.g, "shackle_rect", None)

        if lock_rect_base is None:
            lock_rect_base = lock.get_rect(center=box.center)
        if shackle_rect_base is None:
            shackle_rect_base = shackle.get_rect(center=box.center)

        lock_rect = lock_rect_base.copy()
        shackle_rect = shackle_rect_base.copy()

        # ─────────────────────────────────────────────
        # Animation: shackle rise, then fade out all
        # ─────────────────────────────────────────────
        if self._powers_unlock_anim_active:
            t = now - self._powers_unlock_anim_start_ms
            rise_ms = max(1, int(self._powers_unlock_shackle_rise_ms))
            fade_ms = max(1, int(self._powers_unlock_fade_ms))

            # Phase 1: shackle rises
            if t <= rise_ms:
                u = max(0.0, min(1.0, t / float(rise_ms)))

                start_y = shackle_rect_base.centery
                end_y = box.top + self._powers_unlock_shackle_margin_top + (shackle.get_height() // 2)

                # Smoothstep easing
                u = u * u * (3 - 2 * u)

                shackle_rect.centery = int(round(start_y + (end_y - start_y) * u))
                alpha = 255

            # Phase 2: fade out everything
            else:
                v = (t - rise_ms) / float(fade_ms)
                v = max(0.0, min(1.0, v))
                alpha = int(round(255 * (1.0 - v)))

                # Keep shackle at final "up" position during fade
                shackle_rect.centery = box.top + self._powers_unlock_shackle_margin_top + (shackle.get_height() // 2)

                # End
                if v >= 1.0:
                    self._powers_unlock_anim_active = False
                    self.g.powers_unlocked = True
                    return

        # Helper: blit with alpha (without modifying originals)
        def _blit_with_alpha(src: pygame.Surface, dest_xy, a: int):
            if a >= 255:
                self.g.screen.blit(src, dest_xy)
            elif a > 0:
                tmp = src.copy()
                tmp.set_alpha(a)
                self.g.screen.blit(tmp, dest_xy)

        # ─────────────────────────────────────────────
        # 1) CHAIN (back)
        # ─────────────────────────────────────────────
        if chain:
            _blit_with_alpha(chain, chain_rect.topleft, alpha)

        # ─────────────────────────────────────────────
        # 2) SHACKLE (middle) — CLIPPED so it looks inserted
        # ─────────────────────────────────────────────
        # We clip the shackle to only draw the portion above a cutoff line.
        # Tune this cutoff if needed.
        #
        # "Mouth line" heuristic:
        #   Use lock_rect's top + some fraction of lock height.
        #   If your lock art differs, adjust the fraction.
        MOUTH_FRAC = 0.30  # 0.25–0.40 are common good ranges
        mouth_y = int(round(lock_rect.top + lock_rect.height * MOUTH_FRAC))

        if shackle and alpha > 0:
            # Compute intersection between shackle_rect and "allowed area above mouth_y"
            allowed = pygame.Rect(box.left, box.top, box.width, max(0, mouth_y - box.top))
            shackle_vis = shackle_rect.clip(allowed)

            if shackle_vis.width > 0 and shackle_vis.height > 0:
                # Build source rect in shackle's local coords
                src_rect = pygame.Rect(
                    shackle_vis.left - shackle_rect.left,
                    shackle_vis.top - shackle_rect.top,
                    shackle_vis.width,
                    shackle_vis.height,
                )

                tmp = shackle.subsurface(src_rect).copy()
                if alpha < 255:
                    tmp.set_alpha(alpha)
                self.g.screen.blit(tmp, shackle_vis.topleft)

        # ─────────────────────────────────────────────
        # 3) LOCK (front)
        # ─────────────────────────────────────────────
        if lock:
            _blit_with_alpha(lock, lock_rect.topleft, alpha)


    def draw_portrait_area(self):
        def get_quadrant_crop(sheet, wins):
            sheet_width, sheet_height = sheet.get_size()
            quad_width = sheet_width // 2
            quad_height = sheet_height // 2
            quad_x = (wins % 2) * quad_width
            quad_y = (wins // 2) * quad_height
            return sheet.subsurface(pygame.Rect(quad_x, quad_y, quad_width, quad_height))

        def scale_to_fit(img, max_w, max_h):
            ow, oh = img.get_size()
            scale = min(max_w / ow, max_h / oh)
            return pygame.transform.scale(img, (int(ow * scale), int(oh * scale)))

        PORTRAIT_GAP_Y = 218
        PORTRAIT_X_OFFSET = 50
        TARGET_SCALE_WIDTH = config.PORTRAIT_WIDTH - 20
        TARGET_SCALE_HEIGHT = config.HEIGHT - 20

        ai_crop = get_quadrant_crop(self.g.portrait_img, self.g.player_wins)
        ai_scaled = scale_to_fit(ai_crop, TARGET_SCALE_WIDTH, TARGET_SCALE_HEIGHT)
        ai_width, ai_height = ai_scaled.get_size()

        center_y = config.HEIGHT // 2 - ai_height // 2
        ai_target_y = center_y - PORTRAIT_GAP_Y if self.g.player_side == "white" else center_y + PORTRAIT_GAP_Y

        if self.g.enemy_portrait_y_actual is None:
            self.g.enemy_portrait_y_actual = ai_target_y
        else:
            self.g.enemy_portrait_y_actual += (ai_target_y - self.g.enemy_portrait_y_actual) * 0.2

        ai_x = (config.PORTRAIT_WIDTH - ai_width) // 2 + PORTRAIT_X_OFFSET
        self.g.screen.blit(ai_scaled, (ai_x, int(self.g.enemy_portrait_y_actual)))

        hero_crop = get_quadrant_crop(self.g.hero_portrait, self.g.current_state_wins)
        hero_scaled = scale_to_fit(hero_crop, TARGET_SCALE_WIDTH, TARGET_SCALE_HEIGHT)
        hero_width, hero_height = hero_scaled.get_size()

        hero_target_y = center_y + PORTRAIT_GAP_Y if self.g.player_side == "white" else center_y - PORTRAIT_GAP_Y

        if self.g.hero_portrait_y_actual is None:
            self.g.hero_portrait_y_actual = hero_target_y
        else:
            self.g.hero_portrait_y_actual += (hero_target_y - self.g.hero_portrait_y_actual) * 0.2

        hero_x = (config.PORTRAIT_WIDTH - hero_width) // 2 + PORTRAIT_X_OFFSET
        self.g.screen.blit(hero_scaled, (hero_x, int(self.g.hero_portrait_y_actual)))

        if self.enemy_dialog_text and self.enemy_dialog_alpha > 0:
            enemy_rect = pygame.Rect(ai_x, int(self.g.enemy_portrait_y_actual), ai_width, ai_height)
            self.render_enemy_dialog(self.enemy_dialog_text, enemy_rect)

        mouse_x, mouse_y = pygame.mouse.get_pos()
        hero_rect = pygame.Rect(hero_x, int(self.g.hero_portrait_y_actual), hero_width, hero_height)
        if hero_rect.collidepoint(mouse_x, mouse_y):
            self.g.show_quest_status = bool(getattr(self.g, "main_game_screen", False))
        else:
            self.g.show_quest_status = False

        if self.gstate_display_active:
            now = pygame.time.get_ticks()
            elapsed = now - self.gstate_display_start_time
            scale = 1.0

            if self.gstate_display_type != "check":
                if elapsed > self.gstate_display_max_time:
                    self.gstate_display_active = False
                    return
                if elapsed < self.gstate_display_anim_duration:
                    scale = elapsed / self.gstate_display_anim_duration
                else:
                    scale = 1.0
            else:
                if self.g.board.is_game_over():
                    self.gstate_display_active = False
                    return
                if not self.g.board.is_check():
                    fade_out_time = 300
                    fade_elapsed = elapsed
                    if fade_elapsed > fade_out_time:
                        self.gstate_display_active = False
                        return
                    scale = max(0.1, 1.0 - (fade_elapsed / fade_out_time))
                else:
                    if elapsed < self.gstate_display_anim_duration:
                        scale = elapsed / self.gstate_display_anim_duration
                    else:
                        scale = 1.0

            scale = max(0.1, min(1.0, scale))

            image = {
                "check": self.g.gamestate_image_check,
                "checkmate": self.g.gamestate_image_checkmate,
                "stalemate": self.g.gamestate_image_stalemate,
                "rage_quit": self.g.gamestate_image_ragequit,
            }.get(self.gstate_display_type)

            if image:
                ow, oh = image.get_size()
                max_w = config.PORTRAIT_WIDTH + 80
                base_scale = max_w / ow
                final_scale = base_scale * scale

                new_w = int(ow * final_scale)
                new_h = int(oh * final_scale)
                if new_w <= 0 or new_h <= 0:
                    return

                scaled = pygame.transform.smoothscale(image, (new_w, new_h))

                x = (config.PORTRAIT_WIDTH - new_w) // 2 + PORTRAIT_X_OFFSET
                y = (config.HEIGHT - new_h) // 2

                shadow = pygame.transform.smoothscale(image, (new_w, new_h))
                shadow.fill((0, 0, 0, 100), special_flags=pygame.BLEND_RGBA_MULT)
                self.g.screen.blit(shadow, (x + 2, y + 2))
                self.g.screen.blit(scaled, (x, y))

    def trigger_gamestate_display(self, state_name):
        priority_order = {
            "check": 1,
            "stalemate": 2,
            "rage_quit": 2,
            "checkmate": 3,
            "concede": 4
        }

        new_priority = priority_order.get(state_name, 0)
        current_priority = priority_order.get(self.gstate_display_type, 0)

        if self.gstate_display_active and new_priority < current_priority:
            return

        self.gstate_display_type = state_name
        self.gstate_display_active = True
        self.gstate_display_start_time = pygame.time.get_ticks()

    def render_enemy_dialog(self, dialog_text, portrait_rect):
        font = pygame.font.Font(None, 24)
        max_width = 300
        padding = 10
        tail_height = 70
        tail_width = 14
        corner_radius = 12
        overlap_ratio = 0.35

        words = dialog_text.split()
        lines = []
        current = ""
        for word in words:
            test = current + " " + word if current else word
            if font.size(test)[0] <= max_width:
                current = test
            else:
                lines.append(current)
                current = word
        lines.append(current)

        line_height = font.get_height()
        text_width = max(font.size(line)[0] for line in lines)
        bubble_width = text_width + 2 * padding
        bubble_height = line_height * len(lines) + 2 * padding
        total_height = bubble_height + tail_height

        is_above = portrait_rect.centery < config.HEIGHT // 2
        tail_tip_x = bubble_width // 2
        overlap_pixels = int(portrait_rect.height * overlap_ratio)

        bubble_surf = pygame.Surface((bubble_width, total_height), pygame.SRCALPHA)

        if is_above:
            body_rect = pygame.Rect(0, tail_height, bubble_width, bubble_height)
            triangle_tip = (tail_tip_x, 0)
            triangle_base_left = (tail_tip_x - tail_width // 2, tail_height)
            triangle_base_right = (tail_tip_x + tail_width // 2, tail_height)
        else:
            body_rect = pygame.Rect(0, 0, bubble_width, bubble_height)
            triangle_tip = (tail_tip_x, bubble_height + tail_height)
            triangle_base_left = (tail_tip_x - tail_width // 2, bubble_height)
            triangle_base_right = (tail_tip_x + tail_width // 2, bubble_height)

        pygame.draw.polygon(bubble_surf, (0, 0, 0), [triangle_tip, triangle_base_left, triangle_base_right])
        pygame.draw.rect(bubble_surf, (0, 0, 0), body_rect, border_radius=corner_radius)

        mask = pygame.mask.from_surface(bubble_surf)
        shrink_px = 4
        new_width = max(1, mask.get_size()[0] - shrink_px * 2)
        new_height = max(1, mask.get_size()[1] - shrink_px * 3)

        eroded_mask = mask.scale((new_width, new_height))
        interior = eroded_mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))

        offset_x = (mask.get_size()[0] - new_width) // 2
        if is_above:
            offset_y = (mask.get_size()[1] - new_height) // 2 + shrink_px - 1
        else:
            offset_y = (mask.get_size()[1] - new_height) // 2 - shrink_px
        bubble_surf.blit(interior, (offset_x, offset_y))

        for i, line in enumerate(lines):
            text_surf = font.render(line, True, (0, 0, 0))
            text_y = body_rect.top + padding + i * line_height
            bubble_surf.blit(text_surf, (padding, text_y))

        x = portrait_rect.centerx - bubble_width // 2
        y = portrait_rect.bottom - overlap_pixels if is_above else portrait_rect.top - total_height + overlap_pixels

        x = max(0, min(x, config.WIDTH - bubble_width))
        y = max(0, min(y, config.HEIGHT - total_height))

        self.g.screen.blit(bubble_surf, (x, y))

    def draw_feedback(self):
        SCROLL_SCALE = 0.4
        SCROLL_X_ANCHOR = 0.85
        SCROLL_Y_ANCHOR = 0.5
        SCROLL_Y_OFFSET = -20
        TEXT_WRAP_RATIO = 0.50
        TEXT_PADDING = 40

        def wrap_text_multiline(text, font, maxw):
            words = text.split()
            lines, current = [], ""
            for w in words:
                t = current + (" " if current else "") + w
                if font.size(t)[0] <= maxw:
                    current = t
                else:
                    lines.append(current)
                    current = w
            if current:
                lines.append(current)
            return lines

        if not (self.feedback_text and self.feedback_alpha > 0):
            return

        self.feedback_frame_counter += 1
        font = self.g.font
        img = self.g.spell_scroll
        w0, h0 = img.get_size()
        cap = 264
        mid0 = h0 - 2 * cap
        w = int(w0 * SCROLL_SCALE)
        cap_s = int(cap * SCROLL_SCALE)

        u = self.feedback_unfold_frames
        c = u

        if self.feedback_collapse_early:
            if not hasattr(self, "feedback_collapse_start_frame"):
                self.feedback_collapse_start_frame = self.feedback_frame_counter
            frame_delta = self.feedback_frame_counter - self.feedback_collapse_start_frame
            if frame_delta < c:
                unfold_ratio = 1.0 - 0.8 * (frame_delta / c)
            else:
                unfold_ratio = 0.2
                self.feedback_alpha = max(0, self.feedback_alpha - 5)
        else:
            if self.feedback_frame_counter < u:
                unfold_ratio = 0.2 + 0.8 * (self.feedback_frame_counter / u)
            else:
                unfold_ratio = 1.0

        wrapped = wrap_text_multiline(self.feedback_text, font, int(w * TEXT_WRAP_RATIO))
        lh = font.get_height()
        th = lh * len(wrapped)
        max_mid = max(1, th + TEXT_PADDING)
        cur_mid = int(max_mid * unfold_ratio)

        top = pygame.transform.smoothscale(img.subsurface((0, 0, w0, cap)).copy(), (w, cap_s))
        mid = img.subsurface((0, cap, w0, mid0)).copy()
        mid_s = pygame.transform.smoothscale(mid, (w, cur_mid))
        bot = pygame.transform.smoothscale(img.subsurface((0, h0 - cap, w0, cap)).copy(), (w, cap_s))

        ch = 2 * cap_s + cur_mid
        surf = pygame.Surface((w, ch), pygame.SRCALPHA)
        surf.blit(top, (0, 0))
        surf.blit(mid_s, (0, cap_s))
        surf.blit(bot, (0, cap_s + cur_mid))
        surf.set_alpha(self.feedback_alpha)

        rect = surf.get_rect()
        rect.centerx = int(config.WIDTH * SCROLL_X_ANCHOR)
        anchor_y = int(config.HEIGHT * SCROLL_Y_ANCHOR) + SCROLL_Y_OFFSET
        rect.y = anchor_y - rect.height if SCROLL_Y_ANCHOR == 1.0 else anchor_y - int(rect.height * SCROLL_Y_ANCHOR)

        offset = (2 * cap_s + max_mid) - ch
        rect.y += offset

        self.g.screen.blit(surf, rect)

        if unfold_ratio >= 0.99:
            start_y = rect.top + cap_s + (cur_mid - th) // 2
            cx = rect.left + rect.width // 2
            for i, line in enumerate(wrapped):
                ls = font.render(line, True, (0, 0, 0))
                ls.set_alpha(self.feedback_alpha)
                lr = ls.get_rect(center=(cx, start_y + i * lh))
                self.g.screen.blit(ls, lr)

        if self.feedback_alpha == 0:
            self.feedback_text = ""
            self.feedback_collapse_early = False
            if hasattr(self, "feedback_collapse_start_frame"):
                del self.feedback_collapse_start_frame

    def draw_quest_status_scroll(self):
        scroll = pygame.transform.smoothscale(self.g.quest_status_scroll, (1200, 800))
        sx = config.WIDTH - 10 - scroll.get_width()
        sy = config.HEIGHT - 10 - scroll.get_height()
        self.g.screen.blit(scroll, (sx, sy))

        margin_x = 303
        margin_y = 259
        text_x = sx + margin_x
        text_y = sy + margin_y
        usable_height = scroll.get_height() - 2 * margin_y

        seen_keys = set()
        quest_lines = []
        for key, val in self.g.quests.quest_status.items():
            if key not in seen_keys:
                quest_lines.append(f"{key}: {val}")
                seen_keys.add(key)

        base_font_size = 48
        line_spacing = base_font_size + 8
        while line_spacing * len(quest_lines) > usable_height and base_font_size > 20:
            base_font_size -= 2
            line_spacing = base_font_size + 6

        font = pygame.font.SysFont(None, base_font_size)

        for line in quest_lines:
            rendered = font.render(line, True, (40, 20, 0))
            self.g.screen.blit(rendered, (text_x, text_y))
            text_y += line_spacing

    def unlock_powers_area(self):
        """
        Trigger the unlock animation (shackle rises then fades out),
        and at the end sets self.g.powers_unlocked = True.

        Safe to call multiple times; it won't restart once unlocked.
        """
        if getattr(self.g, "powers_unlocked", False):
            return
        if self._powers_unlock_anim_active:
            return

        self._powers_unlock_anim_active = True
        self._powers_unlock_anim_start_ms = pygame.time.get_ticks()

    def reset_powers_unlock_animation(self):
        """
        Cancel any in-progress powers unlock animation without unlocking powers.
        Used when a new match starts and inventory should relock.
        """
        self._powers_unlock_anim_active = False
        self._powers_unlock_anim_start_ms = 0
        
    ########################################################################
    #                          ☰ MENU Helpers                              #
    ########################################################################
    def _draw_dim_overlay(self, alpha=160):
        if not hasattr(self, "_dim_overlay") or self._dim_overlay.get_size() != (config.WIDTH, config.HEIGHT):
            self._dim_overlay = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        self._dim_overlay.fill((0, 0, 0, max(0, min(255, alpha))))
        self.g.screen.blit(self._dim_overlay, (0, 0))

    def _draw_game_menu_overlay_if_open(self):
        if not hasattr(self.g, "menu"):
            return
        if not getattr(self.g.menu, "is_open", False):
            return

        self._draw_dim_overlay(alpha=170)

        if hasattr(self.g.menu, "draw"):
            self.g.menu.draw(self.g.screen)
        else:
            font = pygame.font.SysFont(None, 36)
            txt = font.render("MENU (no draw() found)", True, (255, 255, 255))
            self.g.screen.blit(txt, (config.WIDTH // 2 - txt.get_width() // 2, 100))
