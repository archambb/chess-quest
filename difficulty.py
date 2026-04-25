# difficulty.py
import traceback
import config

DIFFICULTY_RANKS = [
    "VERY EASY", "EASY", "NORMAL", "CHALLENGING",
    "ADVANCED", "EXPERT", "MASTER", "GRANDMASTER"
]

DIFFICULTY_TABLE = {
    "VERY EASY":    [1, 1, 1, 1, 2, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4],
    "EASY":         [1, 2, 2, 2, 3, 3, 3, 3, 4, 4, 4, 4, 4, 5, 6, 6],
    "NORMAL":       [7, 7, 8, 8, 9, 9,10,10,11,12,13,14,15,16,17,18],
    "CHALLENGING":  [8, 8, 9, 9,10,10,11,11,12,13,14,15,16,17,18,19],
    "ADVANCED":     [8, 8,10,11,12,13,14,15,16,17,18,19,20,20,20,20],
    "EXPERT":       [8, 8,10,11,12,13,14,15,16,17,18,19,20,20,20,20],
    "MASTER":       [9,10,11,12,13,14,15,16,17,18,19,20,20,20,20,20],
    "GRANDMASTER":  [9,12,14,16,18,20,20,20,20,20,20,20,20,20,20,20],
}

def _clamp(n, lo, hi):
    return max(lo, min(hi, n))

class DifficultyManager:
    def __init__(self, game):
        self.g = game
        self._printed_options = False

    # ─────────────────────────────────────────────────────────────
    # PUBLIC API
    # ─────────────────────────────────────────────────────────────
    def SetEngineDifficulty(self):
        level = self._compute_stockfish_level()
        self._apply_engine_level(level)
        self.g.current_stockfish_level = level
        self.g.stockfish_level = level
        print(f"[Difficulty] Persistent Skill Level set → {level}")
        return level

    def SetEngineDifficultyTemp(self):
        level = self._compute_stockfish_level()
        self._apply_engine_level(level)
        self.g.current_stockfish_level = level
        print(f"[Difficulty] TEMP Skill Level set → {level}")
        return level

    def RestoreDifficulty(self):
        original = getattr(self.g, "stockfish_level", None)
        if original is None:
            print("[Difficulty] No stored difficulty to restore.")
            return None
        self.g.current_stockfish_level = original
        self._apply_engine_level(original)
        print(f"[Difficulty] Restored Skill Level → {original}")
        return original

    # ─────────────────────────────────────────────────────────────
    # INTERNALS
    # ─────────────────────────────────────────────────────────────
    def _compute_stockfish_level(self) -> int:
        try:
            idx = int(getattr(config, "difficulty", 0))
        except Exception:
            idx = 0
        idx = _clamp(idx, 0, len(DIFFICULTY_RANKS) - 1)
        rank = DIFFICULTY_RANKS[idx]

        beaten = self._get_worlds_beaten()
        beaten = _clamp(beaten, 0, 15)

        level = DIFFICULTY_TABLE[rank][beaten]
        print(f"[Difficulty] Rank={rank}, WorldsBeaten={beaten} → Skill {level}")
        return int(level)

    def _apply_engine_level(self, level: int):
        """
        ONLY use Stockfish 'Skill Level'. No Elo, no UCI_LimitStrength.
        Stockfish expects Skill Level in [0..20].
        Your table uses [1..20], so we map 1→0, 20→19 by default,
        but we clamp so you can still feed 20 safely (20 stays 20).
        """
        try:
            eng = self.g.engine
            opts = getattr(eng, "options", {})

            if not self._printed_options:
                try:
                    print("[Difficulty] Engine options:", {k: str(v) for k, v in opts.items()})
                except Exception:
                    pass
                self._printed_options = True

            if "Skill Level" not in opts:
                print("[Difficulty][WARN] Engine does not expose 'Skill Level'. "
                      "This Stockfish binary may not support it via UCI.")
                return

            # Map 1..20 -> 0..20 (preference: 1->0 to make 'VERY EASY' actually very easy)
            lvl = int(level)
            sf_level = _clamp(lvl - 1, 0, 20)

            eng.configure({"Skill Level": sf_level})
            print(f"[Difficulty] Applied Skill Level={sf_level} (from table level={lvl})")

        except Exception:
            print("[Difficulty][ERROR] Could not configure engine:")
            traceback.print_exc()

    def _get_worlds_beaten(self) -> int:
        candidates = [
            getattr(self.g, "world", None),
            getattr(self.g, "game_world", None),
            getattr(self.g, "overworld", None),
        ]
        for w in candidates:
            if w is None:
                continue
            if hasattr(w, "beaten_count"):
                try:
                    return int(w.beaten_count())
                except:
                    pass
            data = getattr(w, "world_data", None)
            if isinstance(data, dict):
                try:
                    return sum(1 for cell in data.values() if cell.get("win"))
                except:
                    pass
        data = getattr(self.g, "world_data", None)
        if isinstance(data, dict):
            return sum(1 for cell in data.values() if cell.get("win"))
        return 0
