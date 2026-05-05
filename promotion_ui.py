from __future__ import annotations

import chess
import pygame

import config


PROMOTION_OPTIONS = (
    (chess.QUEEN, "Queen", "Q"),
    (chess.ROOK, "Rook", "R"),
    (chess.BISHOP, "Bishop", "B"),
    (chess.KNIGHT, "Knight", "N"),
)


def choose_promotion_piece_type(game, color: chess.Color) -> chess.PieceType | None:
    """
    Blocking promotion picker for normal player moves.

    Returns a python-chess piece type. Returns None only if the window close event
    is received, so the main loop can handle the reposted QUIT event.
    """
    clock = pygame.time.Clock()
    font = pygame.font.SysFont(None, 30)
    small_font = pygame.font.SysFont(None, 22)
    title_font = pygame.font.SysFont(None, 42)

    option_rects = _build_option_rects(game)
    player_symbol_is_upper = (color == chess.WHITE)

    while True:
        mouse_pos = pygame.mouse.get_pos()

        renderer = getattr(game, "renderer", None)
        if renderer:
            renderer.draw("main", hovered_square=None, hovered_power=None, flip=False)
        else:
            game.screen.fill((20, 20, 20))

        _draw_overlay(
            game,
            option_rects,
            mouse_pos,
            player_symbol_is_upper,
            font,
            small_font,
            title_font,
        )
        pygame.display.flip()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.event.post(event)
                return None

            if event.type == pygame.MOUSEBUTTONDOWN and getattr(event, "button", 1) == 1:
                for piece_type, _, _, rect in option_rects:
                    if rect.collidepoint(event.pos):
                        return piece_type

            if event.type == pygame.KEYDOWN:
                key_map = {
                    pygame.K_q: chess.QUEEN,
                    pygame.K_r: chess.ROOK,
                    pygame.K_b: chess.BISHOP,
                    pygame.K_n: chess.KNIGHT,
                }
                if event.key in key_map:
                    return key_map[event.key]

        clock.tick(config.FPS)


def _build_option_rects(game):
    button_w = 150
    button_h = 180
    gap = 18
    total_w = len(PROMOTION_OPTIONS) * button_w + (len(PROMOTION_OPTIONS) - 1) * gap
    start_x = (game.screen.get_width() - total_w) // 2
    y = game.screen.get_height() // 2 - button_h // 2 + 35

    rects = []
    for idx, (piece_type, label, symbol) in enumerate(PROMOTION_OPTIONS):
        rect = pygame.Rect(start_x + idx * (button_w + gap), y, button_w, button_h)
        rects.append((piece_type, label, symbol, rect))
    return rects


def _draw_overlay(
    game,
    option_rects,
    mouse_pos,
    player_symbol_is_upper,
    font,
    small_font,
    title_font,
):
    screen = game.screen
    dim = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
    dim.fill((0, 0, 0, 150))
    screen.blit(dim, (0, 0))

    panel_rect = pygame.Rect(0, 0, 760, 330)
    panel_rect.center = (screen.get_width() // 2, screen.get_height() // 2 + 30)
    pygame.draw.rect(screen, (34, 24, 20), panel_rect, border_radius=8)
    pygame.draw.rect(screen, (214, 168, 80), panel_rect, width=3, border_radius=8)

    title = title_font.render("Choose Promotion", True, (255, 235, 190))
    title_rect = title.get_rect(center=(panel_rect.centerx, panel_rect.y + 45))
    screen.blit(title, title_rect)

    hint = small_font.render("Select a piece to complete the pawn move.", True, (230, 210, 170))
    hint_rect = hint.get_rect(center=(panel_rect.centerx, panel_rect.y + 78))
    screen.blit(hint, hint_rect)

    for _, label, symbol, rect in option_rects:
        hovered = rect.collidepoint(mouse_pos)
        fill = (86, 54, 34) if hovered else (58, 40, 32)
        outline = (255, 205, 95) if hovered else (170, 125, 62)
        pygame.draw.rect(screen, fill, rect, border_radius=8)
        pygame.draw.rect(screen, outline, rect, width=2, border_radius=8)

        draw_symbol = symbol if player_symbol_is_upper else symbol.lower()
        piece_image = getattr(game, "PIECE_IMAGES", {}).get(draw_symbol)
        if piece_image:
            image = _fit_surface(piece_image, 98, 112)
            image_rect = image.get_rect(center=(rect.centerx, rect.y + 76))
            screen.blit(image, image_rect)

        label_surface = font.render(label, True, (255, 242, 212))
        label_rect = label_surface.get_rect(center=(rect.centerx, rect.bottom - 30))
        screen.blit(label_surface, label_rect)


def _fit_surface(surface: pygame.Surface, max_w: int, max_h: int) -> pygame.Surface:
    src_w, src_h = surface.get_size()
    if src_w <= 0 or src_h <= 0:
        return surface
    scale = min(max_w / src_w, max_h / src_h)
    size = (max(1, int(src_w * scale)), max(1, int(src_h * scale)))
    return pygame.transform.smoothscale(surface, size)
