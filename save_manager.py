from __future__ import annotations

import json
import os
from datetime import datetime

import chess
import pygame
import config


class SaveManager:
    CURRENT_VERSION = 1

    def __init__(self, game, save_dir="saves"):
        self.g = game
        self.save_dir = save_dir

    def slot_path(self, slot_id="slot_1"):
        return os.path.join(self.save_dir, f"{slot_id}.json")

    def save_slot(self, slot_id="slot_1"):
        os.makedirs(self.save_dir, exist_ok=True)
        path = self.slot_path(slot_id)
        tmp_path = f"{path}.tmp"
        data = self.build_save_dict(slot_id=slot_id)
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, sort_keys=True)
        os.replace(tmp_path, path)
        print(f"[SAVE] Saved {slot_id} to {path}")
        return path

    def load_slot(self, slot_id="slot_1"):
        path = self.slot_path(slot_id)
        if not os.path.exists(path):
            print(f"[SAVE] No save file found at {path}")
            return False
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        data = self._migrate(data)
        self.apply_save_dict(data)
        print(f"[SAVE] Loaded {slot_id} from {path}")
        return True

    def build_save_dict(self, slot_id="slot_1"):
        g = self.g
        mode = getattr(g, "current_game_mode", None)
        if mode is None:
            mode = "combat" if getattr(g, "main_game_screen", False) or getattr(g, "spellbook_open", False) else "overworld"

        return {
            "schema_version": self.CURRENT_VERSION,
            "saved_at": datetime.now().isoformat(timespec="seconds"),
            "slot_id": slot_id,
            "mode": {
                "primary": mode,
                "submode": self._submode(),
            },
            "campaign": self._campaign_dict(),
            "world": self._world_dict(),
            "combat": self._combat_dict(),
            "quests": self._quests_dict(),
            "inventory": self._inventory_dict(),
            "spells": self._spells_dict(),
            "gear": self._gear_dict(),
            "map_challenges": self._map_challenges_dict(),
            "pending_actions": self._pending_actions_dict(),
        }

    def apply_save_dict(self, data):
        g = self.g

        self._apply_campaign(data.get("campaign", {}))
        self._apply_world(data.get("world", {}))

        mode = data.get("mode", {}).get("primary", "combat")
        g.current_game_mode = mode

        self._apply_inventory(data.get("inventory", {}))
        self._apply_spells(data.get("spells", {}))
        self._apply_gear(data.get("gear", {}))
        self._apply_combat(data.get("combat", {}))
        self._apply_quests(data.get("quests", {}))
        self._apply_map_challenges(data.get("map_challenges", {}))
        self._apply_pending_actions(data.get("pending_actions", {}))
        self._rebuild_after_load(mode)

    def _migrate(self, data):
        version = int(data.get("schema_version", 0))
        if version == self.CURRENT_VERSION:
            return data
        if version == 0:
            data["schema_version"] = 1
            return data
        raise ValueError(f"Unsupported save schema version: {version}")

    def _submode(self):
        g = self.g
        if getattr(g, "spellbook_open", False):
            return "spellbook"
        if getattr(getattr(g, "menu", None), "is_open", False):
            return "menu"
        return "main_board" if getattr(g, "main_game_screen", False) else "overworld"

    def _campaign_dict(self):
        g = self.g
        return {
            "player_gold": int(getattr(g, "player_gold", 0)),
            "player_army_fen": getattr(g, "player_army_fen", "PPPPPPPP/RNBQKBNR"),
            "player_set": getattr(g, "player_set", 0),
            "player_wins": int(getattr(g, "player_wins", 0)),
            "player_losses": int(getattr(g, "player_losses", 0)),
            "player_stalemates": int(getattr(g, "player_stalemates", 0)),
            "difficulty_index": getattr(g, "difficulty_index", None),
            "stockfish_level": getattr(g, "stockfish_level", None),
            "current_stockfish_level": getattr(g, "current_stockfish_level", None),
            "gold_per_unit": getattr(g, "gold_per_unit", None),
        }

    def _world_dict(self):
        world = getattr(self.g, "world", None)
        if world is None:
            return {}
        cells = []
        for pos, cell in getattr(world, "world_data", {}).items():
            x, y = pos
            out = dict(cell)
            out["pos"] = [x, y]
            cells.append(out)
        return {
            "player_pos": list(getattr(world, "player_pos", (0, 3))),
            "current_year": getattr(world, "current_year", 1065),
            "current_month_index": getattr(world, "current_month_index", 5),
            "bank_balance": getattr(world, "bank_balance", 0),
            "bank_interest_rate": getattr(world, "bank_interest_rate", 0.05),
            "tax_office_balance": getattr(world, "tax_office_balance", 0),
            "tax_office_income_per_month": getattr(world, "tax_office_income_per_month", 0),
            "tax_office_bonus": getattr(world, "tax_office_bonus", 0.0),
            "army_cost_per_unit": getattr(world, "army_cost_per_unit", 1),
            "world_data": cells,
        }

    def _combat_dict(self):
        g = self.g
        board = getattr(g, "board", chess.Board())
        return {
            "board_fen": board.fen(),
            "player_side": getattr(g, "player_side", "white"),
            "turns": int(getattr(g, "turns", 0)),
            "completed_turns": int(getattr(g, "completed_turns", 0)),
            "current_state_wins": int(getattr(g, "current_state_wins", 0)),
            "current_state_losses": int(getattr(g, "current_state_losses", 0)),
            "move_history": list(getattr(g, "move_history", [])),
            "gold_pieces": self._square_list(getattr(g, "gold_pieces", set())),
            "frozen_squares": self._square_dict(getattr(g, "frozen_squares", {})),
            "shielded_squares": self._square_dict(getattr(g, "shielded_squares", {})),
            "magnet_square": self._square_or_none(getattr(g, "magnet_square", None)),
            "boulder_squares": self._square_list(getattr(g, "boulder_squares", set())),
            "lost_pieces": self._piece_list(getattr(g, "lost_pieces", [])),
            "enemy_lost_pieces": self._piece_list(getattr(g, "enemy_lost_pieces", [])),
            "powers_unlocked": bool(getattr(g, "powers_unlocked", False)),
            "enemy_rage_quits": bool(getattr(g, "ENEMY_RAGE_QUITS", False)),
            "advanced_shield_kit": bool(getattr(g, "advanced_shield_kit", False)),
        }

    def _quests_dict(self):
        q = getattr(self.g, "quests", None)
        if q is None:
            return {}
        return {
            "active_quests": list(getattr(q, "active_quests", [])),
            "quest_candidates": list(getattr(q, "quest_candidates", [])) if hasattr(q, "quest_candidates") else [],
            "quest_status": dict(getattr(q, "quest_status", {})),
            "runtime": {
                "checked_files_seen": sorted(getattr(q, "checked_files_seen", set())),
                "last_piece_moved_square": self._square_or_none(getattr(q, "last_piece_moved_square", None)),
                "same_piece_move_streak": getattr(q, "same_piece_move_streak", 0),
                "enemy_non_pawn_streak": getattr(q, "enemy_non_pawn_streak", 0),
                "last_captured_piece_type": getattr(q, "last_captured_piece_type", None),
                "rank_8_race_status": getattr(q, "rank_8_race_status", None),
                "king_adjacent_streak": getattr(q, "king_adjacent_streak", 0),
                "moved_pawn_squares": self._square_list(getattr(q, "moved_pawn_squares", set())),
                "moved_knight_squares": self._square_list(getattr(q, "moved_knight_squares", set())),
                "moved_bishop_squares": self._square_list(getattr(q, "moved_bishop_squares", set())),
                "moved_rook_squares": self._square_list(getattr(q, "moved_rook_squares", set())),
                "moved_queen_squares": self._square_list(getattr(q, "moved_queen_squares", set())),
                "moved_king_squares": self._square_list(getattr(q, "moved_king_squares", set())),
                "player_has_promoted": getattr(q, "player_has_promoted", False),
                "last_player_move_was_capture": getattr(q, "last_player_move_was_capture", False),
                "unbroken_diagonals": self._diagonals_to_save(getattr(q, "unbroken_diagonals", {})),
                "longest_unbroken_diagonal_streak": getattr(q, "longest_unbroken_diagonal_streak", 0),
                "last_moved_to_square": self._square_or_none(getattr(q, "last_moved_to_square", None)),
                "same_piece_type_streak": getattr(q, "same_piece_type_streak", 0),
                "last_piece_type": getattr(q, "last_piece_type", None),
                "swap_used_this_turn": getattr(q, "swap_used_this_turn", False),
                "last_enemy_capture_type": getattr(q, "last_enemy_capture_type", None),
                "eye_for_eye_pending": getattr(q, "eye_for_eye_pending", False),
                "eye_for_eye_target_square": self._square_or_none(getattr(q, "eye_for_eye_target_square", None)),
                "eye_for_eye_attacker_type": getattr(q, "eye_for_eye_attacker_type", None),
                "eye_for_eye_victim_type": getattr(q, "eye_for_eye_victim_type", None),
                "player_starting_squares": self._starting_squares_to_save(getattr(q, "player_starting_squares", set())),
            },
            "reward_flags": {
                "enable_checkmate_teleport": getattr(q, "enable_checkmate_teleport", False),
                "enable_reflective_shield": getattr(q, "enable_reflective_shield", False),
                "enable_empowered_freeze": getattr(q, "enable_empowered_freeze", False),
                "set_outer_pawns_as_rooks": getattr(q, "set_outer_pawns_as_rooks", False),
                "enable_knightmare_mode": getattr(q, "enable_knightmare_mode", False),
                "end_board_effects": getattr(q, "end_board_effects", False),
                "enable_poisoned_pawns": getattr(q, "enable_poisoned_pawns", False),
                "enable_no_future_rooks": getattr(q, "enable_no_future_rooks", False),
            },
        }

    def _inventory_dict(self):
        g = self.g
        return {
            "powerups": dict(getattr(g, "powerups", {})),
            "advanced_shield_kit": bool(getattr(g, "advanced_shield_kit", False)),
        }

    def _spells_dict(self):
        g = self.g
        return {
            "spellbook_master": list(getattr(g, "spellbook_master", [])),
            "spellbook": list(getattr(g, "spellbook", [])),
            "spellbook_open": bool(getattr(g, "spellbook_open", False)),
        }

    def _gear_dict(self):
        g = self.g
        gear = getattr(g, "gear", None)
        return {
            "gear": dict(getattr(gear, "gear", {})) if gear else {},
            "gear_owned": list(getattr(g, "gear_owned", [])),
            "gear_slots": dict(getattr(g, "gear_slots", {})),
            "gear_key_unlocked": bool(getattr(gear, "gear_key_unlocked", False)) if gear else False,
        }

    def _map_challenges_dict(self):
        mc = getattr(self.g, "map_challenges", None)
        if mc is None:
            return {}
        return {
            "board_effects_active": bool(getattr(mc, "board_effects_active", True)),
            "lava_row_active": bool(getattr(mc, "_lava_row_active", False)),
            "lava_row_index": getattr(mc, "_lava_row_index", None),
            "lava_row_counter": getattr(mc, "_lava_row_counter", 0),
            "stalker_square": self._square_or_none(getattr(mc, "_stalker_square", None)),
            "stalker_cooldown": getattr(mc, "_stalker_cooldown", 0),
            "astral_gate_held": getattr(mc, "astral_gate_held", None),
        }

    def _pending_actions_dict(self):
        g = self.g
        return {
            "selected_square": self._square_or_none(getattr(g, "selected_square", None)),
            "selected_power": getattr(g, "selected_power", None),
            "selected_spell": getattr(g, "selected_spell", None),
            "swap_selected_square": self._square_or_none(getattr(g, "swap_selected_square", None)),
            "swap_highlight_squares": self._square_list(getattr(g, "swap_highlight_squares", set())),
            "gear_pending_action": getattr(getattr(g, "gear", None), "pending_action", None),
            "wall_of_flame_active": bool(getattr(g, "wall_of_flame_active", False)),
            "shadow_step_active": bool(getattr(g, "shadow_step_active", False)),
            "meteor_active": bool(getattr(g, "meteor_active", False)),
            "meteor_quadrant": getattr(g, "meteor_quadrant", None),
            "spell_target_squares": self._square_list(getattr(g, "spell_target_squares", [])),
            "spell_target_rgb": getattr(g, "spell_target_rgb", None),
        }

    def _apply_campaign(self, data):
        g = self.g
        g.player_gold = int(data.get("player_gold", getattr(g, "player_gold", 0)))
        g.player_army_fen = data.get("player_army_fen", getattr(g, "player_army_fen", "PPPPPPPP/RNBQKBNR"))
        g.player_set = data.get("player_set", getattr(g, "player_set", 0))
        g.player_wins = int(data.get("player_wins", 0))
        g.player_losses = int(data.get("player_losses", 0))
        g.player_stalemates = int(data.get("player_stalemates", 0))
        if data.get("difficulty_index") is not None:
            g.difficulty_index = data["difficulty_index"]
        if data.get("stockfish_level") is not None:
            g.stockfish_level = data["stockfish_level"]
        if data.get("current_stockfish_level") is not None:
            g.current_stockfish_level = data["current_stockfish_level"]
        if data.get("gold_per_unit") is not None:
            g.gold_per_unit = data["gold_per_unit"]

    def _apply_world(self, data):
        world = getattr(self.g, "world", None)
        if world is None or not data:
            return
        world.player_pos = tuple(data.get("player_pos", getattr(world, "player_pos", (0, 3))))
        world.current_year = data.get("current_year", getattr(world, "current_year", 1065))
        world.current_month_index = data.get("current_month_index", getattr(world, "current_month_index", 5))
        world.bank_balance = data.get("bank_balance", getattr(world, "bank_balance", 0))
        world.bank_interest_rate = data.get("bank_interest_rate", getattr(world, "bank_interest_rate", 0.05))
        world.tax_office_balance = data.get("tax_office_balance", getattr(world, "tax_office_balance", 0))
        world.tax_office_income_per_month = data.get("tax_office_income_per_month", getattr(world, "tax_office_income_per_month", 0))
        world.tax_office_bonus = data.get("tax_office_bonus", getattr(world, "tax_office_bonus", 0.0))
        world.army_cost_per_unit = data.get("army_cost_per_unit", getattr(world, "army_cost_per_unit", 1))
        cells = data.get("world_data", [])
        if cells:
            world.world_data = {}
            for cell in cells:
                pos = tuple(cell["pos"])
                out = dict(cell)
                out.pop("pos", None)
                out.setdefault("building", None)
                out.setdefault("visits", 0)
                out.setdefault("lose", 0)
                out.setdefault("win", False)
                out.setdefault("state", "new")
                world.world_data[pos] = out

    def _apply_combat(self, data):
        g = self.g
        fen = data.get("board_fen")
        if fen:
            g.board = chess.Board(fen)
        g.player_side = data.get("player_side", getattr(g, "player_side", "white"))
        g.turns = int(data.get("turns", 0))
        g.completed_turns = int(data.get("completed_turns", 0))
        g.current_state_wins = int(data.get("current_state_wins", 0))
        g.current_state_losses = int(data.get("current_state_losses", 0))
        g.move_history = list(data.get("move_history", []))
        g.gold_pieces = set(self._squares_from_list(data.get("gold_pieces", [])))
        g.frozen_squares = self._square_dict_from_save(data.get("frozen_squares", {}))
        g.shielded_squares = self._square_dict_from_save(data.get("shielded_squares", {}))
        g.magnet_square = self._square_from_any(data.get("magnet_square"))
        g.boulder_squares = set(self._squares_from_list(data.get("boulder_squares", [])))
        g.lost_pieces = self._pieces_from_list(data.get("lost_pieces", []))
        g.enemy_lost_pieces = self._pieces_from_list(data.get("enemy_lost_pieces", []))
        g.powers_unlocked = bool(data.get("powers_unlocked", False))
        g.ENEMY_RAGE_QUITS = bool(data.get("enemy_rage_quits", False))
        g.advanced_shield_kit = bool(data.get("advanced_shield_kit", getattr(g, "advanced_shield_kit", False)))

    def _apply_quests(self, data):
        q = getattr(self.g, "quests", None)
        if q is None or not data:
            return
        q.active_quests = list(data.get("active_quests", []))
        q.quest_candidates = list(data.get("quest_candidates", []))
        if not q.quest_candidates:
            q.quest_candidates = list(q.active_quests)
        q.quest_status = dict(data.get("quest_status", {}))
        runtime = data.get("runtime", {})
        q.checked_files_seen = set(runtime.get("checked_files_seen", []))
        q.last_piece_moved_square = self._square_from_any(runtime.get("last_piece_moved_square"))
        q.same_piece_move_streak = runtime.get("same_piece_move_streak", 0)
        q.enemy_non_pawn_streak = runtime.get("enemy_non_pawn_streak", 0)
        q.last_captured_piece_type = runtime.get("last_captured_piece_type")
        q.rank_8_race_status = runtime.get("rank_8_race_status")
        q.king_adjacent_streak = runtime.get("king_adjacent_streak", 0)
        q.moved_pawn_squares = set(self._squares_from_list(runtime.get("moved_pawn_squares", [])))
        q.moved_knight_squares = set(self._squares_from_list(runtime.get("moved_knight_squares", [])))
        q.moved_bishop_squares = set(self._squares_from_list(runtime.get("moved_bishop_squares", [])))
        q.moved_rook_squares = set(self._squares_from_list(runtime.get("moved_rook_squares", [])))
        q.moved_queen_squares = set(self._squares_from_list(runtime.get("moved_queen_squares", [])))
        q.moved_king_squares = set(self._squares_from_list(runtime.get("moved_king_squares", [])))
        q.player_has_promoted = runtime.get("player_has_promoted", False)
        q.last_player_move_was_capture = runtime.get("last_player_move_was_capture", False)
        q.unbroken_diagonals = self._diagonals_from_save(runtime.get("unbroken_diagonals", []))
        q.longest_unbroken_diagonal_streak = runtime.get("longest_unbroken_diagonal_streak", 0)
        q.last_moved_to_square = self._square_from_any(runtime.get("last_moved_to_square"))
        q.same_piece_type_streak = runtime.get("same_piece_type_streak", 0)
        q.last_piece_type = runtime.get("last_piece_type")
        q.swap_used_this_turn = runtime.get("swap_used_this_turn", False)
        q.last_enemy_capture_type = runtime.get("last_enemy_capture_type")
        q.eye_for_eye_pending = runtime.get("eye_for_eye_pending", False)
        q.eye_for_eye_target_square = self._square_from_any(runtime.get("eye_for_eye_target_square"))
        q.eye_for_eye_attacker_type = runtime.get("eye_for_eye_attacker_type")
        q.eye_for_eye_victim_type = runtime.get("eye_for_eye_victim_type")
        q.player_starting_squares = self._starting_squares_from_save(runtime.get("player_starting_squares", []))
        for key, value in data.get("reward_flags", {}).items():
            setattr(q, key, value)

    def _apply_inventory(self, data):
        g = self.g
        saved = dict(data.get("powerups", {}))
        if saved:
            for key in getattr(g, "powerups", {}).keys():
                g.powerups[key] = int(saved.get(key, 0))
            for key, value in saved.items():
                if key not in g.powerups:
                    g.powerups[key] = int(value)
        g.advanced_shield_kit = bool(data.get("advanced_shield_kit", getattr(g, "advanced_shield_kit", False)))

    def _apply_spells(self, data):
        g = self.g
        g.spellbook_master = list(data.get("spellbook_master", getattr(g, "spellbook_master", [])))
        g.spellbook = list(data.get("spellbook", getattr(g, "spellbook", [])))
        g.spellbook_open = bool(data.get("spellbook_open", False))
        g._spell_cache_dirty = True
        g.cached_spell_availability = {}

    def _apply_gear(self, data):
        g = self.g
        gear = getattr(g, "gear", None)
        if gear is not None:
            saved_gear = dict(data.get("gear", {}))
            for key in gear.gear.keys():
                gear.gear[key] = int(saved_gear.get(key, 0))
            for key, value in saved_gear.items():
                if key not in gear.gear:
                    gear.gear[key] = int(value)
            gear.gear_key_unlocked = bool(data.get("gear_key_unlocked", getattr(gear, "gear_key_unlocked", False)))
        g.gear_owned = list(data.get("gear_owned", getattr(g, "gear_owned", [])))
        g.gear_slots = dict(data.get("gear_slots", getattr(g, "gear_slots", {})))

    def _apply_map_challenges(self, data):
        mc = getattr(self.g, "map_challenges", None)
        if mc is None:
            return
        mc.board_effects_active = bool(data.get("board_effects_active", True))
        mc._lava_row_active = bool(data.get("lava_row_active", False))
        mc._lava_row_index = data.get("lava_row_index")
        mc._lava_row_counter = data.get("lava_row_counter", 0)
        mc._stalker_square = self._square_from_any(data.get("stalker_square"))
        mc._stalker_cooldown = data.get("stalker_cooldown", 0)
        mc.astral_gate_held = data.get("astral_gate_held")

    def _apply_pending_actions(self, data):
        g = self.g
        g.selected_square = self._square_from_any(data.get("selected_square"))
        g.selected_power = data.get("selected_power")
        g.selected_spell = data.get("selected_spell")
        g.swap_selected_square = self._square_from_any(data.get("swap_selected_square"))
        g.swap_highlight_squares = set(self._squares_from_list(data.get("swap_highlight_squares", [])))
        if getattr(g, "gear", None) is not None:
            g.gear.pending_action = data.get("gear_pending_action")
        g.wall_of_flame_active = bool(data.get("wall_of_flame_active", False))
        g.shadow_step_active = bool(data.get("shadow_step_active", False))
        g.meteor_active = bool(data.get("meteor_active", False))
        g.meteor_quadrant = data.get("meteor_quadrant")
        g.spell_target_squares = self._squares_from_list(data.get("spell_target_squares", []))
        g.spell_target_rgb = data.get("spell_target_rgb")

    def _rebuild_after_load(self, mode):
        g = self.g
        stage = 0
        try:
            stage = g.world.world_data[g.world.player_pos]["stage_id"]
        except Exception:
            pass

        try:
            g.background_image = g.assets.load_background_image(stage)
            if hasattr(g, "_bg_scaled"):
                del g._bg_scaled
        except Exception as exc:
            print(f"[SAVE] Background rebuild skipped: {exc}")

        try:
            g.portrait_img = g.assets.load_portrait_image(stage)
            g.PIECE_IMAGES = g.assets.load_piece_images()
        except Exception as exc:
            print(f"[SAVE] Piece/portrait rebuild skipped: {exc}")

        g.gold_icons = {}
        if getattr(g, "gold_coins", None):
            icon = g.gold_coins[0]
            for sq in getattr(g, "gold_pieces", set()):
                g.gold_icons[sq] = icon
        g.landed_gold_pieces = set(getattr(g, "gold_pieces", set()))

        g.active_effects = {}
        if getattr(g, "effects", None):
            try:
                g.effects.psys.emitters.clear()
                g.effects.psys.particles.clear()
            except Exception:
                pass
        if getattr(g, "quest_reward_handler", None):
            g.quest_reward_handler.clear_reward_queue()

        g.hard_pause_start_time = None
        g.hard_pause_callback = None
        g.click_pause_active = False
        g.click_pause_callback = None
        if getattr(g, "menu", None):
            g.menu.is_open = False
        if getattr(g, "renderer", None):
            r = g.renderer
            for attr, value in {
                "feedback_text": "",
                "feedback_frame_counter": 0,
                "feedback_waiting_for_click": False,
                "gamestate_display_active": False,
                "enemy_dialog_text": "",
                "enemy_dialog_timer": 0,
                "enemy_dialog_alpha": 0,
            }.items():
                if hasattr(r, attr):
                    setattr(r, attr, value)

        g.current_game_mode = mode
        g.main_game_screen = (mode == "combat")
        if mode != "combat":
            g.selected_square = None
            g.selected_power = None
            g.selected_spell = None
            g.spellbook_open = False
        elif getattr(g, "selected_square", None) is not None:
            try:
                g.board_manager.update_allowed_moves()
            except Exception:
                g.possible_moves = []
        else:
            g.possible_moves = []

        self._rebuild_quest_cards()

        try:
            if getattr(g, "engine", None) and getattr(g, "current_stockfish_level", None) is not None:
                g.engine.configure({"Skill Level": int(g.current_stockfish_level)})
        except Exception as exc:
            print(f"[SAVE] Engine difficulty restore skipped: {exc}")

    def _rebuild_quest_cards(self):
        q = getattr(self.g, "quests", None)
        if q is None:
            return

        candidates = list(getattr(q, "quest_candidates", []))
        if not candidates:
            candidates = list(getattr(q, "active_quests", []))
            q.quest_candidates = candidates

        q.quest_cards = []
        q.card_rects = []
        q.continue_rect = None
        q.quest_selection_done = True
        q.show_continue_button = False
        q.hovered_card_index = None
        q.quest_card_hovered = False

        if not candidates:
            q.original_card_size = (0, 0)
            q.card_hover_scales = []
            return

        try:
            from quest_cards import CreateQuestCard

            rebuilt_candidates = []
            for qid in candidates:
                try:
                    card = CreateQuestCard(qid)
                    width, height = card.get_size()
                    q.original_card_size = (width, height)
                    scaled = pygame.transform.smoothscale(
                        card,
                        (int(width * config.CARD_SCALE_EXPAND), int(height * config.CARD_SCALE_EXPAND)),
                    )
                    q.quest_cards.append(scaled)
                    rebuilt_candidates.append(qid)
                except Exception as exc:
                    print(f"[SAVE] Quest card rebuild skipped for quest {qid}: {exc}")
            q.quest_candidates = rebuilt_candidates
            q.card_hover_scales = [config.CARD_SCALE] * len(q.quest_cards)
        except Exception as exc:
            print(f"[SAVE] Quest card rebuild failed: {exc}")
            q.quest_candidates = []
            q.quest_cards = []
            q.original_card_size = (0, 0)
            q.card_hover_scales = []

    def _square_or_none(self, square):
        if square is None:
            return None
        try:
            return chess.square_name(int(square))
        except Exception:
            return None

    def _square_from_any(self, value):
        if value is None:
            return None
        if isinstance(value, int):
            return value if 0 <= value < 64 else None
        try:
            return chess.parse_square(value)
        except Exception:
            return None

    def _square_list(self, squares):
        return sorted(
            chess.square_name(int(sq))
            for sq in squares
            if sq is not None and 0 <= int(sq) < 64
        )

    def _squares_from_list(self, values):
        out = []
        for value in values or []:
            sq = self._square_from_any(value)
            if sq is not None:
                out.append(sq)
        return out

    def _square_dict(self, mapping):
        return {
            chess.square_name(int(square)): value
            for square, value in dict(mapping).items()
            if square is not None and 0 <= int(square) < 64
        }

    def _square_dict_from_save(self, mapping):
        out = {}
        for key, value in dict(mapping or {}).items():
            sq = self._square_from_any(key)
            if sq is not None:
                out[sq] = value
        return out

    def _piece_list(self, pieces):
        out = []
        for piece in pieces:
            if isinstance(piece, chess.Piece):
                out.append(piece.symbol())
            elif isinstance(piece, str):
                out.append(piece)
        return out

    def _pieces_from_list(self, values):
        pieces = []
        for value in values or []:
            try:
                pieces.append(chess.Piece.from_symbol(value))
            except Exception:
                pass
        return pieces

    def _diagonals_to_save(self, diagonals):
        out = []
        for squares, streak in dict(diagonals).items():
            out.append({"squares": self._square_list(squares), "streak": streak})
        return out

    def _diagonals_from_save(self, values):
        out = {}
        for item in values or []:
            squares = tuple(self._squares_from_list(item.get("squares", [])))
            out[squares] = item.get("streak", 0)
        return out

    def _starting_squares_to_save(self, values):
        out = []
        for square, piece_type in values or []:
            out.append({"square": self._square_or_none(square), "piece_type": piece_type})
        return out

    def _starting_squares_from_save(self, values):
        out = set()
        for item in values or []:
            sq = self._square_from_any(item.get("square"))
            if sq is not None:
                out.add((sq, item.get("piece_type")))
        return out
