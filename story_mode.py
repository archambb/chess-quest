import pygame
from play_story import StoryPlayer


class StoryMode:
    """
    Handles all story / narrative logic for Chess Quest, driven by:
    - stories.json (story IDs like Misty_Fens_Win, Ember_Spire_First_Visit, etc.)
    - frames.json (per-frame return_rewards: powerups + spells)

    It talks back to the main game object (ChessScreen) to grant rewards,
    inspect world state, etc.
    """

    # Mapping from stage_id → story prefix used in stories.json
    # Order matches your stories.json stage groups.
    STAGE_STORY_PREFIXES = {
        1: "Misty_Fens",
        2: "Ember_Spire",
        3: "Emerald_Grove",
        4: "Shadow_Realms",
        5: "Frozen_Lake",
        6: "Storm_Reaches",
        7: "Grave_Hollow",
        8: "Shifting_Sands",
        9: "Iron_Keep",
        10: "Astral_Gate",
        11: "Verdant_Citadel",
        12: "Crimson_Court",
        13: "Sanctuary_of_Light",
        14: "Dreamland",
    }

    def __init__(self, game):
        """
        :param game: The ChessScreen instance (main game controller).
        """
        self.g = game
        self.screen = self.g.screen
        self.story_player = StoryPlayer(self.screen)

    # ──────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────

    def _refresh_story_player(self):
        """Rebuild a StoryPlayer in case screen surfaces changed."""
        self.story_player = StoryPlayer(self.screen)

    def _current_stage_id(self):
        """Read stage_id for the tile the player is currently on."""
        world = getattr(self.g, "world", None)
        if not world:
            return None
        node = world.world_data.get(world.player_pos)
        if not node:
            return None
        return node.get("stage_id")

    def _stage_prefix_for_current_world(self):
        """Map current stage_id → stories.json prefix like 'Misty_Fens'."""
        stage_id = self._current_stage_id()
        if stage_id is None:
            return None
        return self.STAGE_STORY_PREFIXES.get(stage_id)

    def _normalize_story_result_and_apply_rewards(self, raw_result):
        """
        Accept whatever StoryPlayer.play_story() returns and normalize it
        to a simple result string, while also applying any rewards from
        frames.json.

        Supported shapes:
        - Old:    play_story() -> "kill"
        - New A:  play_story() -> {"result": "kill", "return_rewards": {...}}
        - New B:  play_story() -> ("kill", {"powerups": {...}, "spells": [...]})
        """
        result = None
        rewards = None

        # dict-style return (recommended)
        if isinstance(raw_result, dict):
            result = (
                raw_result.get("result")
                or raw_result.get("target")
                or raw_result.get("choice")
            )
            rewards = (
                raw_result.get("return_rewards")
                or raw_result.get("rewards")
            )

        # tuple-style return
        elif isinstance(raw_result, tuple) and len(raw_result) == 2:
            result, rewards = raw_result

        # plain string
        else:
            result = raw_result

        if rewards:
            self._apply_story_rewards(rewards)

        return result

    def _apply_story_rewards(self, rewards):
        """
        Apply rewards from frames.json. Example schema:

        "return_rewards": {
          "powerups": {
            "shields": 2,
            "promotions": 2
          },
          "spells": [
            "Summon Boulder"
          ]
        }
        """
        # Powerups
        powerups = rewards.get("powerups", {})
        if powerups:
            for name, amount in powerups.items():
                current = self.g.powerups.get(name, 0)
                self.g.powerups[name] = current + amount
                print(f"[STORY REWARD] +{amount} {name} (total {self.g.powerups[name]})")

        # Spells
        spells = rewards.get("spells", [])
        for spell in spells:
            if spell not in self.g.spellbook_master:
                self.g.spellbook_master.append(spell)
            if spell not in self.g.spellbook:
                self.g.spellbook.append(spell)
            print(f"[STORY REWARD] Learned spell: {spell}")

    # ──────────────────────────────────────────────────────────────
    # Intro / tutorial sequence
    # ──────────────────────────────────────────────────────────────

    def play_intro_and_tutorial(self):
        """
        Play the intro story, optional tutorial, and 'return' sequence.

        Uses the top-level keys in stories.json:
        - "Intro"          (frames 1-6)
        - "Tutorial"       (frame 10)   — only if the player chooses it
        - "Intro_return"   (frames 7-9)
        """
        self._refresh_story_player()

        intro_raw = self.story_player.play_story("Intro")
        intro_result = self._normalize_story_result_and_apply_rewards(intro_raw)

        if intro_result == "Tutorial":
            tut_raw = self.story_player.play_story("Tutorial")
            self._normalize_story_result_and_apply_rewards(tut_raw)

        ret_raw = self.story_player.play_story("Intro_return")
        self._normalize_story_result_and_apply_rewards(ret_raw)

    # ──────────────────────────────────────────────────────────────
    # Stage entry (new level) stories
    # ──────────────────────────────────────────────────────────────

    def handle_new_level_story(self):
        """
        Called after the overworld moves the player to a new tile but before
        the chess board is set up for that stage.

        Logic:
        - Peek at this world's losses count in world.world_data.
        - If losses == 0 → first time here → "<Prefix>_First_Visit"
        - If losses > 0  → returning after failure → "<Prefix>_Return"
        """
        prefix = self._stage_prefix_for_current_world()
        if not prefix:
            # No mapping for this stage; silently skip.
            return

        world = self.g.world
        node = world.world_data.get(world.player_pos, {})
        losses = node.get("losses", 0)

        if losses > 0:
            story_id = f"{prefix}_Return"
        else:
            story_id = f"{prefix}_First_Visit"

        print(f"[STORY] Entering stage → {story_id}")
        self._refresh_story_player()
        raw = self.story_player.play_story(story_id)
        self._normalize_story_result_and_apply_rewards(raw)

    # ──────────────────────────────────────────────────────────────
    # Stage win / loss stories
    # ──────────────────────────────────────────────────────────────

    def handle_win_story(self):
        """
        Called when the player wins a *stage* (3 board wins) before moving
        on the overworld.

        Uses "<Prefix>_Win" from stories.json for normal stages.

        For the early Stone wizard arc, falls back to "Stone_Plead_1" -
        which still uses frames.json (return_rewards) and the old
        kill/free semantics.
        """
        prefix = self._stage_prefix_for_current_world()

        if prefix:
            story_id = f"{prefix}_Win"
        else:
            # Prologue / Wizard of Stone
            story_id = "Stone_Plead_1"

        print(f"[STORY] Stage victory → {story_id}")
        self._refresh_story_player()
        raw = self.story_player.play_story(story_id)
        result = self._normalize_story_result_and_apply_rewards(raw)

        # Optional: preserve the original Stone logic on top of any rewards
        if story_id == "Stone_Plead_1":
            if result == "kill":
                self.g.powerups["promotions"] = self.g.powerups.get("promotions", 0) + 2
                self.g.powerups["shields"] = self.g.powerups.get("shields", 0) + 2
                print("[STONE] Extra +2 promotions, +2 shields (legacy behavior).")
            elif result == "free":
                if "Summon Boulder" not in self.g.spellbook_master:
                    self.g.spellbook_master.append("Summon Boulder")
                if "Summon Boulder" not in self.g.spellbook:
                    self.g.spellbook.append("Summon Boulder")
                print("[STONE] Learned Summon Boulder (legacy behavior).")

    def handle_lose_story(self):
        """
        Called when the player loses a *stage* (3 board losses) before moving
        on the overworld.

        Uses "<Prefix>_Failure" from stories.json where available.
        """
        prefix = self._stage_prefix_for_current_world()
        if not prefix:
            # If you want Stone failures to do something, you can
            # e.g. call "Return_to_stone" here instead of skipping.
            # story_id = "Return_to_stone"
            # ...
            return

        story_id = f"{prefix}_Failure"
        print(f"[STORY] Stage failure → {story_id}")
        self._refresh_story_player()
        raw = self.story_player.play_story(story_id)
        self._normalize_story_result_and_apply_rewards(raw)
