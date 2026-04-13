"""Level 2: Alignment Detail View — side-by-side MIDI + camera panels."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSignalBlocker
from PyQt5.QtGui import QKeySequence
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QSplitter, QLabel,
    QPushButton, QComboBox, QLineEdit, QMessageBox, QInputDialog,
    QShortcut,
)

from alignment_tool.core.models import AlignmentState, MidiFileInfo, CameraFileInfo, Anchor
from alignment_tool.core.errors import (
    MarkersNotSetError, AnchorsExistError, UnknownMidiFileError,
)
from alignment_tool.io.midi_adapter import MidiAdapter
from alignment_tool.services.alignment_service import AlignmentService
from alignment_tool.services.level2_controller import (
    Level2Controller, Mode, SyncOutput,
)
from alignment_tool.ui.level2_midi_panel import MidiPanelWidget
from alignment_tool.ui.level2_camera_panel import CameraPanelWidget
from alignment_tool.ui.level2_anchor_table import AnchorTableWidget
from alignment_tool.ui.level2_overlap_indicator import OverlapIndicatorWidget
from alignment_tool.core import engine


class Level2View(QWidget):
    """Alignment detail view for a MIDI + camera pair."""

    back_requested = pyqtSignal()
    state_modified = pyqtSignal()  # any alignment state change

    def __init__(self, parent=None):
        super().__init__(parent)
        self._state: AlignmentState | None = None
        self._service: AlignmentService | None = None
        self._controller: Level2Controller | None = None
        self._midi_index: int = 0
        self._camera_index: int = 0
        self._midi_adapter: MidiAdapter | None = None
        self._active_panel: str = "camera"  # still view-local: which panel last had focus

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

        # Overlap indicator (clickable navigation bar)
        self._overlap = OverlapIndicatorWidget()
        self._overlap.midi_time_clicked.connect(self._on_overlap_midi_clicked)
        self._overlap.camera_frame_clicked.connect(self._on_overlap_camera_clicked)
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

    def attach(
        self, state: AlignmentState,
        service: AlignmentService,
        controller: Level2Controller,
    ) -> None:
        self._state = state
        self._service = service
        self._controller = controller

    def load_pair(self, midi_index: int, camera_index: int) -> None:
        """Load a MIDI + camera pair for alignment."""
        if self._controller is None or self._state is None:
            return
        self._midi_index = midi_index
        self._camera_index = camera_index
        self._controller.load_pair(midi_index, camera_index)
        self._update_marker_ui()

        # Populate combos
        self._midi_combo.blockSignals(True)
        self._midi_combo.clear()
        for mf in self._state.midi_files:
            self._midi_combo.addItem(mf.filename)
        self._midi_combo.setCurrentIndex(midi_index)
        self._midi_combo.blockSignals(False)

        self._camera_combo.blockSignals(True)
        self._camera_combo.clear()
        for cf in self._state.camera_files:
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
        self._midi_panel.show_normal()
        # Jump to the earliest-onset note so the user sees content immediately.
        notes = self._midi_adapter.notes
        if notes:
            first_note_time = min(n.start for n in notes)
            self._midi_panel.set_position(first_note_time)

    def _load_camera_file(self, index: int):
        if self._state is None:
            return
        cf = self._state.camera_files[index]
        self._camera_index = index
        self._camera_panel.load_video(cf)
        self._camera_panel.show_normal()
        self._refresh_anchor_table()
        self._anchor_table.set_context(self._state, self._service, self._camera_index)

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
        if self._controller is None:
            return
        new_mode = Mode.LOCKED if self._mode_btn.isChecked() else Mode.FREE
        self._controller.set_mode(new_mode)
        self._mode_btn.setText(f"Mode: {'Locked' if new_mode == Mode.LOCKED else 'Independent'}")
        self._update_status_line()

        if new_mode == Mode.LOCKED:
            # Anchor lock rule: if active anchor, switch MIDI to anchor's file
            self._apply_anchor_lock_rule()
            # Sync panels when entering locked mode (even without anchor)
            self._sync_from_camera()
        else:
            # Leaving locked mode: clear any stuck out-of-range display on
            # either panel, since OOR is only meaningful while locked.
            self._reset_panels_to_normal()

    def _reset_panels_to_normal(self):
        self._midi_panel.show_normal()
        self._camera_panel.show_normal()

    def _apply_anchor_lock_rule(self):
        """When locked + anchor active, auto-switch MIDI file to anchor's reference."""
        if self._state is None or self._controller is None:
            return
        cf = self._state.camera_files[self._camera_index]
        anchor = cf.get_active_anchor()
        locked = self._controller.mode == Mode.LOCKED
        if anchor is not None and locked:
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
                # Notify controller of the MIDI-file switch so its sync math uses it.
                self._controller.load_pair(target_index, self._camera_index)
                self._controller.set_mode(Mode.LOCKED)
                # Navigate to the anchor's position in the new file
                self._midi_panel.set_position(anchor.midi_timestamp_seconds)

            # Sync panels based on current camera position
            self._sync_from_camera()
        else:
            self._midi_combo.setEnabled(True)

    # --- Locked mode navigation ---

    def _get_effective_shift(self) -> float:
        if self._service is None:
            return 0.0
        return self._service.effective_shift_for(self._camera_index)

    def _set_midi_playhead(self, time_seconds: float) -> None:
        """Push the MIDI overlap playhead to the given MIDI-relative time."""
        if self._state is None:
            return
        mf = self._state.midi_files[self._midi_index]
        self._overlap.set_midi_playhead(mf.unix_start + time_seconds)

    def _set_camera_playhead(self, frame: int) -> None:
        """Push the camera overlap playhead to the given frame, aligned by effective shift."""
        if self._state is None:
            return
        cf = self._state.camera_files[self._camera_index]
        eff = self._get_effective_shift()
        self._overlap.set_camera_playhead(engine.camera_frame_to_unix(frame, cf) + eff)

    def _snap_both_overlap_playheads_to_frame(self, frame: int) -> None:
        """Set both overlap playheads to the same unix time derived from a frame.

        Used in locked mode when MIDI drives the camera. The MIDI overlap
        playhead would otherwise sit at the user's continuous drag time while
        the camera playhead sits at the frame-quantized unix time; this gap
        (up to 0.5/fps s) can render as a visible 1-pixel offset via the
        overlap indicator's int(px) rounding. Snapping both to the frame
        grid guarantees perfect visual alignment. The MIDI panel's own
        internal playhead (red line) is unaffected.
        """
        if self._state is None:
            return
        cf = self._state.camera_files[self._camera_index]
        eff = self._get_effective_shift()
        aligned_unix = engine.camera_frame_to_unix(frame, cf) + eff
        self._overlap.set_camera_playhead(aligned_unix)
        self._overlap.set_midi_playhead(aligned_unix)

    def _on_midi_position_changed(self, time_seconds: float):
        if self._controller is None or self._state is None:
            return
        # Always update MIDI indicator (works in both modes)
        self._set_midi_playhead(time_seconds)

        out = self._controller.on_midi_position_changed(time_seconds)
        self._apply_sync_output(out, driven_panel="midi")

    def _on_camera_position_changed(self, frame: int):
        if self._controller is None or self._state is None:
            return
        # Always update camera indicator (works in both modes)
        self._set_camera_playhead(frame)

        out = self._controller.on_camera_position_changed(frame)
        self._apply_sync_output(out, driven_panel="camera")

    def _apply_sync_output(self, out: SyncOutput, driven_panel: str = "") -> None:
        """Render a controller SyncOutput onto the panels.

        Feedback-loop safe via QSignalBlocker around mirrored ``set_*`` calls.
        Because the blocker swallows the mirrored panel's ``position_changed``
        signal, the overlap playhead on the mirrored side must be pushed
        explicitly here (otherwise only the driven side's indicator moves).
        ``driven_panel`` indicates which panel triggered the update so that OOR
        display targets the mirrored (other) panel.
        """
        if out.new_camera_frame is not None:
            self._camera_panel.show_normal()
            with QSignalBlocker(self._camera_panel):
                self._camera_panel.set_frame(out.new_camera_frame)
            # MIDI drove camera in locked mode. Snap BOTH overlap playheads to
            # the camera-frame unix so the two vertical indicators can't drift
            # apart due to round()-vs-continuous quantization (~sub-pixel but
            # visible after int(px) rounding).
            self._snap_both_overlap_playheads_to_frame(out.new_camera_frame)
        if out.new_midi_time is not None:
            self._midi_panel.show_normal()
            with QSignalBlocker(self._midi_panel):
                self._midi_panel.set_position(out.new_midi_time)
            self._set_midi_playhead(out.new_midi_time)
            # No symmetric snap needed: when camera drives, new_midi_time was
            # computed FROM the frame so set_midi_playhead(new_midi_time)
            # already lands at exactly the same unix as the camera playhead.
        if out.out_of_range_delta is not None:
            self._show_oor(out.out_of_range_delta, driven_panel)
        else:
            self._clear_oor(driven_panel)

    def _show_oor(self, delta: float, driven_panel: str) -> None:
        """Show an out-of-range message on the mirrored panel."""
        if driven_panel == "midi":
            if delta > 0:
                self._camera_panel.show_out_of_range(f"Camera clip starts in {delta:.2f} s")
            else:
                self._camera_panel.show_out_of_range(f"Camera clip ended {abs(delta):.2f} s ago")
        else:
            if delta > 0:
                self._midi_panel.show_out_of_range(f"MIDI file starts in {delta:.2f} s")
            else:
                self._midi_panel.show_out_of_range(f"MIDI file ended {abs(delta):.2f} s ago")

    def _clear_oor(self, driven_panel: str = "") -> None:
        """No-op: panels get show_normal() restored as part of set_frame/set_position paths."""
        # When a valid frame/time is produced, `_apply_sync_output` already calls
        # show_normal() before mirroring. When nothing is produced (e.g. FREE mode),
        # there is no OOR to clear. Keep this as an explicit hook for clarity.
        return

    def _sync_from_camera(self):
        """Sync MIDI panel to current camera position using effective shift."""
        if self._controller is None or self._controller.mode != Mode.LOCKED or self._state is None:
            return
        frame = self._camera_panel.current_frame
        self._on_camera_position_changed(frame)

    def _sync_from_midi(self):
        """Sync camera panel to current MIDI position using effective shift."""
        if self._controller is None or self._controller.mode != Mode.LOCKED or self._state is None:
            return
        t = self._midi_panel.current_time
        self._on_midi_position_changed(t)

    # --- Markers ---

    def _mark_midi(self):
        if self._controller is None:
            return
        self._controller.mark_midi(self._midi_panel.current_time)
        self._update_marker_ui()
        self._flash_label(self._midi_marker_label)

    def _mark_camera(self):
        if self._controller is None:
            return
        self._controller.mark_camera(self._camera_panel.current_frame)
        self._update_marker_ui()
        self._flash_label(self._camera_marker_label)

    def _update_marker_ui(self):
        if self._controller is None or self._state is None:
            return
        midi_m = self._controller.midi_marker
        cam_m = self._controller.camera_marker

        if midi_m is not None:
            mf = self._state.midi_files[self._midi_index]
            self._midi_marker_label.setText(f"MIDI mark: {mf.filename} @ {midi_m:.3f}s")
        else:
            self._midi_marker_label.setText("MIDI mark: (none)")

        if cam_m is not None:
            cf = self._state.camera_files[self._camera_index]
            time_s = cam_m / cf.capture_fps
            self._camera_marker_label.setText(f"Camera mark: frame {cam_m} ({time_s:.3f}s)")
        else:
            self._camera_marker_label.setText("Camera mark: (none)")

        both_set = midi_m is not None and cam_m is not None
        self._compute_shift_btn.setEnabled(both_set)
        self._add_anchor_btn.setEnabled(both_set)
        if both_set:
            self._compute_shift_btn.setToolTip("")
            self._add_anchor_btn.setToolTip("")
        else:
            self._compute_shift_btn.setToolTip("Set markers first: press M on MIDI panel, C on camera panel")
            self._add_anchor_btn.setToolTip("Set markers first: press M on MIDI panel, C on camera panel")

    def _on_compute_shift(self):
        if self._controller is None or self._service is None:
            return
        try:
            new_shift = self._controller.compute_shift_from_markers()
        except MarkersNotSetError as exc:
            QMessageBox.warning(self, "Markers not set", str(exc))
            return

        reply = QMessageBox.question(
            self, "Apply Global Shift",
            f"Computed global shift: {new_shift:.4f} s\n\nApply this as the global shift?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if reply != QMessageBox.Yes:
            return

        try:
            self._service.set_global_shift(new_shift, clear_anchors_if_needed=False)
        except AnchorsExistError as exc:
            reply = QMessageBox.warning(
                self, "Confirm",
                f"This will remove all {exc.count} anchor(s). Continue?",
                QMessageBox.Yes | QMessageBox.No, QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return
            self._service.set_global_shift(new_shift, clear_anchors_if_needed=True)

        self._controller.clear_markers()
        self._update_marker_ui()
        self._refresh_anchor_table()
        self._update_overlap()
        self.state_modified.emit()

    def _on_add_anchor(self):
        if self._controller is None or self._service is None:
            return
        label, ok = QInputDialog.getText(self, "Anchor Label", "Optional label for this anchor:")
        if not ok:
            return
        try:
            anchor = self._controller.build_anchor_from_markers(label=label)
        except MarkersNotSetError as exc:
            QMessageBox.warning(self, "Markers not set", str(exc))
            return
        try:
            idx = self._service.add_anchor(self._camera_index, anchor)
        except UnknownMidiFileError as exc:
            QMessageBox.warning(self, "Unknown MIDI file", str(exc))
            return
        self._refresh_anchor_table()
        self._controller.clear_markers()
        self._update_marker_ui()
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
        self._reset_panels_to_normal()
        self._update_overlap()
        self.state_modified.emit()

    def _on_anchor_deleted(self, index: int):
        self._update_overlap()
        self.state_modified.emit()

    # --- Overlap navigation bar ---

    def _on_overlap_midi_clicked(self, midi_seconds: float):
        """User clicked/dragged on the MIDI track of the navigation bar."""
        self._midi_panel.show_normal()
        self._midi_panel.set_position(midi_seconds)

    def _on_overlap_camera_clicked(self, frame: int):
        """User clicked/dragged on the camera track of the navigation bar."""
        self._camera_panel.show_normal()
        self._camera_panel.set_frame(frame)

    def _update_overlap(self):
        if self._state is None:
            return
        mf = self._state.midi_files[self._midi_index]
        cf = self._state.camera_files[self._camera_index]
        eff = self._get_effective_shift()
        self._overlap.set_clips(mf, cf, eff)
        # Always keep indicators in sync with current panel positions and eff
        self._overlap.set_midi_playhead(mf.unix_start + self._midi_panel.current_time)
        self._overlap.set_camera_playhead(engine.camera_frame_to_unix(self._camera_panel.current_frame, cf) + eff)

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
        self._midi_panel.show_normal()
        self._midi_panel.set_position(midi_seconds)

        # Position camera panel at overlap start. After the engine's boundary
        # clamp fix, midi_unix_to_camera_frame always returns a valid frame
        # when overlap exists, but we keep a safe default for paranoia.
        frame = engine.midi_unix_to_camera_frame(overlap_start_unix, eff, cf)
        if frame is None:
            frame = 0
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
        if self._controller is None:
            return
        if self._controller.midi_marker is not None and self._controller.camera_marker is not None:
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
        locked = self._controller is not None and self._controller.mode == Mode.LOCKED
        mode = "Locked" if locked else "Independent"
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
