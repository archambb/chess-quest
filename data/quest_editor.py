# quest_editor_gui.py
import sys
import json
import os
from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QTextEdit, QMessageBox, QLineEdit, QFormLayout, QDialog,
    QDialogButtonBox, QComboBox, QSpinBox
)

QUEST_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "quests.json")

# Load quests from file or start empty
try:
    with open(QUEST_FILE, "r", encoding="utf-8") as f:
        QUESTS = json.load(f)
except FileNotFoundError:
    QUESTS = []

def get_all_feedback_keys():
    keys = set()
    for q in QUESTS:
        keys.update(q.get("feedback", []))
        for pair in q.get("win_reward_pairs", []):
            keys.update(pair.get("to_win", {}).keys())
    return sorted(keys)

class QuestEditorDialog(QDialog):
    def __init__(self, quest=None):
        super().__init__()
        self.setWindowTitle("Edit Quest" if quest else "Add Quest")
        self.quest = quest or {"quest_number": 0, "title": "", "rules": "", "feedback": [], "win_reward_pairs": []}
        self.feedback_keys = get_all_feedback_keys()

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.title_edit = QLineEdit(self.quest['title'])
        self.rules_edit = QTextEdit(self.quest['rules'])

        self.feedback_combo = QComboBox()
        self.feedback_combo.setEditable(True)
        self.feedback_combo.addItems(self.feedback_keys)

        self.feedback_list = QListWidget()
        for key in self.quest.get("feedback", []):
            self.feedback_list.addItem(key)

        add_fb_btn = QPushButton("Add Feedback")
        add_fb_btn.clicked.connect(self.add_feedback)

        self.pairs_list = QListWidget()
        self.refresh_pairs_list()
        self.pairs_list.itemDoubleClicked.connect(self.remove_selected_pair)

        self.cond_combo = QComboBox()
        self.cond_combo.setEditable(True)
        self.cond_combo.addItems(self.feedback_keys)
        self.cond_value = QSpinBox()
        self.reward_combo = QComboBox()
        self.reward_combo.setEditable(True)
        self.reward_combo.addItems(["promotion", "shield", "freeze", "time_warp", "swaps", "magnet", "advanced_shield", "advance_rows", "no_future_rooks", "outer_pawns_start_as_rooks"])
        self.reward_value = QSpinBox()
        add_pair_btn = QPushButton("Add Win/Reward Pair")
        add_pair_btn.clicked.connect(self.add_pair)

        form.addRow("Title:", self.title_edit)
        form.addRow("Rules:", self.rules_edit)
        form.addRow("Feedback Key:", self.feedback_combo)
        form.addRow(add_fb_btn)
        form.addRow(QLabel("Feedback List:"), self.feedback_list)
        form.addRow(QLabel("Win Condition Key:"), self.cond_combo)
        form.addRow("Value:", self.cond_value)
        form.addRow(QLabel("Reward Key:"), self.reward_combo)
        form.addRow("Value:", self.reward_value)
        form.addRow(add_pair_btn)
        form.addRow(QLabel("Win/Reward Pairs (double-click to remove):"), self.pairs_list)

        layout.addLayout(form)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def add_feedback(self):
        key = self.feedback_combo.currentText().strip()
        if key and key not in [self.feedback_list.item(i).text() for i in range(self.feedback_list.count())]:
            self.feedback_list.addItem(key)

    def add_pair(self):
        cond_key = self.cond_combo.currentText().strip()
        cond_val = self.cond_value.value()
        reward_key = self.reward_combo.currentText().strip()
        reward_val = self.reward_value.value()

        if not cond_key or not reward_key:
            return

        # Try to find existing to_win dict that matches all keys
        for pair in self.quest['win_reward_pairs']:
            if cond_key in pair['to_win'] and pair['to_win'][cond_key] == cond_val:
                pair['reward'][reward_key] = reward_val
                self.refresh_pairs_list()
                return

        # Try to find partial match where to_win keys differ, merge into one if same values
        for pair in self.quest['win_reward_pairs']:
            if cond_key not in pair['to_win'] and cond_val not in pair['to_win'].values():
                pair['to_win'][cond_key] = cond_val
                pair['reward'][reward_key] = reward_val
                self.refresh_pairs_list()
                return

        # Otherwise, create new
        self.quest['win_reward_pairs'].append({
            "to_win": {cond_key: cond_val},
            "reward": {reward_key: reward_val}
        })
        self.refresh_pairs_list()

    def refresh_pairs_list(self):
        self.pairs_list.clear()
        for pair in self.quest['win_reward_pairs']:
            self.pairs_list.addItem(json.dumps(pair))

    def remove_selected_pair(self, item):
        try:
            self.quest['win_reward_pairs'].remove(json.loads(item.text()))
            self.refresh_pairs_list()
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to remove pair: {e}")

    def get_result(self):
        self.quest['title'] = self.title_edit.text()
        self.quest['rules'] = self.rules_edit.toPlainText()
        self.quest['feedback'] = [self.feedback_list.item(i).text() for i in range(self.feedback_list.count())]
        return self.quest

class QuestViewer(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Chess Quest Editor")
        self.setMinimumSize(900, 600)
        self.layout = QVBoxLayout(self)

        self.list_widget = QListWidget()
        self.refresh_list()
        self.list_widget.currentRowChanged.connect(self.display_quest)

        self.detail_box = QTextEdit()
        self.detail_box.setReadOnly(True)

        button_layout = QHBoxLayout()
        self.add_button = QPushButton("Add Quest")
        self.remove_button = QPushButton("Remove Quest")
        self.edit_button = QPushButton("Edit Quest")
        self.save_button = QPushButton("Save to quests.json")

        self.add_button.clicked.connect(self.add_quest)
        self.remove_button.clicked.connect(self.remove_quest)
        self.edit_button.clicked.connect(self.edit_quest)
        self.save_button.clicked.connect(self.save_quests)

        button_layout.addWidget(self.add_button)
        button_layout.addWidget(self.edit_button)
        button_layout.addWidget(self.remove_button)
        button_layout.addWidget(self.save_button)


        self.layout.addWidget(QLabel("Select a Quest:"))
        self.layout.addWidget(self.list_widget)
        self.layout.addWidget(QLabel("Quest Details:"))
        self.layout.addWidget(self.detail_box)
        self.layout.addLayout(button_layout)

        self.evaluate_towin_button = QPushButton("Evaluate To_Win")
        self.evaluate_rewards_button = QPushButton("Evaluate Rewards")
        self.evaluate_towin_button.clicked.connect(self.evaluate_towin)
        self.evaluate_rewards_button.clicked.connect(self.evaluate_rewards)

        button_layout.addWidget(self.evaluate_towin_button)
        button_layout.addWidget(self.evaluate_rewards_button)

    def evaluate_towin(self):
        win_map = {}
        for quest in QUESTS:
            for pair in quest.get("win_reward_pairs", []):
                for key in pair.get("to_win", {}):
                    win_map.setdefault(key, []).append((quest["quest_number"], quest["title"]))

        self.show_evaluation_dialog("To_Win Conditions", win_map)

    def evaluate_rewards(self):
        reward_map = {}
        for quest in QUESTS:
            for pair in quest.get("win_reward_pairs", []):
                for key in pair.get("reward", {}):
                    reward_map.setdefault(key, []).append((quest["quest_number"], quest["title"]))

        self.show_evaluation_dialog("Reward Effects", reward_map)

    def show_evaluation_dialog(self, title, data_map):
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        layout = QVBoxLayout(dialog)

        combo = QComboBox()
        combo.addItems(sorted(data_map.keys()))
        text_area = QTextEdit()
        text_area.setReadOnly(True)

        def update_text():
            selected = combo.currentText()
            quests = data_map.get(selected, [])
            if not quests:
                text_area.setText("None.")
            else:
                text_area.setText("\n".join(f"#{num}: {title}" for num, title in quests))

        combo.currentTextChanged.connect(update_text)
        layout.addWidget(combo)
        layout.addWidget(text_area)

        close_btns = QDialogButtonBox(QDialogButtonBox.Close)
        close_btns.rejected.connect(dialog.reject)
        layout.addWidget(close_btns)

        update_text()  # initialize
        dialog.exec()

    def refresh_list(self):
        self.list_widget.clear()
        for quest in QUESTS:
            self.list_widget.addItem(f"#{quest['quest_number']}: {quest['title']}")

    def display_quest(self, index):
        if index < 0 or index >= len(QUESTS):
            self.detail_box.setText("")
            return

        quest = QUESTS[index]
        text = f"Title: {quest['title']}\n\nRules: {quest['rules']}\n\nFeedback Keys: {', '.join(quest['feedback'])}\n\nWin Conditions & Rewards:\n"
        for pair in quest.get("win_reward_pairs", []):
            conditions = ', '.join(f"{k}: {v}" for k, v in pair['to_win'].items())
            rewards = ', '.join(f"{k}: {v}" for k, v in pair['reward'].items())
            text += f"\n  To Win: {conditions}\n  Reward: {rewards}\n"
        self.detail_box.setText(text)

    def add_quest(self):
        dialog = QuestEditorDialog()
        if dialog.exec() == QDialog.Accepted:
            quest = dialog.get_result()
            if quest:
                quest["quest_number"] = max([q["quest_number"] for q in QUESTS] + [0]) + 1
                QUESTS.append(quest)
                self.refresh_list()

    def edit_quest(self):
        index = self.list_widget.currentRow()
        if index < 0 or index >= len(QUESTS):
            return
        dialog = QuestEditorDialog(QUESTS[index])
        if dialog.exec() == QDialog.Accepted:
            result = dialog.get_result()
            if result:
                QUESTS[index] = result
                self.refresh_list()
                self.display_quest(index)

    def remove_quest(self):
        index = self.list_widget.currentRow()
        if index >= 0 and index < len(QUESTS):
            del QUESTS[index]
            self.refresh_list()
            self.detail_box.clear()

    def save_quests(self):
        try:
            with open(QUEST_FILE, "w", encoding="utf-8") as f:
                json.dump(QUESTS, f, indent=2)
            QMessageBox.information(self, "Success", "Quests saved to quests.json")
        except Exception as e:
            QMessageBox.critical(self, "Error", str(e))

if __name__ == '__main__':
    app = QApplication(sys.argv)
    viewer = QuestViewer()
    viewer.show()
    sys.exit(app.exec())
