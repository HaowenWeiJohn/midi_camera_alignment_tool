"""Level 2: Alignment Detail View — side-by-side MIDI + camera panels."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QComboBox, QLineEdit, QMessageBox, QInputDialog,
)

from alignment_tool.models import AlignmentState, MidiFileInfo, CameraFileInfo, Anchor
from alignment_tool.midi_adapter import MidiAdapter
from alignment_tool.midi_panel import MidiPanelWidget
from alignment_tool.camera_panel import CameraPanelWidget
from alignment_tool.anchor_table import AnchorTableWidget
from alignment_tool.overlap_indicator import OverlapIndicatorWidget
from alignment_tool import alignment_engine as engine


class Level2View(QWidget):
    """Alignment detail view for a MIDI + camera pair."""

    back_requested = pyqtSignal()
    state_modified = pyqtSignal()  # any alignment state change

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state: AlignmentState | None = None
        self._midi_index: int = 0
        self._camera_index: int = 0
        self._midi_adapter: MidiAdapter | None = None

        # Mode
        self._locked: bool = False
        self._active_panel: str = "camera"  # which panel is the "driver"

        # Markers
        self._midi_marker: tuple[str, float] | None = None  # (filename, seconds_from_start)
        self._camera_marker: int | None = None  # frame index

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Top bar: back button + dropdowns + mode toggle
        top_bar = QHBoxLayout()
        self._back_btn = QPushButton("< Back")
        self._back_btn.clicked.connect(self.back_requested.emit)
        top_bar.addWidget(self._back_btn)

        top_bar.addWidget(QLabel("MIDI:"))
        self._midi_combo = QComboBox()
        self._midi_combo.currentIndexChanged.connect(self._on_midi_combo_changed)
        top_bar.addWidget(self._midi_combo)

        top_bar.addWidget(QLabel("Camera:"))
        self._camera_combo = QComboBox()
        self._camera_combo.currentIndexChanged.connect(self._on_camera_combo_changed)
        top_bar.addWidget(self._camera_combo)

        self._mode_btn = QPushButton("Mode: Independent")
        self._mode_btn.setCheckable(True)
        self._mode_btn.clicked.connect(self._toggle_mode)
        top_bar.addWidget(self._mode_btn)

        top_bar.addStretch()
        layout.addLayout(top_bar)

        # Status line: mode + active panel + hints
        self._status_line = QLabel()
        self._status_line.setStyleSheet("color: #888; font-size: 11px; padding: 2px 4px;")
        layout.addWidget(self._status_line)
        self._update_status_line()

        # Overlap indicator
        self._overlap = OverlapIndicatorWidget()
        layout.addWidget(self._overlap)

        # Main panels (splitter)
        splitter = QSplitter(Qt.Horizontal)
        self._midi_panel = MidiPanelWidget()
        self._camera_panel = CameraPanelWidget()
        splitter.addWidget(self._midi_panel)
        splitter.addWidget(self._camera_panel)
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, stretch=1)

        # Marker display + buttons
        marker_layout = QHBoxLayout()
        self._midi_marker_label = QLabel("MIDI mark: (none)")
        self._camera_marker_label = QLabel("Camera mark: (none)")
        marker_layout.addWidget(self._midi_marker_label)
        marker_layout.addWidget(self._camera_marker_label)

        self._compute_shift_btn = QPushButton("Compute Global Shift")
        self._compute_shift_btn.setEnabled(False)
        self._compute_shift_btn.setToolTip("Set markers first: press M on MIDI panel, C on camera panel")
        self._compute_shift_btn.clicked.connect(self._on_compute_shift)
        marker_layout.addWidget(self._compute_shift_btn)

        self._add_anchor_btn = QPushButton("Add Anchor (A)")
        self._add_anchor_btn.setEnabled(False)
        self._add_anchor_btn.setToolTip("Set markers first: press M on MIDI panel, C on camera panel")
        self._add_anchor_btn.clicked.connect(self._on_add_anchor)
        marker_layout.addWidget(self._add_anchor_btn)

        marker_layout.addStretch()
        layout.addLayout(marker_layout)

        # Anchor table
        self._anchor_table = AnchorTableWidget()
        self._anchor_table.anchor_activated.connect(self._on_anchor_activated)
        self._anchor_table.anchor_deactivated.connect(self._on_anchor_deactivated)
        self._anchor_table.anchor_deleted.connect(self._on_anchor_deleted)
        self._anchor_table.setMaximumHeight(200)
        layout.addWidget(self._anchor_table)

        # Connect panel position signals
        self._midi_panel.position_changed.connect(self._on_midi_position_changed)
        self._camera_panel.position_changed.connect(self._on_camera_position_changed)

    def load_pair(self, state: AlignmentState, midi_index: int, camera_index: int):
        """Load a MIDI + camera pair for alignment."""
        self._state = state
        self._midi_index = midi_index
        self._camera_index = camera_index
        self._midi_marker = None
        self._camera_marker = None
        self._update_marker_ui()

        # Populate combos
        self._midi_combo.blockSignals(True)
        self._midi_combo.clear()
        for mf in state.midi_files:
            self._midi_combo.addItem(mf.filename)
        self._midi_combo.setCurrentIndex(midi_index)
        self._midi_combo.blockSignals(False)

        self._camera_combo.blockSignals(True)
        self._camera_combo.clear()
        for cf in state.camera_files:
            self._camera_combo.addItem(cf.filename)
        self._camera_combo.setCurrentIndex(camera_index)
        self._camera_combo.blockSignals(False)

        self._load_midi_file(midi_index)
        self._load_camera_file(camera_index)
        self._refresh_anchor_table()
        self._update_overlap()

    def _load_midi_file(self, index: int):
        if self._state is None:
            return
        mf = self._state.midi_files[index]
        self._midi_index = index
        self._midi_adapter = MidiAdapter(mf.file_path)
        self._midi_panel.load_midi(mf, self._midi_adapter)

    def _load_camera_file(self, index: int):
        if self._state is None:
            return
        cf = self._state.camera_files[index]
        self._camera_index = index
        self._camera_panel.load_video(cf)
        self._refresh_anchor_table()

    def _on_midi_combo_changed(self, index: int):
        if index >= 0:
            self._load_midi_file(index)
            self._update_overlap()

    def _on_camera_combo_changed(self, index: int):
        if index >= 0:
            self._load_camera_file(index)
            self._update_overlap()

    # --- Mode ---

    def _toggle_mode(self):
        self._locked = self._mode_btn.isChecked()
        self._mode_btn.setText(f"Mode: {'Locked' if self._locked else 'Independent'}")
        self._update_status_line()

        # Anchor lock rule: if locked and active anchor, switch MIDI to anchor's file
        if self._locked:
            self._apply_anchor_lock_rule()

    def _apply_anchor_lock_rule(self):
        """When locked + anchor active, auto-switch MIDI file to anchor's reference."""
        if self._state is None:
            return
        cf = self._state.camera_files[self._camera_index]
        anchor = cf.get_active_anchor()
        if anchor is not None and self._locked:
            # Find MIDI file index matching anchor's midi_filename
            for i, mf in enumerate(self._state.midi_files):
                if mf.filename == anchor.midi_filename:
                    self._midi_combo.blockSignals(True)
                    self._midi_combo.setCurrentIndex(i)
                    self._midi_combo.setEnabled(False)
                    self._midi_combo.blockSignals(False)
                    self._load_midi_file(i)
                    break
        else:
            self._midi_combo.setEnabled(True)

    # --- Locked mode navigation ---

    def _get_effective_shift(self) -> float:
        if self._state is None:
            return 0.0
        midi_lookup = {mf.filename: mf for mf in self._state.midi_files}
        cf = self._state.camera_files[self._camera_index]
        return engine.get_effective_shift_for_camera(cf, self._state.global_shift_seconds, midi_lookup)

    def _on_midi_position_changed(self, time_seconds: float):
        if not self._locked or self._state is None:
            return
        mf = self._state.midi_files[self._midi_index]
        cf = self._state.camera_files[self._camera_index]
        eff = self._get_effective_shift()

        midi_unix = mf.unix_start + time_seconds
        frame = engine.midi_unix_to_camera_frame(midi_unix, eff, cf)

        if frame is not None:
            self._camera_panel.show_normal()
            self._camera_panel.set_frame(frame)
        else:
            delta = engine.out_of_range_delta(midi_unix, eff, cf)
            if delta is not None and delta > 0:
                self._camera_panel.show_out_of_range(f"Camera clip starts in {delta:.2f} s")
            elif delta is not None:
                self._camera_panel.show_out_of_range(f"Camera clip ended {abs(delta):.2f} s ago")

        self._overlap.set_playhead(midi_unix)

    def _on_camera_position_changed(self, frame: int):
        if not self._locked or self._state is None:
            return
        mf = self._state.midi_files[self._midi_index]
        cf = self._state.camera_files[self._camera_index]
        eff = self._get_effective_shift()

        midi_seconds = engine.camera_frame_to_midi_seconds(frame, eff, cf, mf)

        if midi_seconds is not None:
            self._midi_panel.show_normal()
            self._midi_panel.set_position(midi_seconds)
        else:
            camera_unix = engine.camera_frame_to_unix(frame, cf)
            midi_unix = camera_unix + eff
            midi_seconds_raw = midi_unix - mf.unix_start
            if midi_seconds_raw < 0:
                self._midi_panel.show_out_of_range(f"MIDI file starts in {abs(midi_seconds_raw):.2f} s")
            else:
                self._midi_panel.show_out_of_range(f"MIDI file ended {midi_seconds_raw - mf.duration:.2f} s ago")

        camera_unix = engine.camera_frame_to_unix(frame, cf)
        self._overlap.set_playhead(camera_unix + eff)

    # --- Markers ---

    def _mark_midi(self):
        if self._state is None:
            return
        mf = self._state.midi_files[self._midi_index]
        self._midi_marker = (mf.filename, self._midi_panel.current_time)
        self._update_marker_ui()
        self._flash_label(self._midi_marker_label)

    def _mark_camera(self):
        self._camera_marker = self._camera_panel.current_frame
        self._update_marker_ui()
        self._flash_label(self._camera_marker_label)

    def _update_marker_ui(self):
        if self._midi_marker:
            fname, t = self._midi_marker
            self._midi_marker_label.setText(f"MIDI mark: {fname} @ {t:.3f}s")
        else:
            self._midi_marker_label.setText("MIDI mark: (none)")

        if self._camera_marker is not None:
            cf = self._state.camera_files[self._camera_index] if self._state else None
            if cf:
                time_s = self._camera_marker / cf.capture_fps
                self._camera_marker_label.setText(f"Camera mark: frame {self._camera_marker} ({time_s:.3f}s)")
            else:
                self._camera_marker_label.setText(f"Camera mark: frame {self._camera_marker}")
        else:
            self._camera_marker_label.setText("Camera mark: (none)")

        both_set = self._midi_marker is not None and self._camera_marker is not None
        self._compute_shift_btn.setEnabled(both_set)
        self._add_anchor_btn.setEnabled(both_set)
        if both_set:
            self._compute_shift_btn.setToolTip("")
            self._add_anchor_btn.setToolTip("")
        else:
            self._compute_shift_btn.setToolTip("Set markers first: press M on MIDI panel, C on camera panel")
            self._add_anchor_btn.setToolTip("Set markers first: press M on MIDI panel, C on camera panel")

    def _on_compute_shift(self):
        if self._state is None or self._midi_marker is None or self._camera_marker is None:
            return
        midi_filename, midi_seconds = self._midi_marker
        midi_file = self._state.midi_file_by_name(midi_filename)
        if midi_file is None:
            return
        cf = self._state.camera_files[self._camera_index]

        midi_unix = engine.midi_seconds_to_unix(midi_seconds, midi_file)
        camera_unix = engine.camera_frame_to_unix(self._camera_marker, cf)
        shift = engine.compute_global_shift_from_markers(midi_unix, camera_unix)

        result = QMessageBox.question(
            self, "Apply Global Shift",
            f"Computed global shift: {shift:.4f} s\n\nApply this as the global shift?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if result == QMessageBox.Yes:
            # Check existing anchors
            anchor_count = self._state.total_anchor_count()
            if anchor_count > 0:
                confirm = QMessageBox.warning(
                    self, "Confirm",
                    f"This will remove all {anchor_count} anchor(s). Continue?",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
                )
                if confirm != QMessageBox.Yes:
                    return
                self._state.clear_all_anchors()

            self._state.global_shift_seconds = shift
            self._refresh_anchor_table()
            self._update_overlap()
            self.state_modified.emit()

    def _on_add_anchor(self):
        if self._state is None or self._midi_marker is None or self._camera_marker is None:
            return
        label, ok = QInputDialog.getText(self, "Anchor Label", "Optional label for this anchor:")
        if not ok:
            return
        midi_filename, midi_seconds = self._midi_marker
        anchor = Anchor(
            midi_filename=midi_filename,
            midi_timestamp_seconds=midi_seconds,
            camera_frame=self._camera_marker,
            label=label,
        )
        self._anchor_table.add_anchor(anchor)
        self.state_modified.emit()

    # --- Anchors ---

    def _refresh_anchor_table(self):
        if self._state is None:
            return
        cf = self._state.camera_files[self._camera_index]
        midi_lookup = {mf.filename: mf for mf in self._state.midi_files}
        self._anchor_table.set_data(cf, midi_lookup, self._state.global_shift_seconds)

    def _on_anchor_activated(self, index: int):
        self._apply_anchor_lock_rule()
        self._update_overlap()
        self.state_modified.emit()

    def _on_anchor_deactivated(self):
        self._midi_combo.setEnabled(True)
        self._update_overlap()
        self.state_modified.emit()

    def _on_anchor_deleted(self, index: int):
        self._update_overlap()
        self.state_modified.emit()

    # --- Overlap ---

    def _update_overlap(self):
        if self._state is None:
            return
        mf = self._state.midi_files[self._midi_index]
        cf = self._state.camera_files[self._camera_index]
        eff = self._get_effective_shift()
        self._overlap.set_clips(mf, cf, eff)

    # --- Keyboard ---

    def keyPressEvent(self, event):
        key = event.key()
        shift = event.modifiers() & Qt.ShiftModifier

        if key == Qt.Key_M:
            self._mark_midi()
        elif key == Qt.Key_C:
            self._mark_camera()
        elif key == Qt.Key_L:
            self._mode_btn.click()
        elif key == Qt.Key_A:
            if self._midi_marker is not None and self._camera_marker is not None:
                self._on_add_anchor()
        elif key == Qt.Key_Left:
            if self._active_panel == "midi":
                self._midi_panel.step_ticks(-100 if shift else -1)
            else:
                self._camera_panel.step(-10 if shift else -1)
        elif key == Qt.Key_Right:
            if self._active_panel == "midi":
                self._midi_panel.step_ticks(100 if shift else 1)
            else:
                self._camera_panel.step(10 if shift else 1)
        elif key == Qt.Key_Tab:
            self._active_panel = "camera" if self._active_panel == "midi" else "midi"
            self._update_panel_focus_indicator()
        elif key == Qt.Key_Escape:
            self.back_requested.emit()
        else:
            super().keyPressEvent(event)

    def _update_panel_focus_indicator(self):
        midi_style = "border: 2px solid #4488ff;" if self._active_panel == "midi" else "border: 1px solid #555;"
        cam_style = "border: 2px solid #ff8844;" if self._active_panel == "camera" else "border: 1px solid #555;"
        self._midi_panel.setStyleSheet(midi_style)
        self._camera_panel.setStyleSheet(cam_style)
        self._update_status_line()

    def _update_status_line(self):
        mode = "Locked" if self._locked else "Independent"
        active = "MIDI" if self._active_panel == "midi" else "Camera"
        self._status_line.setText(
            f"{mode} Mode  |  Active panel: {active}  |  "
            f"Arrows: navigate  |  Tab: switch panel  |  L: toggle mode  |  "
            f"M: mark MIDI  |  C: mark camera  |  A: add anchor"
        )

    def _flash_label(self, label: QLabel):
        """Brief visual flash to confirm marker was set."""
        original = label.styleSheet()
        label.setStyleSheet("background-color: #446; color: white; font-weight: bold; padding: 2px;")
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(400, lambda: label.setStyleSheet(original))

    def cleanup(self):
        self._camera_panel.cleanup()
