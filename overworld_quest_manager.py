from __future__ import annotations

import json
import os
from copy import deepcopy


class OverworldQuestManager:
    def __init__(self, game, data_path="data/overworld_quests.json"):
        self.g = game
        self.data_path = data_path
        self.quest_defs = {}
        self.available = set()
        self.active = {}
        self.completed = set()
        self.failed = set()
        self.expired = set()
        self.story_flags = set()
        self.dialog_choices = {}
        self.history = []
        self.load_all_quests()

    def load_all_quests(self):
        if not os.path.exists(self.data_path):
            self.quest_defs = {}
            return
        with open(self.data_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        quests = data.get("quests", data if isinstance(data, list) else [])
        self.quest_defs = {
            quest["id"]: quest
            for quest in quests
            if isinstance(quest, dict) and quest.get("id")
        }
        self.refresh_available()

    def refresh_available(self):
        for quest_id, quest in self.quest_defs.items():
            if quest_id in self.active:
                continue
            if quest_id in self.completed or quest_id in self.failed or quest_id in self.expired:
                continue
            if self._conditions_met(quest.get("availability", {})):
                self.available.add(quest_id)
            else:
                self.available.discard(quest_id)

    def start_quest(self, quest_id):
        quest = self.quest_defs.get(quest_id)
        if not quest or quest_id in self.active:
            return False
        if quest_id not in self.available and not self._conditions_met(quest.get("availability", {})):
            return False

        self.active[quest_id] = {
            "step": quest.get("first_step") or self._first_step_id(quest),
            "started_at": self._current_time_marker(),
            "current_location": self._current_location_label(),
            "vars": {},
            "choices": [],
            "completed_board_objectives": [],
        }
        self.available.discard(quest_id)
        self._apply_effects(quest.get("start", {}), quest_id)
        self.history.append({"quest_id": quest_id, "event": "started", "time": self._current_time_marker()})
        return True

    def fail_quest(self, quest_id, reason="failed"):
        if quest_id not in self.active:
            return False
        self.active.pop(quest_id, None)
        self.failed.add(quest_id)
        self.history.append({
            "quest_id": quest_id,
            "event": "failed",
            "reason": reason,
            "location": self._current_location_label(),
            "time": self._current_time_marker(),
        })
        return True

    def complete_quest(self, quest_id, outcome_id=None):
        if quest_id not in self.active:
            return False
        quest = self.quest_defs.get(quest_id, {})
        outcome = (quest.get("outcomes") or {}).get(outcome_id or "", {})
        self._apply_effects(outcome, quest_id)
        self.active.pop(quest_id, None)
        self.completed.add(quest_id)
        self.history.append({
            "quest_id": quest_id,
            "event": "completed",
            "outcome": outcome_id,
            "location": self._current_location_label(),
            "time": self._current_time_marker(),
        })
        return True

    def on_month_advanced(self):
        expired = []
        for quest_id, state in list(self.active.items()):
            quest = self.quest_defs.get(quest_id, {})
            timer = quest.get("timer", {})
            months = timer.get("months")
            if months is None:
                continue
            if self._months_since(state.get("started_at", {})) >= int(months):
                expired.append(quest_id)

        for quest_id in expired:
            self.active.pop(quest_id, None)
            self.expired.add(quest_id)
            self.failed.add(quest_id)
            self.history.append({
                "quest_id": quest_id,
                "event": "expired",
                "location": self._current_location_label(),
                "time": self._current_time_marker(),
            })
            self._notify(f"Quest expired: {self.quest_name(quest_id)}")

        self.refresh_available()

    def on_location_changed(self):
        for state in self.active.values():
            state["current_location"] = self._current_location_label()
        self.refresh_available()
        for quest_id, state in list(self.active.items()):
            quest = self.quest_defs.get(quest_id, {})
            step = self._step_by_id(quest, state.get("step"))
            if step.get("type") == "dialog" and any(self._choice_available(choice) for choice in step.get("choices", [])):
                self.present_conditional_dialog(quest_id)

    def choose_dialog_option(self, quest_id, choice_id):
        quest = self.quest_defs.get(quest_id)
        state = self.active.get(quest_id)
        if not quest or not state:
            return False

        step = self._step_by_id(quest, state.get("step"))
        choice = self._choice_by_id(step, choice_id)
        if not choice or not self._conditions_met(choice.get("requires", {})):
            return False

        costs = choice.get("costs", {})
        if not self._can_pay(costs):
            return False
        self._pay(costs)

        self.dialog_choices.setdefault(quest_id, []).append(choice_id)
        state.setdefault("choices", []).append(choice_id)
        self._apply_effects(choice, quest_id)

        if choice.get("next_step"):
            state["step"] = choice["next_step"]
        if choice.get("fail"):
            return self.fail_quest(quest_id, reason=choice_id)
        if choice.get("complete"):
            return self.complete_quest(quest_id, outcome_id=choice.get("outcome"))
        if choice.get("outcome"):
            outcome = (quest.get("outcomes") or {}).get(choice["outcome"], {})
            self._apply_effects(outcome, quest_id)
            if outcome.get("fail"):
                return self.fail_quest(quest_id, reason=choice["outcome"])
            if outcome.get("complete"):
                return self.complete_quest(quest_id, outcome_id=choice["outcome"])
        return True

    def present_conditional_dialog(self, quest_id):
        quest = self.quest_defs.get(quest_id)
        state = self.active.get(quest_id)
        if not quest or not state:
            return None

        step = self._step_by_id(quest, state.get("step"))
        choices = step.get("choices", [])
        if not choices:
            return None

        import pygame

        screen = getattr(self.g, "screen", None)
        if screen is None:
            return None

        pygame.font.init()
        title_font = pygame.font.SysFont(None, 34)
        body_font = pygame.font.SysFont(None, 26)
        clock = pygame.time.Clock()
        selected = None
        choice_rects = []

        while selected is None:
            mx, my = pygame.mouse.get_pos()
            for event in pygame.event.get():
                if event.type == pygame.QUIT:
                    return None
                if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                    return None
                if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                    for rect, choice in choice_rects:
                        if rect.collidepoint(mx, my) and self._choice_available(choice):
                            if self.choose_dialog_option(quest_id, choice.get("id")):
                                return choice.get("id")

            overlay = pygame.Surface(screen.get_size(), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 170))
            screen.blit(overlay, (0, 0))

            panel = pygame.Rect(0, 0, min(860, screen.get_width() - 120), min(520, screen.get_height() - 120))
            panel.center = screen.get_rect().center
            pygame.draw.rect(screen, (34, 32, 38), panel)
            pygame.draw.rect(screen, (220, 210, 180), panel, 2)

            title = title_font.render(quest.get("name", quest_id), True, (255, 255, 255))
            screen.blit(title, (panel.x + 24, panel.y + 22))

            step_name = body_font.render(step.get("name", state.get("step", "")), True, (230, 230, 230))
            screen.blit(step_name, (panel.x + 24, panel.y + 62))

            y = panel.y + 115
            choice_rects = []
            for choice in choices:
                available = self._choice_available(choice)
                rect = pygame.Rect(panel.x + 32, y, panel.width - 64, 46)
                choice_rects.append((rect, choice))
                color = (88, 76, 52) if available and rect.collidepoint(mx, my) else (58, 58, 64)
                if not available:
                    color = (48, 42, 45)
                pygame.draw.rect(screen, color, rect)
                pygame.draw.rect(screen, (160, 150, 125), rect, 1)
                text_color = (255, 255, 255) if available else (150, 135, 135)
                text = body_font.render(choice.get("text", choice.get("id", "Choice")), True, text_color)
                screen.blit(text, (rect.x + 14, rect.y + 12))
                y += 58

            pygame.display.flip()
            clock.tick(60)

        return selected

    def get_board_quest_definitions(self):
        stage_id = self._current_stage_id()
        if stage_id is None:
            return []

        cards = []
        for quest_id, state in self.active.items():
            quest = self.quest_defs.get(quest_id, {})
            step = self._step_by_id(quest, state.get("step"))
            for objective in step.get("board_objectives", []):
                if objective.get("stage_id") != stage_id:
                    continue
                card_id = objective.get("card_id") or f"owq:{quest_id}:{objective.get('id', len(cards))}"
                if card_id in state.get("completed_board_objectives", []):
                    continue
                card = deepcopy(objective.get("quest_card", {}))
                card.setdefault("quest_number", card_id)
                card.setdefault("source", "overworld")
                card.setdefault("overworld_quest_id", quest_id)
                card.setdefault("overworld_objective_id", objective.get("id"))
                card.setdefault("title", objective.get("title", quest.get("name", "Overworld Quest")))
                card.setdefault("rules", objective.get("rules", "Complete the story objective."))
                card.setdefault("feedback", [])
                card.setdefault("win_reward_pairs", objective.get("win_reward_pairs", []))
                cards.append(card)
        return cards

    def complete_board_objective(self, card_id):
        for quest_id, state in self.active.items():
            quest = self.quest_defs.get(quest_id, {})
            step = self._step_by_id(quest, state.get("step"))
            for objective in step.get("board_objectives", []):
                expected = objective.get("card_id") or f"owq:{quest_id}:{objective.get('id')}"
                if expected != card_id:
                    continue
                objective_id = objective.get("id")
                if objective_id:
                    state.setdefault("completed_board_objectives", []).append(expected)
                if objective.get("next_step"):
                    state["step"] = objective["next_step"]
                if objective.get("outcome"):
                    return self.complete_quest(quest_id, outcome_id=objective.get("outcome"))
                return True
        return False

    def active_summaries(self):
        return [self._summary(quest_id, state) for quest_id, state in self.active.items()]

    def failed_summaries(self):
        summaries = []
        for quest_id in sorted(self.failed):
            summaries.append({
                "id": quest_id,
                "name": self.quest_name(quest_id),
                "step": "Failed",
                "location": self._last_history_location(quest_id),
            })
        return summaries

    def quest_name(self, quest_id):
        return self.quest_defs.get(quest_id, {}).get("name", quest_id)

    def to_save_dict(self):
        return {
            "available": sorted(self.available),
            "active": deepcopy(self.active),
            "completed": sorted(self.completed),
            "failed": sorted(self.failed),
            "expired": sorted(self.expired),
            "story_flags": sorted(self.story_flags),
            "dialog_choices": deepcopy(self.dialog_choices),
            "history": deepcopy(self.history),
        }

    def apply_save_dict(self, data):
        if not data:
            self.refresh_available()
            return
        self.available = set(data.get("available", []))
        self.active = dict(data.get("active", {}))
        self.completed = set(data.get("completed", []))
        self.failed = set(data.get("failed", []))
        self.expired = set(data.get("expired", []))
        self.story_flags = set(data.get("story_flags", []))
        self.dialog_choices = dict(data.get("dialog_choices", {}))
        self.history = list(data.get("history", []))
        self.refresh_available()

    def _conditions_met(self, conditions):
        if not conditions:
            return True
        if isinstance(conditions, list):
            return all(self._condition_met(cond) for cond in conditions)
        if "all" in conditions:
            return all(self._condition_met(cond) for cond in conditions.get("all", []))
        if "any" in conditions:
            return any(self._condition_met(cond) for cond in conditions.get("any", []))
        return self._condition_met(conditions)

    def _condition_met(self, condition):
        ctype = condition.get("type")
        if ctype == "flag_present":
            return condition.get("flag") in self.story_flags
        if ctype == "flag_absent":
            return condition.get("flag") not in self.story_flags
        if ctype == "gold_at_least":
            return getattr(self.g, "player_gold", 0) >= int(condition.get("amount", 0))
        if ctype == "gear_owned":
            gear = getattr(self.g, "gear", None)
            return bool(gear and gear.has(condition.get("id")))
        if ctype == "quest_completed":
            return condition.get("quest_id") in self.completed
        if ctype == "quest_failed":
            return condition.get("quest_id") in self.failed
        if ctype == "current_stage":
            return self._current_stage_id() == condition.get("stage_id")
        if ctype == "area_state":
            return self._area_state_matches(condition)
        if ctype == "month_at_least":
            marker = self._current_time_marker()
            return self._month_number(marker) >= int(condition.get("value", 0))
        return False

    def _area_state_matches(self, condition):
        world = getattr(self.g, "world", None)
        if not world:
            return False
        stage_id = condition.get("stage_id")
        desired = condition.get("state")
        for cell in world.world_data.values():
            if cell.get("stage_id") != stage_id:
                continue
            if desired == "won":
                return bool(cell.get("win"))
            if desired == "lost":
                return cell.get("lose", 0) > 0 or cell.get("state") == "lost"
            if desired == "untouched":
                return not cell.get("win") and cell.get("lose", 0) == 0 and cell.get("visits", 0) == 0
            return cell.get("state") == desired
        return False

    def _apply_effects(self, data, quest_id):
        for flag in data.get("set_flags", []):
            self.story_flags.add(flag)
        for flag in data.get("clear_flags", []):
            self.story_flags.discard(flag)
        if data.get("story"):
            self._play_story(data["story"])

    def _play_story(self, story_id):
        story_mode = getattr(self.g, "story_mode", None)
        if not story_mode:
            return
        story_mode._refresh_story_player()
        raw = story_mode.story_player.play_story(story_id)
        story_mode._normalize_story_result_and_apply_rewards(raw, resolve_story_targets=True)

    def _can_pay(self, costs):
        return getattr(self.g, "player_gold", 0) >= int(costs.get("gold", 0))

    def _pay(self, costs):
        self.g.player_gold -= int(costs.get("gold", 0))

    def _first_step_id(self, quest):
        steps = quest.get("steps", [])
        return steps[0].get("id") if steps else None

    def _step_by_id(self, quest, step_id):
        for step in quest.get("steps", []):
            if step.get("id") == step_id:
                return step
        return {}

    def _choice_by_id(self, step, choice_id):
        for choice in step.get("choices", []):
            if choice.get("id") == choice_id:
                return choice
        return None

    def _choice_available(self, choice):
        return self._conditions_met(choice.get("requires", {})) and self._can_pay(choice.get("costs", {}))

    def _summary(self, quest_id, state):
        quest = self.quest_defs.get(quest_id, {})
        step = self._step_by_id(quest, state.get("step"))
        return {
            "id": quest_id,
            "name": quest.get("name", quest_id),
            "step": step.get("name") or state.get("step") or "Active",
            "location": state.get("current_location") or self._current_location_label(),
        }

    def _last_history_location(self, quest_id):
        for item in reversed(self.history):
            if item.get("quest_id") == quest_id:
                return item.get("location", "")
        return ""

    def _current_stage_id(self):
        world = getattr(self.g, "world", None)
        if not world:
            return None
        return world.world_data.get(world.player_pos, {}).get("stage_id")

    def _current_location_label(self):
        world = getattr(self.g, "world", None)
        if not world:
            return ""
        stage_id = self._current_stage_id()
        info = world.stage_info.get(stage_id, {})
        return info.get("name", f"Stage {stage_id}")

    def _current_time_marker(self):
        world = getattr(self.g, "world", None)
        return {
            "year": getattr(world, "current_year", 1065),
            "month_index": getattr(world, "current_month_index", 0),
        }

    def _month_number(self, marker):
        return int(marker.get("year", 0)) * 12 + int(marker.get("month_index", 0))

    def _months_since(self, marker):
        return self._month_number(self._current_time_marker()) - self._month_number(marker)

    def _notify(self, message):
        ui = getattr(self.g, "ui_state", None)
        if ui:
            ui.send_feedback(message)
        else:
            print(f"[OVERWORLD QUEST] {message}")
