import json
import os
from typing import Any, Dict, List, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)


class SoraPrompterMainWindow(QMainWindow):
    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("SORA Prompter")

        self.knight_description: str = ""
        self.style_description: str = ""
        self.entries: List[Dict[str, Any]] = []

        self._build_ui()
        self._build_menu()

        # Try to auto-load a default JSON on startup
        default_path = os.path.join(os.path.dirname(__file__), "story_image_prompts.json")
        if os.path.exists(default_path):
            self.load_json(default_path)

    # ─────────────────────────────────────────────────────────────
    # UI setup
    # ─────────────────────────────────────────────────────────────
    def _build_ui(self) -> None:
        central = QWidget(self)
        self.setCentralWidget(central)

        main_layout = QHBoxLayout(central)

        # Left: list of frames
        left_layout = QVBoxLayout()
        self.list_label = QLabel("Frames / Scenes:")
        self.scene_list = QListWidget()
        self.scene_list.currentItemChanged.connect(self.on_scene_selected)

        left_layout.addWidget(self.list_label)
        left_layout.addWidget(self.scene_list)

        # Right: prompt viewer + copy button
        right_layout = QVBoxLayout()
        self.prompt_label = QLabel("Prompt:")
        self.prompt_view = QTextEdit()
        self.prompt_view.setReadOnly(True)

        self.copy_button = QPushButton("Copy Prompt to Clipboard")
        self.copy_button.clicked.connect(self.copy_to_clipboard)

        right_layout.addWidget(self.prompt_label)
        right_layout.addWidget(self.prompt_view, stretch=1)
        right_layout.addWidget(self.copy_button)

        main_layout.addLayout(left_layout, stretch=1)
        main_layout.addLayout(right_layout, stretch=2)

        self.resize(1000, 600)

    def _build_menu(self) -> None:
        menubar = self.menuBar()
        file_menu = menubar.addMenu("&File")

        open_action = QAction("Open JSON…", self)
        open_action.triggered.connect(self.open_json_dialog)
        file_menu.addAction(open_action)

        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    # ─────────────────────────────────────────────────────────────
    # JSON loading
    # ─────────────────────────────────────────────────────────────
    def open_json_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open SORA Prompt JSON",
            "",
            "JSON Files (*.json);;All Files (*)",
        )
        if not path:
            return

        self.load_json(path)

    def load_json(self, path: str) -> None:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Failed to load JSON:\n{e}")
            return

        try:
            global_data = data.get("global", {})
            images_data = data.get("images", {})

            self.knight_description = global_data.get("knight_description", "").strip()
            self.style_description = global_data.get("style", "").strip()

            self.entries.clear()
            self.scene_list.clear()

            # Flatten images into a list of entries
            for story_name, entries in images_data.items():
                if not isinstance(entries, list):
                    continue
                for entry in entries:
                    start_frame = entry.get("start_frame")
                    end_frame = entry.get("end_frame")
                    scene_text = entry.get("scene")
                    prompt_text = entry.get("prompt")

                    # Store everything we might need
                    model_entry = {
                        "story_name": story_name,
                        "start_frame": start_frame,
                        "end_frame": end_frame,
                        "scene": scene_text,
                        "prompt": prompt_text,
                    }
                    self.entries.append(model_entry)

            # Populate list widget
            for idx, entry in enumerate(self.entries):
                story_name = entry.get("story_name", "Unknown")
                start_frame = entry.get("start_frame", "?")
                end_frame = entry.get("end_frame", "?")
                label = f"{story_name}  [frames {start_frame}-{end_frame}]"
                item = QListWidgetItem(label)
                # Store index in item
                item.setData(Qt.UserRole, idx)
                self.scene_list.addItem(item)

            if self.entries:
                self.scene_list.setCurrentRow(0)

            self.statusBar().showMessage(f"Loaded: {os.path.basename(path)}", 5000)

        except Exception as e:  # noqa: BLE001
            QMessageBox.critical(self, "Error", f"Invalid JSON structure:\n{e}")

    # ─────────────────────────────────────────────────────────────
    # Selection & prompt building
    # ─────────────────────────────────────────────────────────────
    def on_scene_selected(
        self,
        current: Optional[QListWidgetItem],
        previous: Optional[QListWidgetItem],  # noqa: ARG002
    ) -> None:
        if current is None:
            self.prompt_view.clear()
            return

        idx = current.data(Qt.UserRole)
        if idx is None:
            self.prompt_view.clear()
            return

        try:
            entry = self.entries[int(idx)]
        except (IndexError, ValueError):
            self.prompt_view.clear()
            return

        full_prompt = self.build_full_prompt(entry)
        self.prompt_view.setPlainText(full_prompt)

    def build_full_prompt(self, entry: Dict[str, Any]) -> str:
        """
        Build the full prompt from globals + scene/entry.
        If the JSON provides 'scene', we use globals + scene.
        If only 'prompt' exists, we just show that prompt as-is.
        """

        start_frame = entry.get("start_frame")
        end_frame = entry.get("end_frame")
        scene_text = entry.get("scene")
        prompt_text = entry.get("prompt")

        # If we have a separate scene and global info, build the full “The Knight Description / Style / Scene” prompt
        if scene_text:
            parts: List[str] = []

            # Optional: show frames at the very top for reference
            if start_frame is not None and end_frame is not None:
                parts.append(f"Frames: {start_frame}-{end_frame}\n")

            if self.knight_description:
                parts.append(f"The Knight Description: {self.knight_description}")
            if self.style_description:
                parts.append(f"\nStyle: {self.style_description}")

            parts.append(f"\n\nScene: {scene_text}")

            return "".join(parts).strip()

        # Fallback: if JSON already has a combined 'prompt', just show that.
        if prompt_text:
            return str(prompt_text).strip()

        # Last resort: nothing usable
        return "No prompt or scene text available for this entry."

    # ─────────────────────────────────────────────────────────────
    # Clipboard
    # ─────────────────────────────────────────────────────────────
    def copy_to_clipboard(self) -> None:
        text = self.prompt_view.toPlainText().strip()
        if not text:
            QMessageBox.information(self, "Copy", "Nothing to copy.")
            return

        QApplication.clipboard().setText(text)
        self.statusBar().showMessage("Prompt copied to clipboard.", 3000)


def main() -> None:
    import sys

    app = QApplication(sys.argv)
    window = SoraPrompterMainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
