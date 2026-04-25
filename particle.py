# particle.py
# ---------------------------------------------------------------------------
# A complete pygame particle engine with:
# - PNG registry (single or multi-frame spritesheets) -> particle "numbers" (ids)
# - Animation modes: "repeat" (loop), "pendulum", "once" (with start delay ticks)
# - Emitters: spray (pps) and burst (one-shot), with physics & randomness knobs
# - Physics: air resistance (drag), wind, gravity
# - Lifetime: sustain_time (emitter), decay_time (per-particle life/fade)
# - Decay layer painting: paint particle "death" onto a persistent layer
# - Public API intended to be game-friendly (Chess Quest, etc.)
#
# DEMO USAGE:
#   python particle.py
#   - Cycles through animation modes & emitter types.
#   - SPACE: spawn a puff burst at mouse.
#   - L toggles drawing the persistent "decay" layer; C clears it.
#   - A/D rotate the spray direction; 1/2/3 set animation mode.
# ---------------------------------------------------------------------------

from __future__ import annotations

import os
import math
import random
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Sequence, Tuple, Union

import pygame


# =========================
# Utility helpers
# =========================

Vec2 = pygame.math.Vector2
ColorLike = Union[Tuple[int, int, int], Tuple[int, int, int, int], pygame.Color]


def _rng_range(v: Union[float, Tuple[float, float]]) -> float:
    """Return a random value. If v is a scalar, return it; if (min,max), sample uniform."""
    if isinstance(v, (tuple, list)) and len(v) == 2:
        return random.uniform(float(v[0]), float(v[1]))
    return float(v)


def _rng_range_vec2(vx: Union[float, Tuple[float, float]],
                    vy: Union[float, Tuple[float, float]]) -> Vec2:
    return Vec2(_rng_range(vx), _rng_range(vy))


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _weighted_choice(ids: Sequence[int], weights: Optional[Sequence[float]]) -> int:
    if not ids:
        raise ValueError("Empty particle id list.")
    if weights is None:
        return random.choice(list(ids))
    return random.choices(list(ids), weights=weights, k=1)[0]


# =========================
# Image registry & animation
# =========================

ANIM_REPEAT = "repeat"     # loop 0..N-1..0..N-1...
ANIM_PENDULUM = "pendulum" # swing 0..N-1..0..N-1...
ANIM_ONCE = "once"         # play 0..N-1 (hold last frame)

@dataclass
class ImageDef:
    image_id: int
    name: str
    frames: List[pygame.Surface]                # ordered frames
    anim_mode: str = ANIM_REPEAT
    ticks_per_frame: int = 4                    # how many engine ticks per animation frame
    start_delay_ticks: int = 0                  # delay before animation begins
    anchor: Tuple[float, float] = (0.5, 0.5)    # anchor in [0..1] for x,y within frame (center default)

    def frame_count(self) -> int:
        return len(self.frames)

    def get_frame(self, idx: int) -> pygame.Surface:
        return self.frames[idx % len(self.frames)]


class ImageRegistry:
    def __init__(self):
        self._images: Dict[int, ImageDef] = {}
        self._by_name: Dict[str, int] = {}
        self._next_id: int = 1

    # ---- register helpers ----

    def register_surfaces(self,
                          name: str,
                          frames: List[pygame.Surface],
                          anim_mode: str = ANIM_REPEAT,
                          ticks_per_frame: int = 4,
                          start_delay_ticks: int = 0,
                          anchor: Tuple[float, float] = (0.5, 0.5)) -> int:
        iid = self._next_id
        self._next_id += 1
        img = ImageDef(
            image_id=iid,
            name=name,
            frames=[f.convert_alpha() for f in frames],
            anim_mode=anim_mode,
            ticks_per_frame=int(max(1, ticks_per_frame)),
            start_delay_ticks=int(max(0, start_delay_ticks)),
            anchor=anchor,
        )
        self._images[iid] = img
        self._by_name[name] = iid
        return iid

    def register_png(self,
                     name: str,
                     path: str,
                     *,
                     # Either specify frame_w/h OR rows/cols OR frame_count across width
                     frame_w: Optional[int] = None,
                     frame_h: Optional[int] = None,
                     cols: Optional[int] = None,
                     rows: Optional[int] = None,
                     frame_count: Optional[int] = None,
                     anim_mode: str = ANIM_REPEAT,
                     ticks_per_frame: int = 4,
                     start_delay_ticks: int = 0,
                     anchor: Tuple[float, float] = (0.5, 0.5)) -> int:
        """Load a single PNG (single frame or spritesheet) and slice frames."""
        surf = pygame.image.load(path).convert_alpha()
        frames = self._slice_frames(surf, frame_w, frame_h, cols, rows, frame_count)
        return self.register_surfaces(name, frames, anim_mode, ticks_per_frame, start_delay_ticks, anchor)

    def id_by_name(self, name: str) -> Optional[int]:
        return self._by_name.get(name)

    def get(self, image_id: int) -> ImageDef:
        return self._images[image_id]

    # ---- slicing ----

    @staticmethod
    def _slice_frames(sheet: pygame.Surface,
                      frame_w: Optional[int],
                      frame_h: Optional[int],
                      cols: Optional[int],
                      rows: Optional[int],
                      frame_count: Optional[int]) -> List[pygame.Surface]:
        W, H = sheet.get_width(), sheet.get_height()

        # Single-frame fallback
        if not any([frame_w, frame_h, cols, rows, frame_count]):
            return [sheet]

        # Deduce columns/rows/size if needed
        if frame_w and not cols:
            cols = max(1, W // frame_w)
        if frame_h and not rows:
            rows = max(1, H // frame_h)
        if cols and not frame_w:
            frame_w = W // cols
        if rows and not frame_h:
            frame_h = H // rows

        fw = frame_w or W
        fh = frame_h or H
        cc = cols or max(1, W // fw)
        rr = rows or max(1, H // fh)
        total = (frame_count or (cc * rr))
        frames: List[pygame.Surface] = []

        count = 0
        for r in range(rr):
            for c in range(cc):
                rect = pygame.Rect(c * fw, r * fh, fw, fh)
                frame = pygame.Surface((fw, fh), pygame.SRCALPHA, 32)
                frame.blit(sheet, (0, 0), rect)
                frames.append(frame)
                count += 1
                if count >= total:
                    return frames
        return frames


# =========================
# Particle core types
# =========================

@dataclass
class Particle:
    pos: Vec2
    vel: Vec2
    image_id: int
    life_ticks: int                       # when age_ticks >= life_ticks -> die
    alpha0: int                           # starting alpha (0..255)
    scale: float = 1.0
    rotation_deg: float = 0.0            # initial rotation
    angular_vel_deg: float = 0.0         # spin per second
    align_to_velocity: bool = False
    image_rotation_offset_deg: float = 0.0 
    # Animation state:
    anim_tick_acc: float = 0.0           # counts up to ticks_per_frame
    anim_frame_idx: int = 0
    anim_forward: int = 1                # for pendulum
    anim_started: bool = False
    anim_delay_ticks_left: int = 0
    # Lifespan:
    age_ticks: int = 0

    # Per-particle accelerations (constant during life, sampled at spawn)
    gravity: Vec2 = field(default_factory=lambda: Vec2(0, 0))
    wind: Vec2 = field(default_factory=lambda: Vec2(0, 0))
    drag: float = 0.0                     # air resistance coefficient (per second)

    def alive(self) -> bool:
        return self.age_ticks < self.life_ticks


@dataclass
class Emitter:
    # --- all NON-default fields first ---
    emitter_id: int
    type: str
    position: Vec2
    particles_per_second: float
    burst_count: int
    emit_angle_deg: float
    angle_spread_deg: float
    speed_range: Tuple[float, float]
    pos_jitter_xy: Tuple[float, float]
    wind_accel_range: Tuple[Tuple[float, float], Tuple[float, float]]
    gravity_accel_range: Tuple[Tuple[float, float], Tuple[float, float]]
    air_resistance: float
    sustain_time: float
    decay_time: float
    decay_layer_paint: bool
    decay_paint_color: pygame.Color
    decay_paint_radius: int
    size_range: Tuple[float, float]
    alpha_range: Tuple[int, int]
    align_to_velocity: bool
    image_rotation_offset_deg: float
    anim_delay_ticks_override: Optional[int]
    image_ids: List[int]
    image_weights: Optional[List[float]]  # still non-default (no "= None")
    # --- now fields WITH defaults ---
    max_particles: Optional[int] = None

    # new sprite-stamping options (all have defaults → must be after non-defaults)
    decay_paint_style: str = "dot"                 # "dot" or "sprite"
    decay_use_particle_alpha: bool = True
    decay_tint_color: Optional[pygame.Color] = None

    # runtime
    enabled: bool = True
    elapsed: float = 0.0
    reservoir: float = 0.0
    fired_burst: bool = False


    def finished(self) -> bool:
        if self.type == "burst":
            return self.fired_burst
        if self.sustain_time < 0:
            return False
        return self.elapsed >= self.sustain_time


# =========================
# Particle System
# =========================

class ParticleSystem:
    def __init__(self, screen_size: Tuple[int, int], tick_rate: int = 60):
        self.tick_rate = int(max(1, tick_rate))
        self.images = ImageRegistry()
        self.emitters: Dict[int, Emitter] = {}
        self._emitter_next_id = 1
        self.particles: List[Particle] = []

        self.decay_layer = pygame.Surface(screen_size, pygame.SRCALPHA, 32).convert_alpha()
        self.draw_decay_layer_enabled = True

        # fractional tick accumulation for animation math
        self._tick_accum = 0.0

    # ---- External API ----

    def register_png(self, *args, **kwargs) -> int:
        """Proxy to ImageRegistry.register_png (returns image/particle id)."""
        return self.images.register_png(*args, **kwargs)

    def register_surfaces(self, *args, **kwargs) -> int:
        """Proxy to ImageRegistry.register_surfaces (returns image/particle id)."""
        return self.images.register_surfaces(*args, **kwargs)

    def get_image_id(self, name: str) -> Optional[int]:
        return self.images.id_by_name(name)

    def create_emitter(self,
                       *,
                       emitter_type: str,                       # "spray" | "burst"
                       emitter_angle: float,                    # degrees; 0=right, 90=down (pygame coords)
                       particles_per_second: float = 0.0,      # used for spray
                       burst_count: int = 0,                    # used for burst
                       x: float, y: float,
                       particle_numbers: Sequence[int],         # image ids
                       particle_weights: Optional[Sequence[float]] = None,
                       velocity_speed_range: Tuple[float, float] = (150, 250),
                       angle_spread_deg: float = 10.0,
                       air_resistance: float = 0.0,
                       wind_vector_range: Tuple[Tuple[float, float], Tuple[float, float]] = ((0, 0), (0, 0)),
                       gravity_vector_range: Tuple[Tuple[float, float], Tuple[float, float]] = ((0, 300), (0, 300)),
                       sustain_time: float = -1.0,
                       decay_time: float = 1.2,
                       decay_result_color: ColorLike = (255, 255, 255, 160),
                       decay_layer_paint: bool = False,
                       decay_paint_radius: int = 2,
                       decay_paint_style: str = "dot",
                       decay_use_particle_alpha: bool = True,
                       decay_tint_color: Optional[ColorLike] = None,
                       pos_jitter_xy: Tuple[float, float] = (0.0, 0.0),
                       size_range: Tuple[float, float] = (1.0, 1.0),
                       alpha_range: Tuple[int, int] = (200, 255),
                       align_to_velocity: bool = False,
                       image_rotation_offset_deg: float = 0.0,
                       anim_delay_ticks_override: Optional[int] = None,
                       max_particles: Optional[int] = None) -> int:
        """Create an emitter. Returns emitter_id."""
        eid = self._emitter_next_id
        self._emitter_next_id += 1

        # Normalize & copy ids
        ids = [int(i) for i in particle_numbers if i in self.images._images]
        if not ids:
            raise ValueError("No valid particle_numbers provided (register images first).")

        weights = None
        if particle_weights:
            if len(particle_weights) != len(ids):
                raise ValueError("particle_weights must match length of particle_numbers")
            weights = [float(w) for w in particle_weights]

        emitter = Emitter(
            emitter_id=eid,
            type=emitter_type.lower(),
            position=Vec2(float(x), float(y)),
            particles_per_second=float(particles_per_second),
            burst_count=int(burst_count),
            emit_angle_deg=float(emitter_angle),
            angle_spread_deg=float(angle_spread_deg),
            speed_range=(float(velocity_speed_range[0]), float(velocity_speed_range[1])),
            pos_jitter_xy=(float(pos_jitter_xy[0]), float(pos_jitter_xy[1])),
            wind_accel_range=((float(wind_vector_range[0][0]), float(wind_vector_range[0][1])),
                              (float(wind_vector_range[1][0]), float(wind_vector_range[1][1]))),
            gravity_accel_range=((float(gravity_vector_range[0][0]), float(gravity_vector_range[0][1])),
                                 (float(gravity_vector_range[1][0]), float(gravity_vector_range[1][1]))),
            air_resistance=float(air_resistance),
            sustain_time=float(sustain_time),
            decay_time=float(decay_time),
            decay_layer_paint=bool(decay_layer_paint),
            decay_paint_color=pygame.Color(*decay_result_color),
            decay_paint_radius=int(decay_paint_radius),
            decay_paint_style=str(decay_paint_style),
            decay_use_particle_alpha=bool(decay_use_particle_alpha),
            decay_tint_color=(pygame.Color(*decay_tint_color)
                if decay_tint_color is not None else None),
            size_range=(float(size_range[0]), float(size_range[1])),
            alpha_range=(int(alpha_range[0]), int(alpha_range[1])),
            align_to_velocity=bool(align_to_velocity),
            image_rotation_offset_deg=float(image_rotation_offset_deg),
            anim_delay_ticks_override=anim_delay_ticks_override if anim_delay_ticks_override is None else int(anim_delay_ticks_override),
            image_ids=ids,
            image_weights=weights,
            max_particles=int(max_particles) if max_particles is not None else None,
        )
        self.emitters[eid] = emitter
        return eid

    def set_emitter_position(self, emitter_id: int, x: float, y: float) -> None:
        self.emitters[emitter_id].position.update(x, y)

    def set_emitter_angle(self, emitter_id: int, angle_deg: float) -> None:
        self.emitters[emitter_id].emit_angle_deg = float(angle_deg)

    def enable_emitter(self, emitter_id: int, enabled: bool) -> None:
        self.emitters[emitter_id].enabled = enabled

    def destroy_emitter(self, emitter_id: int) -> None:
        self.emitters.pop(emitter_id, None)

    def trigger_burst(self, emitter_id: int, at: Optional[Tuple[float, float]] = None, count: Optional[int] = None) -> None:
        """Manually fire a burst emitter again (or early), optionally moving it first."""
        em = self.emitters[emitter_id]
        if at is not None:
            em.position.update(at[0], at[1])
        # Temporarily "unfire" to allow multiple bursts
        em.fired_burst = False
        if count is not None:
            em.burst_count = int(count)

    def clear_particles(self) -> None:
        self.particles.clear()

    def clear_decay_layer(self) -> None:
        self.decay_layer.fill((0, 0, 0, 0))

    def draw_decay_layer(self, dest_surface: pygame.Surface, clear_after: bool = False) -> None:
        if self.draw_decay_layer_enabled:
            dest_surface.blit(self.decay_layer, (0, 0))
            if clear_after:
                self.clear_decay_layer()

    # ---- Update & Draw ----

    def update(self, dt: float) -> None:
        """Advance simulation by dt seconds."""
        ticks_f = dt * self.tick_rate
        self._tick_accum += ticks_f

        # Emit from active emitters
        for em in list(self.emitters.values()):
            em.elapsed += dt
            if not em.enabled:
                continue
            if em.type == "burst":
                if not em.fired_burst:
                    self._spawn_n(em, em.burst_count)
                    em.fired_burst = True
            elif em.type == "spray":
                if em.sustain_time < 0 or em.elapsed <= em.sustain_time:
                    em.reservoir += em.particles_per_second * dt
                    n = int(em.reservoir)
                    if n > 0:
                        self._spawn_n(em, n)
                        em.reservoir -= n

        # Physics & animation for particles
        alive_particles: List[Particle] = []
        for p in self.particles:
            if not p.alive():
                # dead - paint to decay if desired, then skip adding back
                # (we paint once at death; here we only catch exact death if life_ticks==age_ticks)
                # In practice, since we check after increment, we paint where age exceeded life previously.
                continue

            # integrate physics
            # Drag: dv/dt = -drag * v  => v *= exp(-drag * dt) (approx)
            if p.drag > 0.0:
                p.vel *= math.exp(-p.drag * dt)
            # constant accel:
            p.vel += (p.gravity + p.wind) * dt
            # position:
            p.pos += p.vel * dt
            p.rotation_deg += p.angular_vel_deg * dt

            # age
            p.age_ticks += ticks_f

            # Animation advance
            img = self.images.get(p.image_id)
            # Delay start?
            if not p.anim_started:
                if p.anim_delay_ticks_left <= 0:
                    p.anim_started = True
                    p.anim_tick_acc = 0.0
                else:
                    p.anim_delay_ticks_left -= ticks_f
            else:
                p.anim_tick_acc += ticks_f
                while p.anim_tick_acc >= img.ticks_per_frame:
                    p.anim_tick_acc -= img.ticks_per_frame
                    if img.anim_mode == ANIM_REPEAT:
                        p.anim_frame_idx = (p.anim_frame_idx + 1) % img.frame_count()
                    elif img.anim_mode == ANIM_PENDULUM:
                        next_idx = p.anim_frame_idx + p.anim_forward
                        if next_idx >= img.frame_count():
                            p.anim_forward = -1
                            next_idx = img.frame_count() - 2 if img.frame_count() > 1 else 0
                        elif next_idx < 0:
                            p.anim_forward = 1
                            next_idx = 1 if img.frame_count() > 1 else 0
                        p.anim_frame_idx = next_idx
                    elif img.anim_mode == ANIM_ONCE:
                        if p.anim_frame_idx < img.frame_count() - 1:
                            p.anim_frame_idx += 1
                        # else hold last frame

            # Still alive?
            if p.alive():
                alive_particles.append(p)
            else:
                # died this frame -> paint decay
                self._decay_paint(p)

        self.particles = alive_particles

    def draw(self, dest_surface: pygame.Surface, sort_by_y: bool = False) -> None:
        """Draw live particles (decay layer drawn separately via draw_decay_layer)."""
        to_draw = self.particles
        if sort_by_y:
            to_draw = sorted(to_draw, key=lambda p: p.pos.y)

        for p in to_draw:
            img = self.images.get(p.image_id)
            frame = img.get_frame(p.anim_frame_idx)

            # Alpha fade (linear vs life)
            t = _clamp(p.age_ticks / max(1.0, p.life_ticks), 0.0, 1.0)
            alpha = int(p.alpha0 * (1.0 - t))
            if alpha <= 0:
                continue

            # Orientation
            angle = p.rotation_deg + (p.image_rotation_offset_deg or 0.0)
            if p.align_to_velocity and (p.vel.length_squared() > 1e-6):
                angle = math.degrees(math.atan2(p.vel.y, p.vel.x))

            # Transform
            if p.scale != 1.0 or angle != 0.0:
                frame = pygame.transform.rotozoom(frame, -angle, p.scale)

            # Compute blit position from anchor
            fw, fh = frame.get_width(), frame.get_height()
            ox = int(fw * img.anchor[0])
            oy = int(fh * img.anchor[1])
            blit_pos = (int(p.pos.x) - ox, int(p.pos.y) - oy)

            # Copy to apply alpha without mutating cached frame
            temp = frame.copy()
            temp.set_alpha(alpha)
            dest_surface.blit(temp, blit_pos)

    # ---- internals ----

    def _spawn_n(self, em: Emitter, n: int) -> None:
        for _ in range(n):
            if em.max_particles is not None and len(self.particles) >= em.max_particles:
                break

            image_id = _weighted_choice(em.image_ids, em.image_weights)
            img = self.images.get(image_id)

            # position (with jitter)
            jx, jy = em.pos_jitter_xy
            pos = em.position + Vec2(random.uniform(-jx, jx), random.uniform(-jy, jy))

            # velocity: sample angle +/- spread, and speed
            base_ang = math.radians(em.emit_angle_deg)
            spread = math.radians(em.angle_spread_deg) * 0.5
            ang = base_ang + random.uniform(-spread, spread)
            speed = random.uniform(em.speed_range[0], em.speed_range[1])
            vel = Vec2(math.cos(ang) * speed, math.sin(ang) * speed)

            # size & alpha
            scale = random.uniform(em.size_range[0], em.size_range[1])
            alpha0 = random.randint(em.alpha_range[0], em.alpha_range[1])

            # per-particle const accelerations
            wind = _rng_range_vec2(em.wind_accel_range[0], em.wind_accel_range[1])
            grav = _rng_range_vec2(em.gravity_accel_range[0], em.gravity_accel_range[1])

            # anim delay override or per-image
            anim_delay = em.anim_delay_ticks_override if em.anim_delay_ticks_override is not None else img.start_delay_ticks

            p = Particle(
                pos=pos,
                vel=vel,
                image_id=image_id,
                life_ticks=max(1, int(round(em.decay_time * self.tick_rate))),
                alpha0=alpha0,
                scale=scale,
                rotation_deg=random.uniform(0, 360),
                angular_vel_deg=random.uniform(-90, 90),  # gentle spin by default
                align_to_velocity=em.align_to_velocity,
                image_rotation_offset_deg=em.image_rotation_offset_deg,
                anim_delay_ticks_left=anim_delay,
                gravity=grav,
                wind=wind,
                drag=em.air_resistance,
            )
            self.particles.append(p)

    def _decay_paint(self, p: Particle) -> None:
        # Which emitter wants painting? (first match wins)
        em = next((e for e in self.emitters.values()
                if e.decay_layer_paint and (p.image_id in e.image_ids)), None)
        if em is None:
            return

        if em.decay_paint_style == "dot":
            pygame.draw.circle(self.decay_layer, em.decay_paint_color,
                            (int(p.pos.x), int(p.pos.y)), max(1, em.decay_paint_radius))
            return

        # --- "sprite" stamping path ---
        img = self.images.get(p.image_id)
        frame = img.get_frame(p.anim_frame_idx)

        # Compute final angle
        angle = p.rotation_deg + (p.image_rotation_offset_deg or 0.0)
        if p.align_to_velocity and (p.vel.length_squared() > 1e-6):
            angle = math.degrees(math.atan2(p.vel.y, p.vel.x))

        # Transform (rotozoom)
        stamped = pygame.transform.rotozoom(frame, -angle, p.scale)

        # Optional tint
        if em.decay_tint_color is not None:
            stamped = self._tint_multiply(stamped, em.decay_tint_color)

        # Alpha to use on the stamp
        # If using particle alpha at death, compute the same linear fade alpha we used in draw()
        if em.decay_use_particle_alpha:
            t = _clamp(p.age_ticks / max(1.0, p.life_ticks), 0.0, 1.0)
            alpha = int(p.alpha0 * (1.0 - t))
        else:
            alpha = em.decay_paint_color.a  # fixed (from decay_result_color)

        if alpha <= 0:
            return

        stamped = stamped.copy()
        stamped.set_alpha(alpha)

        # Anchor-aware blit position (same logic as draw())
        fw, fh = stamped.get_width(), stamped.get_height()
        ox = int(fw * img.anchor[0])
        oy = int(fh * img.anchor[1])
        blit_pos = (int(p.pos.x) - ox, int(p.pos.y) - oy)

        self.decay_layer.blit(stamped, blit_pos)


    def _tint_multiply(self, src: pygame.Surface, tint: pygame.Color) -> pygame.Surface:
        """Returns a new surface that is src * tint (per-channel multiply)."""
        out = src.copy()
        # Multiply RGB; preserve src alpha
        mult = pygame.Surface(out.get_size(), pygame.SRCALPHA, 32)
        mult.fill((tint.r, tint.g, tint.b, 255))
        out.blit(mult, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        # Apply alpha from tint as a second step (modulate)
        if tint.a != 255:
            alpha_mod = pygame.Surface(out.get_size(), pygame.SRCALPHA, 32)
            alpha_mod.fill((255, 255, 255, tint.a))
            out.blit(alpha_mod, (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
        return out

# =========================
# Demo content (no external files required)
# =========================

def _make_ring_spritesheet(radius: int, frames: int, size: int) -> List[pygame.Surface]:
    """Generate a 'puff ring' expanding animation."""
    out = []
    cx = cy = size // 2
    for i in range(frames):
        surf = pygame.Surface((size, size), pygame.SRCALPHA, 32)
        r = int(radius * (i + 1) / frames)
        pygame.draw.circle(surf, (255, 255, 255, 40), (cx, cy), r)
        pygame.draw.circle(surf, (255, 255, 255, 120), (cx, cy), max(1, r - 2), width=2)
        out.append(surf)
    return out


def _make_spark_spritesheet(length: int, frames: int, size: int) -> List[pygame.Surface]:
    """Generate a small spark that flickers."""
    out = []
    cx = cy = size // 2
    for i in range(frames):
        surf = pygame.Surface((size, size), pygame.SRCALPHA, 32)
        a = 255 - int(155 * (i / max(1, frames - 1)))
        col = (255, 240, 128, a)
        pygame.draw.line(surf, col, (cx - length, cy), (cx + length, cy), width=2)
        pygame.draw.line(surf, col, (cx, cy - length), (cx, cy + length), width=2)
        pygame.draw.circle(surf, (255, 255, 255, a), (cx, cy), 2)
        out.append(surf)
    return out


def _make_leaf(size: int = 20) -> List[pygame.Surface]:
    """Single-frame 'leaf' stand-in."""
    surf = pygame.Surface((size, size), pygame.SRCALPHA, 32)
    pygame.draw.ellipse(surf, (128, 200, 90, 255), (0, 4, size, size - 8))
    pygame.draw.line(surf, (60, 120, 60, 255), (size // 2, 4), (size // 2, size - 4), 2)
    return [surf]


# =========================
# Demo runner
# =========================

def demo(width: int = 960, height: int = 600, tick_rate: int = 60) -> None:
    pygame.init()
    pygame.display.set_caption("Particle Engine Demo")
    screen = pygame.display.set_mode((width, height), pygame.SRCALPHA)
    clock = pygame.time.Clock()

    psys = ParticleSystem((width, height), tick_rate=tick_rate)

    # Try loading external PNGs if available (examples commented; adapt paths to your assets)
    # spark_id = psys.register_png("spark", "assets/spark.png", frame_w=32, frame_h=32, cols=6,
    #                              anim_mode=ANIM_REPEAT, ticks_per_frame=2)
    # puff_id  = psys.register_png("puff",  "assets/puff.png",  frame_w=48, frame_h=48, cols=8,
    #                              anim_mode=ANIM_ONCE, start_delay_ticks=8, ticks_per_frame=2)
    # leaf_id  = psys.register_png("leaf",  "assets/leaf.png")

    # Procedural fallback if you don't have sprites on disk:
    spark_id = psys.register_surfaces("spark", _make_spark_spritesheet(length=6, frames=6, size=32),
                                      anim_mode=ANIM_REPEAT, ticks_per_frame=2)
    puff_id = psys.register_surfaces("puff", _make_ring_spritesheet(radius=14, frames=10, size=48),
                                     anim_mode=ANIM_ONCE, ticks_per_frame=2, start_delay_ticks=10)
    leaf_id = psys.register_surfaces("leaf", _make_leaf(22), anim_mode=ANIM_REPEAT, ticks_per_frame=8)

    center = (width // 2, height // 2)

    # One spray emitter (continuous)
    spray_id = psys.create_emitter(
        emitter_type="spray",
        emitter_angle=0.0,
        particles_per_second=220,
        x=center[0],
        y=center[1],
        particle_numbers=[spark_id, leaf_id],
        particle_weights=[3.0, 1.0],
        velocity_speed_range=(220, 360),
        angle_spread_deg=26,
        air_resistance=0.7,  # gentle drag
        wind_vector_range=((-10, -20), (10, 10)),  # (x_min,x_max),(y_min,y_max) accel px/s^2
        gravity_vector_range=((0, 80), (0, 140)),
        sustain_time=-1.0,               # infinite
        decay_time=0.9,                  # particle life seconds
        decay_result_color=(255, 230, 150, 90),
        decay_layer_paint=False,
        decay_paint_radius=2,
        pos_jitter_xy=(6, 6),
        size_range=(0.7, 1.2),
        alpha_range=(160, 255),
        align_to_velocity=True,
        image_rotation_offset_deg=0.0,
        anim_delay_ticks_override=None,
        max_particles=3500,
    )

    # One burst template emitter (we'll re-fire it on SPACE)
    burst_id = psys.create_emitter(
        emitter_type="burst",
        emitter_angle=90.0,
        burst_count=120,
        x=center[0],
        y=center[1] + 100,
        particle_numbers=[puff_id],
        velocity_speed_range=(140, 220),
        angle_spread_deg=120,
        air_resistance=0.2,
        wind_vector_range=((-20, -10), (10, 30)),
        gravity_vector_range=((0, -20), (0, 20)),
        sustain_time=0.0,        # irrelevant for burst
        decay_time=1.4,
        decay_result_color=(255, 255, 255, 60),
        decay_layer_paint=True,
        decay_paint_style="sprite",          # <— stamp the sprite
        decay_use_particle_alpha=True,       # <— use particle’s current alpha at death
        decay_tint_color=(255, 255, 255, 255),  # or try a colored tint like (255, 200, 150, 220)
        decay_paint_radius=3,                # unused for sprite; still used for "dot"
        pos_jitter_xy=(2, 2),
        size_range=(0.9, 1.4),
        alpha_range=(180, 255),
        align_to_velocity=False,
        image_rotation_offset_deg=0.0,
        anim_delay_ticks_override=None,
        max_particles=2500,
    )

    # Demo cycling through animation modes
    anim_modes = [ANIM_REPEAT, ANIM_PENDULUM, ANIM_ONCE]
    anim_idx = 0
    mode_time = 0.0
    MODE_PERIOD = 5.0  # seconds per demo phase

    font = pygame.font.SysFont("consolas", 16)

    running = True
    while running:
        dt = clock.tick(tick_rate) / 1000.0
        mode_time += dt

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            elif event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    running = False
                elif event.key == pygame.K_SPACE:
                    # Burst at mouse
                    mx, my = pygame.mouse.get_pos()
                    psys.trigger_burst(burst_id, at=(mx, my), count=None)
                elif event.key == pygame.K_l:
                    psys.draw_decay_layer_enabled = not psys.draw_decay_layer_enabled
                elif event.key == pygame.K_c:
                    psys.clear_decay_layer()
                elif event.key == pygame.K_a:
                    # rotate spray left
                    em = psys.emitters[spray_id]
                    em.emit_angle_deg -= 10
                elif event.key == pygame.K_d:
                    # rotate spray right
                    em = psys.emitters[spray_id]
                    em.emit_angle_deg += 10
                elif event.key == pygame.K_1:
                    anim_idx = 0
                elif event.key == pygame.K_2:
                    anim_idx = 1
                elif event.key == pygame.K_3:
                    anim_idx = 2

        # Auto-cycle modes every MODE_PERIOD seconds
        if mode_time >= MODE_PERIOD:
            mode_time = 0.0
            anim_idx = (anim_idx + 1) % len(anim_modes)

        # Update animation mode on registered images
        current_mode = anim_modes[anim_idx]
        # spark toggles among modes
        spark_img = psys.images.get(spark_id)
        spark_img.anim_mode = current_mode
        # leaf sticks to repeat (keeps variety)
        # puff stays "once" but we also showcase start_delay_ticks
        puff_img = psys.images.get(puff_id)
        puff_img.anim_mode = ANIM_ONCE
        puff_img.start_delay_ticks = 8  # move a bit before expanding

        psys.update(dt)

        screen.fill((15, 18, 24))
        # Draw persistent layer first
        psys.draw_decay_layer(screen, clear_after=False)
        # Draw live particles
        psys.draw(screen, sort_by_y=True)

        # UI
        lines = [
            f"Particles: {len(psys.particles)}   Emitters: {len(psys.emitters)}",
            f"Mode (spark): {current_mode}   Spray angle: {psys.emitters[spray_id].emit_angle_deg:.1f}°",
            "SPACE: Puff burst at mouse  |  A/D: rotate spray",
            "1/2/3: repeat / pendulum / once   |   L: toggle decay layer   C: clear",
        ]
        y = 8
        for ln in lines:
            txt = font.render(ln, True, (220, 230, 240))
            screen.blit(txt, (8, y))
            y += 18

        pygame.display.flip()

    pygame.quit()


# =========================
# Public API summary (for your Chess Quest integration)
# =========================
#
# psys = ParticleSystem(screen_size=(W,H), tick_rate=60)
# img_id = psys.register_png(name, path, frame_w=..., frame_h=..., cols=..., rows=..., frame_count=...,
#                            anim_mode=ANIM_REPEAT|ANIM_PENDULUM|ANIM_ONCE, ticks_per_frame=4, start_delay_ticks=0)
# OR:
# img_id = psys.register_surfaces(name, [list_of_surfaces], anim_mode=..., ticks_per_frame=..., start_delay_ticks=...)
#
# eid = psys.create_emitter(
#     emitter_type="spray"|"burst",
#     emitter_angle=deg,
#     particles_per_second=...,   # spray only
#     burst_count=...,            # burst only (and with trigger_burst you can re-fire)
#     x=..., y=...,
#     particle_numbers=[img_id1, img_id2, ...],
#     particle_weights=[w1, w2, ...],     # optional weights
#     velocity_speed_range=(min,max),
#     angle_spread_deg=...,
#     air_resistance=...,         # drag coef (0..~2 typical)
#     wind_vector_range=((x_min,x_max),(y_min,y_max)),   # accel ranges
#     gravity_vector_range=((x_min,x_max),(y_min,y_max)),# accel ranges
#     sustain_time=-1.0,          # seconds; -1 => infinite (spray)
#     decay_time=1.2,             # particle life seconds
#     decay_result_color=(r,g,b,a),
#     decay_layer_paint=True|False,
#     decay_paint_radius=2,
#     pos_jitter_xy=(jx,jy),
#     size_range=(smin,smax),
#     alpha_range=(amin,amax),
#     align_to_velocity=True|False,
#     image_rotation_offset_deg=0.0,
#     anim_delay_ticks_override=None,
#     max_particles=2000,
# )
#
# # Per-frame:
# psys.update(dt_seconds)
# psys.draw(screen_surface, sort_by_y=True)
# psys.draw_decay_layer(screen_surface, clear_after=False)  # draws persistent marks; clear if you like
#
# # Controls:
# psys.set_emitter_position(eid, x, y)
# psys.set_emitter_angle(eid, angle_deg)
# psys.enable_emitter(eid, True/False)
# psys.trigger_burst(eid, at=(x,y), count=Optional[int])    # re-fire a burst emitter
# psys.clear_particles()
# psys.clear_decay_layer()
#
# Image modes can be changed at runtime:
#   img = psys.images.get(img_id)
#   img.anim_mode = ANIM_ONCE
#   img.ticks_per_frame = 3
#   img.start_delay_ticks = 10
#
# =========================

if __name__ == "__main__":
    demo()
