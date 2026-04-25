# spell_targeting.py
import chess
from typing import Optional


class SpellTargeting:
    """
    Owns:
      - arming spells from spellbook selection
      - computing legal target squares to highlight
      - consuming a board-click to cast / activate

    Renderer reads:
      g.spell_target_squares (list[chess.Square])
      g.spell_target_rgb (tuple[int,int,int])
    """

    SPELLBOOK_POWER_SPELLS = {"Ice Blast", "Inspire Soldier", "Shadow Step", "Meteor Shower"}

    def __init__(self, game):
        self.g = game

    # ---------- public API ----------
    def arm_from_spellbook(self, spell_name: str) -> None:
        """Call when user clicks a spell in the spellbook UI."""
        g = self.g

        self._clear_targeting_state()
        g.selected_square = None
        g.possible_moves = []

        if self._spell_casting_blocked():
            g.ui_state.send_feedback("Your spell is blocked by the Wizard of Light!")
            return

        spell_def = self._get_spell_def(spell_name)
        cast_type = spell_def.get("cast_type", "instant")

        # Keep special power-based activation paths where needed
        if spell_name in ("Ice Blast", "Inspire Soldier"):
            g.selected_power = spell_name
            g.selected_spell = None
            self._set_spell_targets_for_power_spell(spell_name)
            self._finalize_arming_or_fail(spell_name)
            return

        if spell_name == "Shadow Step":
            g.shadow_step_active = True
            g.selected_power = "Shadow Step"
            g.selected_spell = None
            self._set_spell_targets_shadow_step()
            self._finalize_arming_or_fail(spell_name)
            return

        if spell_name == "Meteor Shower":
            g.meteor_active = True
            g.meteor_quadrant = None
            g.selected_power = "Meteor Shower"
            g.selected_spell = None
            self._set_spell_targets_meteor_quadrant()
            self._finalize_arming_or_fail(spell_name)
            return

        if cast_type == "instant":
            self.cast_instant(spell_name)
            return

        if cast_type == "targeted":
            g.selected_spell = spell_name
            g.selected_power = None
            self._set_spell_targets_for_selected_spell(spell_name)
            self._finalize_arming_or_fail(spell_name)
            return

        self.cast_instant(spell_name)

    def handle_board_click(self, square: Optional[chess.Square]) -> bool:
        """Return True if the click was consumed by spell targeting."""
        if square is None:
            return False

        g = self.g
        if not self.is_spell_targeting_active():
            return False

        targets = set(getattr(g, "spell_target_squares", []) or [])
        if not targets:
            g.ui_state.send_feedback("That spell has no valid targets right now.")
            self._clear_targeting_state()
            return True

        if square not in targets:
            g.ui_state.send_feedback("That square is not a valid target.")
            return True

        if self._spell_casting_blocked():
            g.ui_state.send_feedback("Your spell is blocked by the Wizard of Light!")
            self._clear_targeting_state()
            return True

        used = False
        spell = getattr(g, "selected_spell", None)
        selp = getattr(g, "selected_power", None)

        if spell == "Flood":
            used = bool(g.cast_spells.cast_flood(square))
        elif spell == "Granite Elf":
            used = bool(g.cast_spells.cast_granite_elf(square))
        elif selp in ("Ice Blast", "Inspire Soldier", "Shadow Step", "Meteor Shower"):
            used = bool(g.powers.activate_power(selp, square, allow_spellbook=True))
        else:
            g.ui_state.send_feedback("That spell can't be targeted right now.")
            self._clear_targeting_state()
            return True

        if used:
            self._clear_targeting_state()

        return True

    def cast_instant(self, spell_name: str) -> None:
        g = self.g
        self._clear_targeting_state()

        if self._spell_casting_blocked():
            g.ui_state.send_feedback("Your spell is blocked by the Wizard of Light!")
            return

        if spell_name == "Wind Storm":
            g.cast_spells.cast_wind_storm()
        elif spell_name == "Desert Sun":
            g.cast_spells.cast_desert_sun()
        elif spell_name == "Orb of Premonition":
            g.cast_spells.cast_orb_of_premonition()
        elif spell_name == "Heal Pawns":
            g.cast_spells.cast_heal_pawns()
        elif spell_name == "Summon Elf":
            g.cast_spells.cast_summon_elf()
        elif spell_name == "Summon Undead Elves":
            g.cast_spells.cast_summon_undead_elves()
        elif spell_name == "Mirror Armies":
            g.cast_spells.cast_mirror_armies()
        elif spell_name == "Sacrifice":
            g.cast_spells.cast_sacrifice()
        elif spell_name == "One With Light":
            g.cast_spells.cast_one_with_light()
        elif spell_name == "Greed":
            g.cast_spells.cast_greed()
        else:
            g.ui_state.send_feedback("Spell not implemented.")
            return

        try:
            g.board_manager.update_allowed_moves()
        except Exception:
            pass

    def is_spell_targeting_active(self) -> bool:
        g = self.g
        if getattr(g, "selected_spell", None):
            return True
        if getattr(g, "selected_power", None) in self.SPELLBOOK_POWER_SPELLS:
            return True
        if getattr(g, "shadow_step_active", False):
            return True
        if getattr(g, "meteor_active", False):
            return True
        return False

    # ---------- metadata helpers ----------
    def _get_spell_def(self, spell_name: str) -> dict:
        return (getattr(self.g, "spell_info", {}) or {}).get(spell_name, {
            "name": spell_name,
            "description": "",
            "cast_type": "instant",
            "target_mode": None,
            "target_rgb": None,
        })

    def _get_spell_rgb(self, spell_name: str):
        rgb = self._get_spell_def(spell_name).get("target_rgb")
        return tuple(rgb) if rgb else None

    # ---------- internals ----------
    def _spell_casting_blocked(self) -> bool:
        try:
            return self.g.world.get_stage_id() == 13 and self.g.map_challenges.board_effects_active is True
        except Exception:
            return False

    def _finalize_arming_or_fail(self, spell_name: str) -> None:
        g = self.g
        targets = list(getattr(g, "spell_target_squares", []) or [])
        if targets:
            return

        self._clear_targeting_state()
        no_target_messages = {
            "Inspire Soldier": "You have no pawns available to inspire.",
            "Shadow Step": "You have no legal shadow step destinations.",
            "Meteor Shower": "There is no valid quadrant to target right now.",
            "Granite Elf": "You have no bishops available to turn to granite.",
        }
        g.ui_state.send_feedback(no_target_messages.get(spell_name, "That spell has no valid targets right now."))

    def _clear_targeting_state(self) -> None:
        g = self.g
        g.selected_spell = None
        if getattr(g, "selected_power", None) in self.SPELLBOOK_POWER_SPELLS:
            g.selected_power = None

        g.shadow_step_active = False
        g.meteor_active = False
        g.meteor_quadrant = None
        g.spell_target_squares = []
        g.spell_target_rgb = None

    def _set_spell_targets_for_selected_spell(self, spell_name: str) -> None:
        g = self.g
        is_on_side = g.powers.is_on_player_side
        rgb = self._get_spell_rgb(spell_name)

        if spell_name == "Flood":
            g.spell_target_squares = [sq for sq in chess.SQUARES if is_on_side(sq)]
            g.spell_target_rgb = rgb or (40, 120, 255)

        elif spell_name == "Granite Elf":
            player_color = chess.WHITE if g.player_side == "white" else chess.BLACK
            squares = []

            for sq, piece in g.board.piece_map().items():
                if not is_on_side(sq):
                    continue
                if piece.color != player_color:
                    continue
                if piece.piece_type != chess.BISHOP:
                    continue
                squares.append(sq)

            g.spell_target_squares = squares
            g.spell_target_rgb = rgb or (140, 140, 140)

        else:
            g.spell_target_squares = []
            g.spell_target_rgb = rgb or (255, 255, 255)

    def _set_spell_targets_for_power_spell(self, spell_name: str) -> None:
        g = self.g
        is_on_side = g.powers.is_on_player_side
        rgb = self._get_spell_rgb(spell_name)

        if spell_name == "Ice Blast":
            g.spell_target_squares = [sq for sq in chess.SQUARES if is_on_side(sq)]
            g.spell_target_rgb = rgb or (0, 200, 255)
            return

        if spell_name == "Inspire Soldier":
            player_color = chess.WHITE if g.player_side == "white" else chess.BLACK
            squares = []
            for sq, piece in g.board.piece_map().items():
                if not is_on_side(sq):
                    continue
                if piece.color != player_color:
                    continue
                if piece.piece_type != chess.PAWN:
                    continue
                squares.append(sq)
            g.spell_target_squares = squares
            g.spell_target_rgb = rgb or (180, 255, 120)
            return

        g.spell_target_squares = []
        g.spell_target_rgb = rgb or (255, 255, 255)

    def _set_spell_targets_shadow_step(self) -> None:
        g = self.g
        is_on_side = g.powers.is_on_player_side
        rgb = self._get_spell_rgb("Shadow Step")
        squares = []
        for sq in chess.SQUARES:
            if not is_on_side(sq):
                continue
            if g.board.piece_at(sq) is None:
                squares.append(sq)
        g.spell_target_squares = squares
        g.spell_target_rgb = rgb or (160, 80, 255)

    def _set_spell_targets_meteor_quadrant(self) -> None:
        g = self.g
        is_on_side = g.powers.is_on_player_side
        rgb = self._get_spell_rgb("Meteor Shower")
        g.spell_target_squares = [sq for sq in chess.SQUARES if is_on_side(sq)]
        g.spell_target_rgb = rgb or (255, 80, 80)