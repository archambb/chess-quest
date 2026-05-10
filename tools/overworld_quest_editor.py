from __future__ import annotations

import argparse
import copy
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config


DEFAULT_PATH = Path("data/overworld_quests.json")
DEFAULT_STORIES_PATH = Path("data/stories.json")
DEFAULT_FRAMES_PATH = Path("data/frames.json")
CARD_ART_DIR = Path("assets/GFX/overworld_quests/cards")


def load_data(path: Path):
    if not path.exists():
        return {"quests": []}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return {"quests": data}
    data.setdefault("quests", [])
    return data


def save_data(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
        f.write("\n")


def list_quests(path: Path):
    data = load_data(path)
    for quest in data.get("quests", []):
        print(f"{quest.get('id', '<missing id>')}: {quest.get('name', '<unnamed>')}")


def load_optional_json(path: Path, fallback):
    if not path.exists():
        return fallback
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def validate_data(data, stories=None, frames=None):
    seen = set()
    errors = []
    known_stories = set((stories or {}).keys())
    known_frames = {str(key) for key in (frames or {}).keys()}
    known_gear = set(config.GEAR_ORDER)

    if stories:
        for story_id, frame_ids in stories.items():
            for frame_id in frame_ids:
                if str(frame_id) not in known_frames:
                    errors.append(f"Story {story_id}: missing frame {frame_id}")
        for frame_id, frame in (frames or {}).items():
            rewards = frame.get("return_rewards", {}) if isinstance(frame, dict) else {}
            for gear_id in rewards.get("gear", []):
                if gear_id not in known_gear:
                    errors.append(f"Frame {frame_id}: unknown gear reward {gear_id}")

    for index, quest in enumerate(data.get("quests", []), start=1):
        quest_id = quest.get("id")
        label = quest_id or f"Quest #{index}"
        if not quest_id:
            errors.append(f"Quest #{index} is missing id")
            continue
        if quest_id in seen:
            errors.append(f"Duplicate quest id: {quest_id}")
        seen.add(quest_id)
        if not quest.get("name"):
            errors.append(f"{label}: missing name")
        if not isinstance(quest.get("availability", {}), dict):
            errors.append(f"{label}: availability must be an object")
        if not isinstance(quest.get("steps", []), list):
            errors.append(f"{label}: steps must be a list")
        if not isinstance(quest.get("outcomes", {}), dict):
            errors.append(f"{label}: outcomes must be an object")
        start_story = quest.get("start", {}).get("story")
        if start_story and known_stories and start_story not in known_stories:
            errors.append(f"{label}: start references missing story {start_story}")
        for step in quest.get("steps", []):
            step_id = step.get("id")
            if not step_id:
                errors.append(f"{label}: a step is missing id")
            story = step.get("story")
            if story and known_stories and story not in known_stories:
                errors.append(f"{label}/{step_id}: references missing story {story}")
            if "choices" in step and not isinstance(step["choices"], list):
                errors.append(f"{label}/{step_id}: choices must be a list")
            if "board_objectives" in step and not isinstance(step["board_objectives"], list):
                errors.append(f"{label}/{step_id}: board_objectives must be a list")
            for objective in step.get("board_objectives", []):
                stage_id = objective.get("stage_id")
                if stage_id is not None and not (0 <= int(stage_id) <= 15):
                    errors.append(f"{label}/{step_id}: board objective stage_id {stage_id} is outside 0-15")
        for outcome_id, outcome in quest.get("outcomes", {}).items():
            story = outcome.get("story")
            if story and known_stories and story not in known_stories:
                errors.append(f"{label}/{outcome_id}: references missing story {story}")
            for gear_id in outcome.get("gear", []):
                if gear_id not in known_gear:
                    errors.append(f"{label}/{outcome_id}: unknown gear reward {gear_id}")
    return errors


def validate(path: Path):
    errors = validate_data(
        load_data(path),
        stories=load_optional_json(DEFAULT_STORIES_PATH, {}),
        frames=load_optional_json(DEFAULT_FRAMES_PATH, {}),
    )
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1
    print(f"OK: {len(load_data(path).get('quests', []))} overworld quest(s) validated.")
    return 0


def starter_quest(quest_id: str, name: str):
    return {
        "id": quest_id,
        "name": name,
        "description": "",
        "timer": {"months": None},
        "start_location": {"stage_id": 0},
        "locations": {},
        "availability": {"all": []},
        "first_step": "start",
        "steps": [
            {
                "id": "start",
                "name": "Start",
                "type": "dialog",
                "choices": []
            }
        ],
        "outcomes": {}
    }


def new_quest(path: Path, quest_id: str, name: str):
    data = load_data(path)
    if any(q.get("id") == quest_id for q in data.get("quests", [])):
        raise SystemExit(f"Quest already exists: {quest_id}")
    data["quests"].append(starter_quest(quest_id, name))
    save_data(path, data)
    print(f"Created quest: {quest_id}")


def pretty(value):
    return json.dumps(value, indent=2)


def parse_json(text, fallback):
    text = text.strip()
    if not text:
        return copy.deepcopy(fallback)
    return json.loads(text)


def comma_list(text):
    return [item.strip() for item in text.split(",") if item.strip()]


def list_text(values):
    return ", ".join(str(value) for value in values or [])


def run_gui(path: Path):
    try:
        from PySide6.QtCore import Qt
        from PySide6.QtGui import QAction, QKeySequence, QPixmap
        from PySide6.QtWidgets import (
            QApplication,
            QCheckBox,
            QComboBox,
            QFileDialog,
            QFormLayout,
            QHBoxLayout,
            QInputDialog,
            QLabel,
            QLineEdit,
            QListWidget,
            QMainWindow,
            QMessageBox,
            QPushButton,
            QPlainTextEdit,
            QSpinBox,
            QSplitter,
            QTabWidget,
            QTableWidget,
            QTableWidgetItem,
            QTextEdit,
            QToolBar,
            QVBoxLayout,
            QWidget,
        )
    except ImportError as exc:
        raise SystemExit(
            "PySide6 is required for the GUI editor. Install it with: pip install PySide6"
        ) from exc

    class QuestEditorWindow(QMainWindow):
        def __init__(self, initial_path: Path):
            super().__init__()
            self.path = initial_path
            self.data = load_data(self.path)
            self.current_index = None
            self.loading = False
            self.dirty = False

            self.setWindowTitle("Chess Quest - Overworld Quest Editor")
            self.resize(1320, 840)
            self._build_actions()
            self._build_ui()
            self.refresh_quest_list()
            if self.data.get("quests"):
                self.quest_list.setCurrentRow(0)

        def _build_actions(self):
            file_menu = self.menuBar().addMenu("&File")
            quest_menu = self.menuBar().addMenu("&Quest")

            open_action = QAction("&Open...", self)
            open_action.setShortcut(QKeySequence.Open)
            open_action.triggered.connect(self.open_file)
            file_menu.addAction(open_action)

            save_action = QAction("&Save", self)
            save_action.setShortcut(QKeySequence.Save)
            save_action.triggered.connect(self.save_file)
            file_menu.addAction(save_action)

            save_as_action = QAction("Save &As...", self)
            save_as_action.triggered.connect(self.save_file_as)
            file_menu.addAction(save_as_action)

            validate_action = QAction("&Validate", self)
            validate_action.setShortcut("Ctrl+Shift+V")
            validate_action.triggered.connect(self.validate_current_data)
            file_menu.addAction(validate_action)

            new_action = QAction("&New Quest", self)
            new_action.setShortcut(QKeySequence.New)
            new_action.triggered.connect(self.add_quest)
            quest_menu.addAction(new_action)

            duplicate_action = QAction("&Duplicate Quest", self)
            duplicate_action.triggered.connect(self.duplicate_quest)
            quest_menu.addAction(duplicate_action)

            delete_action = QAction("&Delete Quest", self)
            delete_action.setShortcut(QKeySequence.Delete)
            delete_action.triggered.connect(self.delete_quest)
            quest_menu.addAction(delete_action)

            toolbar = QToolBar("Main")
            self.addToolBar(toolbar)
            for action in (open_action, save_action, validate_action, new_action, duplicate_action, delete_action):
                toolbar.addAction(action)

        def _build_ui(self):
            root = QSplitter()
            self.setCentralWidget(root)

            left = QWidget()
            left_layout = QVBoxLayout(left)
            self.search = QLineEdit()
            self.search.setPlaceholderText("Filter quests...")
            self.search.textChanged.connect(self.refresh_quest_list)
            self.quest_list = QListWidget()
            self.quest_list.currentRowChanged.connect(self.select_quest)
            left_layout.addWidget(QLabel("Quests"))
            left_layout.addWidget(self.search)
            left_layout.addWidget(self.quest_list)

            button_row = QHBoxLayout()
            for label, slot in (
                ("New", self.add_quest),
                ("Duplicate", self.duplicate_quest),
                ("Delete", self.delete_quest),
            ):
                button = QPushButton(label)
                button.clicked.connect(slot)
                button_row.addWidget(button)
            left_layout.addLayout(button_row)
            root.addWidget(left)

            right = QWidget()
            right_layout = QVBoxLayout(right)
            self.tabs = QTabWidget()
            right_layout.addWidget(self.tabs)
            self.status = QTextEdit()
            self.status.setReadOnly(True)
            self.status.setMaximumHeight(110)
            right_layout.addWidget(self.status)
            root.addWidget(right)
            root.setStretchFactor(1, 1)

            self._build_basics_tab()
            self._build_locations_tab()
            self._build_steps_tab()
            self._build_outcomes_tab()
            self._build_raw_tab()

        def _build_basics_tab(self):
            tab = QWidget()
            layout = QFormLayout(tab)
            self.quest_id = QLineEdit()
            self.quest_name = QLineEdit()
            self.description = QPlainTextEdit()
            self.description.setMaximumHeight(100)
            self.infinite_timer = QCheckBox("Infinite")
            self.timer_months = QSpinBox()
            self.timer_months.setRange(1, 240)
            self.start_stage = QSpinBox()
            self.start_stage.setRange(0, 99)
            self.first_step = QComboBox()
            self.first_step.setEditable(True)
            self.availability = QPlainTextEdit()
            self.availability.setPlaceholderText('{"all": [{"type": "flag_absent", "flag": "king_dead"}]}')
            self.card_art_preview = QLabel("No card art")
            self.card_art_preview.setMinimumHeight(120)
            self.card_art_preview.setAlignment(Qt.AlignCenter)
            self.card_art_preview.setStyleSheet("border: 1px solid #777; background: #222; color: #ddd;")
            self.card_art_button = QPushButton("Import <quest id>.png Card Art")
            self.card_art_button.clicked.connect(self.import_card_art)

            timer_row = QHBoxLayout()
            timer_row.addWidget(self.infinite_timer)
            timer_row.addWidget(QLabel("Months"))
            timer_row.addWidget(self.timer_months)
            timer_widget = QWidget()
            timer_widget.setLayout(timer_row)

            layout.addRow("Quest ID", self.quest_id)
            layout.addRow("Display Name", self.quest_name)
            layout.addRow("Description", self.description)
            layout.addRow("Timer", timer_widget)
            layout.addRow("Starting Stage", self.start_stage)
            layout.addRow("First Step", self.first_step)
            layout.addRow("Availability JSON", self.availability)
            layout.addRow("Card Art", self.card_art_preview)
            layout.addRow("", self.card_art_button)
            self.tabs.addTab(tab, "Basics")

        def _build_locations_tab(self):
            tab = QWidget()
            layout = QVBoxLayout(tab)
            self.locations_table = QTableWidget(0, 2)
            self.locations_table.setHorizontalHeaderLabels(["Key", "Stage ID"])
            layout.addWidget(QLabel("Named quest locations"))
            layout.addWidget(self.locations_table)
            row = QHBoxLayout()
            add = QPushButton("Add Location")
            remove = QPushButton("Remove Selected")
            add.clicked.connect(lambda: self.locations_table.insertRow(self.locations_table.rowCount()))
            remove.clicked.connect(lambda: self._remove_selected_rows(self.locations_table))
            row.addWidget(add)
            row.addWidget(remove)
            row.addStretch()
            layout.addLayout(row)
            self.tabs.addTab(tab, "Locations")

        def _build_steps_tab(self):
            tab = QWidget()
            layout = QHBoxLayout(tab)
            self.step_list = QListWidget()
            self.step_list.currentRowChanged.connect(self.load_step)
            layout.addWidget(self.step_list, 1)

            editor = QWidget()
            editor_layout = QVBoxLayout(editor)
            form = QFormLayout()
            self.step_id = QLineEdit()
            self.step_name = QLineEdit()
            self.step_type = QComboBox()
            self.step_type.addItems(["dialog", "choice", "board", "travel", "story"])
            self.step_story = QLineEdit()
            self.board_objectives = QPlainTextEdit()
            self.board_objectives.setPlaceholderText("[]")
            form.addRow("Step ID", self.step_id)
            form.addRow("Name", self.step_name)
            form.addRow("Type", self.step_type)
            form.addRow("Story", self.step_story)
            form.addRow("Board Objectives JSON", self.board_objectives)
            editor_layout.addLayout(form)

            self.choices_table = QTableWidget(0, 8)
            self.choices_table.setHorizontalHeaderLabels([
                "ID", "Text", "Next Step", "Outcome", "Requires JSON", "Costs JSON", "Set Flags", "Clear Flags"
            ])
            editor_layout.addWidget(QLabel("Dialog choices"))
            editor_layout.addWidget(self.choices_table)
            choice_buttons = QHBoxLayout()
            add_choice = QPushButton("Add Choice")
            remove_choice = QPushButton("Remove Choice")
            add_choice.clicked.connect(lambda: self.choices_table.insertRow(self.choices_table.rowCount()))
            remove_choice.clicked.connect(lambda: self._remove_selected_rows(self.choices_table))
            choice_buttons.addWidget(add_choice)
            choice_buttons.addWidget(remove_choice)
            choice_buttons.addStretch()
            editor_layout.addLayout(choice_buttons)

            step_buttons = QHBoxLayout()
            for label, slot in (
                ("Apply Step", self.save_step_from_fields),
                ("Add Step", self.add_step),
                ("Duplicate Step", self.duplicate_step),
                ("Delete Step", self.delete_step),
            ):
                button = QPushButton(label)
                button.clicked.connect(slot)
                step_buttons.addWidget(button)
            editor_layout.addLayout(step_buttons)
            layout.addWidget(editor, 3)
            self.tabs.addTab(tab, "Steps")

        def _build_outcomes_tab(self):
            tab = QWidget()
            layout = QHBoxLayout(tab)
            self.outcome_list = QListWidget()
            self.outcome_list.currentRowChanged.connect(self.load_outcome)
            layout.addWidget(self.outcome_list, 1)

            editor = QWidget()
            editor_layout = QFormLayout(editor)
            self.outcome_id = QLineEdit()
            self.outcome_story = QLineEdit()
            self.outcome_complete = QCheckBox()
            self.outcome_fail = QCheckBox()
            self.outcome_set_flags = QLineEdit()
            self.outcome_clear_flags = QLineEdit()
            self.outcome_rewards = QPlainTextEdit()
            self.outcome_rewards.setPlaceholderText('{"gold": 5, "gear": ["gear_key"]}')
            editor_layout.addRow("Outcome ID", self.outcome_id)
            editor_layout.addRow("Story", self.outcome_story)
            editor_layout.addRow("Complete Quest", self.outcome_complete)
            editor_layout.addRow("Fail Quest", self.outcome_fail)
            editor_layout.addRow("Set Flags", self.outcome_set_flags)
            editor_layout.addRow("Clear Flags", self.outcome_clear_flags)
            editor_layout.addRow("Story Rewards JSON", self.outcome_rewards)

            buttons = QHBoxLayout()
            for label, slot in (
                ("Apply Outcome", self.save_outcome_from_fields),
                ("Create Story", self.create_story_for_outcome),
                ("Add Outcome", self.add_outcome),
                ("Duplicate Outcome", self.duplicate_outcome),
                ("Delete Outcome", self.delete_outcome),
            ):
                button = QPushButton(label)
                button.clicked.connect(slot)
                buttons.addWidget(button)
            editor_layout.addRow(buttons)
            layout.addWidget(editor, 3)
            self.tabs.addTab(tab, "Outcomes")

        def _build_raw_tab(self):
            tab = QWidget()
            layout = QVBoxLayout(tab)
            self.raw_json = QPlainTextEdit()
            layout.addWidget(QLabel("Full selected quest JSON. Use for advanced fields not exposed above."))
            layout.addWidget(self.raw_json)
            apply_raw = QPushButton("Apply Raw JSON To Quest")
            apply_raw.clicked.connect(self.apply_raw_json)
            layout.addWidget(apply_raw)
            self.tabs.addTab(tab, "Raw JSON")

        def current_quest(self):
            if self.current_index is None:
                return None
            quests = self.data.get("quests", [])
            if 0 <= self.current_index < len(quests):
                return quests[self.current_index]
            return None

        def refresh_quest_list(self, *_):
            selected_id = self.current_quest().get("id") if self.current_quest() else None
            self.quest_list.blockSignals(True)
            self.quest_list.clear()
            text = self.search.text().lower() if hasattr(self, "search") else ""
            self.visible_indexes = []
            for index, quest in enumerate(self.data.get("quests", [])):
                label = f"{quest.get('id', '<missing>')} - {quest.get('name', '<unnamed>')}"
                if text and text not in label.lower():
                    continue
                self.visible_indexes.append(index)
                self.quest_list.addItem(label)
            self.quest_list.blockSignals(False)
            if selected_id:
                for row, index in enumerate(self.visible_indexes):
                    if self.data["quests"][index].get("id") == selected_id:
                        self.quest_list.setCurrentRow(row)
                        return

        def select_quest(self, visible_row):
            self.save_current_quest()
            if visible_row < 0 or visible_row >= len(getattr(self, "visible_indexes", [])):
                self.current_index = None
                return
            self.current_index = self.visible_indexes[visible_row]
            self.load_current_quest()

        def load_current_quest(self):
            quest = self.current_quest()
            if not quest:
                return
            self.loading = True
            self.quest_id.setText(quest.get("id", ""))
            self.quest_name.setText(quest.get("name", ""))
            self.description.setPlainText(quest.get("description", ""))
            timer_months = quest.get("timer", {}).get("months")
            self.infinite_timer.setChecked(timer_months is None)
            self.timer_months.setValue(int(timer_months or 1))
            self.start_stage.setValue(int(quest.get("start_location", {}).get("stage_id", 0)))
            self.availability.setPlainText(pretty(quest.get("availability", {"all": []})))
            self.refresh_card_art_preview()

            self.first_step.clear()
            step_ids = [step.get("id", "") for step in quest.get("steps", []) if step.get("id")]
            self.first_step.addItems(step_ids)
            self.first_step.setEditText(quest.get("first_step", step_ids[0] if step_ids else ""))

            self._load_locations(quest.get("locations", {}))
            self._load_step_list()
            self._load_outcome_list()
            self.raw_json.setPlainText(pretty(quest))
            self.loading = False
            self.validate_current_data(show_success=False)

        def save_current_quest(self):
            quest = self.current_quest()
            if self.loading or quest is None:
                return
            try:
                self.save_step_from_fields(silent=True)
                self.save_outcome_from_fields(silent=True)
                quest["id"] = self.quest_id.text().strip()
                quest["name"] = self.quest_name.text().strip()
                quest["description"] = self.description.toPlainText()
                quest["timer"] = {"months": None if self.infinite_timer.isChecked() else self.timer_months.value()}
                quest["start_location"] = {"stage_id": self.start_stage.value()}
                quest["first_step"] = self.first_step.currentText().strip()
                quest["availability"] = parse_json(self.availability.toPlainText(), {"all": []})
                quest["locations"] = self._locations_from_table()
                self.raw_json.setPlainText(pretty(quest))
                self.dirty = True
            except Exception as exc:
                self.show_error("Could not apply quest fields", exc)

        def import_card_art(self):
            quest = self.current_quest()
            if not quest:
                return
            quest_id = self.quest_id.text().strip() or quest.get("id")
            if not quest_id:
                QMessageBox.warning(self, "Missing Quest ID", "Set the quest ID before importing card art.")
                return
            selected, _ = QFileDialog.getOpenFileName(self, "Import quest card art", "", "PNG Images (*.png)")
            if not selected:
                return
            CARD_ART_DIR.mkdir(parents=True, exist_ok=True)
            dest = CARD_ART_DIR / f"{self._safe_asset_name(quest_id)}.png"
            shutil.copyfile(selected, dest)
            self.status.setPlainText(f"Imported card art: {dest}")
            self.refresh_card_art_preview()

        def refresh_card_art_preview(self):
            quest = self.current_quest()
            quest_id = (self.quest_id.text().strip() if hasattr(self, "quest_id") else "") or (quest or {}).get("id", "")
            path = CARD_ART_DIR / f"{self._safe_asset_name(quest_id)}.png"
            if not quest_id or not path.exists():
                self.card_art_preview.setText(f"Missing: {path.name if quest_id else '<quest id>.png'}")
                self.card_art_preview.setPixmap(QPixmap())
                return
            pix = QPixmap(str(path))
            if pix.isNull():
                self.card_art_preview.setText(f"Could not load {path.name}")
                return
            self.card_art_preview.setPixmap(pix.scaled(220, 120, Qt.KeepAspectRatio, Qt.SmoothTransformation))
            self.card_art_preview.setToolTip(str(path))

        def _safe_asset_name(self, value):
            return str(value).replace(":", "_").replace("/", "_").replace("\\", "_")

        def _load_locations(self, locations):
            self.locations_table.setRowCount(0)
            for key, value in locations.items():
                row = self.locations_table.rowCount()
                self.locations_table.insertRow(row)
                self.locations_table.setItem(row, 0, QTableWidgetItem(str(key)))
                self.locations_table.setItem(row, 1, QTableWidgetItem(str(value.get("stage_id", ""))))

        def _locations_from_table(self):
            locations = {}
            for row in range(self.locations_table.rowCount()):
                key = self._table_text(self.locations_table, row, 0)
                if not key:
                    continue
                stage_text = self._table_text(self.locations_table, row, 1)
                locations[key] = {"stage_id": int(stage_text or 0)}
            return locations

        def _load_step_list(self):
            self.step_list.blockSignals(True)
            self.step_list.clear()
            for step in self.current_quest().get("steps", []):
                self.step_list.addItem(f"{step.get('id', '<missing>')} - {step.get('name', '')}")
            self.step_list.blockSignals(False)
            if self.step_list.count():
                self.step_list.setCurrentRow(0)

        def selected_step(self):
            quest = self.current_quest()
            row = self.step_list.currentRow()
            steps = quest.get("steps", []) if quest else []
            return steps[row] if 0 <= row < len(steps) else None

        def load_step(self, *_):
            step = self.selected_step()
            if not step:
                return
            self.step_id.setText(step.get("id", ""))
            self.step_name.setText(step.get("name", ""))
            self.step_type.setCurrentText(step.get("type", "dialog"))
            self.step_story.setText(step.get("story", ""))
            self.board_objectives.setPlainText(pretty(step.get("board_objectives", [])))
            self.choices_table.setRowCount(0)
            for choice in step.get("choices", []):
                row = self.choices_table.rowCount()
                self.choices_table.insertRow(row)
                values = [
                    choice.get("id", ""),
                    choice.get("text", ""),
                    choice.get("next_step", ""),
                    choice.get("outcome", ""),
                    pretty(choice.get("requires", [])),
                    pretty(choice.get("costs", {})),
                    list_text(choice.get("set_flags", [])),
                    list_text(choice.get("clear_flags", [])),
                ]
                for col, value in enumerate(values):
                    self.choices_table.setItem(row, col, QTableWidgetItem(str(value)))

        def save_step_from_fields(self, silent=False):
            step = self.selected_step()
            if not step:
                return
            try:
                step["id"] = self.step_id.text().strip()
                step["name"] = self.step_name.text().strip()
                step["type"] = self.step_type.currentText().strip()
                if self.step_story.text().strip():
                    step["story"] = self.step_story.text().strip()
                else:
                    step.pop("story", None)
                step["board_objectives"] = parse_json(self.board_objectives.toPlainText(), [])
                step["choices"] = self._choices_from_table()
                self._load_step_list()
                self.raw_json.setPlainText(pretty(self.current_quest()))
            except Exception as exc:
                if not silent:
                    self.show_error("Could not apply step", exc)

        def _choices_from_table(self):
            choices = []
            for row in range(self.choices_table.rowCount()):
                choice_id = self._table_text(self.choices_table, row, 0)
                if not choice_id:
                    continue
                choice = {
                    "id": choice_id,
                    "text": self._table_text(self.choices_table, row, 1),
                }
                for key, col in (("next_step", 2), ("outcome", 3)):
                    value = self._table_text(self.choices_table, row, col)
                    if value:
                        choice[key] = value
                requires = parse_json(self._table_text(self.choices_table, row, 4), [])
                costs = parse_json(self._table_text(self.choices_table, row, 5), {})
                if requires:
                    choice["requires"] = requires
                if costs:
                    choice["costs"] = costs
                set_flags = comma_list(self._table_text(self.choices_table, row, 6))
                clear_flags = comma_list(self._table_text(self.choices_table, row, 7))
                if set_flags:
                    choice["set_flags"] = set_flags
                if clear_flags:
                    choice["clear_flags"] = clear_flags
                choices.append(choice)
            return choices

        def _load_outcome_list(self):
            self.outcome_list.blockSignals(True)
            self.outcome_list.clear()
            for key in self.current_quest().get("outcomes", {}).keys():
                self.outcome_list.addItem(key)
            self.outcome_list.blockSignals(False)
            if self.outcome_list.count():
                self.outcome_list.setCurrentRow(0)

        def selected_outcome_key(self):
            item = self.outcome_list.currentItem()
            return item.text() if item else None

        def load_outcome(self, *_):
            key = self.selected_outcome_key()
            outcome = self.current_quest().get("outcomes", {}).get(key, {}) if key else {}
            self.outcome_id.setText(key or "")
            self.outcome_story.setText(outcome.get("story", ""))
            self.outcome_complete.setChecked(bool(outcome.get("complete", False)))
            self.outcome_fail.setChecked(bool(outcome.get("fail", False)))
            self.outcome_set_flags.setText(list_text(outcome.get("set_flags", [])))
            self.outcome_clear_flags.setText(list_text(outcome.get("clear_flags", [])))
            rewards = {
                key: value
                for key, value in outcome.items()
                if key not in {"story", "complete", "fail", "set_flags", "clear_flags"}
            }
            self.outcome_rewards.setPlainText(pretty(rewards))

        def save_outcome_from_fields(self, silent=False):
            quest = self.current_quest()
            old_key = self.selected_outcome_key()
            new_key = self.outcome_id.text().strip()
            if not quest or not old_key or not new_key:
                return
            try:
                outcome = parse_json(self.outcome_rewards.toPlainText(), {})
                if self.outcome_story.text().strip():
                    outcome["story"] = self.outcome_story.text().strip()
                if self.outcome_complete.isChecked():
                    outcome["complete"] = True
                if self.outcome_fail.isChecked():
                    outcome["fail"] = True
                set_flags = comma_list(self.outcome_set_flags.text())
                clear_flags = comma_list(self.outcome_clear_flags.text())
                if set_flags:
                    outcome["set_flags"] = set_flags
                if clear_flags:
                    outcome["clear_flags"] = clear_flags
                if new_key != old_key:
                    quest.setdefault("outcomes", {}).pop(old_key, None)
                quest.setdefault("outcomes", {})[new_key] = outcome
                self._load_outcome_list()
                self.raw_json.setPlainText(pretty(quest))
            except Exception as exc:
                if not silent:
                    self.show_error("Could not apply outcome", exc)

        def add_quest(self):
            quest_id, ok = QInputDialog.getText(self, "New Quest", "Quest ID:")
            if not ok or not quest_id.strip():
                return
            name, ok = QInputDialog.getText(self, "New Quest", "Display name:")
            if not ok:
                return
            self.save_current_quest()
            self.data.setdefault("quests", []).append(starter_quest(quest_id.strip(), name.strip() or quest_id.strip()))
            self.current_index = len(self.data["quests"]) - 1
            self.refresh_quest_list()
            self.load_current_quest()

        def duplicate_quest(self):
            quest = self.current_quest()
            if not quest:
                return
            self.save_current_quest()
            duplicate = copy.deepcopy(quest)
            duplicate["id"] = f"{quest.get('id', 'quest')}_copy"
            duplicate["name"] = f"{quest.get('name', 'Quest')} Copy"
            self.data["quests"].append(duplicate)
            self.current_index = len(self.data["quests"]) - 1
            self.refresh_quest_list()
            self.load_current_quest()

        def delete_quest(self):
            if self.current_index is None:
                return
            quest = self.current_quest()
            answer = QMessageBox.question(self, "Delete Quest", f"Delete {quest.get('id', 'this quest')}?")
            if answer != QMessageBox.Yes:
                return
            self.data["quests"].pop(self.current_index)
            self.current_index = None
            self.refresh_quest_list()
            if self.data.get("quests"):
                self.quest_list.setCurrentRow(0)

        def add_step(self):
            quest = self.current_quest()
            if not quest:
                return
            quest.setdefault("steps", []).append({"id": "new_step", "name": "New Step", "type": "dialog", "choices": []})
            self._load_step_list()
            self.step_list.setCurrentRow(self.step_list.count() - 1)

        def duplicate_step(self):
            step = self.selected_step()
            quest = self.current_quest()
            if not step or not quest:
                return
            duplicate = copy.deepcopy(step)
            duplicate["id"] = f"{step.get('id', 'step')}_copy"
            quest.setdefault("steps", []).append(duplicate)
            self._load_step_list()
            self.step_list.setCurrentRow(self.step_list.count() - 1)

        def delete_step(self):
            quest = self.current_quest()
            row = self.step_list.currentRow()
            if quest and 0 <= row < len(quest.get("steps", [])):
                quest["steps"].pop(row)
                self._load_step_list()

        def add_outcome(self):
            quest = self.current_quest()
            if not quest:
                return
            quest.setdefault("outcomes", {})["new_outcome"] = {"complete": True}
            self._load_outcome_list()
            self.outcome_list.setCurrentRow(self.outcome_list.count() - 1)

        def duplicate_outcome(self):
            quest = self.current_quest()
            key = self.selected_outcome_key()
            if not quest or not key:
                return
            quest.setdefault("outcomes", {})[f"{key}_copy"] = copy.deepcopy(quest["outcomes"][key])
            self._load_outcome_list()
            self.outcome_list.setCurrentRow(self.outcome_list.count() - 1)

        def delete_outcome(self):
            quest = self.current_quest()
            key = self.selected_outcome_key()
            if quest and key:
                quest.get("outcomes", {}).pop(key, None)
                self._load_outcome_list()

        def create_story_for_outcome(self):
            story_id = self.outcome_story.text().strip()
            if not story_id:
                quest = self.current_quest() or {}
                outcome_id = self.outcome_id.text().strip() or "outcome"
                story_id = f"{quest.get('id', 'quest')}_{outcome_id}"
                self.outcome_story.setText(story_id)

            stories = load_optional_json(DEFAULT_STORIES_PATH, {})
            frames = load_optional_json(DEFAULT_FRAMES_PATH, {})
            if story_id in stories:
                QMessageBox.information(self, "Story Exists", f"{story_id} already exists.")
                return

            used = set()
            for key in frames.keys():
                try:
                    used.add(int(key))
                except ValueError:
                    pass
            for frame_ids in stories.values():
                for frame_id in frame_ids:
                    try:
                        used.add(int(frame_id))
                    except (TypeError, ValueError):
                        pass
            new_frame = max(used) + 1 if used else 1
            stories[story_id] = [new_frame]
            frames[str(new_frame)] = {"text": story_id}

            with DEFAULT_STORIES_PATH.open("w", encoding="utf-8") as f:
                json.dump(stories, f, indent=2)
                f.write("\n")
            with DEFAULT_FRAMES_PATH.open("w", encoding="utf-8") as f:
                json.dump(frames, f, indent=2)
                f.write("\n")

            self.save_outcome_from_fields(silent=True)
            self.status.setPlainText(f"Created story {story_id} with frame {new_frame}.")

        def apply_raw_json(self):
            if self.current_index is None:
                return
            try:
                quest = parse_json(self.raw_json.toPlainText(), {})
                if not isinstance(quest, dict):
                    raise ValueError("Quest JSON must be an object")
                self.data["quests"][self.current_index] = quest
                self.load_current_quest()
            except Exception as exc:
                self.show_error("Raw JSON is invalid", exc)

        def open_file(self):
            selected, _ = QFileDialog.getOpenFileName(self, "Open overworld quest data", str(self.path), "JSON Files (*.json)")
            if selected:
                self.path = Path(selected)
                self.data = load_data(self.path)
                self.current_index = None
                self.refresh_quest_list()
                if self.data.get("quests"):
                    self.quest_list.setCurrentRow(0)

        def save_file(self):
            self.save_current_quest()
            save_data(self.path, self.data)
            self.dirty = False
            self.status.setPlainText(f"Saved {self.path}")

        def save_file_as(self):
            selected, _ = QFileDialog.getSaveFileName(self, "Save overworld quest data", str(self.path), "JSON Files (*.json)")
            if selected:
                self.path = Path(selected)
                self.save_file()

        def validate_current_data(self, show_success=True):
            self.save_current_quest()
            errors = validate_data(
                self.data,
                stories=load_optional_json(DEFAULT_STORIES_PATH, {}),
                frames=load_optional_json(DEFAULT_FRAMES_PATH, {}),
            )
            if errors:
                self.status.setPlainText("\n".join(f"ERROR: {error}" for error in errors))
                return False
            message = f"OK: {len(self.data.get('quests', []))} overworld quest(s) validated."
            self.status.setPlainText(message)
            if show_success:
                QMessageBox.information(self, "Validation", message)
            return True

        def _table_text(self, table, row, col):
            item = table.item(row, col)
            return item.text().strip() if item else ""

        def _remove_selected_rows(self, table):
            rows = sorted({index.row() for index in table.selectedIndexes()}, reverse=True)
            for row in rows:
                table.removeRow(row)

        def show_error(self, title, exc):
            QMessageBox.critical(self, title, str(exc))
            self.status.setPlainText(f"ERROR: {title}\n{exc}")

        def closeEvent(self, event):
            self.save_current_quest()
            if self.dirty:
                answer = QMessageBox.question(self, "Unsaved Changes", "Save changes before closing?")
                if answer == QMessageBox.Yes:
                    self.save_file()
            event.accept()

    app = QApplication(sys.argv)
    window = QuestEditorWindow(path)
    window.show()
    return app.exec()


def main():
    parser = argparse.ArgumentParser(description="Edit and validate overworld quest data.")
    parser.add_argument("--path", default=str(DEFAULT_PATH), help="Path to overworld_quests.json")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("gui", help="Open the PySide6 GUI editor")
    sub.add_parser("list", help="List overworld quests")
    sub.add_parser("validate", help="Validate overworld quest data")

    new_parser = sub.add_parser("new", help="Create a starter quest entry")
    new_parser.add_argument("quest_id")
    new_parser.add_argument("name")

    args = parser.parse_args()
    path = Path(args.path)

    if args.command in (None, "gui"):
        return run_gui(path)
    if args.command == "list":
        list_quests(path)
        return 0
    if args.command == "validate":
        return validate(path)
    if args.command == "new":
        new_quest(path, args.quest_id, args.name)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
