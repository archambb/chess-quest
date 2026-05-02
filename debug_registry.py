from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any


REGISTRY_PATH = os.path.join("data", "debug_overlay_registry.json")


class DebugRegistryError(Exception):
    pass


@dataclass
class ResolvedPath:
    owner: object
    attr: str


class DebugRegistry:
    """
    Loads debug overlay metadata from JSON and exposes only approved object roots.
    JSON describes what may be displayed or edited; Python still owns behavior.
    """

    ALLOWED_ROOTS = {"game", "quests", "world", "gear", "renderer", "board"}
    ALLOWED_TYPES = {"bool", "int", "float", "str", "enum", "list", "dict"}

    def __init__(self, game, path: str = REGISTRY_PATH):
        self.g = game
        self.path = path
        self.tabs: list[dict[str, Any]] = []
        self.errors: list[str] = []
        self.load()

    def load(self) -> None:
        self.tabs = []
        self.errors = []

        try:
            with open(self.path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as exc:
            self.errors.append(f"Could not load {self.path}: {exc}")
            return

        tabs = data.get("tabs", [])
        if not isinstance(tabs, list):
            self.errors.append("Registry field 'tabs' must be a list.")
            return

        for tab in tabs:
            if not isinstance(tab, dict):
                self.errors.append("Skipping non-object tab.")
                continue
            entries = tab.get("entries", [])
            if not isinstance(entries, list):
                self.errors.append(f"Tab {tab.get('id', '?')} entries must be a list.")
                entries = []
            clean_entries = []
            for entry in entries:
                ok, message = self.validate_entry(entry)
                if ok:
                    clean_entries.append(entry)
                else:
                    entry_id = entry.get("id", "?") if isinstance(entry, dict) else "?"
                    self.errors.append(f"{entry_id}: {message}")
            clean_tab = dict(tab)
            clean_tab["entries"] = clean_entries
            self.tabs.append(clean_tab)

    def validate_entry(self, entry: Any) -> tuple[bool, str]:
        if not isinstance(entry, dict):
            return False, "entry must be an object"
        kind = entry.get("kind")
        if kind == "value":
            path = entry.get("path")
            type_name = entry.get("type")
            if not isinstance(path, str):
                return False, "value entry needs a string path"
            if type_name not in self.ALLOWED_TYPES:
                return False, f"unsupported type {type_name!r}"
            try:
                self._validate_path_string(path)
            except DebugRegistryError as exc:
                return False, str(exc)
            return True, ""
        if kind == "action":
            if not isinstance(entry.get("action"), str):
                return False, "action entry needs an action name"
            return True, ""
        return False, f"unsupported kind {kind!r}"

    def _validate_path_string(self, path: str) -> None:
        parts = path.split(".")
        if len(parts) < 2:
            raise DebugRegistryError("path must include root and attribute")
        if parts[0] not in self.ALLOWED_ROOTS:
            raise DebugRegistryError(f"root {parts[0]!r} is not allowed")
        for part in parts:
            if not part or part.startswith("_") or "__" in part:
                raise DebugRegistryError("private or magic attributes are not allowed")

    def roots(self) -> dict[str, object]:
        return {
            "game": self.g,
            "quests": getattr(self.g, "quests", None),
            "world": getattr(self.g, "world", None),
            "gear": getattr(self.g, "gear", None),
            "renderer": getattr(self.g, "renderer", None),
            "board": getattr(self.g, "board", None),
        }

    def resolve(self, path: str) -> ResolvedPath:
        self._validate_path_string(path)
        parts = path.split(".")
        obj = self.roots().get(parts[0])
        if obj is None:
            raise DebugRegistryError(f"root {parts[0]!r} is not available")
        for part in parts[1:-1]:
            obj = getattr(obj, part, None)
            if obj is None:
                raise DebugRegistryError(f"path segment {part!r} is not available")
        return ResolvedPath(obj, parts[-1])

    def get_value(self, entry: dict[str, Any]) -> Any:
        resolved = self.resolve(entry["path"])
        return getattr(resolved.owner, resolved.attr)

    def set_value(self, entry: dict[str, Any], value: Any) -> None:
        if not entry.get("editable", False):
            raise DebugRegistryError("entry is read-only")
        resolved = self.resolve(entry["path"])
        value = self.coerce_value(entry, value)
        setattr(resolved.owner, resolved.attr, value)

    def coerce_value(self, entry: dict[str, Any], value: Any) -> Any:
        type_name = entry.get("type")
        if type_name == "bool":
            return bool(value)
        if type_name == "int":
            value = int(value)
            if "min" in entry:
                value = max(int(entry["min"]), value)
            if "max" in entry:
                value = min(int(entry["max"]), value)
            return value
        if type_name == "float":
            value = float(value)
            if "min" in entry:
                value = max(float(entry["min"]), value)
            if "max" in entry:
                value = min(float(entry["max"]), value)
            return value
        if type_name == "str":
            return "" if value is None else str(value)
        if type_name == "enum":
            options = entry.get("options") or []
            if value not in options:
                raise DebugRegistryError(f"{value!r} is not a valid option")
            return value
        if type_name in ("list", "dict"):
            if isinstance(value, str):
                value = json.loads(value)
            if type_name == "list" and not isinstance(value, list):
                raise DebugRegistryError("expected list")
            if type_name == "dict" and not isinstance(value, dict):
                raise DebugRegistryError("expected dict")
            return value
        raise DebugRegistryError(f"unsupported type {type_name!r}")
