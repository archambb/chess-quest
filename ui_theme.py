import math
import pygame

PALETTE = {
    "gold": (160, 140, 0),
    "bronze": (120, 80, 40),

    "hover_dark": (120, 0, 0),
    "hover_bright": (255, 0, 0),

    "disabled_dark": (70, 70, 80),
    "disabled_bright": (120, 120, 130),

    "cyan_frame": (0, 200, 255),
    "panel_bg": (22, 24, 30),
    "panel_border": (110, 120, 150),
}

def lerp_rgb(a, b, t):
    return (
        int(a[0] * (1 - t) + b[0] * t),
        int(a[1] * (1 - t) + b[1] * t),
        int(a[2] * (1 - t) + b[2] * t),
    )

def draw_glimmer_text(
    surf: pygame.Surface,
    text: str,
    x: int,
    y: int,
    *,
    font: pygame.font.Font,
    timer: float,
    mode: str = "normal",   # normal | hover | disabled | selected
    phase_step: float = 0.30,
    speed: float = 0.20,
):
    if mode == "hover" or mode == "selected":
        dark, bright = PALETTE["hover_dark"], PALETTE["hover_bright"]
    elif mode == "disabled":
        dark, bright = PALETTE["disabled_dark"], PALETTE["disabled_bright"]
    else:
        dark, bright = PALETTE["bronze"], PALETTE["gold"]

    cx = x
    for idx, ch in enumerate(text):
        phase = idx * phase_step
        t = (math.sin(timer * speed + phase) + 1) / 2
        color = lerp_rgb(dark, bright, t)
        glyph = font.render(ch, True, color)
        surf.blit(glyph, (cx, y))
        cx += glyph.get_width()

    return cx  # handy if you want to append text after
