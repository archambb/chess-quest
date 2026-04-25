import sys
import json
import os
import shutil

from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget,
    QHBoxLayout, QVBoxLayout, QListWidget, QSplitter,
    QGraphicsView, QGraphicsScene, QGraphicsItem, QGraphicsPathItem,
    QLabel, QMenu, QComboBox, QTextEdit,
    QTableWidget, QTableWidgetItem, QPushButton,
    QListWidgetItem, QDialog, QInputDialog, QMessageBox,
    QListView, QAbstractItemView
)
from PySide6.QtCore import Qt, QRectF, Signal, QPointF, QSize
from PySide6.QtGui import (
    QBrush, QColor, QPen, QPainterPath, QPainter,
    QPixmap, QIcon
)

# ─────────────────────────────────────────────────────────────
# Paths for images and SORA prompts
# ─────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FRAMES_DIR = os.path.normpath(os.path.join(BASE_DIR, "..", "assets", "GFX", "frame"))
PROMPTS_PATH = os.path.normpath(os.path.join(BASE_DIR, "..", "tools", "story_image_prompts.json"))

os.makedirs(FRAMES_DIR, exist_ok=True)

# ─────────────────────────────────────────────────────────────
# Constants for rewards
# ─────────────────────────────────────────────────────────────

POWERUPS = [
    "bombs",
    "freezes",
    "swaps",
    "shields",
    "advanced_shields",
    "promotions",
    "time_warps",
    "magnets"
]

SPELLS = [
    "Desert Sun",
    "Flood",
    "Granite Elf",
    "Greed",
    "Heal Pawns",
    "Ice Blast",
    "Inspire Soldier",
    "Meteor Shower",
    "Mirror Armies",
    "One With Light",
    "Orb of Premonition",
    "Sacrifice",
    "Shadow Step",
    "Summon Elf",
    "Summon Undead Elves",
    "Wind Storm"
]

# ─────────────────────────────────────────────────────────────
# Data Model
# ─────────────────────────────────────────────────────────────

class StoryProject:
    """
    Loads and saves frames.json and stories.json.
    Frames support two formats:
      - Legacy: option_1/story_1/... + frame["return_choice"]
      - New:   frame["options"] = [{text, target, return_choice}, ...]
    """

    def __init__(self,
                 frames_path="data/frames.json",
                 stories_path="data/stories.json"):
        self.frames_path = frames_path
        self.stories_path = stories_path

        self.frames = {}   # {frame_id (str): dict}
        self.stories = {}  # {story_name: [frame_ids]}
        self.load()

    def load(self):
        if not os.path.exists(self.frames_path):
            raise FileNotFoundError(f"frames file not found: {self.frames_path}")
        if not os.path.exists(self.stories_path):
            raise FileNotFoundError(f"stories file not found: {self.stories_path}")

        with open(self.frames_path, "r", encoding="utf-8") as f:
            self.frames = json.load(f)

        with open(self.stories_path, "r", encoding="utf-8") as f:
            self.stories = json.load(f)

    def save(self):
        # Make sure directories exist
        if self.frames_path:
            d = os.path.dirname(self.frames_path)
            if d:
                os.makedirs(d, exist_ok=True)
        if self.stories_path:
            d = os.path.dirname(self.stories_path)
            if d:
                os.makedirs(d, exist_ok=True)

        with open(self.frames_path, "w", encoding="utf-8") as f:
            json.dump(self.frames, f, indent=2, ensure_ascii=False)

        with open(self.stories_path, "w", encoding="utf-8") as f:
            json.dump(self.stories, f, indent=2, ensure_ascii=False)

        print("[SAVE] frames.json and stories.json written.")


# ─────────────────────────────────────────────────────────────
# SORA Prompt Manager
# ─────────────────────────────────────────────────────────────

class StoryImagePromptManager:
    """
    Handles loading/saving SORA prompts from story_image_prompts.json.

    The JSON format:

    {
      "global": {...},
      "images": {
        "Intro": [
          { "start_frame": 1, "end_frame": 6, "prompt": "..." },
          ...
        ],
        "Stone_Plead_1": [...]
      }
    }

    For a given frame_id, we look for any entry where
    start_frame <= frame_id <= end_frame.

    When saving:
      - If an entry already exists covering that frame, we update its 'prompt'
        (affects the whole range).
      - If none exists and text is non-empty, we create a new range in a
        "Misc" bucket with start=end=frame_id.
    """

    def __init__(self, path=PROMPTS_PATH):
        self.path = path
        self.data = {"global": {}, "images": {}}
        self.load()

    def load(self):
        if os.path.exists(self.path):
            with open(self.path, "r", encoding="utf-8") as f:
                self.data = json.load(f)
        else:
            self.data = {"global": {}, "images": {}}

    def save(self):
        d = os.path.dirname(self.path)
        if d:
            os.makedirs(d, exist_ok=True)
        with open(self.path, "w", encoding="utf-8") as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)
        print("[SAVE] story_image_prompts.json written.")

    def _find_entry_for_frame(self, frame_id: int):
        images_dict = self.data.get("images", {})
        for bucket_name, entries in images_dict.items():
            if not isinstance(entries, list):
                continue
            for idx, entry in enumerate(entries):
                try:
                    start_f = int(entry.get("start_frame", 0))
                    end_f = int(entry.get("end_frame", 0))
                except (TypeError, ValueError):
                    continue
                if start_f <= frame_id <= end_f:
                    return bucket_name, idx, entry
        return None, None, None

    def get_prompt_for_frame(self, frame_id: int) -> str:
        _, _, entry = self._find_entry_for_frame(frame_id)
        if not entry:
            return ""

        prompt = entry.get("prompt", "")
        if isinstance(prompt, str):
            return prompt

        # Future-proof: show structured prompt JSON as text if needed
        try:
            return json.dumps(prompt, indent=2, ensure_ascii=False)
        except Exception:
            return str(prompt)

    def set_prompt_for_frame(self, frame_id: int, text: str):
        """
        Update or create a prompt entry for this frame.
        If the text is empty and no entry exists, we do nothing.
        """
        text = text or ""
        bucket_name, idx, entry = self._find_entry_for_frame(frame_id)

        if entry is None:
            # No existing entry
            if not text.strip():
                # nothing to store
                return
            images_dict = self.data.setdefault("images", {})
            # Use a generic bucket so you don't have to decide story name now.
            bucket = images_dict.setdefault("Misc", [])
            new_entry = {
                "start_frame": frame_id,
                "end_frame": frame_id,
                "prompt": text,
            }
            bucket.append(new_entry)
            print(f"[PROMPTS] Created new Misc entry for frame {frame_id}")
        else:
            entry["prompt"] = text
            print(f"[PROMPTS] Updated prompt for frame {frame_id} in bucket '{bucket_name}'")

        self.save()


# ─────────────────────────────────────────────────────────────
# Frame Images Widget (bottom strip, drag & drop)
# ─────────────────────────────────────────────────────────────

class FrameImageListWidget(QListWidget):
    """
    Shows all images for the current frame:

        ..\\GFX\\frame\\frame_<frame_id>_<counter>.png

    - Icon view, horizontal flow.
    - Accepts drag-dropped .png files from the OS:
        * Computes next counter for that frame.
        * Copies as frame_<frame_id>_<next>.png into FRAMES_DIR.
    """

    images_changed = Signal()  # 🔔 tell MainWindow when images may have changed

    def __init__(self, frames_dir: str, parent=None):
        super().__init__(parent)
        self.frames_dir = frames_dir
        self.current_frame_id = None

        self.setViewMode(QListView.IconMode)
        self.setIconSize(QSize(128, 72))
        self.setResizeMode(QListView.Adjust)
        self.setMovement(QListView.Static)
        self.setSpacing(8)
        self.setWrapping(True)
        self.setFlow(QListView.LeftToRight)

        # changed from NoSelection so we can see what we right-clicked, if you want
        self.setSelectionMode(QAbstractItemView.SingleSelection)

        # 🔑 Allow external drops
        self.setAcceptDrops(True)
        self.viewport().setAcceptDrops(True)
        self.setDropIndicatorShown(True)

        # We don't want to drag *from* this widget, only drop *into* it
        self.setDragEnabled(False)
        self.setDragDropMode(QAbstractItemView.DropOnly)

        self.setMinimumHeight(120)

    # --- context menu for per-image actions ---

    def contextMenuEvent(self, event):
        """
        Right-click on an image → show 'Reassign...' menu.
        """
        item = self.itemAt(event.pos())
        if item is None:
            return  # no menu on empty space for now

        menu = QMenu(self)
        act_reassign = menu.addAction("Reassign...")

        chosen = menu.exec(event.globalPos())
        if chosen == act_reassign:
            self._reassign_image_dialog(item)

    def _parse_frame_and_counter(self, filename: str):
        """
        filename like 'frame_186_1.png' -> (186, 1)
        Returns (None, None) on failure.
        """
        try:
            base = os.path.splitext(filename)[0]  # 'frame_186_1'
            parts = base.split("_")
            if len(parts) < 3 or parts[0] != "frame":
                return None, None
            frame_id = int(parts[1])
            counter = int(parts[2])
            return frame_id, counter
        except Exception:
            return None, None

    def _reassign_image_dialog(self, item: QListWidgetItem):
        """
        Ask for a new frame number and move/rename the file accordingly,
        then renumber the source frame's remaining images to be compact.
        """
        fname = item.text()
        old_frame, old_counter = self._parse_frame_and_counter(fname)
        if old_frame is None:
            QMessageBox.warning(self, "Invalid filename",
                                f"Cannot parse frame/counter from '{fname}'.")
            return

        # Ask user for new frame number
        new_frame, ok = QInputDialog.getInt(
            self,
            "Reassign Image",
            "Reassign to frame number:",
            old_frame,     # initial value
            1,             # minValue
            999999,        # maxValue (or something sane)
            1              # step
        )

        if not ok:
            return

        if new_frame == old_frame:
            # No-op; nothing to do.
            return

        # Ensure directory exists
        os.makedirs(self.frames_dir, exist_ok=True)

        # Compute new counter for destination frame
        dest_prefix = f"frame_{new_frame}_"
        existing_dest = [
            f for f in os.listdir(self.frames_dir)
            if f.startswith(dest_prefix) and f.lower().endswith(".png")
        ]

        dest_counters = []
        for name in existing_dest:
            base = os.path.splitext(name)[0]
            parts = base.split("_")
            try:
                dest_counters.append(int(parts[-1]))
            except Exception:
                continue

        if dest_counters:
            new_counter = max(dest_counters) + 1
        else:
            new_counter = 1

        old_path = os.path.join(self.frames_dir, fname)
        new_name = f"frame_{new_frame}_{new_counter}.png"
        new_path = os.path.join(self.frames_dir, new_name)

        # Move/rename the selected image to its new frame
        try:
            os.rename(old_path, new_path)
            print(f"[FRAME IMG] Reassigned {old_path} -> {new_path}")
        except Exception as e:
            QMessageBox.warning(
                self,
                "Reassign failed",
                f"Failed to move:\n{old_path}\n→ {new_path}\n\nError: {e}",
            )
            return

        # Now compact the counters for the *source* frame (old_frame)
        self._compact_frame_counters(old_frame)

        # Refresh UI + emit images_changed (MainWindow will re-highlight stories)
        self.refresh()

    def _compact_frame_counters(self, frame_id: int):
        """
        For a given frame N, rename all frame_N_x.png to frame_N_1.png, 2, 3...
        in ascending order of the original counter, preserving order but removing gaps.
        """
        prefix = f"frame_{frame_id}_"
        files = [
            f for f in os.listdir(self.frames_dir)
            if f.startswith(prefix) and f.lower().endswith(".png")
        ]

        def _counter_from_name(name: str):
            try:
                base = os.path.splitext(name)[0]  # frame_186_2
                parts = base.split("_")
                return int(parts[-1])
            except Exception:
                return 0

        files.sort(key=_counter_from_name)

        next_index = 1
        for name in files:
            current_counter = _counter_from_name(name)
            if current_counter == 0:
                continue

            desired_name = f"frame_{frame_id}_{next_index}.png"
            if name != desired_name:
                src = os.path.join(self.frames_dir, name)
                dst = os.path.join(self.frames_dir, desired_name)
                # No conflict expected because we're moving to lower indexes
                try:
                    os.rename(src, dst)
                    print(f"[FRAME IMG] Renumber {src} -> {dst}")
                except Exception as e:
                    print(f"[FRAME IMG] Failed to renumber {name}: {e}")
            next_index += 1

    # --- public API ---

    def set_frame(self, frame_id: int | None):
        self.current_frame_id = frame_id
        self.refresh()

    def refresh(self):
        self.clear()
        if not self.current_frame_id:
            return

        if not os.path.isdir(self.frames_dir):
            os.makedirs(self.frames_dir, exist_ok=True)

        prefix = f"frame_{self.current_frame_id}_"
        files = [
            f for f in os.listdir(self.frames_dir)
            if f.startswith(prefix) and f.lower().endswith(".png")
        ]

        def _counter_from_name(name: str):
            try:
                base = os.path.splitext(name)[0]  # frame_133_2
                parts = base.split("_")
                return int(parts[-1])
            except Exception:
                return 0

        files.sort(key=_counter_from_name)

        for fname in files:
            path = os.path.join(self.frames_dir, fname)
            pix = QPixmap(path)
            if not pix.isNull():
                icon = QIcon(pix)
                item = QListWidgetItem(icon, fname)
            else:
                item = QListWidgetItem(fname)
            item.setToolTip(path)
            self.addItem(item)

        # 🔔 Notify that the image set for some frame may have changed
        self.images_changed.emit()

    # --- drag & drop ---

    def dragEnterEvent(self, event):
        if self._has_acceptable_urls(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dragMoveEvent(self, event):
        if self._has_acceptable_urls(event):
            event.acceptProposedAction()
        else:
            event.ignore()

    def dropEvent(self, event):
        if not self.current_frame_id:
            QMessageBox.warning(self, "No frame selected",
                                "Select a frame before dropping images.")
            event.ignore()
            return

        mime = event.mimeData()
        if not mime.hasUrls():
            event.ignore()
            return

        urls = mime.urls()
        if not urls:
            event.ignore()
            return

        os.makedirs(self.frames_dir, exist_ok=True)

        for url in urls:
            src_path = url.toLocalFile()
            if not src_path:
                continue

            ext = os.path.splitext(src_path)[1].lower()
            if ext != ".png":
                QMessageBox.warning(
                    self,
                    "Unsupported file",
                    f"Only .png files are supported.\n\nSkipped: {src_path}",
                )
                continue

            # Find next counter for this frame
            prefix = f"frame_{self.current_frame_id}_"
            existing = [
                f for f in os.listdir(self.frames_dir)
                if f.startswith(prefix) and f.lower().endswith(".png")
            ]

            counters = []
            for name in existing:
                base = os.path.splitext(name)[0]
                parts = base.split("_")
                try:
                    counters.append(int(parts[-1]))
                except Exception:
                    continue

            next_counter = (max(counters) + 1) if counters else 1
            dest_name = f"frame_{self.current_frame_id}_{next_counter}.png"
            dest_path = os.path.join(self.frames_dir, dest_name)

            try:
                # MOVE instead of copy → delete the source
                shutil.move(src_path, dest_path)
                print(f"[FRAME IMG] Moved {src_path} -> {dest_path}")
            except Exception as e:
                QMessageBox.warning(
                    self,
                    "Move failed",
                    f"Failed to move:\n{src_path}\n\nError: {e}",
                )

        self.refresh()
        event.acceptProposedAction()


    def _has_acceptable_urls(self, event) -> bool:
        mime = event.mimeData()
        if not mime.hasUrls():
            return False
        for url in mime.urls():
            path = url.toLocalFile()
            if not path:
                continue
            ext = os.path.splitext(path)[1].lower()
            if ext == ".png":
                return True
        return False


# ─────────────────────────────────────────────────────────────
# Graphics Items (Nodes & Edges)
# ─────────────────────────────────────────────────────────────

class StoryNodeItem(QGraphicsItem):
    """
    Rectangular / oval node representing a story (Intro, Tutorial, etc.).

    - Green oval: entry point (no incoming edges)
    - Red oval: story has at least one option with return_choice = true
    - Gray rounded rectangle: normal story
    """
    WIDTH = 220
    HEIGHT = 80

    def __init__(self, story_name, frame_count):
        super().__init__()
        self.story_name = story_name
        self.frame_count = frame_count
        self.edges = []  # StoryEdgeItem instances

        self.is_entry_node = False     # computed by graph
        self.is_return_node = False    # computed by graph

        self.setFlags(
            QGraphicsItem.ItemIsMovable |
            QGraphicsItem.ItemIsSelectable |
            QGraphicsItem.ItemSendsGeometryChanges
        )

    def add_edge(self, edge):
        self.edges.append(edge)

    def boundingRect(self) -> QRectF:
        return QRectF(0, 0, self.WIDTH, self.HEIGHT)

    def paint(self, painter: QPainter, option, widget=None):
        rect = self.boundingRect()

        # Determine fill color and shape
        if self.is_return_node:
            base_color = QColor("#3d0c0c")  # red-ish
            shape = "oval"
        elif self.is_entry_node:
            base_color = QColor("#093809")  # green-ish
            shape = "oval"
        else:
            base_color = QColor("#e0e0e0")  # neutral
            shape = "rect"

        if self.isSelected():
            # Slightly darker when selected
            base_color = base_color.darker(110)

        painter.setBrush(QBrush(base_color))
        painter.setPen(QPen(Qt.black, 2))

        if shape == "oval":
            painter.drawEllipse(rect)
        else:
            painter.drawRoundedRect(rect, 10, 10)

        # Title
        painter.setPen(QPen(Qt.black))
        painter.drawText(rect.adjusted(8, 8, -8, -8),
                         Qt.AlignLeft | Qt.AlignTop,
                         self.story_name)

        # Metadata
        painter.setPen(QPen(Qt.darkGray))
        painter.drawText(rect.adjusted(8, 30, -8, -8),
                         Qt.AlignLeft | Qt.AlignTop,
                         f"Frames: {self.frame_count}")

    def itemChange(self, change, value):
        """
        When node moves, update connected edges.
        """
        if change == QGraphicsItem.ItemPositionHasChanged:
            for edge in self.edges:
                edge.update_path()
        return super().itemChange(change, value)

    def center_in_scene(self) -> QPointF:
        """Center point of this node in scene coordinates."""
        rect = self.boundingRect()
        return self.mapToScene(rect.center())


class StoryEdgeItem(QGraphicsPathItem):
    """
    Curved arrow from one story node to another, with a text label.
    """

    def __init__(self, source_node: StoryNodeItem, target_node: StoryNodeItem, label_text: str = ""):
        super().__init__()
        self.source_node = source_node
        self.target_node = target_node
        self.label_text = label_text

        self.setZValue(-1)  # draw under nodes
        self.setPen(QPen(QColor("#555555"), 2))

        # register with nodes
        self.source_node.add_edge(self)
        self.target_node.add_edge(self)

        self.update_path()

    def update_path(self):
        src = self.source_node.center_in_scene()
        dst = self.target_node.center_in_scene()

        path = QPainterPath(src)

        # Simple curved path: control points halfway with some vertical offset
        dx = dst.x() - src.x()
        dy = dst.y() - src.y()
        ctrl1 = QPointF(src.x() + dx * 0.25, src.y() + dy * 0.1 - 40)
        ctrl2 = QPointF(src.x() + dx * 0.75, src.y() + dy * 0.1 - 40)
        path.cubicTo(ctrl1, ctrl2, dst)

        self.setPath(path)

    def paint(self, painter: QPainter, option, widget=None):
        # Draw the path first
        painter.setPen(self.pen())
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(self.path())

        # Arrowhead at end
        path = self.path()
        length = path.length()
        if length > 10:
            end_point = path.pointAtPercent(1.0)
            tangent = path.angleAtPercent(1.0)
            angle = -tangent

            arrow_size = 10
            painter.save()
            painter.translate(end_point)
            painter.rotate(angle)

            p1 = QPointF(0, 0)
            p2 = QPointF(-arrow_size, arrow_size / 2)
            p3 = QPointF(-arrow_size, -arrow_size / 2)
            arrow_path = QPainterPath(p1)
            arrow_path.lineTo(p2)
            arrow_path.lineTo(p3)
            arrow_path.closeSubpath()

            painter.setBrush(QBrush(self.pen().color()))
            painter.drawPath(arrow_path)
            painter.restore()

        # Label near the middle of the edge
        if self.label_text:
            mid_point = path.pointAtPercent(0.5)
            text_rect = QRectF(mid_point.x() - 80, mid_point.y() - 12, 160, 24)
            painter.setPen(QPen(QColor("#333333")))
            painter.drawText(text_rect, Qt.AlignCenter, self._short_label())

    def _short_label(self) -> str:
        text = self.label_text.strip()
        if len(text) > 30:
            return text[:27] + "..."
        return text


# ─────────────────────────────────────────────────────────────
# Graph View
# ─────────────────────────────────────────────────────────────

class StoryGraphView(QGraphicsView):
    """
    Shows stories as nodes and edges between them.
    Emits story_selected when a node is clicked.

    Node flags:
      - is_entry_node: true if no incoming edges
      - is_return_node: true if any option in any frame has return_choice = true
    """
    story_selected = Signal(str)

    def __init__(self, project: StoryProject):
        super().__init__()

        self.project = project
        self.scene = QGraphicsScene(self)
        self.setScene(self.scene)

        self.setRenderHints(self.renderHints() | QPainter.Antialiasing)
        self.setDragMode(QGraphicsView.RubberBandDrag)

        self.nodes = {}   # story_name -> StoryNodeItem
        self.edges = []   # list of StoryEdgeItem

        self._build_nodes()
        self._build_edges()
        self.recompute_node_flags()
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    # --- build graph ---

    def _build_nodes(self):
        spacing_x = 300
        spacing_y = 180
        x = 0
        y = 0
        i = 0

        for story_name in sorted(self.project.stories.keys()):
            frame_ids = self.project.stories[story_name]
            node = StoryNodeItem(story_name, len(frame_ids))
            node.setPos(x, y)
            self.scene.addItem(node)
            self.nodes[story_name] = node

            x += spacing_x
            i += 1
            if i % 3 == 0:
                x = 0
                y += spacing_y

    @staticmethod
    def _extract_options_from_frame(frame_data: dict):
        """
        Returns a list of option dicts:
          { "text": str, "target": str, "return_choice": bool }
        Supports legacy and new formats.
        """
        options = []

        if isinstance(frame_data.get("options"), list):
            for opt in frame_data["options"]:
                if not isinstance(opt, dict):
                    continue
                text = opt.get("text", "").strip()
                target = opt.get("target", "").strip()
                rc = bool(opt.get("return_choice", False))
                if text or target or rc:
                    options.append({"text": text, "target": target, "return_choice": rc})
        else:
            # Legacy format: option_i / story_i + frame-level return_choice
            frame_rc = bool(frame_data.get("return_choice", False))
            i = 1
            while True:
                opt_key = f"option_{i}"
                tgt_key = f"story_{i}"
                if opt_key not in frame_data and tgt_key not in frame_data:
                    break
                text = frame_data.get(opt_key, "").strip()
                target = frame_data.get(tgt_key, "").strip()
                if text or target:
                    options.append({"text": text, "target": target, "return_choice": frame_rc})
                i += 1

        return options

    def _build_edges(self):
        """
        Clear and rebuild all edges from current project data.
        """
        # Remove old edges from scene
        for e in self.edges:
            self.scene.removeItem(e)
        self.edges.clear()

        seen_edges = set()  # (source_story, target_story, option_text)

        for story_name, frame_ids in self.project.stories.items():
            if story_name not in self.nodes:
                continue

            for frame_id in frame_ids:
                frame_key = str(frame_id)
                frame_data = self.project.frames.get(frame_key, {})
                if not frame_data:
                    continue

                options = self._extract_options_from_frame(frame_data)
                for opt in options:
                    option_text = opt["text"]
                    target_story = opt["target"]
                    if target_story and target_story in self.nodes:
                        sig = (story_name, target_story, option_text)
                        if sig not in seen_edges:
                            seen_edges.add(sig)
                            src_node = self.nodes[story_name]
                            dst_node = self.nodes[target_story]
                            edge = StoryEdgeItem(src_node, dst_node, option_text)
                            self.scene.addItem(edge)
                            self.edges.append(edge)

    def rebuild_edges_and_flags(self):
        """
        Rebuilds edges from current project + recomputes node flags,
        keeps existing node positions.
        """
        self._build_edges()
        self.recompute_node_flags()
        self.scene.setSceneRect(self.scene.itemsBoundingRect())

    def recompute_node_flags(self):
        """
        Recompute entry/return flags for all nodes.
        - entry: story with no incoming edges
        - return: story with any option where return_choice == True
        """
        for node in self.nodes.values():
            node.is_entry_node = False
            node.is_return_node = False

        # Compute incoming edge count from edges list
        indegree = {name: 0 for name in self.nodes.keys()}
        for edge in self.edges:
            indegree[edge.target_node.story_name] += 1

        for name, deg in indegree.items():
            if deg == 0:
                self.nodes[name].is_entry_node = True

        # Check return_choice flags in frames/options
        for story_name, frame_ids in self.project.stories.items():
            node = self.nodes.get(story_name)
            if not node:
                continue

            is_return_node = False
            for fid in frame_ids:
                frame = self.project.frames.get(str(fid), {})
                options = self._extract_options_from_frame(frame)

                # If any option has return_choice True, this is a return node
                if any(opt.get("return_choice") for opt in options):
                    is_return_node = True
                    break

                # Legacy safety net: frame-level return_choice without options
                if not options and frame.get("return_choice"):
                    is_return_node = True
                    break

            node.is_return_node = is_return_node

        for node in self.nodes.values():
            node.update()

    # --- dynamic node operations ---

    def add_story_node(self, story_name: str):
        """
        Create a new node for a freshly added story.
        Starts hidden (consistent with 'no branches visible' default).
        """
        if story_name in self.nodes:
            return

        y = len(self.nodes) * 50  # simple spacing
        node = StoryNodeItem(story_name, len(self.project.stories.get(story_name, [])))
        node.setPos(0, y)
        node.setVisible(False)
        self.scene.addItem(node)
        self.nodes[story_name] = node

    def remove_story_node(self, story_name: str):
        node = self.nodes.pop(story_name, None)
        if not node:
            return

        # Remove edges attached to this node
        for edge in list(self.edges):
            if edge.source_node is node or edge.target_node is node:
                self.scene.removeItem(edge)
                self.edges.remove(edge)

        self.scene.removeItem(node)

    # --- visibility controls ---

    def hide_all_nodes(self):
        for node in self.nodes.values():
            node.setVisible(False)
        for edge in self.edges:
            edge.setVisible(False)

    def show_all_nodes(self):
        for node in self.nodes.values():
            node.setVisible(True)
        for edge in self.edges:
            edge.setVisible(True)
        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    def hide_branch_from(self, story_name: str):
        """
        Hide this story node and all nodes reachable via outgoing edges.
        (Used by context menu 'Hide Branch From This Node'.)
        """
        start = self.nodes.get(story_name)
        if not start:
            return

        to_hide_nodes = set()
        stack = [start]

        while stack:
            node = stack.pop()
            if node in to_hide_nodes:
                continue
            to_hide_nodes.add(node)

            # follow outgoing edges only
            for edge in node.edges:
                if edge.source_node is node:
                    stack.append(edge.target_node)

        for node in to_hide_nodes:
            node.setVisible(False)
        for edge in self.edges:
            if (not edge.source_node.isVisible()) or (not edge.target_node.isVisible()):
                edge.setVisible(False)

    def show_branch_from(self, story_name: str):
        """
        Show this story node and all nodes that are connected to it
        via edges in *either* direction (full connected component).
        Hide everything else.
        """
        start = self.nodes.get(story_name)
        if not start:
            return

        # First hide all
        for node in self.nodes.values():
            node.setVisible(False)
        for edge in self.edges:
            edge.setVisible(False)

        # Flood-fill over undirected graph of nodes
        visible_nodes = set()
        stack = [start]

        while stack:
            node = stack.pop()
            if node in visible_nodes:
                continue
            visible_nodes.add(node)

            for edge in node.edges:
                # treat edges as undirected for visibility
                other = edge.source_node if edge.target_node is node else edge.target_node
                if other not in visible_nodes:
                    stack.append(other)

        # Now show only that component
        for node in visible_nodes:
            node.setVisible(True)

        for edge in self.edges:
            if edge.source_node in visible_nodes and edge.target_node in visible_nodes:
                edge.setVisible(True)

        self.scene.setSceneRect(self.scene.itemsBoundingRect())
        self.fitInView(self.scene.sceneRect(), Qt.KeepAspectRatio)

    # --- interaction ---

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        item = self.itemAt(event.pos())
        while item is not None and not isinstance(item, StoryNodeItem):
            item = item.parentItem()

        if isinstance(item, StoryNodeItem):
            self.story_selected.emit(item.story_name)

    def contextMenuEvent(self, event):
        """
        Right-click on graph:
         - on a node: "Hide Branch From This Node"
         - on empty space: "Show All Nodes"
        """
        item = self.itemAt(event.pos())
        while item is not None and not isinstance(item, StoryNodeItem):
            item = item.parentItem()

        menu = QMenu(self)

        if isinstance(item, StoryNodeItem):
            act_hide = menu.addAction("Hide Branch From This Node")
            chosen = menu.exec(event.globalPos())
            if chosen == act_hide:
                self.hide_branch_from(item.story_name)
        else:
            act_show_all = menu.addAction("Show All Nodes")
            chosen = menu.exec(event.globalPos())
            if chosen == act_show_all:
                self.show_all_nodes()

    def wheelEvent(self, event):
        """
        Simple zoom with ctrl+wheel (otherwise scroll).
        """
        if event.modifiers() & Qt.ControlModifier:
            zoom_in_factor = 1.25
            zoom_out_factor = 1 / zoom_in_factor

            if event.angleDelta().y() > 0:
                zoom_factor = zoom_in_factor
            else:
                zoom_factor = zoom_out_factor

            self.scale(zoom_factor, zoom_factor)
        else:
            super().wheelEvent(event)

    def focus_on_story(self, story_name: str):
        node = self.nodes.get(story_name)
        if node and node.isVisible():
            self.centerOn(node)
            # select only this node
            for n in self.nodes.values():
                n.setSelected(n is node)


# ─────────────────────────────────────────────────────────────
# Playthrough Simulator
# ─────────────────────────────────────────────────────────────

class PlaythroughDialog(QDialog):
    """
    Simple simulator of play_story for a given starting story.
    Uses per-option return_choice:
      - If return_choice is True: endpoint / return to caller
      - Else: jump to target story (if exists)
    """

    def __init__(self, project: StoryProject, start_story: str, parent=None):
        super().__init__(parent)
        self.project = project
        self.current_story = start_story
        self.frame_index = 0

        self.setWindowTitle(f"Playthrough: {start_story}")
        self.resize(700, 500)

        self.label_header = QLabel()
        self.text_frame = QTextEdit()
        self.text_frame.setReadOnly(True)
        self.label_status = QLabel()
        self.options_layout = QVBoxLayout()

        layout = QVBoxLayout(self)
        layout.addWidget(self.label_header)
        layout.addWidget(self.text_frame)
        layout.addWidget(self.label_status)
        layout.addLayout(self.options_layout)

        self._load_current_frame()

    def _clear_options(self):
        while self.options_layout.count():
            item = self.options_layout.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _get_current_frames_list(self):
        return self.project.stories.get(self.current_story, [])

    def _extract_options_from_frame(self, frame: dict):
        # Reuse same semantics as graph/editor
        return StoryGraphView._extract_options_from_frame(frame)

    def _load_current_frame(self):
        self._clear_options()

        frames = self._get_current_frames_list()
        if not frames:
            self.label_header.setText(f"Story: {self.current_story} (no frames)")
            self.text_frame.setPlainText("")
            self.label_status.setText("No frames in this story.")
            btn = QPushButton("Close")
            btn.clicked.connect(self.accept)
            self.options_layout.addWidget(btn)
            return

        if self.frame_index < 0 or self.frame_index >= len(frames):
            self.frame_index = 0

        frame_id = frames[self.frame_index]
        frame = self.project.frames.get(str(frame_id), {})

        self.label_header.setText(
            f"Story: {self.current_story}  |  Frame {self.frame_index + 1}/{len(frames)} (ID {frame_id})"
        )
        self.text_frame.setPlainText(frame.get("text", ""))

        options = self._extract_options_from_frame(frame)

        if options:
            self.label_status.setText("Choose an option:")
            for opt in options:
                text = opt.get("text", "")
                tgt = opt.get("target", "")
                label = text
                if tgt and tgt not in self.project.stories and not tgt.startswith("game_"):
                    label += "  [INVALID TARGET]"
                elif tgt.startswith("game_"):
                    label += f"  [mini-game: {tgt}]"
                btn = QPushButton(label)
                btn.clicked.connect(lambda _, o=opt: self._choose_option(o))
                self.options_layout.addWidget(btn)
        else:
            # No options → linear progression / end
            if self.frame_index < len(frames) - 1:
                self.label_status.setText("No options. Continue to next frame.")
                btn_next = QPushButton("Next Frame")
                btn_next.clicked.connect(self._next_frame)
                self.options_layout.addWidget(btn_next)
            else:
                self.label_status.setText("End of this story.")
                btn_close = QPushButton("Close Playthrough")
                btn_close.clicked.connect(self.accept)
                self.options_layout.addWidget(btn_close)

    def _next_frame(self):
        self.frame_index += 1
        self._load_current_frame()

    def _choose_option(self, option: dict):
        target_story = option.get("target", "").strip()
        return_choice = bool(option.get("return_choice", False))

        # Mini-game or explicit return_choice → treat as endpoint/return to caller
        if return_choice or target_story.startswith("game_"):
            if target_story.startswith("game_"):
                self.label_status.setText(f"Mini-game '{target_story}' would run here. Returning to caller.")
            else:
                self.label_status.setText("Return choice to caller (endpoint).")
            # Just close the simulator; in-game, the caller would handle this.
            self.accept()
            return

        if not target_story:
            self.label_status.setText("This option has no target story (invalid).")
            return
        if target_story not in self.project.stories:
            self.label_status.setText(f"Target story '{target_story}' does not exist (invalid).")
            return

        self.current_story = target_story
        self.frame_index = 0
        self._load_current_frame()


# ─────────────────────────────────────────────────────────────
# Editor Panel - Frame, options, rewards, SORA prompt, images
# ─────────────────────────────────────────────────────────────

class StoryEditorPanel(QWidget):
    """
    Story/frame editor:
      - choose story
      - choose frame within that story
      - edit text
      - edit options with per-option return_choice
      - edit return_rewards (powerups + spells)
      - SORA Prompt textbox (per frame, saved in story_image_prompts.json)
      - bottom frame showing all images for this frame and accepting drops
      - add new frame to current story (globally unique)
      - save frame (also saves SORA prompt)
      - save whole project (both JSON files)
      - run playthrough simulator from this story
    """

    frame_added = Signal(str, int)   # story_name, new_frame_id
    frame_saved = Signal(str)        # story_name

    def __init__(self, project: StoryProject):
        super().__init__()
        self.project = project

        self.current_story = None
        self.current_frame_id = None

        # SORA prompt manager
        self.prompt_manager = StoryImagePromptManager(PROMPTS_PATH)

        # Widgets
        self.label_story = QLabel("Story: (none)")
        self.combo_frame = QComboBox()
        self.combo_frame.currentTextChanged.connect(self._on_frame_changed)

        self.btn_add_frame = QPushButton("Add Frame to This Story")
        self.btn_add_frame.clicked.connect(self._add_frame_to_story)

        # SORA Prompt (top textbox)
        self.sora_prompt_edit = QTextEdit()
        self.sora_prompt_edit.setPlaceholderText("SORA Prompt for this frame (range-based in story_image_prompts.json)...")
        self.sora_prompt_edit.setMinimumHeight(100)

        self.text_edit = QTextEdit()
        self.text_edit.setPlaceholderText("Frame text...")

        # Options table: text, target, return?
        self.options_table = QTableWidget(0, 3)
        self.options_table.setHorizontalHeaderLabels(
            ["Option Text", "Target Story / game_*", "Return?"]
        )
        self.options_table.horizontalHeader().setStretchLastSection(True)

        self.btn_add_option = QPushButton("Add Option")
        self.btn_remove_option = QPushButton("Remove Selected Option")

        self.btn_add_option.clicked.connect(self._add_option_row)
        self.btn_remove_option.clicked.connect(self._remove_selected_option)
        self.options_table.itemChanged.connect(self._validate_options)

        # Rewards: powerups
        self.label_rewards = QLabel("Return Rewards:")
        self.powerup_table = QTableWidget(len(POWERUPS), 2)
        self.powerup_table.setHorizontalHeaderLabels(["Powerup", "Count"])
        self.powerup_table.horizontalHeader().setStretchLastSection(True)
        for row, name in enumerate(POWERUPS):
            name_item = QTableWidgetItem(name)
            name_item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            self.powerup_table.setItem(row, 0, name_item)
            self.powerup_table.setItem(row, 1, QTableWidgetItem(""))

        # Rewards: spells (checklist)
        self.spell_list = QListWidget()
        for s in SPELLS:
            item = QListWidgetItem(s)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.spell_list.addItem(item)

        # Frame images bottom strip
        self.frame_images = FrameImageListWidget(FRAMES_DIR)

        self.btn_save_frame = QPushButton("Save Frame")
        self.btn_save_frame.clicked.connect(self._save_current_frame)

        self.btn_save_project = QPushButton("Save Project (frames + stories)")
        self.btn_save_project.clicked.connect(self._save_project)

        self.btn_playthrough = QPushButton("Playthrough from This Story")
        self.btn_playthrough.clicked.connect(self._playthrough_from_story)

        # Layout
        layout = QVBoxLayout(self)
        layout.addWidget(self.label_story)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Frame:"))
        top_row.addWidget(self.combo_frame)
        top_row.addWidget(self.btn_add_frame)
        layout.addLayout(top_row)

        layout.addWidget(QLabel("SORA Prompt:"))
        layout.addWidget(self.sora_prompt_edit)

        layout.addWidget(QLabel("Text:"))
        layout.addWidget(self.text_edit)

        layout.addWidget(QLabel("Options:"))
        layout.addWidget(self.options_table)

        btn_row = QHBoxLayout()
        btn_row.addWidget(self.btn_add_option)
        btn_row.addWidget(self.btn_remove_option)
        layout.addLayout(btn_row)

        layout.addWidget(self.label_rewards)
        layout.addWidget(QLabel("Powerups (counts):"))
        layout.addWidget(self.powerup_table)
        layout.addWidget(QLabel("Spells (checked = granted):"))
        layout.addWidget(self.spell_list)

        layout.addWidget(QLabel("Frame Images (drop .png files here):"))
        layout.addWidget(self.frame_images)

        layout.addWidget(self.btn_save_frame)
        layout.addWidget(self.btn_save_project)
        layout.addWidget(self.btn_playthrough)
        layout.addStretch()

    # --- public API ---

    def set_story(self, story_name):
        self.current_story = story_name
        if not story_name:
            self.label_story.setText("Story: (none)")
            self.combo_frame.blockSignals(True)
            self.combo_frame.clear()
            self.combo_frame.blockSignals(False)
            self.text_edit.clear()
            self.options_table.setRowCount(0)
            self._clear_rewards_ui()
            self.sora_prompt_edit.clear()
            self.frame_images.set_frame(None)
            return

        frames = self.project.stories.get(story_name, [])

        self.label_story.setText(f"Story: {story_name}")
        self.combo_frame.blockSignals(True)
        self.combo_frame.clear()
        for fid in frames:
            self.combo_frame.addItem(str(fid))
        self.combo_frame.blockSignals(False)

        if frames:
            self._load_frame(frames[0])
        else:
            self.current_frame_id = None
            self.text_edit.clear()
            self.options_table.setRowCount(0)
            self._clear_rewards_ui()
            self.sora_prompt_edit.clear()
            self.frame_images.set_frame(None)

    # --- internal helpers ---

    def _on_frame_changed(self, frame_id_str: str):
        if not frame_id_str:
            return
        try:
            fid = int(frame_id_str)
        except ValueError:
            return
        self._load_frame(fid)

    def _clear_rewards_ui(self):
        # powerups
        for row in range(self.powerup_table.rowCount()):
            item = self.powerup_table.item(row, 1)
            if item:
                item.setText("")
        # spells
        for i in range(self.spell_list.count()):
            item = self.spell_list.item(i)
            item.setCheckState(Qt.Unchecked)

    def _make_return_item(self, checked: bool = False) -> QTableWidgetItem:
        item = QTableWidgetItem()
        item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if checked else Qt.Unchecked)
        return item

    def _load_frame(self, frame_id: int):
        self.current_frame_id = frame_id
        frame_key = str(frame_id)
        frame_data = self.project.frames.get(frame_key, {})

        # Text
        self.text_edit.setPlainText(frame_data.get("text", ""))

        # SORA Prompt
        self.sora_prompt_edit.blockSignals(True)
        sora_text = self.prompt_manager.get_prompt_for_frame(frame_id)
        self.sora_prompt_edit.setPlainText(sora_text)
        self.sora_prompt_edit.blockSignals(False)

        # Options
        self.options_table.blockSignals(True)
        self.options_table.setRowCount(0)

        options = StoryGraphView._extract_options_from_frame(frame_data)

        if not options and "options" not in frame_data:
            # Legacy frame with no options at all; keep visible as empty table
            pass
        else:
            for opt in options:
                row = self.options_table.rowCount()
                self.options_table.insertRow(row)

                opt_text = opt.get("text", "")
                tgt_story = opt.get("target", "")
                rc = bool(opt.get("return_choice", False))

                opt_item = QTableWidgetItem(opt_text)
                tgt_item = QTableWidgetItem(tgt_story)
                ret_item = self._make_return_item(rc)

                self.options_table.setItem(row, 0, opt_item)
                self.options_table.setItem(row, 1, tgt_item)
                self.options_table.setItem(row, 2, ret_item)

        self.options_table.blockSignals(False)
        self._validate_options()

        # Rewards
        self._clear_rewards_ui()
        rr = frame_data.get("return_rewards", {})
        rr_p = rr.get("powerups", {})
        rr_s = rr.get("spells", [])

        # powerups
        for row in range(self.powerup_table.rowCount()):
            name_item = self.powerup_table.item(row, 0)
            count_item = self.powerup_table.item(row, 1)
            if not name_item or not count_item:
                continue
            name = name_item.text()
            count = rr_p.get(name, None)
            count_item.setText("" if count is None else str(count))

        # spells
        for i in range(self.spell_list.count()):
            item = self.spell_list.item(i)
            if item.text() in rr_s:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)

        # Frame images at bottom
        self.frame_images.set_frame(self.current_frame_id)

    def _add_option_row(self):
        row = self.options_table.rowCount()
        self.options_table.insertRow(row)
        self.options_table.setItem(row, 0, QTableWidgetItem(""))
        self.options_table.setItem(row, 1, QTableWidgetItem(""))
        self.options_table.setItem(row, 2, self._make_return_item(False))
        self._validate_options()

    def _remove_selected_option(self):
        row = self.options_table.currentRow()
        if row >= 0:
            self.options_table.removeRow(row)
        self._validate_options()

    def _validate_options(self, item=None):
        """
        Validation rules:
          - Normal target: must exist in stories.json
          - game_* target: ignore story check, but require per-row return_choice=True
          - Empty target: allowed (treated as no-op)
        Colors cell in Target column.
        """
        valid_stories = set(self.project.stories.keys())
        default_brush = QBrush()

        for row in range(self.options_table.rowCount()):
            tgt_item = self.options_table.item(row, 1)
            ret_item = self.options_table.item(row, 2)

            if not tgt_item:
                continue

            text = tgt_item.text().strip()
            rc = False
            if ret_item is not None:
                rc = (ret_item.checkState() == Qt.Checked)

            # case 1: empty target → always valid
            if not text:
                tgt_item.setBackground(default_brush)
                continue

            # case 2: mini-game
            if text.startswith("game_"):
                if rc:
                    tgt_item.setBackground(default_brush)
                else:
                    # mini-game must return to caller
                    tgt_item.setBackground(QColor(255, 180, 180))
                continue

            # case 3: normal story
            if text not in valid_stories:
                tgt_item.setBackground(QColor(255, 200, 200))
            else:
                tgt_item.setBackground(default_brush)

    def _add_frame_to_story(self):
        if self.current_story is None:
            return

        # Compute a globally unique frame ID
        used_ids = set()

        # 1) All existing frame keys
        for k in self.project.frames.keys():
            try:
                used_ids.add(int(k))
            except ValueError:
                continue

        # 2) All frame IDs referenced in stories.json (including unsaved changes)
        for frames in self.project.stories.values():
            for fid in frames:
                try:
                    used_ids.add(int(fid))
                except ValueError:
                    continue

        new_id = max(used_ids) + 1 if used_ids else 1

        # Create bare frame
        self.project.frames[str(new_id)] = {"text": ""}

        # Attach to current story
        frames = self.project.stories.setdefault(self.current_story, [])
        frames.append(new_id)

        # Save project
        self.project.save()

        # Update UI
        self.combo_frame.blockSignals(True)
        self.combo_frame.addItem(str(new_id))
        self.combo_frame.blockSignals(False)

        self.combo_frame.setCurrentText(str(new_id))
        self._load_frame(new_id)

        # Notify main window so it can bump frame count on node
        self.frame_added.emit(self.current_story, new_id)

        print(f"[ADD FRAME] Added frame {new_id} to story '{self.current_story}'")

    def _save_current_frame(self):
        if self.current_story is None or self.current_frame_id is None:
            print("[SAVE FRAME] No current story/frame selected.")
            return

        frame_key = str(self.current_frame_id)
        frame = self.project.frames.get(frame_key)
        if frame is None:
            frame = {}
            self.project.frames[frame_key] = frame

        # text
        frame["text"] = self.text_edit.toPlainText()

        # Options → new structure
        options = []
        for row in range(self.options_table.rowCount()):
            opt_item = self.options_table.item(row, 0)
            tgt_item = self.options_table.item(row, 1)
            ret_item = self.options_table.item(row, 2)

            opt_text = (opt_item.text().strip() if opt_item else "")
            tgt_story = (tgt_item.text().strip() if tgt_item else "")
            rc = (ret_item.checkState() == Qt.Checked) if ret_item else False

            # skip completely empty rows (no text, no target, no return flag)
            if not opt_text and not tgt_story and not rc:
                continue

            options.append({
                "text": opt_text,
                "target": tgt_story,
                "return_choice": rc,
            })

        if options:
            frame["options"] = options
        else:
            frame.pop("options", None)

        # Clear legacy option_*/story_* and frame-level return_choice
        to_delete = [k for k in list(frame.keys())
                     if k.startswith("option_") or k.startswith("story_")]
        for k in to_delete:
            del frame[k]
        frame.pop("return_choice", None)

        # Rewards
        rr = {}
        # powerups
        rp = {}
        for row in range(self.powerup_table.rowCount()):
            name_item = self.powerup_table.item(row, 0)
            count_item = self.powerup_table.item(row, 1)
            if not name_item or not count_item:
                continue
            name = name_item.text()
            count_text = count_item.text().strip()
            if not count_text:
                continue
            try:
                val = int(count_text)
            except ValueError:
                continue
            if val > 0:
                rp[name] = val
        if rp:
            rr["powerups"] = rp

        # spells
        rs = []
        for i in range(self.spell_list.count()):
            item = self.spell_list.item(i)
            if item.checkState() == Qt.Checked:
                rs.append(item.text())
        if rs:
            rr["spells"] = rs

        # apply to frame
        if rr:
            frame["return_rewards"] = rr
        else:
            frame.pop("return_rewards", None)

        # Save to disk
        self.project.save()
        self._validate_options()

        # Save SORA Prompt for this frame
        sora_text = self.sora_prompt_edit.toPlainText()
        self.prompt_manager.set_prompt_for_frame(self.current_frame_id, sora_text)

        # Quick visual confirmation
        base_label = f"Story: {self.current_story}" if self.current_story else "Story: (none)"
        self.label_story.setText(base_label + "   [Frame saved]")
        print(f"[SAVE FRAME] Saved frame {frame_key} of story '{self.current_story}'")

        self.frame_saved.emit(self.current_story)

    def _save_project(self):
        # Only saves frames.json and stories.json (prompts are saved when frame is saved)
        self.project.save()
        base_label = f"Story: {self.current_story}" if self.current_story else "Story: (none)"
        self.label_story.setText(base_label + "   [Project saved]")
        print("[SAVE PROJECT] Explicit save requested.")

    def _playthrough_from_story(self):
        if not self.current_story:
            return
        # Save current frame so playthrough uses up-to-date content (including prompts)
        self._save_current_frame()
        dlg = PlaythroughDialog(self.project, self.current_story, self)
        dlg.exec()


# ─────────────────────────────────────────────────────────────
# Main Window
# ─────────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("ChessQuest Story Graph Editor")
        self.resize(1600, 900)

        # Load project
        self.project = StoryProject(
            frames_path="data/frames.json",
            stories_path="data/stories.json",
        )

        # Left: story list
        self.story_list = QListWidget()
        for name in sorted(self.project.stories.keys()):
            self.story_list.addItem(name)

        # Single-click: edit only
        self.story_list.currentTextChanged.connect(self._on_story_list_selected)
        # Double-click: reveal branch in graph
        self.story_list.itemDoubleClicked.connect(self._on_story_double_clicked)

        # Context menu on story list for add/delete nodes
        self.story_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.story_list.customContextMenuRequested.connect(self._on_story_list_context_menu)

        # Center: graph view
        self.graph_view = StoryGraphView(self.project)
        self.graph_view.story_selected.connect(self._on_graph_story_selected)
        # Default: hide everything until user picks something
        self.graph_view.hide_all_nodes()

        # Right: editor panel
        self.editor_panel = StoryEditorPanel(self.project)
        self.editor_panel.frame_added.connect(self._on_frame_added)
        self.editor_panel.frame_saved.connect(self._on_frame_saved)

        # 🔔 Recolor stories whenever frame images may have changed
        self.editor_panel.frame_images.images_changed.connect(
            self._update_story_image_highlights
        )

        # Layout via splitter
        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(self.story_list)
        splitter.addWidget(self.graph_view)
        splitter.addWidget(self.editor_panel)
        splitter.setSizes([220, 900, 480])

        container = QWidget()
        layout = QHBoxLayout(container)
        layout.addWidget(splitter)

        self.setCentralWidget(container)

        # Initial highlight state based on existing images on disk
        self._update_story_image_highlights()

    def _update_story_image_highlights(self):
        """
        Per-story highlighting based on frame images:

        - Green: every frame in the story has at least one image.
        - Yellow: some (but not all) frames have images.
        - No highlight: no frames in the story have images.
        """
        # Build a set of frame IDs that have at least one image file
        frame_ids_with_images = set()
        if os.path.isdir(FRAMES_DIR):
            for fname in os.listdir(FRAMES_DIR):
                if not fname.lower().endswith(".png"):
                    continue
                base = os.path.splitext(fname)[0]  # frame_123_1
                parts = base.split("_")
                if len(parts) < 3 or parts[0] != "frame":
                    continue
                try:
                    fid = int(parts[1])
                except ValueError:
                    continue
                frame_ids_with_images.add(fid)

        # Colors
        brush_all = QBrush(QColor("#10330d"))   # soft green
        brush_some = QBrush(QColor("#b09f06"))  # soft yellow
        brush_none = QBrush()                   # default

        # For each story, count how many of its frames have images
        for i in range(self.story_list.count()):
            item = self.story_list.item(i)
            story_name = item.text()

            frames = self.project.stories.get(story_name, [])
            if not frames:
                # No frames → no highlight
                item.setBackground(brush_none)
                continue

            total_frames = len(frames)
            frames_with_images = 0

            for fid in frames:
                try:
                    int_fid = int(fid)
                except (TypeError, ValueError):
                    continue
                if int_fid in frame_ids_with_images:
                    frames_with_images += 1

            if frames_with_images == 0:
                # No frames have images
                item.setBackground(brush_none)
            elif frames_with_images == total_frames:
                # Every frame has at least one image
                item.setBackground(brush_all)
            else:
                # Some but not all frames have images
                item.setBackground(brush_some)

    # --- story list context menu ---

    def _on_story_list_context_menu(self, pos):
        menu = QMenu(self)
        act_add = menu.addAction("Add Story Node...")

        selected_items = self.story_list.selectedItems()
        if selected_items:
            act_del = menu.addAction("Delete Selected Story Node(s)...")
        else:
            act_del = None

        chosen = menu.exec(self.story_list.mapToGlobal(pos))
        if chosen == act_add:
            self._add_story_node_dialog()
        elif act_del is not None and chosen == act_del:
            self._delete_story_nodes_dialog()

    def _add_story_node_dialog(self):
        name, ok = QInputDialog.getText(self, "Add Story Node", "Story name:")
        if not ok:
            return
        story_name = name.strip()
        if not story_name:
            return

        if story_name in self.project.stories:
            QMessageBox.warning(self, "Duplicate Story", f"Story '{story_name}' already exists.")
            return

        # Add to project
        self.project.stories[story_name] = []
        self.project.save()

        # Add to list and graph
        self.story_list.addItem(story_name)
        self.graph_view.add_story_node(story_name)
        self.graph_view.rebuild_edges_and_flags()

        # Update highlights (new story may or may not have images)
        self._update_story_image_highlights()

    def _delete_story_nodes_dialog(self):
        items = self.story_list.selectedItems()
        if not items:
            return

        names = [i.text() for i in items]
        msg = "Are you sure you want to delete the following story node(s)?\n\n" + "\n".join(names)
        reply = QMessageBox.question(self, "Delete Story Node(s)", msg,
                                     QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
        if reply != QMessageBox.Yes:
            return

        # Remove from project, list, graph
        for item in items:
            story_name = item.text()
            if story_name in self.project.stories:
                del self.project.stories[story_name]
            row = self.story_list.row(item)
            self.story_list.takeItem(row)
            self.graph_view.remove_story_node(story_name)

            # If editor was showing this story, clear it
            if self.editor_panel.current_story == story_name:
                self.editor_panel.set_story(None)

        self.project.save()
        self.graph_view.rebuild_edges_and_flags()

        # Update highlights (new story may or may not have images)
        self._update_story_image_highlights()

    # --- callbacks ---

    def _on_story_list_selected(self, story_name: str):
        """
        Single-click in the list: just edit that story.
        Does NOT change graph visibility (per your request).
        """
        if not story_name:
            self.editor_panel.set_story(None)
            return
        self.editor_panel.set_story(story_name)

    def _on_story_double_clicked(self, item):
        """
        Double-click in the list: show this story's branch on the graph.
        """
        story_name = item.text()
        if not story_name:
            return
        self.graph_view.show_branch_from(story_name)
        self.graph_view.focus_on_story(story_name)
        self.editor_panel.set_story(story_name)

    def _on_graph_story_selected(self, story_name: str):
        # Select in list
        matching = self.story_list.findItems(story_name, Qt.MatchExactly)
        if matching:
            self.story_list.setCurrentItem(matching[0])
        self.editor_panel.set_story(story_name)

    def _on_frame_added(self, story_name: str, new_frame_id: int):
        """
        Update node label's frame count when a new frame is added.
        """
        node = self.graph_view.nodes.get(story_name)
        if node:
            node.frame_count += 1
            node.update()
        self.graph_view.rebuild_edges_and_flags()

        # Update highlights (new story may or may not have images)
        self._update_story_image_highlights()

    def _on_frame_saved(self, story_name: str):
        """
        After a frame is saved, edges or return_choice flags may change.
        """
        self.graph_view.rebuild_edges_and_flags()


# ─────────────────────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────────────────────

if __name__ == "__main__":
    app = QApplication(sys.argv)
    win = MainWindow()
    win.show()
    sys.exit(app.exec())
