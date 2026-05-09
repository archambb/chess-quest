# render_board.py
import pygame
import math
import chess
import config


class BoardRenderer:
    """
    Component: board drawing + board overlays.

    Mixed into RenderPipeline via inheritance:
        class RenderPipeline(BoardRenderer):
            ...
    """

    def draw_board(self, hovered_square=None, hover_alpha=128, opacity=200):
        board_w = board_h = 8 * config.SQUARE_SIZE
        board_surf = pygame.Surface((board_w, board_h), pygame.SRCALPHA)

        self._draw_checkerboard(board_surf)
        self._draw_square_effects(board_surf, hovered_square, hover_alpha)
        self._draw_power_effects(board_surf, hovered_square)
        self._draw_astral_hint(board_surf)
        self._draw_quadrant_effects()
        self._draw_screen_overlays()

        board_surf.set_alpha(opacity)
        self.g.screen.blit(board_surf, (self.g.board_origin_x, self.g.board_origin_y))

    # ─────────────────────────────────────────────────────────────
    # Core board
    # ─────────────────────────────────────────────────────────────
    def _draw_checkerboard(self, board_surf):
        colors = [self.g.WHITE, self.g.BLACK]
        for row in range(8):
            for col in range(8):
                color = colors[(row + col) % 2]
                rect = pygame.Rect(
                    col * config.SQUARE_SIZE,
                    row * config.SQUARE_SIZE,
                    config.SQUARE_SIZE,
                    config.SQUARE_SIZE
                )
                pygame.draw.rect(board_surf, color, rect)

    # ─────────────────────────────────────────────────────────────
    # Targeting region helpers
    # ─────────────────────────────────────────────────────────────
    def _is_on_player_side(self, sq: chess.Square) -> bool:
        """
        Player side = ranks 1-4 for white (rank 0..3),
                      ranks 5-8 for black (rank 4..7)
        Matches Powers.is_on_player_side().
        """
        r = chess.square_rank(sq)
        if self.g.player_side == "white":
            return r <= 3
        return r >= 4

    def _iter_player_side_squares(self):
        for sq in chess.SQUARES:
            if self._is_on_player_side(sq):
                yield sq

    # ─────────────────────────────────────────────────────────────
    # Flashy targeting helpers
    # ─────────────────────────────────────────────────────────────
    def _flash_target_square(
        self,
        board_surf: pygame.Surface,
        square: chess.Square,
        *,
        rgb=(255, 60, 60),
        t_ms: int | None = None,
        base_alpha: int = 40,
        pulse_alpha: int = 80,
        outline_w_min: int = 2,
        outline_w_max: int = 6,
        corner_len: int = 16,
        corner_w: int = 3,
        phase: float = 0.0,
    ):
        if t_ms is None:
            t_ms = pygame.time.get_ticks()

        S = config.SQUARE_SIZE
        col = chess.square_file(square)
        row = 7 - chess.square_rank(square)
        x = col * S
        y = row * S
        rect = pygame.Rect(x, y, S, S)

        # Pulse 0..1 (dual sine so it feels alive)
        p1 = (math.sin((t_ms * 0.010) + phase) + 1.0) * 0.5
        p2 = (math.sin((t_ms * 0.017) + phase * 1.7) + 1.0) * 0.5
        p = 0.65 * p1 + 0.35 * p2

        a = int(base_alpha + pulse_alpha * p)
        ow = int(outline_w_min + (outline_w_max - outline_w_min) * p)

        # Fill
        fill = pygame.Surface((S, S), pygame.SRCALPHA)
        fill.fill((rgb[0], rgb[1], rgb[2], a))
        board_surf.blit(fill, rect.topleft)

        # Outline
        outline = pygame.Surface((S, S), pygame.SRCALPHA)
        pygame.draw.rect(outline, (rgb[0], rgb[1], rgb[2], min(255, a + 90)), outline.get_rect(), ow)
        board_surf.blit(outline, rect.topleft)

        # Corner ticks
        ca = int(90 + 165 * p)
        tick = (rgb[0], rgb[1], rgb[2], ca)
        c = pygame.Surface((S, S), pygame.SRCALPHA)

        L = max(6, min(S // 2, corner_len))
        w = max(1, corner_w)

        # TL
        pygame.draw.line(c, tick, (2, 2), (2 + L, 2), w)
        pygame.draw.line(c, tick, (2, 2), (2, 2 + L), w)
        # TR
        pygame.draw.line(c, tick, (S - 3, 2), (S - 3 - L, 2), w)
        pygame.draw.line(c, tick, (S - 3, 2), (S - 3, 2 + L), w)
        # BL
        pygame.draw.line(c, tick, (2, S - 3), (2 + L, S - 3), w)
        pygame.draw.line(c, tick, (2, S - 3), (2, S - 3 - L), w)
        # BR
        pygame.draw.line(c, tick, (S - 3, S - 3), (S - 3 - L, S - 3), w)
        pygame.draw.line(c, tick, (S - 3, S - 3), (S - 3, S - 3 - L), w)

        board_surf.blit(c, rect.topleft)

    def _flash_targets(
        self,
        board_surf: pygame.Surface,
        squares,
        *,
        rgb,
        t_ms: int,
        base_alpha=18,
        pulse_alpha=90,
        outline_w_min=2,
        outline_w_max=6,
        corner_len=16,
        corner_w=3,
        phase_seed=0.0,
    ):
        if not squares:
            return
        for sq in squares:
            c = chess.square_file(sq)
            r = 7 - chess.square_rank(sq)
            phase = phase_seed + (c * 0.45 + r * 0.25)
            self._flash_target_square(
                board_surf,
                sq,
                rgb=rgb,
                t_ms=t_ms,
                base_alpha=base_alpha,
                pulse_alpha=pulse_alpha,
                outline_w_min=outline_w_min,
                outline_w_max=outline_w_max,
                corner_len=corner_len,
                corner_w=corner_w,
                phase=phase,
            )

    # ─────────────────────────────────────────────────────────────
    # Static overlays (selection, hovered, status squares, etc.)
    # ─────────────────────────────────────────────────────────────
    def _draw_square_effects(self, board_surf, hovered_square, hover_alpha):
        t_ms = pygame.time.get_ticks()
        sel = getattr(self.g, "selected_power", None)

        # Pre-calc swap targets (second-click targets)
        swap_targets = set()
        if sel == "swaps":
            swap_targets_raw = set(getattr(self.g, "swap_highlight_squares", set()) or set())
            player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
            enemy_color = not player_color

            # 2nd swap click targets: enemy pieces only, and still player-side-only
            swap_targets = set()
            for sq in swap_targets_raw:
                if not self._is_on_player_side(sq):
                    continue
                p = self.g.board.piece_at(sq)
                if not p:
                    continue
                if p.piece_type == chess.KING:
                    continue
                if p.color != enemy_color:
                    continue
                swap_targets.add(sq)

        for row in range(8):
            for col in range(8):
                square = chess.square(col, 7 - row)
                rect = pygame.Rect(
                    col * config.SQUARE_SIZE,
                    row * config.SQUARE_SIZE,
                    config.SQUARE_SIZE,
                    config.SQUARE_SIZE
                )
                color = self.g.WHITE if (row + col) % 2 == 0 else self.g.BLACK

                if square in self.g.possible_moves:
                    overlay = pygame.Surface((config.SQUARE_SIZE, config.SQUARE_SIZE), pygame.SRCALPHA)
                    overlay.fill((255, 255, 0, 100))
                    board_surf.blit(overlay, rect.topleft)

                if square == self.g.selected_square:
                    highlight = self.g.LIGHT_BLUE if color == self.g.WHITE else self.g.DARKER_BLUE
                    pygame.draw.rect(board_surf, highlight, rect)

                # Swap: first picked square
                if square == getattr(self.g, "swap_selected_square", None):
                    pink = pygame.Surface((config.SQUARE_SIZE, config.SQUARE_SIZE), pygame.SRCALPHA)
                    pink.fill((255, 105, 180, 110))
                    board_surf.blit(pink, rect.topleft)

                    self._flash_target_square(
                        board_surf,
                        square,
                        rgb=(255, 105, 180),
                        t_ms=t_ms,
                        base_alpha=10,
                        pulse_alpha=70,
                        outline_w_min=3,
                        outline_w_max=7,
                        corner_len=18,
                        corner_w=3,
                        phase=col * 0.7 + row * 0.4,
                    )

                # Swap: second-click valid targets (FLASHY teal)
                if swap_targets and square in swap_targets:
                    phase = (col * 0.55 + row * 0.35)
                    self._flash_target_square(
                        board_surf,
                        square,
                        rgb=(0, 255, 220),
                        t_ms=t_ms,
                        base_alpha=18,
                        pulse_alpha=90,
                        outline_w_min=2,
                        outline_w_max=6,
                        corner_len=16,
                        corner_w=3,
                        phase=phase,
                    )

                if square == hovered_square:
                    hover = pygame.Surface((config.SQUARE_SIZE, config.SQUARE_SIZE), pygame.SRCALPHA)
                    outline = (*self.g.BLUE_OUTLINE, hover_alpha)
                    pygame.draw.rect(hover, outline, hover.get_rect(), 3)
                    board_surf.blit(hover, rect.topleft)

                if square in self.g.shielded_squares:
                    shield = pygame.Surface((config.SQUARE_SIZE, config.SQUARE_SIZE), pygame.SRCALPHA)
                    shield.fill((128, 128, 128, 100))
                    board_surf.blit(shield, rect.topleft)

                if square in self.g.frozen_squares:
                    frozen = pygame.Surface((config.SQUARE_SIZE, config.SQUARE_SIZE), pygame.SRCALPHA)
                    frozen.fill((0, 0, 255, 100))
                    board_surf.blit(frozen, rect.topleft)

                if getattr(self.g, "magnet_square", None) == square:
                    board_surf.blit(self.g.power_icons["magnets"], rect.topleft)

        # Gear targeting highlights (Ice Pick / Hatchet)
        equip = getattr(self.g, "gear", None)
        if equip and getattr(equip, "pending_action", None):
            if equip.pending_action == "ice_pick_target":
                for sq in self.g.frozen_squares:
                    self._draw_highlight(board_surf, sq, color=(0, 200, 255, 120))
            elif equip.pending_action == "hatchet_target":
                for sq in self.g.shielded_squares:
                    self._draw_highlight(board_surf, sq, color=(255, 200, 0, 120))

        # In BoardRenderer._draw_square_effects (near the end), after normal overlays:

        # Spell targeting highlight (covers selected_spell + spell-powers)
        spell_targets = getattr(self.g, "spell_target_squares", []) or []
        spell_rgb = getattr(self.g, "spell_target_rgb", None)
        if spell_targets and spell_rgb:
            # also enforce player-side-only as a final safety net
            filtered = [sq for sq in spell_targets if self.g.powers.is_on_player_side(sq)]
            self._flash_targets(
                board_surf,
                filtered,
                rgb=spell_rgb,
                t_ms=t_ms,
                base_alpha=16,
                pulse_alpha=95,
                outline_w_min=2,
                outline_w_max=7,
                corner_len=18,
                corner_w=3,
                phase_seed=7.7,
            )

        if getattr(self.g, "wall_of_flame_active", False) and hovered_square is not None:
            self._draw_wall_of_flame_hover_row(board_surf, hovered_square, t_ms)


    def _draw_highlight(self, board_surf, square, color=(0, 200, 255, 120)):
        S = config.SQUARE_SIZE
        col = chess.square_file(square)
        row = 7 - chess.square_rank(square)

        overlay = pygame.Surface((S, S), pygame.SRCALPHA)
        overlay.fill(color)
        board_surf.blit(overlay, (col * S, row * S))

    # ─────────────────────────────────────────────────────────────
    # Hints / special overlays
    # ─────────────────────────────────────────────────────────────
    def _draw_wall_of_flame_hover_row(self, board_surf, hovered_square, t_ms):
        rank = chess.square_rank(hovered_square)
        palette = [
            (255, 40, 0),
            (255, 120, 0),
            (255, 220, 0),
        ]

        for file in range(8):
            square = chess.square(file, rank)
            rgb = palette[((t_ms // 120) + file) % len(palette)]
            self._flash_target_square(
                board_surf,
                square,
                rgb=rgb,
                t_ms=t_ms,
                base_alpha=28,
                pulse_alpha=125,
                outline_w_min=3,
                outline_w_max=8,
                corner_len=20,
                corner_w=4,
                phase=file * 0.55,
            )

    def _draw_astral_hint(self, board_surf):
        try:
            stage_id = self.g.world.world_data[self.g.world.player_pos]["stage_id"]
        except Exception:
            stage_id = None
        if stage_id != 10:
            return

        hint = getattr(self.g, "astral_best_hint", None)
        if not hint:
            return

        S = config.SQUARE_SIZE
        (from_sq, to_sq) = hint

        def blit_purple(sq, alpha=130):
            col, row = chess.square_file(sq), 7 - chess.square_rank(sq)
            r = pygame.Rect(col * S, row * S, S, S)
            overlay = pygame.Surface((S, S), pygame.SRCALPHA)
            overlay.fill((150, 0, 200, alpha))
            board_surf.blit(overlay, r.topleft)

        blit_purple(from_sq, 110)
        blit_purple(to_sq,   160)

    def _draw_compass_hint(self, board_surf):
        hint = getattr(self.g, "compass_hint", None)
        if not hint:
            return

        S = config.SQUARE_SIZE
        from_sq, to_sq = hint

        def blit_purple(sq, alpha=130):
            col = chess.square_file(sq)
            row = 7 - chess.square_rank(sq)
            r = pygame.Rect(col * S, row * S, S, S)
            overlay = pygame.Surface((S, S), pygame.SRCALPHA)
            overlay.fill((150, 0, 200, alpha))
            board_surf.blit(overlay, r.topleft)

        blit_purple(from_sq, 110)
        blit_purple(to_sq,   160)

    # ─────────────────────────────────────────────────────────────
    # POWER TARGET OVERLAYS (POWERS ONLY — player-side-only)
    # ─────────────────────────────────────────────────────────────
    def _draw_power_effects(self, board_surf, hovered_square):
        t_ms = pygame.time.get_ticks()
        sel = getattr(self.g, "selected_power", None)

        powerups = getattr(self.g, "powerups", {}) or {}
        if sel not in powerups:
            return

        player_color = chess.WHITE if self.g.player_side == "white" else chess.BLACK
        enemy_color = not player_color

        # Optional universal hook — BUT we enforce player-side-only here.
        pts = getattr(self.g, "power_target_squares", None)
        if isinstance(pts, dict) and sel in pts and pts[sel]:
            color_map = getattr(self.g, "power_target_colors", {}) or {}
            rgb = color_map.get(sel, (255, 255, 255))
            filtered = [sq for sq in pts[sel] if self._is_on_player_side(sq)]
            self._flash_targets(board_surf, filtered, rgb=rgb, t_ms=t_ms, phase_seed=1.2)
            return

        # Convenience: restrict EVERYTHING to player half (your request)
        player_half = list(self._iter_player_side_squares())

        # ─────────────────────────────────────────────
        # BOMBS: player-half + occupied only (as requested)
        # ─────────────────────────────────────────────
        if sel == "bombs":
            only_occupied = True  # as you set

            targets = []
            for sq in player_half:
                p = self.g.board.piece_at(sq)
                if only_occupied and p is None:
                    continue
                # ✅ Bombs can ONLY target pawns
                if not p or p.piece_type != chess.PAWN:
                    continue
                targets.append(sq)

            self._flash_targets(
                board_surf, targets,
                rgb=(255, 60, 60),
                t_ms=t_ms,
                base_alpha=18,
                pulse_alpha=95,
                outline_w_min=2,
                outline_w_max=6,
                corner_len=16,
                corner_w=3,
                phase_seed=0.0,
            )
            return


        # ─────────────────────────────────────────────
        # FREEZES: player-half + enemy pieces only + not king
        # ─────────────────────────────────────────────
        if sel == "freezes":
            targets = []
            for sq in player_half:
                p = self.g.board.piece_at(sq)
                if not p:
                    continue
                if p.piece_type == chess.KING:
                    continue
                if p.color != enemy_color:
                    continue
                targets.append(sq)

            self._flash_targets(
                board_surf, targets,
                rgb=(0, 180, 255),
                t_ms=t_ms,
                base_alpha=14,
                pulse_alpha=90,
                outline_w_min=2,
                outline_w_max=6,
                corner_len=16,
                corner_w=3,
                phase_seed=2.0,
            )
            return


        # ─────────────────────────────────────────────
        # SHIELDS + ADVANCED SHIELDS: player-half (meaningful targets = occupied only)
        # ─────────────────────────────────────────────
        if sel in ("shields", "advanced_shields"):
            targets = []
            for sq in player_half:
                p = self.g.board.piece_at(sq)
                if not p:
                    continue
                if p.piece_type == chess.KING:
                    continue
                if p.color != player_color:
                    continue
                targets.append(sq)

            self._flash_targets(
                board_surf, targets,
                rgb=(200, 200, 200),
                t_ms=t_ms,
                base_alpha=10,
                pulse_alpha=80,
                outline_w_min=2,
                outline_w_max=6,
                corner_len=16,
                corner_w=3,
                phase_seed=4.1,
            )
            return


        # ─────────────────────────────────────────────
        # PROMOTIONS: player-half + your pawns only
        # ─────────────────────────────────────────────
        if sel == "promotions":
            targets = []
            for sq in player_half:
                p = self.g.board.piece_at(sq)
                if not p:
                    continue
                if p.color != player_color:
                    continue
                if p.piece_type != chess.PAWN:
                    continue
                targets.append(sq)

            self._flash_targets(
                board_surf, targets,
                rgb=(140, 0, 255),
                t_ms=t_ms,
                base_alpha=12,
                pulse_alpha=90,
                outline_w_min=2,
                outline_w_max=6,
                corner_len=16,
                corner_w=3,
                phase_seed=5.2,
            )
            return

        # ─────────────────────────────────────────────
        # MAGNETS: player-half + ANY square (occupied or empty)
        # ─────────────────────────────────────────────
        if sel == "magnets":
            targets = list(player_half)
            self._flash_targets(
                board_surf, targets,
                rgb=(255, 120, 0),
                t_ms=t_ms,
                base_alpha=10,
                pulse_alpha=85,
                outline_w_min=2,
                outline_w_max=6,
                corner_len=16,
                corner_w=3,
                phase_seed=1.0,
            )
            return

        # ─────────────────────────────────────────────
        # SWAPS: FIRST PICK targets (player-half + occupied)
        # Second-pick targets are handled in _draw_square_effects via swap_highlight_squares
        # ─────────────────────────────────────────────
        if sel == "swaps":
            if getattr(self.g, "swap_selected_square", None) is None:
                targets = []
                for sq in player_half:
                    p = self.g.board.piece_at(sq)
                    if not p:
                        continue
                    if p.piece_type == chess.KING:
                        continue
                    if p.color != player_color:
                        continue
                    targets.append(sq)

                self._flash_targets(
                    board_surf, targets,
                    rgb=(255, 105, 180),  # pink
                    t_ms=t_ms,
                    base_alpha=10,
                    pulse_alpha=85,
                    outline_w_min=2,
                    outline_w_max=6,
                    corner_len=16,
                    corner_w=3,
                    phase_seed=3.4,
                )
            return


        # ─────────────────────────────────────────────
        # Other powers (time_warps, etc): player-half (generic highlight)
        # ─────────────────────────────────────────────
        # This gives you “something” immediately and keeps the rule:
        # EVERYTHING is player-half-only.
        targets = list(player_half)
        self._flash_targets(
            board_surf, targets,
            rgb=(255, 255, 255),
            t_ms=t_ms,
            base_alpha=6,
            pulse_alpha=55,
            outline_w_min=1,
            outline_w_max=4,
            corner_len=12,
            corner_w=2,
            phase_seed=9.0,
        )

    # ─────────────────────────────────────────────────────────────
    # Quadrant / screen overlays (unchanged)
    # ─────────────────────────────────────────────────────────────
    def _draw_quadrant_effects(self):
        if self.g.meteor_active and self.g.meteor_quadrant is None:
            S = config.SQUARE_SIZE
            tick = (pygame.time.get_ticks() // 300) % 2
            colors = [
                [(255, 0, 0, 80), (128, 0, 0, 80)],
                [(0, 255, 0, 80), (0, 128, 0, 80)],
                [(0, 255, 255, 80), (0, 128, 128, 80)],
                [(255, 0, 255, 80), (128, 0, 128, 80)]
            ]
            quads = [(0, 0), (4, 0), (0, 4), (4, 4)]

            for i, (qx, qy) in enumerate(quads):
                quad = pygame.Surface((4 * S, 4 * S), pygame.SRCALPHA)
                quad.fill(colors[i][tick])
                self.g.screen.blit(quad, (
                    self.g.board_origin_x + qx * S,
                    self.g.board_origin_y + qy * S
                ))

    def _draw_screen_overlays(self):
        S = config.SQUARE_SIZE

        if self.g.orb_highlight_squares:
            if self.g.orb_pulse_direction == 1:
                self.g.orb_pulse_alpha += 6
                if self.g.orb_pulse_alpha >= 248:
                    self.g.orb_pulse_direction = -1
            else:
                self.g.orb_pulse_alpha -= 6
                if self.g.orb_pulse_alpha <= 40:
                    self.g.orb_pulse_direction = 1

            for sq in self.g.orb_highlight_squares:
                col, row = chess.square_file(sq), 7 - chess.square_rank(sq)
                x = self.g.board_origin_x + col * S
                y = self.g.board_origin_y + row * S
                overlay = pygame.Surface((S, S), pygame.SRCALPHA)
                overlay.fill((255, 0, 0, self.g.orb_pulse_alpha))
                self.g.screen.blit(overlay, (x, y))

        if self.g.greed_active:
            pulse = 60 + int(60 * math.sin(pygame.time.get_ticks() / 180))
            glow = pygame.Surface((S, S), pygame.SRCALPHA)
            glow.fill((255, 215, 0, pulse))
            for sq in self.g.gold_pieces:
                col, row = chess.square_file(sq), 7 - chess.square_rank(sq)
                x = self.g.board_origin_x + col * S
                y = self.g.board_origin_y + row * S
                self.g.screen.blit(glow, (x, y))
