"""Level 2: Alignment Detail View — side-by-side MIDI + camera panels."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QComboBox, QLineEdit, QMessageBox, QInputDialog,
    QShortcut,
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

        # Keyboard shortcuts (work regardless of which child widget has focus)
        self._setup_shortcuts()

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
        self._update_panel_focus_indicator()

    def _load_midi_file(self, index: int):
        if self._state is None:
            return
        mf = self._state.midi_files[index]
        self._midi_index = index
        self._midi_adapter = MidiAdapter(mf.file_path)
        self._midi_panel.load_midi(mf, self._midi_adapter)
        # Jump to first note so the user sees content immediately
        if self._midi_adapter.notes:
            first_note_time = self._midi_adapter.notes[0].start
            self._midi_panel.set_position(first_note_time)

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

        if self._locked:
            # Anchor lock rule: if active anchor, switch MIDI to anchor's file
            self._apply_anchor_lock_rule()
            # Sync panels when entering locked mode (even without anchor)
            self._sync_from_camera()

    def _apply_anchor_lock_rule(self):
        """When locked + anchor active, auto-switch MIDI file to anchor's reference."""
        if self._state is None:
            return
        cf = self._state.camera_files[self._camera_index]
        anchor = cf.get_active_anchor()
        if anchor is not None and self._locked:
            # Find MIDI file index matching anchor's midi_filename
            target_index = None
            for i, mf in enumerate(self._state.midi_files):
                if mf.filename == anchor.midi_filename:
                    target_index = i
                    break
            if target_index is None:
                return

            # Always lock the combo to the anchor's file
            self._midi_combo.blockSignals(True)
            self._midi_combo.setCurrentIndex(target_index)
            self._midi_combo.setEnabled(False)
            self._midi_combo.blockSignals(False)

            # Only reload if switching to a different MIDI file
            if target_index != self._midi_index:
                self._load_midi_file(target_index)
                # Navigate to the anchor's position in the new file
                self._midi_panel.set_position(anchor.midi_timestamp_seconds)

            # Sync panels based on current camera position
            self._sync_from_camera()
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

    def _sync_from_camera(self):
        """Sync MIDI panel to current camera position using effective shift."""
        if not self._locked or self._state is None:
            return
        frame = self._camera_panel.current_frame
        self._on_camera_position_changed(frame)

    def _sync_from_midi(self):
        """Sync camera panel to current MIDI position using effective shift."""
        if not self._locked or self._state is None:
            return
        t = self._midi_panel.current_time
        self._on_midi_position_changed(t)

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

    def _jump_to_overlap(self):
        """Jump both panels to the start of the overlap region."""
        if self._state is None:
            return
        mf = self._state.midi_files[self._midi_index]
        cf = self._state.camera_files[self._camera_index]
        eff = self._get_effective_shift()

        aligned_cam_start = cf.raw_unix_start + eff
        aligned_cam_end = cf.raw_unix_end + eff

        # Overlap start = max(midi_start, aligned_cam_start)
        overlap_start_unix = max(mf.unix_start, aligned_cam_start)
        # Overlap end = min(midi_end, aligned_cam_end)
        overlap_end_unix = min(mf.unix_end, aligned_cam_end)

        if overlap_start_unix >= overlap_end_unix:
            QMessageBox.information(
                self, "No Overlap",
                "The selected MIDI file and camera clip do not overlap "
                "with the current alignment. Try adjusting the global shift first."
            )
            return

        # Position MIDI panel at overlap start
        midi_seconds = overlap_start_unix - mf.unix_start
        midi_seconds = max(0.0, min(midi_seconds, mf.duration))
        self._midi_panel.set_position(midi_seconds)

        # Position camera panel at overlap start
        camera_unix = overlap_start_unix - eff
        frame = round((camera_unix - cf.raw_unix_start) * cf.capture_fps)
        frame = max(0, min(frame, cf.total_frames - 1))
        self._camera_panel.show_normal()
        self._camera_panel.set_frame(frame)

    # --- Keyboard shortcuts ---

    def _setup_shortcuts(self):
        """Create QShortcut objects that work regardless of child widget focus."""
        ctx = Qt.WidgetWithChildrenShortcut

        def shortcut(key, slot):
            s = QShortcut(QKeySequence(key), self)
            s.setContext(ctx)
            s.activated.connect(slot)
            return s

        shortcut(Qt.Key_M, self._mark_midi)
        shortcut(Qt.Key_C, self._mark_camera)
        shortcut(Qt.Key_L, lambda: self._mode_btn.click())
        shortcut(Qt.Key_A, self._shortcut_add_anchor)
        shortcut(Qt.Key_Left, lambda: self._step_active(-1, False))
        shortcut(Qt.Key_Right, lambda: self._step_active(1, False))
        shortcut(Qt.SHIFT + Qt.Key_Left, lambda: self._step_active(-1, True))
        shortcut(Qt.SHIFT + Qt.Key_Right, lambda: self._step_active(1, True))
        shortcut(Qt.Key_O, self._jump_to_overlap)
        shortcut(Qt.Key_Tab, self._switch_active_panel)
        shortcut(Qt.Key_Escape, self.back_requested.emit)

    def _shortcut_add_anchor(self):
        if self._midi_marker is not None and self._camera_marker is not None:
            self._on_add_anchor()

    def _step_active(self, direction: int, large: bool):
        if self._active_panel == "midi":
            ticks = (100 if large else 1) * direction
            self._midi_panel.step_ticks(ticks)
        else:
            frames = (10 if large else 1) * direction
            self._camera_panel.step(frames)

    def _switch_active_panel(self):
        self._active_panel = "camera" if self._active_panel == "midi" else "midi"
        self._update_panel_focus_indicator()

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
            f"{mode} Mode  |  Active: {active} (Tab to switch)  |  "
            f"Arrows: navigate  |  L: toggle mode  |  "
            f"M: mark MIDI  |  C: mark camera  |  A: add anchor  |  O: jump to overlap"
        )

    def _flash_label(self, label: QLabel):
        """Brief visual flash to confirm marker was set."""
        original = label.styleSheet()
        label.setStyleSheet("background-color: #446; color: white; font-weight: bold; padding: 2px;")
        QTimer.singleShot(400, lambda: label.setStyleSheet(original))

    def cleanup(self):
        self._camera_panel.cleanup()
