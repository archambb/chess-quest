import sys
import os
import zipfile
import datetime

from PySide6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QFileDialog,
    QListWidget, QListWidgetItem, QTextEdit, QMessageBox,
    QHBoxLayout, QLabel, QStatusBar, QSpinBox, QCheckBox, QLineEdit
)
from PySide6.QtGui import QClipboard
from PySide6.QtCore import Qt

HEADER_PREFIX = "#### NEW FILE:"


class FilePackager(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("File Packager - Chess Quest Helper")
        self.resize(1000, 820)

        self.selected_dir = None
        self.chunks = []
        self.chunk_line_counts = []
        self.current_chunk_index = 0

        main_layout = QVBoxLayout()

        # Select Directory
        self.dir_btn = QPushButton("Select Directory")
        self.dir_btn.clicked.connect(self.select_directory)
        main_layout.addWidget(self.dir_btn)

        # Option: include subdirectories
        self.recurse_checkbox = QCheckBox("Include subdirectories (full project tree)")
        self.recurse_checkbox.setChecked(True)
        self.recurse_checkbox.stateChanged.connect(self.refresh_file_list)
        main_layout.addWidget(self.recurse_checkbox)

        # Exclude filter row
        exclude_row = QHBoxLayout()
        exclude_row.addWidget(QLabel("Exclude paths containing (comma-separated):"))
        self.exclude_edit = QLineEdit("archive, raw assets")
        exclude_row.addWidget(self.exclude_edit)
        main_layout.addLayout(exclude_row)

        # File list
        self.list_widget = QListWidget()
        main_layout.addWidget(self.list_widget)

        # Chunk size control
        chunk_row = QHBoxLayout()
        chunk_row.addWidget(QLabel("Max lines per chunk:"))
        self.chunk_spin = QSpinBox()
        self.chunk_spin.setRange(500, 10000)
        self.chunk_spin.setValue(2500)
        chunk_row.addWidget(self.chunk_spin)
        main_layout.addLayout(chunk_row)

        # Chunk list (line counts)
        self.chunk_list = QListWidget()
        self.chunk_list.setMinimumHeight(150)
        main_layout.addWidget(QLabel("Generated Chunks:"))
        main_layout.addWidget(self.chunk_list)

        # Buttons
        btn_row = QHBoxLayout()
        self.output_btn = QPushButton("Generate Chunks ➜ Textbox")
        self.output_btn.clicked.connect(self.generate_chunks)

        self.copy_chunk_btn = QPushButton("Copy Chunk 1")
        self.copy_chunk_btn.clicked.connect(self.copy_current_chunk)

        self.structure_btn = QPushButton("Generate File Structure ➜ Textbox")
        self.structure_btn.clicked.connect(self.generate_structure)

        btn_row.addWidget(self.output_btn)
        btn_row.addWidget(self.copy_chunk_btn)
        btn_row.addWidget(self.structure_btn)
        main_layout.addLayout(btn_row)

        # Textbox
        self.textbox = QTextEdit()
        self.textbox.textChanged.connect(self.update_status)
        main_layout.addWidget(self.textbox)

        # Convert Text → ZIP
        self.to_files_btn = QPushButton("To Files ➜ Create ZIP")
        self.to_files_btn.clicked.connect(self.text_to_files)
        main_layout.addWidget(self.to_files_btn)

        # Status bar
        self.status = QStatusBar()
        self.status_label = QLabel("Lines: 0   Characters: 0   Total Project Lines: 0")
        self.status.addPermanentWidget(self.status_label)
        main_layout.addWidget(self.status)

        self.setLayout(main_layout)

    # ---------------------------------------------------------------
    def update_status(self):
        text = self.textbox.toPlainText()
        lines = text.count("\n") + (1 if text else 0)
        chars = len(text)
        total = sum(self.chunk_line_counts) if self.chunk_line_counts else 0
        self.status_label.setText(
            f"Lines: {lines:,}   Characters: {chars:,}   Total Project Lines: {total:,}"
        )

    # ---------------------------------------------------------------
    def select_directory(self):
        path = QFileDialog.getExistingDirectory(self, "Select directory containing .py files")
        if not path:
            return
        self.selected_dir = path
        self.refresh_file_list()

    # Helper: parse exclude substrings
    def _get_exclude_substrings(self):
        raw = self.exclude_edit.text().strip()
        if not raw:
            return []
        return [s.strip().lower() for s in raw.split(",") if s.strip()]

    # Helper: iterate .py files (relative path, absolute path)
    def iter_py_files(self):
        files = []
        if not self.selected_dir:
            return files

        exclude_subs = self._get_exclude_substrings()

        def is_excluded(rel_path: str) -> bool:
            rp = rel_path.lower()
            for sub in exclude_subs:
                if sub in rp:
                    return True
            return False

        if self.recurse_checkbox.isChecked():
            # full project tree
            for root, dirs, filenames in os.walk(self.selected_dir):
                for name in sorted(filenames):
                    if not name.lower().endswith(".py"):
                        continue
                    full_path = os.path.join(root, name)
                    rel_path = os.path.relpath(full_path, self.selected_dir)
                    rel_path = rel_path.replace(os.sep, "/")
                    if is_excluded(rel_path):
                        continue
                    files.append((rel_path, full_path))
        else:
            # just top-level
            for name in sorted(os.listdir(self.selected_dir)):
                if not name.lower().endswith(".py"):
                    continue
                full_path = os.path.join(self.selected_dir, name)
                rel_path = name
                if is_excluded(rel_path):
                    continue
                files.append((rel_path, full_path))

        return files

    def refresh_file_list(self):
        self.list_widget.clear()
        if not self.selected_dir:
            return

        for rel_path, _ in self.iter_py_files():
            self.list_widget.addItem(rel_path)

    # ---------------------------------------------------------------
    def load_files(self):
        """
        Load all files listed in the UI (using their relative paths)
        and prepend the HEADER_PREFIX line with the relative path.
        """
        all_files = []

        for i in range(self.list_widget.count()):
            rel_path = self.list_widget.item(i).text()
            full_path = os.path.join(self.selected_dir, rel_path.replace("/", os.sep))

            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    lines = f.read().splitlines()
            except Exception as e:
                lines = [f"[ERROR READING FILE: {e}]"]

            header = f"{HEADER_PREFIX} {rel_path} ####"
            all_files.append((rel_path, [header] + lines + [""]))

        return all_files

    # ---------------------------------------------------------------
    def generate_chunks(self):
        if not self.selected_dir:
            QMessageBox.warning(self, "Error", "Please select a directory first.")
            return

        max_lines = self.chunk_spin.value()
        files = self.load_files()

        self.chunks = []
        self.chunk_line_counts = []
        self.current_chunk_index = 0

        current_chunk = []
        current_lines = 0

        # Split into chunks
        for fname, lines in files:
            file_len = len(lines)

            if current_lines + file_len > max_lines and current_chunk:
                self.chunks.append(current_chunk)
                self.chunk_line_counts.append(current_lines)
                current_chunk = []
                current_lines = 0

            current_chunk.extend(lines)
            current_lines += file_len

        if current_chunk:
            self.chunks.append(current_chunk)
            self.chunk_line_counts.append(current_lines)

        # Fill chunk list
        self.chunk_list.clear()
        for i, count in enumerate(self.chunk_line_counts, 1):
            item = QListWidgetItem(f"Chunk {i} — {count:,} lines")
            self.chunk_list.addItem(item)

        # Build preview text
        preview = []
        for i, chunk in enumerate(self.chunks, 1):
            preview.append(f"=== CHUNK {i} ({self.chunk_line_counts[i-1]:,} lines) ===")
            preview.extend(chunk)
            preview.append("")

        self.textbox.setPlainText("\n".join(preview))
        self.update_status()

        # Reset copy button
        self.copy_chunk_btn.setText("Copy Chunk 1")

        QMessageBox.information(self, "Chunks Created",
                                f"Created {len(self.chunks)} chunks.\nMax {max_lines} lines each.")

    # ---------------------------------------------------------------
    def copy_current_chunk(self):
        if not self.chunks:
            QMessageBox.warning(self, "Error", "No chunks generated yet.")
            return

        chunk_text = "\n".join(self.chunks[self.current_chunk_index])
        QApplication.clipboard().setText(chunk_text, QClipboard.Clipboard)

        # Next chunk
        self.current_chunk_index = (self.current_chunk_index + 1) % len(self.chunks)
        next_num = self.current_chunk_index + 1
        self.copy_chunk_btn.setText(f"Copy Chunk {next_num}")

        QMessageBox.information(self, "Copied",
                                f"Copied chunk {next_num if next_num != 1 else len(self.chunks)}.")

    # ---------------------------------------------------------------
    def generate_structure(self):
        """
        Build a complete file-structure listing (with line counts)
        for the currently selected directory (respecting recurse & exclude options)
        and send it to the textbox.
        """
        if not self.selected_dir:
            QMessageBox.warning(self, "Error", "Please select a directory first.")
            return

        files = self.iter_py_files()
        if not files:
            QMessageBox.warning(self, "Error", "No .py files found (after filtering).")
            return

        lines_out = []
        file_line_counts = []
        total_lines = 0

        lines_out.append(f"Project root: {self.selected_dir}")
        lines_out.append("")
        lines_out.append("Python files:")

        for rel_path, full_path in files:
            try:
                with open(full_path, "r", encoding="utf-8") as f:
                    ln = f.read().count("\n") + 1
            except Exception as e:
                ln = 0
                lines_out.append(f"- {rel_path}  [ERROR: {e}]")
            else:
                lines_out.append(f"- {rel_path}  ({ln} lines)")

            file_line_counts.append(ln)
            total_lines += ln

        lines_out.append("")
        lines_out.append(f"Total files: {len(files)}")
        lines_out.append(f"Total lines: {total_lines}")

        self.chunk_line_counts = file_line_counts
        self.textbox.setPlainText("\n".join(lines_out))
        self.update_status()

    # ---------------------------------------------------------------
    def text_to_files(self):
        raw = self.textbox.toPlainText().strip()
        if not raw:
            QMessageBox.warning(self, "Error", "Textbox is empty.")
            return

        lines = raw.splitlines()
        files = {}
        current_file = None
        buf = []

        def flush():
            nonlocal buf, current_file
            if current_file:
                files[current_file] = "\n".join(buf).rstrip("\n")

        for line in lines:
            if line.startswith(HEADER_PREFIX):
                flush()
                buf = []
                fname = line.replace(HEADER_PREFIX, "").replace("####", "").strip()
                current_file = fname
            else:
                buf.append(line)

        flush()

        if not files:
            QMessageBox.warning(self, "Error",
                                "No files detected in textbox.")
            return

        top_file = list(files.keys())[0]
        now = datetime.datetime.now()
        zip_default = f"{now:%Y%m%d}{os.path.splitext(os.path.basename(top_file))[0]}.zip"

        zip_path, _ = QFileDialog.getSaveFileName(
            self, "Save ZIP", zip_default, "Zip Files (*.zip)"
        )

        if not zip_path:
            return

        try:
            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                for fname, content in files.items():
                    # fname may contain subdirectories (e.g. "core/app.py")
                    z.writestr(fname, content)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to create ZIP:\n{e}")
            return

        QMessageBox.information(self, "Success", f"ZIP created:\n{zip_path}")


# ---------------------------------------------------------------
if __name__ == "__main__":
    app = QApplication(sys.argv)
    w = FilePackager()
    w.show()
    sys.exit(app.exec())
