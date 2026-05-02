from __future__ import annotations

import json
from typing import Any

import chess
import pygame

import config
import debug_actions
from debug_registry import DebugRegistry, DebugRegistryError


class DebugOverlay:
    """
    JSON-backed in-game debug panel.

    The overlay owns UI state only. Actual side effects are routed through
    debug_actions.py and value access is routed through DebugRegistry.
    """

    PANEL = pygame.Rect(38, 34, config.WIDTH - 76, config.HEIGHT - 68)
    TAB_H = 38
    ROW_H = 30
    PIECE_SYMBOLS = ["K", "Q", "R", "B", "N", "P", "k", "q", "r", "b", "n", "p"]

    def __init__(self, game):
        self.g = game
        self.registry = DebugRegistry(game)
        self.is_open = False
        self.active_tab = "game"
        self.scroll = 0
        self.message = ""
        self.message_timer = 0
        self.search_text = ""
        self.search_active = False
        self.selected_quest_num = None

        self.click_targets: list[tuple[pygame.Rect, tuple[Any, ...]]] = []
        self.board_rect = pygame.Rect(0, 0, 0, 0)
        self.tray_rect = pygame.Rect(0, 0, 0, 0)
        self.tray_items: list[dict[str, str]] = []
        self.tray_item_rects: list[tuple[pygame.Rect, int]] = []
        self.palette_rects: list[tuple[pygame.Rect, str]] = []
        self.dragging = None
        self.drag_pos = (0, 0)

        self.font = pygame.font.SysFont(None, 22)
        self.small_font = pygame.font.SysFont(None, 18)
        self.title_font = pygame.font.SysFont(None, 28)
        self.big_piece_font = pygame.font.SysFont(None, 32)

    def open(self):
        self.is_open = True
        self.scroll = 0
        self.search_active = False
        if getattr(self.g, "menu", None):
            self.g.menu.is_open = False
        self.set_message("Debug overlay opened.")

    def close(self):
        self.is_open = False
        self.dragging = None
        self.search_active = False
        self.set_message("Debug overlay closed.")

    def toggle(self):
        if self.is_open:
            self.close()
        else:
            self.open()

    def set_message(self, message: str):
        self.message = message
        self.message_timer = 180
        print(f"[DEBUG OVERLAY] {message}")

    def handle_event(self, event) -> bool:
        if not self.is_open:
            return False

        if event.type == pygame.KEYDOWN:
            if event.key in (pygame.K_ESCAPE, pygame.K_BACKQUOTE):
                self.close()
                return True
            if event.key == pygame.K_F5:
                self.registry.load()
                self.set_message("Registry reloaded.")
                return True
            if self.active_tab == "quests" and self.search_active:
                if event.key == pygame.K_BACKSPACE:
                    self.search_text = self.search_text[:-1]
                elif event.key == pygame.K_RETURN:
                    self.search_active = False
                elif event.unicode and event.unicode.isprintable():
                    self.search_text += event.unicode
                return True
            return True

        if event.type == pygame.MOUSEWHEEL:
            self.scroll = max(0, self.scroll - event.y * 36)
            return True

        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self._handle_mouse_down(event.pos)
            return True

        if event.type == pygame.MOUSEMOTION:
            if self.dragging:
                self.drag_pos = event.pos
            return True

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            self._handle_mouse_up(event.pos)
            return True

        return True

    def _handle_mouse_down(self, pos):
        self.search_active = False
        for rect, payload in self.click_targets:
            if rect.collidepoint(pos):
                self._activate_payload(payload)
                return

        if self.active_tab == "board":
            sq = self.square_at_pos(pos)
            if sq is not None:
                piece = self.g.board.piece_at(sq)
                if piece:
                    self.dragging = {"source": "board", "square": sq, "symbol": piece.symbol()}
                    self.drag_pos = pos
                    return
            for rect, index in self.tray_item_rects:
                if rect.collidepoint(pos) and 0 <= index < len(self.tray_items):
                    self.dragging = {"source": "tray", "index": index, **self.tray_items[index]}
                    self.drag_pos = pos
                    return
            for rect, symbol in self.palette_rects:
                if rect.collidepoint(pos):
                    self.dragging = {"source": "palette", "symbol": symbol}
                    self.drag_pos = pos
                    return

    def _handle_mouse_up(self, pos):
        if not self.dragging:
            return

        item = self.dragging
        self.dragging = None
        target_sq = self.square_at_pos(pos)

        if target_sq is not None:
            if item["source"] == "board":
                debug_actions.move_piece(self.g, item["square"], target_sq)
            elif item["source"] == "tray":
                replaced = debug_actions.place_piece_from_symbol(self.g, target_sq, item["symbol"])
                index = item.get("index")
                if isinstance(index, int) and 0 <= index < len(self.tray_items):
                    self.tray_items.pop(index)
                if replaced:
                    self.tray_items.append(replaced)
            elif item["source"] == "palette":
                replaced = debug_actions.place_piece_from_symbol(self.g, target_sq, item["symbol"])
                if replaced:
                    self.tray_items.append(replaced)
            return

        if self.tray_rect.collidepoint(pos) and item["source"] == "board":
            removed = debug_actions.remove_piece_to_tray(self.g, item["square"])
            if removed:
                self.tray_items.append(removed)
            return

        self.set_message("Drag cancelled.")

    def _activate_payload(self, payload):
        kind = payload[0]
        if kind == "tab":
            self.active_tab = payload[1]
            self.scroll = 0
            return
        if kind == "search":
            self.search_active = True
            return
        if kind == "select_quest":
            self.selected_quest_num = payload[1]
            return
        if kind == "quest_action":
            action_name, quest_num = payload[1], payload[2]
            try:
                result = debug_actions.run_action(self.g, action_name, quest_num=quest_num)
                if action_name == "validate_board" and result:
                    self.set_message("; ".join(result[:2]))
                else:
                    self.set_message(f"Ran {action_name}.")
            except Exception as exc:
                self.set_message(f"Action failed: {exc}")
            return
        if kind == "action":
            entry = payload[1]
            args = dict(entry.get("args") or {})
            if entry.get("action") == "clear_board_to_tray":
                args["tray"] = self.tray_items
            try:
                result = debug_actions.run_action(self.g, entry.get("action"), **args)
                if entry.get("action") == "validate_board" and result:
                    self.set_message("; ".join(result[:2]))
                else:
                    self.set_message(f"Ran {entry.get('label', entry.get('action'))}.")
            except Exception as exc:
                self.set_message(f"Action failed: {exc}")
            return
        if kind == "edit":
            entry, op, key = payload[1], payload[2], payload[3] if len(payload) > 3 else None
            self._edit_value(entry, op, key)

    def _edit_value(self, entry, op, key=None):
        try:
            current = self.registry.get_value(entry)
            type_name = entry.get("type")
            if type_name == "bool":
                self.registry.set_value(entry, not bool(current))
            elif type_name == "enum":
                options = entry.get("options") or []
                if options:
                    idx = options.index(current) if current in options else -1
                    self.registry.set_value(entry, options[(idx + 1) % len(options)])
            elif type_name in ("int", "float"):
                delta = 1 if op == "inc" else -1
                self.registry.set_value(entry, current + delta)
            elif type_name == "dict" and key is not None:
                edited = dict(current)
                val = edited.get(key, 0)
                if isinstance(val, bool):
                    edited[key] = not val
                elif isinstance(val, (int, float)):
                    edited[key] = val + (1 if op == "inc" else -1)
                else:
                    edited[key] = "" if val is not None else None
                self.registry.set_value(entry, edited)
            elif type_name == "list" and key is not None:
                edited = list(current)
                if 0 <= key < len(edited):
                    edited.pop(key)
                    self.registry.set_value(entry, edited)
            self.set_message(f"Updated {entry.get('label', entry.get('path'))}.")
        except Exception as exc:
            self.set_message(f"Edit failed: {exc}")

    def draw(self, screen):
        if not self.is_open:
            return

        self.click_targets = []
        dim = pygame.Surface((config.WIDTH, config.HEIGHT), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 145))
        screen.blit(dim, (0, 0))

        panel = pygame.Surface((self.PANEL.w, self.PANEL.h), pygame.SRCALPHA)
        panel.fill((22, 25, 31, 235))
        screen.blit(panel, self.PANEL.topleft)
        pygame.draw.rect(screen, (150, 170, 210), self.PANEL, 2, border_radius=8)

        title = self.title_font.render("Debug Overlay", True, (245, 248, 255))
        screen.blit(title, (self.PANEL.x + 18, self.PANEL.y + 10))
        hint = self.small_font.render("~ or Escape closes. F5 reloads JSON registry.", True, (185, 195, 215))
        screen.blit(hint, (self.PANEL.right - hint.get_width() - 18, self.PANEL.y + 15))

        self._draw_tabs(screen)

        content = pygame.Rect(self.PANEL.x + 18, self.PANEL.y + 72, self.PANEL.w - 36, self.PANEL.h - 92)
        if self.active_tab == "quests":
            self._draw_quests_tab(screen, content)
        elif self.active_tab == "board":
            self._draw_board_tab(screen, content)
        else:
            self._draw_registry_tab(screen, content, self.active_tab)

        if self.registry.errors:
            err = self.small_font.render(f"Registry warnings: {len(self.registry.errors)}", True, (255, 190, 120))
            screen.blit(err, (self.PANEL.x + 20, self.PANEL.bottom - 26))

        if self.message and self.message_timer > 0:
            self.message_timer -= 1
            msg = self.small_font.render(self.message[:110], True, (255, 235, 150))
            screen.blit(msg, (self.PANEL.x + 190, self.PANEL.bottom - 26))

        if self.dragging:
            self._draw_piece_symbol(screen, self.dragging["symbol"], self.drag_pos[0] - 12, self.drag_pos[1] - 14)

    def _draw_tabs(self, screen):
        x = self.PANEL.x + 18
        y = self.PANEL.y + 42
        for tab in self.registry.tabs:
            label = tab.get("label", tab.get("id", "?"))
            rect = pygame.Rect(x, y, 118, self.TAB_H - 6)
            active = tab.get("id") == self.active_tab
            color = (68, 88, 122) if active else (38, 45, 58)
            pygame.draw.rect(screen, color, rect, border_radius=6)
            pygame.draw.rect(screen, (115, 135, 170), rect, 1, border_radius=6)
            txt = self.font.render(label, True, (245, 248, 255))
            screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.y + 7))
            self.click_targets.append((rect, ("tab", tab.get("id"))))
            x += rect.w + 8

    def _draw_registry_tab(self, screen, content, tab_id):
        tab = self._tab_by_id(tab_id)
        if not tab:
            return
        y = content.y - self.scroll
        for entry in tab.get("entries", []):
            entry_h = self._entry_height(entry)
            if y > content.bottom:
                break
            if y + entry_h >= content.y:
                if entry.get("kind") == "value":
                    self._draw_value_entry(screen, entry, content.x, y, content.w)
                elif entry.get("kind") == "action":
                    self._draw_action_entry(screen, entry, content.x, y, content.w)
            y += entry_h + 8

    def _entry_height(self, entry):
        if entry.get("kind") == "value" and entry.get("type") == "dict":
            return self.ROW_H + 7 * 24 + 8
        return self.ROW_H

    def _draw_value_entry(self, screen, entry, x, y, w):
        row = pygame.Rect(x, y, w, self.ROW_H)
        pygame.draw.rect(screen, (30, 34, 43), row, border_radius=5)
        label = self.font.render(entry.get("label", entry.get("path", "?")), True, (230, 235, 245))
        screen.blit(label, (x + 10, y + 6))
        try:
            value = self.registry.get_value(entry)
            type_name = entry.get("type")
            if type_name == "bool":
                self._small_button(screen, pygame.Rect(row.right - 96, y + 4, 82, 22), "True" if value else "False", ("edit", entry, "toggle", None))
            elif type_name == "enum":
                self._small_button(screen, pygame.Rect(row.right - 126, y + 4, 112, 22), str(value), ("edit", entry, "cycle", None))
            elif type_name in ("int", "float"):
                value_txt = self.font.render(str(value), True, (255, 255, 255))
                screen.blit(value_txt, (row.right - 170, y + 6))
                self._small_button(screen, pygame.Rect(row.right - 78, y + 4, 28, 22), "-", ("edit", entry, "dec", None))
                self._small_button(screen, pygame.Rect(row.right - 44, y + 4, 28, 22), "+", ("edit", entry, "inc", None))
            elif type_name == "dict":
                compact = f"{len(value)} keys" if isinstance(value, dict) else str(value)
                screen.blit(self.font.render(compact, True, (220, 225, 235)), (row.right - 170, y + 6))
                self._draw_dict_children(screen, entry, value, x + 28, y + self.ROW_H + 2, w - 40)
            elif type_name == "list":
                compact = f"{len(value)} items: {value[:4]}" if isinstance(value, list) else str(value)
                screen.blit(self.small_font.render(compact[:80], True, (220, 225, 235)), (row.x + 270, y + 8))
        except Exception as exc:
            err = self.small_font.render(str(exc)[:70], True, (255, 140, 140))
            screen.blit(err, (row.x + 270, y + 8))

    def _draw_dict_children(self, screen, entry, value, x, y, w):
        if not isinstance(value, dict):
            return
        for idx, (key, val) in enumerate(list(value.items())[:7]):
            cy = y + idx * 24
            child = pygame.Rect(x, cy, w, 22)
            pygame.draw.rect(screen, (24, 28, 36), child, border_radius=4)
            txt = self.small_font.render(f"{key}: {val}", True, (210, 218, 230))
            screen.blit(txt, (child.x + 8, child.y + 4))
            if isinstance(val, (int, float)) and not isinstance(val, bool):
                self._small_button(screen, pygame.Rect(child.right - 58, child.y + 2, 24, 18), "-", ("edit", entry, "dec", key))
                self._small_button(screen, pygame.Rect(child.right - 30, child.y + 2, 24, 18), "+", ("edit", entry, "inc", key))

    def _draw_action_entry(self, screen, entry, x, y, w):
        width = min(330, w - 10)
        rect = pygame.Rect(x, y, width, self.ROW_H)
        danger = bool(entry.get("danger"))
        color = (88, 48, 48) if danger else (45, 66, 92)
        pygame.draw.rect(screen, color, rect, border_radius=5)
        pygame.draw.rect(screen, (150, 170, 205), rect, 1, border_radius=5)
        label = self.font.render(entry.get("label", entry.get("action", "?")), True, (255, 255, 255))
        screen.blit(label, (rect.x + 10, rect.y + 6))
        self.click_targets.append((rect, ("action", entry)))

    def _small_button(self, screen, rect, label, payload):
        pygame.draw.rect(screen, (56, 65, 82), rect, border_radius=4)
        pygame.draw.rect(screen, (130, 145, 170), rect, 1, border_radius=4)
        txt = self.small_font.render(str(label), True, (245, 248, 255))
        screen.blit(txt, (rect.centerx - txt.get_width() // 2, rect.centery - txt.get_height() // 2))
        self.click_targets.append((rect, payload))

    def _draw_quests_tab(self, screen, content):
        search_rect = pygame.Rect(content.x, content.y, 360, 32)
        pygame.draw.rect(screen, (28, 32, 40), search_rect, border_radius=5)
        pygame.draw.rect(screen, (120, 145, 185) if self.search_active else (80, 95, 120), search_rect, 2, border_radius=5)
        search = self.search_text or "Search quests by title or rules"
        color = (245, 248, 255) if self.search_text else (150, 158, 175)
        screen.blit(self.font.render(search, True, color), (search_rect.x + 10, search_rect.y + 7))
        self.click_targets.append((search_rect, ("search",)))

        quests = getattr(self.g, "quests", None)
        if not quests:
            screen.blit(self.font.render("Quest system not available.", True, (255, 170, 170)), (content.x, content.y + 50))
            return

        active_names = []
        for qid in getattr(quests, "active_quests", []):
            data = quests.quest_lookup.get(qid, {})
            active_names.append(f"{qid}: {data.get('title', 'Unknown')}")
        active = self.small_font.render("Active: " + (", ".join(active_names) or "none"), True, (225, 232, 245))
        screen.blit(active, (content.x + 380, content.y + 9))

        query = self.search_text.lower().strip()
        all_quests = getattr(quests, "all_quests", [])
        matches = []
        for quest in all_quests:
            hay = f"{quest.get('title', '')} {quest.get('rules', '')}".lower()
            if not query or query in hay:
                matches.append(quest)
        matches = matches[:80]

        list_rect = pygame.Rect(content.x, content.y + 46, 500, content.h - 46)
        detail_rect = pygame.Rect(content.x + 520, content.y + 46, content.w - 520, content.h - 46)
        pygame.draw.rect(screen, (24, 28, 36), list_rect, border_radius=5)
        pygame.draw.rect(screen, (24, 28, 36), detail_rect, border_radius=5)

        y = list_rect.y + 8 - self.scroll
        for quest in matches:
            if y > list_rect.bottom:
                break
            qid = quest.get("quest_number")
            if y + 28 >= list_rect.y:
                rect = pygame.Rect(list_rect.x + 8, y, list_rect.w - 16, 26)
                selected = qid == self.selected_quest_num
                pygame.draw.rect(screen, (58, 75, 105) if selected else (34, 40, 52), rect, border_radius=4)
                title = f"{qid}: {quest.get('title', 'Untitled')}"
                screen.blit(self.small_font.render(title[:64], True, (235, 240, 248)), (rect.x + 8, rect.y + 5))
                self.click_targets.append((rect, ("select_quest", qid)))
            y += 30

        if self.selected_quest_num is None and matches:
            self.selected_quest_num = matches[0].get("quest_number")
        self._draw_quest_detail(screen, detail_rect, quests)

    def _draw_quest_detail(self, screen, rect, quests):
        qid = self.selected_quest_num
        quest = quests.quest_lookup.get(qid) if qid is not None else None
        if not quest:
            return
        x, y = rect.x + 14, rect.y + 12
        title = self.title_font.render(f"{qid}: {quest.get('title', 'Untitled')}", True, (245, 248, 255))
        screen.blit(title, (x, y))
        y += 34
        for line in self._wrap(quest.get("rules", ""), self.font, rect.w - 28)[:5]:
            screen.blit(self.font.render(line, True, (220, 226, 238)), (x, y))
            y += 23
        y += 8
        self._small_button(screen, pygame.Rect(x, y, 150, 28), "Start Quest", ("quest_action", "start_quest", qid))
        self._small_button(screen, pygame.Rect(x + 160, y, 170, 28), "Complete Quest", ("quest_action", "complete_quest", qid))
        self._small_button(screen, pygame.Rect(x + 340, y, 150, 28), "Grant Reward", ("quest_action", "grant_quest_reward", qid))
        y += 46
        status = getattr(quests, "quest_status", {})
        screen.blit(self.font.render("Quest Status", True, (245, 248, 255)), (x, y))
        y += 26
        for key, val in list(status.items())[:12]:
            screen.blit(self.small_font.render(f"{key}: {val}", True, (210, 218, 230)), (x + 8, y))
            y += 20

    def _draw_board_tab(self, screen, content):
        board = getattr(self.g, "board", None)
        if not board:
            return
        sq = 34
        self.board_rect = pygame.Rect(content.x + 18, content.y + 18, sq * 8, sq * 8)
        for row in range(8):
            for col in range(8):
                rect = pygame.Rect(self.board_rect.x + col * sq, self.board_rect.y + row * sq, sq, sq)
                color = (226, 210, 178) if (row + col) % 2 == 0 else (132, 98, 74)
                pygame.draw.rect(screen, color, rect)
                square = chess.square(col, 7 - row)
                piece = board.piece_at(square)
                if piece:
                    self._draw_piece_symbol(screen, piece.symbol(), rect.x + 8, rect.y + 5)
        pygame.draw.rect(screen, (245, 248, 255), self.board_rect, 2)

        self.tray_rect = pygame.Rect(self.board_rect.right + 28, self.board_rect.y, 300, self.board_rect.h)
        pygame.draw.rect(screen, (24, 28, 36), self.tray_rect, border_radius=5)
        pygame.draw.rect(screen, (120, 145, 185), self.tray_rect, 1, border_radius=5)
        screen.blit(self.font.render("Removed Piece Tray", True, (245, 248, 255)), (self.tray_rect.x + 10, self.tray_rect.y + 8))
        self.tray_item_rects = []
        tx, ty = self.tray_rect.x + 12, self.tray_rect.y + 40
        for idx, item in enumerate(self.tray_items[:42]):
            rect = pygame.Rect(tx + (idx % 6) * 44, ty + (idx // 6) * 38, 36, 32)
            pygame.draw.rect(screen, (40, 48, 62), rect, border_radius=4)
            self._draw_piece_symbol(screen, item["symbol"], rect.x + 9, rect.y + 3)
            self.tray_item_rects.append((rect, idx))

        palette_rect = pygame.Rect(self.tray_rect.right + 28, self.board_rect.y, 190, 162)
        pygame.draw.rect(screen, (24, 28, 36), palette_rect, border_radius=5)
        pygame.draw.rect(screen, (120, 145, 185), palette_rect, 1, border_radius=5)
        screen.blit(self.font.render("Piece Palette", True, (245, 248, 255)), (palette_rect.x + 10, palette_rect.y + 8))
        self.palette_rects = []
        for idx, symbol in enumerate(self.PIECE_SYMBOLS):
            rect = pygame.Rect(palette_rect.x + 12 + (idx % 6) * 28, palette_rect.y + 40 + (idx // 6) * 38, 24, 30)
            pygame.draw.rect(screen, (40, 48, 62), rect, border_radius=4)
            self._draw_piece_symbol(screen, symbol, rect.x + 5, rect.y + 4)
            self.palette_rects.append((rect, symbol))

        action_x = self.tray_rect.right + 28
        action_y = palette_rect.bottom + 24
        board_tab = self._tab_by_id("board")
        for entry in board_tab.get("entries", []) if board_tab else []:
            self._draw_action_entry(screen, entry, action_x, action_y, 260)
            action_y += 38

        warnings = debug_actions.validate_board_warnings(self.g)
        warn_rect = pygame.Rect(self.board_rect.x, self.board_rect.bottom + 18, 640, 148)
        pygame.draw.rect(screen, (24, 28, 36), warn_rect, border_radius=5)
        screen.blit(self.font.render("Validation", True, (245, 248, 255)), (warn_rect.x + 10, warn_rect.y + 8))
        if warnings:
            for idx, warning in enumerate(warnings[:5]):
                screen.blit(self.small_font.render(warning[:92], True, (255, 200, 150)), (warn_rect.x + 12, warn_rect.y + 36 + idx * 20))
        else:
            screen.blit(self.small_font.render("No warnings.", True, (190, 235, 190)), (warn_rect.x + 12, warn_rect.y + 36))

        fen = board.fen()
        screen.blit(self.small_font.render(f"FEN: {fen[:120]}", True, (210, 218, 230)), (warn_rect.x + 10, warn_rect.bottom - 24))

    def square_at_pos(self, pos):
        if not self.board_rect.collidepoint(pos):
            return None
        sq_size = self.board_rect.w // 8
        col = (pos[0] - self.board_rect.x) // sq_size
        row = (pos[1] - self.board_rect.y) // sq_size
        if 0 <= col < 8 and 0 <= row < 8:
            return chess.square(int(col), 7 - int(row))
        return None

    def _draw_piece_symbol(self, screen, symbol, x, y):
        color = (250, 250, 250) if symbol.isupper() else (15, 18, 24)
        shadow = self.big_piece_font.render(symbol, True, (80, 80, 80))
        text = self.big_piece_font.render(symbol, True, color)
        screen.blit(shadow, (x + 1, y + 1))
        screen.blit(text, (x, y))

    def _tab_by_id(self, tab_id):
        for tab in self.registry.tabs:
            if tab.get("id") == tab_id:
                return tab
        return None

    def _wrap(self, text, font, max_width):
        words = str(text).split()
        lines = []
        current = ""
        for word in words:
            candidate = f"{current} {word}".strip()
            if font.size(candidate)[0] <= max_width:
                current = candidate
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines
