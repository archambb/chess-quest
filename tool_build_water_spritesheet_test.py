#!/usr/bin/env python3
"""
Water sprite-sheet generator (no input PNG required).

- Generates procedural calm-water pixel art
- 8-frame perfect loop via integer rolls + subtle shimmer
- Emits multiple variants to ./water_test/
- Produces:
   • <name>_8x8_sheet_<size>px.png   (64 frames, 8x8 grid, no margins)
   • <name>_8strip_<size>px.png      (8 frames in a row)
   • frames/<name>_<idx>.png         (8 individual frames)

Deps: numpy, Pillow
    pip install numpy pillow
"""

from pathlib import Path
from typing import List, Tuple, Dict
import math
import numpy as np
from PIL import Image

# =========================
# Configurable variants
# =========================
VARIANTS: List[Dict] = [
    # name, output frame size, base tiny tile, palette, shimmer, motion, seed
    {
        "name": "calm_blue_64",
        "frame_size": 64,
        "base_tile": 16,
        "palette": "blue_magic",
        "shimmer_amp": 0.06,
        "shimmer_cycles": 1,
        "shift_px": (1, 1),
        "cycles": (1, 2),
        "seed": 1337,
    },
    {
        "name": "teal_natural_64",
        "frame_size": 64,
        "base_tile": 16,
        "palette": "teal_natural",
        "shimmer_amp": 0.05,
        "shimmer_cycles": 2,
        "shift_px": (1, 1),
        "cycles": (1, 3),
        "seed": 2025,
    },
    {
        "name": "murky_river_64",
        "frame_size": 64,
        "base_tile": 16,
        "palette": "murky",
        "shimmer_amp": 0.04,
        "shimmer_cycles": 2,
        "shift_px": (1, 0),  # mostly lateral drift
        "cycles": (1, 2),
        "seed": 777,
    },
    {
        "name": "crystal_cyan_48",
        "frame_size": 48,
        "base_tile": 12,
        "palette": "crystal",
        "shimmer_amp": 0.07,
        "shimmer_cycles": 2,
        "shift_px": (1, 1),
        "cycles": (2, 3),
        "seed": 4242,
    },
    {
        "name": "deep_blue_32",
        "frame_size": 32,
        "base_tile": 8,
        "palette": "deep_blue",
        "shimmer_amp": 0.05,
        "shimmer_cycles": 1,
        "shift_px": (1, 1),
        "cycles": (1, 2),
        "seed": 991,
    },
]

# Global animation constants
N_FRAMES = 8          # 8-frame loop
GRID_COLS = 8         # 8x8 = 64-frame sheet, repeats the 8 unique frames
GRID_ROWS = 8

# =========================
# Palette definitions
# =========================
def get_palette(name: str) -> List[Tuple[int, int, int, int]]:
    """
    Small, handpicked pixel-art palettes, darkest -> lightest.
    Alpha is applied later; keep RGB opaque here.
    """
    if name == "blue_magic":
        return [
            (10, 24, 48, 255),
            (18, 54, 105, 255),
            (28, 92, 160, 255),
            (46, 132, 206, 255),
            (120, 180, 240, 255),
        ]
    if name == "teal_natural":
        return [
            (8, 28, 30, 255),
            (12, 66, 68, 255),
            (20, 110, 112, 255),
            (40, 150, 150, 255),
            (120, 210, 200, 255),
        ]
    if name == "murky":
        return [
            (18, 24, 14, 255),
            (30, 44, 24, 255),
            (46, 66, 36, 255),
            (70, 96, 52, 255),
            (110, 136, 80, 255),
        ]
    if name == "crystal":
        return [
            (12, 50, 82, 255),
            (18, 92, 122, 255),
            (36, 140, 168, 255),
            (120, 210, 232, 255),
            (200, 245, 255, 255),
        ]
    if name == "deep_blue":
        return [
            (6, 14, 34, 255),
            (12, 34, 74, 255),
            (20, 64, 122, 255),
            (32, 96, 170, 255),
            (80, 140, 210, 255),
        ]
    # fallback
    return [(0, 0, 0, 255), (255, 255, 255, 255)]

# =========================
# Helpers
# =========================
def box_blur_periodic(a: np.ndarray, passes: int = 1) -> np.ndarray:
    """
    Super-cheap smooth noise: periodic box blur using wraparound.
    Keeps it tileable.
    """
    out = a.copy()
    for _ in range(passes):
        # 4-neighbor average + self (simple 5-tap kernel)
        out = (
            out
            + np.roll(out, 1, axis=0)
            + np.roll(out, -1, axis=0)
            + np.roll(out, 1, axis=1)
            + np.roll(out, -1, axis=1)
        ) / 5.0
    return out

def make_height_tile(tile_size: int, seed: int) -> np.ndarray:
    """
    Creates a tiny periodic heightmap, then normalizes to 0..1.
    """
    rng = np.random.default_rng(seed)
    base = rng.random((tile_size, tile_size)).astype(np.float32)
    # Smooth a few times to avoid TV static
    h = box_blur_periodic(base, passes=3)
    # Slight “cells” look by combining different radii
    h2 = box_blur_periodic(h, passes=2)
    h = 0.6 * h2 + 0.4 * h
    # Normalize
    h -= h.min()
    if h.max() > 1e-8:
        h /= h.max()
    return h

def upscale_nearest(a: np.ndarray, out_size: int) -> np.ndarray:
    """
    Upscale tiny heightmap to out_size×out_size using nearest neighbor.
    """
    h, w = a.shape
    img = Image.fromarray((a * 255).astype(np.uint8), mode="L")
    img = img.resize((out_size, out_size), Image.NEAREST)
    return np.array(img, dtype=np.uint8) / 255.0

def palette_map(height: np.ndarray, palette: List[Tuple[int, int, int, int]]) -> np.ndarray:
    """
    Map 0..1 height to a discrete palette (returns HxWx4 uint8).
    """
    h = height.clip(0, 1)
    idx = (h * (len(palette) - 1) + 1e-6).astype(int)
    pal = np.array(palette, dtype=np.uint8)
    out = pal[idx]
    return out  # RGBA uint8, alpha placeholder for now

def integer_roll_rgba(arr: np.ndarray, dx: int, dy: int) -> np.ndarray:
    r = np.roll(arr, dy, axis=0)
    r = np.roll(r, dx, axis=1)
    return r

def apply_shimmer_rgba(arr: np.ndarray, t_norm: float, amp: float, cycles: int) -> np.ndarray:
    """
    Subtle brightness oscillation with separable cosine mask; alpha preserved.
    Only modulates where alpha > 0 (we’ll set a uniform alpha later).
    """
    if amp <= 0:
        return arr
    h, w, _ = arr.shape
    y = np.linspace(0, 1, h, endpoint=False)
    x = np.linspace(0, 1, w, endpoint=False)
    xx, yy = np.meshgrid(x, y)
    phase = 2.0 * math.pi * (cycles * t_norm)
    mask = (np.cos(2 * math.pi * 3 * xx + phase) * np.cos(2 * math.pi * 2 * yy + phase)).astype(np.float32)
    amt = (1.0 + amp * mask).astype(np.float32)

    out = arr.copy().astype(np.float32)
    rgb = out[..., :3]
    a = out[..., 3:4] / 255.0
    rgb = np.where(a > 0, (rgb * amt), rgb)
    out[..., :3] = np.clip(rgb, 0, 255)
    return out.astype(np.uint8)

def make_frames_from_height(
    height_big: np.ndarray,
    palette: List[Tuple[int, int, int, int]],
    n_frames: int,
    shift_px: Tuple[int, int],
    cycles: Tuple[int, int],
    shimmer_amp: float,
    shimmer_cycles: int,
    alpha_value: int = 220,
) -> List[np.ndarray]:
    """
    Build 8 unique frames by blending two integer-rolled layers; perfect 8-frame loop.
    """
    base_rgba = palette_map(height_big, palette)
    # Set uniform alpha (transparent background outside water isn’t needed for a full-tile overlay,
    # but we keep alpha < 255 so it feels like an overlay; adjust if you want fully opaque)
    base_rgba[..., 3] = alpha_value

    frames = []
    sx, sy = shift_px
    c1, c2 = cycles
    for i in range(n_frames):
        t = i / n_frames
        dx1 = int(round(sx * math.sin(2 * math.pi * c1 * t)))
        dy1 = int(round(sy * math.cos(2 * math.pi * c1 * t)))
        dx2 = int(round(sx * math.sin(2 * math.pi * c2 * t + math.pi / 3)))
        dy2 = int(round(sy * math.cos(2 * math.pi * c2 * t + math.pi / 5)))

        L1 = integer_roll_rgba(base_rgba, dx1, dy1).astype(np.float32)
        L2 = integer_roll_rgba(base_rgba, dx2, dy2).astype(np.float32)

        # Simple average keeps palette stable; alpha preserved by max
        alpha = np.maximum(L1[..., 3], L2[..., 3])
        rgb = (L1[..., :3] + L2[..., :3]) / 2.0

        frame = np.zeros_like(base_rgba, dtype=np.uint8)
        frame[..., :3] = np.clip(rgb, 0, 255).astype(np.uint8)
        frame[..., 3] = alpha.astype(np.uint8)

        frame = apply_shimmer_rgba(frame, t, shimmer_amp, shimmer_cycles)
        frames.append(frame)
    return frames

def save_strip(frames: List[np.ndarray], out_path: Path):
    h, w, _ = frames[0].shape
    strip = np.zeros((h, w * len(frames), 4), dtype=np.uint8)
    for i, fr in enumerate(frames):
        strip[:, i * w:(i + 1) * w, :] = fr
    Image.fromarray(strip, mode="RGBA").save(out_path, compress_level=9)

def save_grid_8x8(frames: List[np.ndarray], out_path: Path):
    """
    Make a 64-frame sheet: repeats the 8-frame loop 8 times.
    Exact size, no margins: (8*W) x (8*H).
    """
    h, w, _ = frames[0].shape
    sheet = np.zeros((8 * h, 8 * w, 4), dtype=np.uint8)
    idx = 0
    for r in range(8):
        for c in range(8):
            fr = frames[idx % len(frames)]
            sheet[r * h:(r + 1) * h, c * w:(c + 1) * w, :] = fr
            idx += 1
    Image.fromarray(sheet, mode="RGBA").save(out_path, compress_level=9)

def save_frames(frames: List[np.ndarray], out_dir: Path, base_name: str):
    out_frames = out_dir / "frames"
    out_frames.mkdir(parents=True, exist_ok=True)
    for i, fr in enumerate(frames):
        fn = out_frames / f"{base_name}_{i:02d}.png"
        Image.fromarray(fr, mode="RGBA").save(fn, compress_level=9)

# =========================
# Main build
# =========================
def build_variant(v: Dict, root: Path):
    name = v["name"]
    frame_size = int(v["frame_size"])
    tiny = int(v["base_tile"])
    pal = get_palette(v["palette"])
    shimmer_amp = float(v["shimmer_amp"])
    shimmer_cycles = int(v["shimmer_cycles"])
    shift_px = tuple(v["shift_px"])
    cycles = tuple(v["cycles"])
    seed = int(v["seed"])

    # 1) Tiny periodic height tile
    height_tiny = make_height_tile(tiny, seed=seed)
    # 2) Upscale to requested frame size (NEAREST for crisp pixels)
    height_big = upscale_nearest(height_tiny, frame_size)
    # 3) Make 8 unique frames (perfect loop)
    frames = make_frames_from_height(
        height_big=height_big,
        palette=pal,
        n_frames=N_FRAMES,
        shift_px=shift_px,
        cycles=cycles,
        shimmer_amp=shimmer_amp,
        shimmer_cycles=shimmer_cycles,
        alpha_value=220,  # adjust 0-255 if you want more/less overlay strength
    )

    # Output files
    out_dir = root
    base = name
    strip_path = out_dir / f"{base}_8strip_{frame_size}px.png"
    grid_path  = out_dir / f"{base}_8x8_sheet_{frame_size}px.png"

    save_strip(frames, strip_path)
    save_grid_8x8(frames, grid_path)
    save_frames(frames, out_dir, base)

    print(f"✔ {name}: wrote")
    print(f"   - {strip_path.name}")
    print(f"   - {grid_path.name}")
    print(f"   - frames/{base}_00.png .. _07.png")

def main():
    out_root = Path("./water_test")
    out_root.mkdir(parents=True, exist_ok=True)
    for v in VARIANTS:
        build_variant(v, out_root)
    print("\n✅ All variants written to ./water_test/\n"
          "   • *_8x8_sheet_XXpx.png (64 frames, 8x8, no margins)\n"
          "   • *_8strip_XXpx.png    (8 frames in a row)\n"
          "   • frames/*.png         (8 individual frames)\n")

if __name__ == "__main__":
    main()
