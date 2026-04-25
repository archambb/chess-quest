import sys
import json

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QTextEdit, QVBoxLayout,
    QWidget, QMenuBar, QFileDialog
)
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction


class QuestFormatter(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Quest Formatter")
        self.setAcceptDrops(True)
        self.resize(800, 600)

        # Text area
        self.text_edit = QTextEdit()
        self.text_edit.setReadOnly(True)

        # Layout
        layout = QVBoxLayout()
        layout.addWidget(self.text_edit)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Menu
        self.init_menu()

        print("[Init] Application initialized and ready.")

    def init_menu(self):
        menubar = QMenuBar(self)
        file_menu = menubar.addMenu("File")

        open_action = QAction("Open quests.json...", self)
        open_action.triggered.connect(self.open_file_dialog)
        file_menu.addAction(open_action)

        self.setMenuBar(menubar)

    def open_file_dialog(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open quests.json", "", "JSON Files (*.json)")
        if file_path:
            print(f"[Open File] File selected: {file_path}")
            self.load_quests(file_path)

    def dragEnterEvent(self, event):
        if event.mimeData().hasUrls():
            print("[Drag] Detected file drop.")
            event.acceptProposedAction()
        else:
            print("[Drag] Rejected drag event - no URL.")

    def dropEvent(self, event):
        print("[Drop] Drop event triggered.")
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            print(f"[Drop] File dropped: {path}")
            if path.endswith(".json"):
                self.load_quests(path)
            else:
                print(f"[Drop] Ignored non-JSON file: {path}")

    def load_quests(self, file_path):
        print(f"[Load] Attempting to load file: {file_path}")
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                quests = json.load(f)
                print(f"[Load] Parsed JSON successfully. Found {len(quests)} quests.")
        except Exception as e:
            msg = f"Failed to read file:\n{e}"
            print(f"[Error] {msg}")
            self.text_edit.setPlainText(msg)
            return

        lines = []
        for quest in quests:
            try:
                q_num = quest['quest_number']
                q_title = quest['title']
                q_rules = quest['rules']
                lines.append(f"Q{q_num}: {q_title}")
                lines.append(f"[] Validate: {q_rules}")

                reward_pairs = quest.get("win_reward_pairs", [])
                for pair in reward_pairs:
                    rewards = pair.get("reward", {})
                    reward_text = ", ".join(
                        f"{k.replace('_', ' ').capitalize()}{f' x{v}' if isinstance(v, int) and v > 1 else ''}"
                        for k, v in rewards.items()
                    )
                    lines.append(f"[] Validate: {reward_text}")
                lines.append("")

            except Exception as e:
                error_msg = f"[Parse Error] Malformed quest entry: {e}"
                print(error_msg)
                lines.append(error_msg)

        result = "\n".join(lines)
        self.text_edit.setPlainText(result)
        print("[Done] Output written to text box.")

if __name__ == "__main__":
    print("[Start] Launching application...")
    app = QApplication(sys.argv)
    window = QuestFormatter()
    window.show()
    sys.exit(app.exec())
