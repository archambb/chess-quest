# effects.py
import pygame
import config
from particle import ParticleSystem, ANIM_REPEAT, ANIM_ONCE, ANIM_PENDULUM
import math

class EffectsManager:
    def __init__(self, game):
        self.g = game
        # Own particle system here
        self.psys = ParticleSystem(
            screen_size=(config.WIDTH, config.HEIGHT),
            tick_rate=config.FPS
        )
        self._particle_ids = {}
        self._register_default_particles()

    def update(self, dt):
        self.psys.update(dt)

    def draw(self, surface):
        self.psys.draw_decay_layer(surface, clear_after=False)
        self.psys.draw(surface, sort_by_y=True)

    # ------------------------
    # Public API
    # ------------------------

    def play_reward_effect(self, name, count=1):
        """Trigger a named reward effect with visuals + audio."""
        # Find the screen position of the power-up icon
        rect = self.g.power_icon_rects.get(name)
        pos = rect.center if rect else (config.WIDTH // 2, config.HEIGHT // 2)

        match name:
            case "bombs":
                self._flash_screen("red")
                self._burst_particles("sparkle", pos=pos, count=100)
                self.g.audio.play("bomb")

            case "freezes":
                self._flash_screen("blue")
                self._burst_particles("snow", pos=pos, count=60)
                self.g.audio.play("freeze")

            case "swaps":
                self._flash_screen("orange")
                self._burst_particles("sparkle", pos=pos, count=50)
                self.g.audio.play("swap")

            case "shields":
                self._flash_screen("cyan")
                self._burst_particles("sparkle", pos=pos, count=40)
                self.g.audio.play("shield")

            case "advanced_shields":
                self._flash_screen("cyan")
                self._burst_particles("sparkle", pos=pos, count=70)
                self.g.audio.play("shield_strong")

            case "promotions":
                self._flash_screen("gold")
                self._burst_particles("sparkle", pos=pos, count=80)
                self.g.audio.play("promotion_up")

            case "time_warps":
                self._flash_screen("purple")
                self._burst_particles("clock", pos=pos, count=40)
                self.g.audio.play("timewarp")

            case "magnets":
                self._flash_screen("silver")
                self._burst_particles("sparkle", pos=pos, count=60)
                self.g.audio.play("magnet")

            case _:
                print(f"[Effects] No visual effect defined for reward: {name}")


    # ------------------------
    # Internal helpers
    # ------------------------

    def _flash_screen(self, color_name, duration=300):
        """Call into renderer for a color overlay flash (if supported)."""
        if hasattr(self.g.renderer, "add_flash_overlay"):
            self.g.renderer.add_flash_overlay(color_name, duration)

    def _burst_particles(self, type_name, pos=None, count=50):
        """Spawn a burst emitter with the registered particle type."""
        if pos is None:
            # fallback: middle of screen
            x = config.WIDTH // 2
            y = config.HEIGHT // 2
        else:
            x, y = pos

        # Ensure the particle type is registered
        pid = self._particle_ids.get(type_name)
        if pid is None:
            print(f"[Effects] Unknown particle type: {type_name}")
            return

        # Create a one-shot burst emitter
        eid = self.psys.create_emitter(
            emitter_type="burst",
            emitter_angle=90.0,
            burst_count=count,
            x=x,
            y=y,
            particle_numbers=[pid],
            velocity_speed_range=(100, 220),
            angle_spread_deg=360.0,
            air_resistance=0.3,
            wind_vector_range=((-20, 20), (-20, 20)),
            gravity_vector_range=((-30, 30), (20, 60)),
            sustain_time=0.0,
            decay_time=1.2,
            decay_result_color=(255, 255, 255, 80),
            decay_layer_paint=False,
            pos_jitter_xy=(4, 4),
            size_range=(0.8, 1.4),
            alpha_range=(180, 255),
            align_to_velocity=True,
            image_rotation_offset_deg=0.0,
            anim_delay_ticks_override=None,
            max_particles=1500,
        )
        # Immediately fire the burst
        self.psys.trigger_burst(eid, at=(x, y), count=count)

    def _register_default_particles(self):
        """Register fallback procedural particles for effects."""
        # Sparkle = simple white flickering star
        self._particle_ids["sparkle"] = self.psys.register_surfaces(
            "sparkle",
            self._make_star_spritesheet(6, 8, 24),
            anim_mode=ANIM_REPEAT,
            ticks_per_frame=3
        )

        # Snowflake = soft circles
        self._particle_ids["snow"] = self.psys.register_surfaces(
            "snow",
            self._make_snowflake(20),
            anim_mode=ANIM_REPEAT,
            ticks_per_frame=6
        )

        # Clock = expanding ring pulse
        self._particle_ids["clock"] = self.psys.register_surfaces(
            "clock",
            self._make_ring_spritesheet(18, 10, 48),
            anim_mode=ANIM_ONCE,
            ticks_per_frame=2
        )

    # ------------------------
    # Procedural art helpers
    # ------------------------

    def _make_star_spritesheet(self, spikes: int, frames: int, size: int):
        """Animated sparkle star."""
        out = []
        cx = cy = size // 2
        for i in range(frames):
            surf = pygame.Surface((size, size), pygame.SRCALPHA, 32)
            radius = size // 2 - 2
            phase = (i / frames) * 3.14159
            color = (255, 240, 180, 200)
            for s in range(spikes):
                ang = (s * 2 * 3.14159 / spikes) + phase
                x = cx + int(radius * 0.8 * math.cos(ang))
                y = cy + int(radius * 0.8 * math.sin(ang))
                pygame.draw.line(surf, color, (cx, cy), (x, y), 2)
            out.append(surf)
        return out

    def _make_snowflake(self, size: int = 20):
        """Single-frame snowflake."""
        surf = pygame.Surface((size, size), pygame.SRCALPHA, 32)
        col = (220, 240, 255, 255)
        cx = cy = size // 2
        pygame.draw.circle(surf, col, (cx, cy), size // 3)
        pygame.draw.line(surf, col, (cx, cy - 6), (cx, cy + 6), 2)
        pygame.draw.line(surf, col, (cx - 6, cy), (cx + 6, cy), 2)
        return [surf]

    def _make_ring_spritesheet(self, radius: int, frames: int, size: int):
        """Expanding translucent ring."""
        out = []
        cx = cy = size // 2
        for i in range(frames):
            surf = pygame.Surface((size, size), pygame.SRCALPHA, 32)
            r = int(radius * (i + 1) / frames)
            pygame.draw.circle(surf, (180, 180, 255, 80), (cx, cy), r, width=2)
            out.append(surf)
        return out
