# audio.py
from __future__ import annotations

import os
import random
import pygame
import config


class AudioManager:
    """
    Chess Quest - Audio Manager

    - SFX (piece moves, powers, events): config.SFX_VOLUME (0-100)
    - Music: config.MUSIC_VOLUME (0-100)
    - Voice: config.VOICE_VOLUME (0-100)

    Voice files:
      assets/SFX/voice/stage{stage}_voice{voice}.wav

    Music files:
      assets/SFX/music/stage{stage}.wav or stage{stage}.mp3 (also supports .ogg)
    """

    def __init__(self):
        pygame.mixer.init()

        self.sounds: dict[str, pygame.mixer.Sound] = {}
        self._base_dir = os.path.dirname(os.path.abspath(__file__))

        # Optional: reserve a dedicated channel for voice so it doesn't get cut off by rapid SFX.
        self._voice_channel = pygame.mixer.Channel(1)

        self._load_all_sounds()
        self.update_volumes()

    # ─────────────────────────────────────────────────────────────
    # Volume helpers (support BOTH SFX_VOLUME and sfx_volume styles)
    # ─────────────────────────────────────────────────────────────
    def _normalized(self, value: float) -> float:
        try:
            v = float(value)
        except Exception:
            v = 0.0
        return max(0.0, min(1.0, v / 100.0))

    def _cfg(self, *names: str, default: float = 100.0) -> float:
        for n in names:
            if hasattr(config, n):
                return getattr(config, n)
        return default

    def _sfx_vol(self) -> float:
        return self._normalized(self._cfg("SFX_VOLUME", default=100.0))

    def _music_vol(self) -> float:
        return self._normalized(self._cfg("MUSIC_VOLUME", default=100.0))

    def _voice_vol(self) -> float:
        return self._normalized(self._cfg("VOICE_VOLUME", default=100.0))

    # ─────────────────────────────────────────────────────────────
    # SFX loading / playback
    # ─────────────────────────────────────────────────────────────
    def load_sound(self, name: str, filepath: str) -> None:
        try:
            sound = pygame.mixer.Sound(filepath)
            sound.set_volume(self._sfx_vol())
            self.sounds[name] = sound
        except pygame.error as e:
            print(f"Error loading sound '{name}' from '{filepath}': {e}")

    def play(self, name: str) -> None:
        sound = self.sounds.get(name)
        if sound:
            sound.set_volume(self._sfx_vol())
            sound.play()
        else:
            print(f"Sound '{name}' not found.")

    def play_random(self, prefix: str) -> None:
        prefix = prefix.lower() + "_"
        matches = [name for name in self.sounds if name.startswith(prefix)]
        if matches:
            self.play(random.choice(matches))
        else:
            print(f"No sound found with prefix '{prefix}'")

    def stop(self, name: str) -> None:
        sound = self.sounds.get(name)
        if sound:
            sound.stop()

    def set_volume(self, name: str, volume: float) -> None:
        sound = self.sounds.get(name)
        if sound:
            sound.set_volume(self._normalized(volume))

    def stop_all(self) -> None:
        pygame.mixer.stop()

    def update_volumes(self) -> None:
        """Update all volumes from config (SFX/MUSIC/VOICE)."""
        sfx_v = self._sfx_vol()
        for sound in self.sounds.values():
            sound.set_volume(sfx_v)

        pygame.mixer.music.set_volume(self._music_vol())
        self._voice_channel.set_volume(self._voice_vol())

    # ─────────────────────────────────────────────────────────────
    # NEW: Voice playback
    # ─────────────────────────────────────────────────────────────
    def play_voice(self, stage: int, voice_file_num: int) -> None:
        """
        Plays:
          assets/SFX/voice/stage{stage}_voice{voice_file_num}.wav
        at config.VOICE_VOLUME.
        """
        voice_dir = os.path.join(self._base_dir, "assets", "SFX", "voice")
        voice_path = os.path.join(voice_dir, f"stage{stage}_voice{voice_file_num}.wav")

        if not os.path.exists(voice_path):
            print(f"[WARN] Voice file not found: {voice_path}")
            return

        try:
            snd = pygame.mixer.Sound(voice_path)
            snd.set_volume(self._voice_vol())
            # Dedicated channel so voice isn't competing with frequent SFX calls.
            self._voice_channel.set_volume(self._voice_vol())
            self._voice_channel.play(snd)
        except pygame.error as e:
            print(f"[ERROR] Failed to play voice '{voice_path}': {e}")

    # ─────────────────────────────────────────────────────────────
    # NEW: Stage music playback
    # ─────────────────────────────────────────────────────────────
    def play_music(self, stage: int, loop: bool = True) -> None:
        """
        Plays stage music from:
          assets/SFX/music/stage{stage}.wav or .mp3 (also .ogg)
        at config.MUSIC_VOLUME.
        """
        music_dir = os.path.join(self._base_dir, "assets", "SFX", "music")
        candidates = [
            os.path.join(music_dir, f"stage{stage}.wav"),
            os.path.join(music_dir, f"stage{stage}.mp3"),
            os.path.join(music_dir, f"stage{stage}.ogg"),
        ]

        music_path = next((p for p in candidates if os.path.exists(p)), None)
        if not music_path:
            print(f"[WARN] No music found for stage {stage} (looked for wav/mp3/ogg).")
            return

        try:
            pygame.mixer.music.load(music_path)
            pygame.mixer.music.set_volume(self._music_vol())
            pygame.mixer.music.play(-1 if loop else 0)
        except Exception as e:
            print(f"[ERROR] Failed to load/play music '{music_path}': {e}")

    def stop_music(self, fade_ms: int = 0) -> None:
        try:
            if fade_ms and fade_ms > 0:
                pygame.mixer.music.fadeout(int(fade_ms))
            else:
                pygame.mixer.music.stop()
        except Exception:
            pass

    # ─────────────────────────────────────────────────────────────
    # Loading all SFX
    # ─────────────────────────────────────────────────────────────
    def _load_all_sounds(self) -> None:
        audio_exts = (".mp3", ".ogg", ".wav")

        def load_group(dir_path: str, prefix: str) -> None:
            if not os.path.isdir(dir_path):
                return
            for filename in os.listdir(dir_path):
                if filename.startswith(prefix) and filename.lower().endswith(audio_exts):
                    sound_path = os.path.join(dir_path, filename)
                    self.load_sound(filename[:-4], sound_path)

        # Piece move SFX
        move_dir = os.path.join(self._base_dir, "assets", "SFX", "move")
        for piece_char in "bknpqr":
            # keep your existing convention: move_{piece}.mp3
            sound_path = os.path.join(move_dir, f"move_{piece_char}.mp3")
            if os.path.exists(sound_path):
                self.load_sound(f"move_{piece_char}", sound_path)

        # Powers SFX
        power_dir = os.path.join(self._base_dir, "assets", "SFX", "powers")
        for prefix in [
            "bomb_", "time_warp_", "freezes_", "swap_", "shields_",
            "promotion_", "greater_shields_", "magnet_"
        ]:
            load_group(power_dir, prefix)

        # Events SFX (coin_1.wav, coin_2.wav, etc.; supports mp3/ogg/wav)
        events_dir = os.path.join(self._base_dir, "assets", "SFX", "events")
        i = 1
        while True:
            found = False
            for ext in audio_exts:
                coin_path = os.path.join(events_dir, f"coin_{i}{ext}")
                if os.path.exists(coin_path):
                    self.load_sound(f"coin_{i}", coin_path)
                    found = True
                    break
            if not found:
                if i == 1:
                    print("[WARN] No coin sounds found!")
                else:
                    print(f"[INFO] Loaded {i - 1} coin sound(s).")
                break
            i += 1

    def load_initial_music(self) -> None:
        # Intro music
        intro_music_path = os.path.join(self._base_dir, "assets", "SFX", "music", "intro.wav")
        try:
            pygame.mixer.music.load(intro_music_path)
            pygame.mixer.music.set_volume(self._music_vol())
            pygame.mixer.music.play(-1)
            print("Intro music playing...")
        except Exception as e:
            print(f"Failed to load intro music: {e}")
