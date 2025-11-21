from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional, Tuple

from PyQt6.QtCore import Qt, QSize, QTimer, QSettings
from PyQt6.QtGui import QIcon, QPixmap, QAction, QKeySequence, QColor, QBrush
from PyQt6.QtWidgets import (
    QFileDialog,
    QHeaderView,
    QLabel,
    QMainWindow,
    QMessageBox,
    QToolBar,
    QTreeWidgetItem,
)
from PyQt6.QtSvgWidgets import QSvgWidget
from PIL import Image, ImageSequence

from .dialogs import SettingsDialog, AboutDialog
from .model import FrameData, AppConfig, load_config, save_config
from .ui_main import build_main_ui


APP_NAME = "Geek's Animated GIF Editor"
ORG_NAME = "GeekToyBox"
SETTINGS_NAME = "GeeksAnimatedGIFEditor"

IMAGE_FILTERS = "Images (*.png *.jpg *.jpeg *.bmp *.gif *.svg);;All Files (*)"
GIF_FILTER = "GIF Images (*.gif);;All Files (*)"

ALIGN_OPTIONS = [
    ("Top Left", (0.0, 0.0)),
    ("Top Center", (0.5, 0.0)),
    ("Top Right", (1.0, 0.0)),
    ("Middle Left", (0.0, 0.5)),
    ("Centered", (0.5, 0.5)),
    ("Middle Right", (1.0, 0.5)),
    ("Bottom Left", (0.0, 1.0)),
    ("Bottom Center", (0.5, 1.0)),
    ("Bottom Right", (1.0, 1.0)),
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle(APP_NAME)
        self.setMinimumSize(900, 600)

        # Paths & assets
        self.base_dir = Path(__file__).resolve().parent
        self.assets_dir = self.base_dir / "assets"

        # State
        self.frames: List[FrameData] = []
        self.current_index: int = -1
        self.default_duration_ms: int = 100
        self.animation_mode: str = "loop"
        self.is_playing: bool = False
        self.play_timer = QTimer(self)
        self.play_timer.timeout.connect(self.advance_frame_for_playback)
        self.wave_direction = 1

        self.unsaved_changes: bool = False
        self.current_gif_path: Optional[Path] = None
        self.align_anchor = (0.5, 0.5)  # centered by default
        self.output_size: Optional[Tuple[int, int]] = None

        # Config
        self.config: AppConfig = load_config(self.base_dir)

        # Checkbox icons — optional
        unchecked_path = self.assets_dir / "checkbox_unchecked_26.png"
        checked_path = self.assets_dir / "checkbox_checked_26.png"
        self.checkbox_unchecked_icon = QIcon(str(unchecked_path)) if unchecked_path.exists() else QIcon()
        self.checkbox_checked_icon = QIcon(str(checked_path)) if checked_path.exists() else QIcon()

        # Actions, menus, toolbars, central UI
        self.create_actions()
        self.create_menu_toolbar()
        build_main_ui(self)
        self.apply_config_to_ui()
        self.wire_signals()
        self.load_window_geometry()
        self.load_app_icon()
        self.update_title_and_status()

    # ---------- Geometry / config ----------
    def closeEvent(self, event):
        if not self.maybe_save_before_discard():
            event.ignore()
            return
        if self.config.remember_geometry:
            self.save_window_geometry()
        save_config(self.base_dir, self.config)
        super().closeEvent(event)

    def save_window_geometry(self) -> None:
        s = QSettings(ORG_NAME, SETTINGS_NAME)
        s.setValue("geometry", self.saveGeometry())
        s.setValue("windowState", self.saveState())

    def load_window_geometry(self) -> None:
        s = QSettings(ORG_NAME, SETTINGS_NAME)
        if self.config.remember_geometry:
            geom = s.value("geometry")
            if geom is not None:
                self.restoreGeometry(geom)
                state = s.value("windowState")
                if state is not None:
                    self.restoreState(state)
            else:
                self.resize(1000, 650)
        else:
            self.resize(1000, 650)

    def load_app_icon(self) -> None:
        """Set window/application icon from GeeksGIFEditorLogo.png (multi-size)."""
        icon_path = self.assets_dir / "GeeksGIFEditorLogo.png"
        if icon_path.exists():
            pix = QPixmap(str(icon_path))
            icon = QIcon()
            for size in (16, 24, 32, 48, 64, 128, 256):
                if not pix.isNull():
                    icon.addPixmap(
                        pix.scaled(
                            size,
                            size,
                            Qt.AspectRatioMode.KeepAspectRatio,
                            Qt.TransformationMode.SmoothTransformation,
                        )
                    )
            self.setWindowIcon(icon)
            from PyQt6.QtWidgets import QApplication

            app = QApplication.instance()
            if app is not None:
                app.setWindowIcon(icon)

    # ---------- UI wiring ----------
    def create_actions(self) -> None:
        self.act_new = QAction("New", self)
        self.act_new.setShortcut(QKeySequence.StandardKey.New)
        self.act_new.triggered.connect(self.new_project)

        self.act_open = QAction("Open...", self)
        self.act_open.setShortcut(QKeySequence.StandardKey.Open)
        self.act_open.triggered.connect(self.open_gif)

        self.act_save = QAction("Save", self)
        self.act_save.setShortcut(QKeySequence.StandardKey.Save)
        self.act_save.triggered.connect(self.save_gif)

        self.act_save_as = QAction("Save As...", self)
        self.act_save_as.setShortcut(QKeySequence.StandardKey.SaveAs)
        self.act_save_as.triggered.connect(self.save_gif_as)

        self.act_settings = QAction("Settings...", self)
        self.act_settings.setShortcut("Ctrl+,")
        if sys.platform == "darwin":
            self.act_settings.setShortcut("Meta+,")
        self.act_settings.triggered.connect(self.open_settings)

        self.act_about = QAction("About", self)
        self.act_about.triggered.connect(self.open_about)

        self.act_quit = QAction("Quit", self)
        self.act_quit.setShortcut(QKeySequence.StandardKey.Quit)
        self.act_quit.triggered.connect(self.close)

    def create_menu_toolbar(self) -> None:
        menubar = self.menuBar()

        file_menu = menubar.addMenu("&File")
        file_menu.addAction(self.act_new)
        file_menu.addAction(self.act_open)
        file_menu.addAction(self.act_save)
        file_menu.addAction(self.act_save_as)
        file_menu.addSeparator()
        file_menu.addAction(self.act_quit)

        edit_menu = menubar.addMenu("&Tools")
        edit_menu.addAction(self.act_settings)

        help_menu = menubar.addMenu("&About")
        help_menu.addAction(self.act_about)

        tb = QToolBar("Main Toolbar", self)
        tb.setObjectName("MainToolbar")
        tb.setIconSize(QSize(20, 20))
        tb.setMovable(False)     # Prevent dragging
        tb.setFloatable(False)   # Prevent detaching
        self.addToolBar(tb)

        tb.addAction(self.act_new)
        tb.addAction(self.act_open)
        tb.addAction(self.act_save)
        tb.addAction(self.act_save_as)
        tb.addSeparator()
        tb.addAction(self.act_settings)
        tb.addSeparator()
        tb.addAction(self.act_about)

    def wire_signals(self) -> None:
        self.tree.itemClicked.connect(self.on_tree_item_clicked)
        self.tree.itemDoubleClicked.connect(self.on_tree_item_double_clicked)

        self.btn_add.clicked.connect(self.add_images)
        self.btn_remove.clicked.connect(self.remove_selected)
        self.btn_duplicate.clicked.connect(self.duplicate_selected)
        self.btn_up.clicked.connect(self.move_up)
        self.btn_down.clicked.connect(self.move_down)
        self.btn_export.clicked.connect(self.export_checked)

        self.btn_play_pause.clicked.connect(self.toggle_play_pause)
        self.btn_prev.clicked.connect(self.prev_frame_clicked)
        self.btn_next.clicked.connect(self.next_frame_clicked)

        self.spin_default_dur.valueChanged.connect(self.on_default_duration_changed)
        self.btn_overwrite_all.clicked.connect(self.on_overwrite_all_clicked)
        self.mode_combo.currentIndexChanged.connect(self.on_mode_changed)

    def apply_config_to_ui(self) -> None:
        self.tree.setIconSize(QSize(self.config.thumb_size, self.config.thumb_size))
        row_h = max(32, self.config.thumb_size + 8)
        self.tree.setStyleSheet(f"QTreeWidget::item {{ height: {row_h}px; }}")

        header = self.tree.header()
        header.setStretchLastSection(False)

        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)

        checkbox_col_width = self.tree.iconSize().width() + 8
        thumb_col_width = self.tree.iconSize().width() + 8
        header.resizeSection(0, checkbox_col_width)
        header.resizeSection(1, thumb_col_width)

        header.setSectionResizeMode(2, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(3, QHeaderView.ResizeMode.ResizeToContents)

    # ---------- Tree / frames ----------
    def rebuild_tree(self) -> None:
        self.tree.clear()
        for idx, frame in enumerate(self.frames):
            item = QTreeWidgetItem(self.tree)
            item.setData(0, Qt.ItemDataRole.UserRole, idx)

            icon = (
                self.checkbox_checked_icon
                if frame.is_checked
                else self.checkbox_unchecked_icon
            )
            item.setIcon(0, icon)
            item.setText(0, "")

            thumb_icon = self.make_thumbnail_icon(frame)
            if thumb_icon is not None:
                item.setIcon(1, thumb_icon)
            item.setText(1, "")

            item.setText(2, frame.display_name)

            if frame.is_custom_duration:
                item.setText(3, str(frame.duration_ms))
                item.setForeground(3, QBrush(QColor(230, 230, 230)))
            else:
                item.setText(3, str(self.default_duration_ms))
                item.setForeground(3, QBrush(QColor(150, 150, 150)))

            item.setTextAlignment(
                3, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
            )

            if frame.is_checked:
                brush = QBrush(QColor(60, 90, 160, 60))
                for c in range(4):
                    item.setBackground(c, brush)

        if 0 <= self.current_index < len(self.frames):
            for i in range(self.tree.topLevelItemCount()):
                it = self.tree.topLevelItem(i)
                if it.data(0, Qt.ItemDataRole.UserRole) == self.current_index:
                    self.tree.setCurrentItem(it)
                    break

        self.update_title_and_status()
        self.update_preview()

    def make_thumbnail_icon(self, frame: FrameData) -> Optional[QIcon]:
        if not frame.source_path:
            return None
        p = Path(frame.source_path)
        if not p.exists():
            return None
        try:
            if p.suffix.lower() == ".svg":
                widget = QSvgWidget(str(p))
                widget.resize(self.config.thumb_size, self.config.thumb_size)
                pix = QPixmap(widget.size())
                pix.fill(Qt.GlobalColor.transparent)
                widget.render(pix)
            else:
                pix = QPixmap(str(p))

            if pix.isNull():
                return None

            pix = pix.scaled(
                self.config.thumb_size,
                self.config.thumb_size,
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            return QIcon(pix)
        except Exception:
            return None

    def on_tree_item_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is None:
            return
        idx = int(idx)

        if column == 3:
            self.edit_duration_for_frame(idx)
        else:
            frame = self.frames[idx]
            frame.is_checked = not frame.is_checked
            self.current_index = idx
            self.mark_unsaved()
            self.rebuild_tree()

    def on_tree_item_double_clicked(self, item: QTreeWidgetItem, column: int) -> None:
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        if idx is None:
            return
        idx = int(idx)
        if column == 3:
            self.edit_duration_for_frame(idx)

    def edit_duration_for_frame(self, idx: int) -> None:
        if idx < 0 or idx >= len(self.frames):
            return
        frame = self.frames[idx]
        from PyQt6.QtWidgets import QInputDialog

        val, ok = QInputDialog.getInt(
            self,
            "Frame Duration",
            f"Duration for frame '{frame.display_name}' (ms):",
            frame.duration_ms if frame.is_custom_duration else self.default_duration_ms,
            10,
            60000,
            10,
        )
        if ok:
            frame.duration_ms = val
            frame.is_custom_duration = val != self.default_duration_ms
            self.current_index = idx
            self.mark_unsaved()
            self.rebuild_tree()

    def on_default_duration_changed(self, value: int) -> None:
        self.default_duration_ms = value
        for f in self.frames:
            if not f.is_custom_duration:
                f.duration_ms = value
        self.mark_unsaved()
        self.rebuild_tree()

    def on_overwrite_all_clicked(self) -> None:
        for f in self.frames:
            f.duration_ms = self.default_duration_ms
            f.is_custom_duration = False
        self.mark_unsaved()
        self.rebuild_tree()

    def on_mode_changed(self, index: int) -> None:
        self.animation_mode = self.mode_combo.currentData()
        self.mark_unsaved()

    # ---------- List actions ----------
    def add_images(self) -> None:
        start_dir = (
            self.config.last_add_dir
            if (self.config.remember_add_dir and self.config.last_add_dir)
            else str(Path.home())
        )
        files, _ = QFileDialog.getOpenFileNames(
            self, "Add Images", start_dir, IMAGE_FILTERS
        )
        if not files:
            return
        if self.config.remember_add_dir:
            self.config.last_add_dir = str(Path(files[0]).parent)

        for f in files:
            p = Path(f)
            frame = FrameData(
                source_path=str(p),
                display_name=p.name,
                duration_ms=self.default_duration_ms,
                is_custom_duration=False,
                is_checked=False,
            )
            self.frames.append(frame)

        if self.current_index == -1 and self.frames:
            self.current_index = 0

        self.mark_unsaved()
        self.rebuild_tree()
        if self.frames and not self.is_playing:
            self.start_playback()

    def get_selected_index(self) -> int:
        item = self.tree.currentItem()
        if not item:
            return -1
        idx = item.data(0, Qt.ItemDataRole.UserRole)
        return int(idx) if idx is not None else -1

    def remove_selected(self) -> None:
        idx = self.get_selected_index()
        if idx < 0 or idx >= len(self.frames):
            return
        del self.frames[idx]
        if not self.frames:
            self.current_index = -1
        else:
            self.current_index = max(0, min(idx, len(self.frames) - 1))
        self.mark_unsaved()
        self.rebuild_tree()

    def duplicate_selected(self) -> None:
        idx = self.get_selected_index()
        if idx < 0 or idx >= len(self.frames):
            return
        f = self.frames[idx]
        dup = FrameData(
            source_path=f.source_path,
            display_name=f"{f.display_name}_copy",
            duration_ms=f.duration_ms,
            is_custom_duration=f.is_custom_duration,
            is_checked=f.is_checked,
        )
        self.frames.insert(idx + 1, dup)
        self.current_index = idx + 1
        self.mark_unsaved()
        self.rebuild_tree()

    def move_up(self) -> None:
        idx = self.get_selected_index()
        if idx <= 0:
            return
        self.frames[idx - 1], self.frames[idx] = (
            self.frames[idx],
            self.frames[idx - 1],
        )
        self.current_index = idx - 1
        self.mark_unsaved()
        self.rebuild_tree()

    def move_down(self) -> None:
        idx = self.get_selected_index()
        if idx < 0 or idx >= len(self.frames) - 1:
            return
        self.frames[idx + 1], self.frames[idx] = (
            self.frames[idx],
            self.frames[idx + 1],
        )
        self.current_index = idx + 1
        self.mark_unsaved()
        self.rebuild_tree()

    def export_checked(self) -> None:
        checked = [f for f in self.frames if f.is_checked]
        if not checked:
            QMessageBox.information(
                self, "Export Frames", "No checked frames to export."
            )
            return

        start_dir = (
            self.config.last_export_dir
            if (self.config.remember_export_dir and self.config.last_export_dir)
            else str(Path.home())
        )
        out_dir_str = QFileDialog.getExistingDirectory(
            self, "Export Frames To Folder", start_dir
        )
        if not out_dir_str:
            return
        if self.config.remember_export_dir:
            self.config.last_export_dir = out_dir_str
        out_dir = Path(out_dir_str)

        for f in checked:
            src = Path(f.source_path) if f.source_path else None
            if not src or not src.exists():
                continue
            if src.suffix.lower() == ".svg":
                widget = QSvgWidget(str(src))
                widget.resize(self.config.thumb_size, self.config.thumb_size)
                pix = QPixmap(widget.size())
                pix.fill(Qt.GlobalColor.transparent)
                widget.render(pix)
                export_path = out_dir / (
                    f.display_name
                    if f.display_name.lower().endswith(".png")
                    else f.display_name + ".png"
                )
                pix.save(str(export_path), "PNG")
            else:
                img = Image.open(str(src))
                export_path = out_dir / f.display_name
                if not export_path.suffix:
                    export_path = export_path.with_suffix(".png")
                img.save(str(export_path))

        QMessageBox.information(
            self,
            "Export Frames",
            f"Exported {len(checked)} frame(s) to {out_dir}",
        )

    # ---------- New/Open/Save ----------
    def new_project(self) -> None:
        if not self.maybe_save_before_discard():
            return
        self.frames.clear()
        self.current_index = -1
        self.current_gif_path = None
        self.unsaved_changes = False
        self.rebuild_tree()

    def open_gif(self) -> None:
        start_dir = (
            self.config.last_open_dir
            if (self.config.remember_open_dir and self.config.last_open_dir)
            else str(Path.home())
        )
        path_str, _ = QFileDialog.getOpenFileName(
            self, "Open Animated GIF", start_dir, GIF_FILTER
        )
        if not path_str:
            return
        p = Path(path_str)
        if self.config.remember_open_dir:
            self.config.last_open_dir = str(p.parent)

        if not self.maybe_save_before_discard():
            return

        try:
            im = Image.open(str(p))
        except Exception as e:
            QMessageBox.critical(
                self, "Open GIF", f"Could not open GIF:\n{e}"
            )
            return

        self.frames.clear()
        base_name = p.stem
        durations: List[int] = []
        tmp_dir = self.base_dir / "_tmp_frames"
        tmp_dir.mkdir(exist_ok=True)

        idx = 1
        try:
            for frame in ImageSequence.Iterator(im):
                dur = frame.info.get("duration", self.default_duration_ms)
                durations.append(dur)
                disp_name = f"{base_name}_{idx:03d}.png"
                tmp_path = tmp_dir / disp_name
                frame_rgba = frame.convert("RGBA")
                frame_rgba.save(str(tmp_path))
                self.frames.append(
                    FrameData(
                        source_path=str(tmp_path),
                        display_name=disp_name,
                        duration_ms=dur,
                        is_custom_duration=False,
                        is_checked=False,
                    )
                )
                idx += 1
        finally:
            im.close()

        if durations and all(d == durations[0] for d in durations):
            self.default_duration_ms = durations[0]
            for f in self.frames:
                f.duration_ms = self.default_duration_ms
                f.is_custom_duration = False
        else:
            for f in self.frames:
                f.is_custom_duration = f.duration_ms != self.default_duration_ms

        self.spin_default_dur.setValue(self.default_duration_ms)
        self.current_index = 0 if self.frames else -1
        self.current_gif_path = p
        self.unsaved_changes = False
        self.rebuild_tree()
        if self.frames:
            self.start_playback()

    def save_gif(self) -> None:
        if self.current_gif_path is None:
            self.save_gif_as()
            return
        self._save_gif_to_path(self.current_gif_path)

    def save_gif_as(self) -> None:
        start_dir = (
            self.config.last_save_dir
            if (self.config.remember_save_dir and self.config.last_save_dir)
            else str(Path.home())
        )
        path_str, _ = QFileDialog.getSaveFileName(
            self, "Save Animated GIF As", start_dir, GIF_FILTER
        )
        if not path_str:
            return
        p = Path(path_str)
        if self.config.remember_save_dir:
            self.config.last_save_dir = str(p.parent)
        if p.suffix.lower() != ".gif":
            p = p.with_suffix(".gif")
        self._save_gif_to_path(p)
        self.current_gif_path = p

    def _save_gif_to_path(self, path: Path) -> None:
        if not self.frames:
            QMessageBox.information(
                self, "Save GIF", "No frames to save."
            )
            return

        images = []
        durations: List[int] = []

        first_img, w, h = self.load_frame_image(self.frames[0], None)
        if first_img is None:
            QMessageBox.critical(
                self, "Save GIF", "Could not load first frame."
            )
            return
        out_size = (w, h)

        for f in self.frames:
            img, _, _ = self.load_frame_image(f, out_size)
            if img is None:
                continue
            images.append(img)
            durations.append(f.duration_ms)

        if not images:
            QMessageBox.critical(
                self,
                "Save GIF",
                "No frames could be loaded for saving.",
            )
            return

        try:
            images[0].save(
                str(path),
                save_all=True,
                append_images=images[1:],
                duration=durations,
                loop=0,
                disposal=2,
            )
        except Exception as e:
            QMessageBox.critical(
                self, "Save GIF", f"Error saving GIF:\n{e}"
            )
            return

        self.unsaved_changes = False
        self.update_title_and_status()
        QMessageBox.information(
            self, "Save GIF", f"Saved animated GIF to:\n{path}"
        )

    def load_frame_image(
        self, frame: FrameData, expected_size: Optional[Tuple[int, int]]
    ):
        if not frame.source_path:
            return None, 0, 0
        p = Path(frame.source_path)
        if not p.exists():
            return None, 0, 0
        try:
            if p.suffix.lower() == ".svg":
                widget = QSvgWidget(str(p))
                widget.resize(*(expected_size or (512, 512)))
                pix = QPixmap(widget.size())
                pix.fill(Qt.GlobalColor.transparent)
                widget.render(pix)
                img_bytes = (
                    pix.toImage()
                    .bits()
                    .asstring(pix.width() * pix.height() * 4)
                )
                from PIL import Image as PILImage

                img = PILImage.frombytes(
                    "RGBA", (pix.width(), pix.height()), img_bytes
                )
            else:
                img = Image.open(str(p)).convert("RGBA")

            if expected_size:
                img = img.resize(expected_size, Image.Resampling.LANCZOS)

            return img, img.width, img.height
        except Exception:
            return None, 0, 0

    # ---------- Unsaved / title ----------
    def mark_unsaved(self) -> None:
        self.unsaved_changes = True
        self.update_title_and_status()

    def update_title_and_status(self) -> None:
        name = self.current_gif_path.name if self.current_gif_path else "Unsaved"
        title = f"{APP_NAME} - {name}"
        if self.unsaved_changes:
            title += " (unsaved)"
        self.setWindowTitle(title)

        if self.current_gif_path:
            text = str(self.current_gif_path)
        else:
            text = "Unsaved"
        if self.unsaved_changes:
            text += " (unsaved)"
        if hasattr(self, "file_label"):
            self.file_label.setText(text)

    def maybe_save_before_discard(self) -> bool:
        if not self.unsaved_changes:
            return True
        resp = QMessageBox.question(
            self,
            "Unsaved Changes",
            "You have unsaved changes. Save before continuing?",
            QMessageBox.StandardButton.Yes
            | QMessageBox.StandardButton.No
            | QMessageBox.StandardButton.Cancel,
        )
        if resp == QMessageBox.StandardButton.Yes:
            self.save_gif()
            return not self.unsaved_changes
        elif resp == QMessageBox.StandardButton.No:
            return True
        return False

    # ---------- Preview / playback ----------
    def update_preview(self) -> None:
        if (
            not self.frames
            or self.current_index < 0
            or self.current_index >= len(self.frames)
        ):
            self.preview_label.setText("No frames loaded.")
            self.preview_label.setPixmap(QPixmap())
            return

        f = self.frames[self.current_index]
        p = Path(f.source_path) if f.source_path else None
        if not p or not p.exists():
            self.preview_label.setText("Missing frame file.")
            self.preview_label.setPixmap(QPixmap())
            return

        if p.suffix.lower() == ".svg":
            widget = QSvgWidget(str(p))
            size = self.preview_label.size()
            widget.resize(size.width(), size.height())
            pix = QPixmap(widget.size())
            pix.fill(Qt.GlobalColor.transparent)
            widget.render(pix)
        else:
            pix = QPixmap(str(p))

        if not pix.isNull():
            size = self.preview_label.size()
            pix = pix.scaled(
                size.width(),
                size.height(),
                Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )
            self.preview_label.setPixmap(pix)
            self.preview_label.setText("")
        else:
            self.preview_label.setText("Unable to display frame.")

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_preview()

    def toggle_play_pause(self) -> None:
        if self.is_playing:
            self.stop_playback()
        else:
            self.start_playback()

    def start_playback(self) -> None:
        if not self.frames:
            return
        self.is_playing = True
        self.btn_play_pause.setText("⏸")
        self.play_timer.stop()
        dur = (
            self.frames[self.current_index].duration_ms
            if self.current_index >= 0
            else self.default_duration_ms
        )
        self.play_timer.start(max(10, dur))

    def stop_playback(self) -> None:
        self.is_playing = False
        self.btn_play_pause.setText("▶")
        self.play_timer.stop()

    def advance_frame_for_playback(self) -> None:
        if not self.frames:
            self.stop_playback()
            return
        self.current_index = self.get_next_index_for_mode()
        self.update_preview()
        dur = self.frames[self.current_index].duration_ms
        self.play_timer.start(max(10, dur))

    def get_next_index_for_mode(self) -> int:
        n = len(self.frames)
        if n == 0:
            return 0
        if self.animation_mode == "loop":
            return (self.current_index + 1) % n
        elif self.animation_mode == "wave":
            if self.current_index <= 0:
                self.wave_direction = 1
            elif self.current_index >= n - 1:
                self.wave_direction = -1
            return max(0, min(n - 1, self.current_index + self.wave_direction))
        return (self.current_index + 1) % n

    def prev_frame_clicked(self) -> None:
        if not self.frames:
            return
        self.stop_playback()
        self.current_index = (self.current_index - 1) % len(self.frames)
        self.update_preview()

    def next_frame_clicked(self) -> None:
        if not self.frames:
            return
        self.stop_playback()
        self.current_index = (self.current_index + 1) % len(self.frames)
        self.update_preview()

    # ---------- Settings / About ----------
    def open_settings(self) -> None:
        dlg = SettingsDialog(self, self.config)
        if dlg.exec():
            dlg.apply_changes()
            self.apply_config_to_ui()
            self.mark_unsaved()

    def open_about(self) -> None:
        dlg = AboutDialog(self, self.assets_dir, APP_NAME)
        dlg.exec()


def run() -> None:
    """Entry point used by main.py."""
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    app.setOrganizationName(ORG_NAME)
    app.setApplicationName(APP_NAME)

    win = MainWindow()
    win.show()
    sys.exit(app.exec())
