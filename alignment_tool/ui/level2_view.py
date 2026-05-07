"""Level 2: Alignment Detail View — side-by-side MIDI + camera panels."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSignalBlocker, QThread, QMetaObject, Q_ARG
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
from alignment_tool.io.intensity_worker import IntensityWorker
from alignment_tool.services.alignment_service import AlignmentService
from alignment_tool.services.level2_controller import (
    Level2Controller, Mode, SyncOutput,
)
from alignment_tool.ui.level2_midi_panel import MidiPanelWidget
from alignment_tool.ui.level2_camera_panel import CameraPanelWidget
from alignment_tool.ui.level2_anchor_table import AnchorTableWidget
from alignment_tool.ui.level2_overlap_indicator import OverlapIndicatorWidget
from alignment_tool.ui.level2_intensity_plot import IntensityPlotWidget
from alignment_tool.core import engine

INTENSITY_HALF_WINDOW = 120


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
        # Pending un-flash timers per marker label; see _flash_label.
        self._flash_timers: dict[QLabel, QTimer] = {}

        self._build_ui()

    def _build_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        # Top bar: back button + dropdowns + mode toggle
        top_bar = QHBoxLayout()
        self._back_btn = QPushButton("< Back")
        self._back_btn.clicked.connect(self._on_back_requested)
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

        self._compute_shift_btn = QPushButton("Compute Global Shift")
        self._compute_shift_btn.setEnabled(False)
        self._compute_shift_btn.setToolTip("Set markers first: press M on MIDI panel, C on camera panel")
        self._compute_shift_btn.clicked.connect(self._on_compute_shift)
        top_bar.addWidget(self._compute_shift_btn)

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

        # Main panels + per-panel marker readouts. Each panel sits in a column
        # container so the marker label lives directly under the panel it
        # describes. The marker labels still belong to Level2View, so
        # _update_marker_ui and _flash_label keep working unchanged.
        self._midi_marker_label = QLabel("MIDI mark: (none)")
        self._midi_marker_label.setAlignment(Qt.AlignCenter)
        self._camera_marker_label = QLabel("Camera mark: (none)")
        self._camera_marker_label.setAlignment(Qt.AlignCenter)

        self._midi_panel = MidiPanelWidget()
        self._camera_panel = CameraPanelWidget()

        midi_col = QWidget()
        midi_col_layout = QVBoxLayout(midi_col)
        midi_col_layout.setContentsMargins(0, 0, 0, 0)
        midi_col_layout.setSpacing(2)
        midi_col_layout.addWidget(self._midi_panel, stretch=1)
        midi_col_layout.addWidget(self._midi_marker_label)

        camera_col = QWidget()
        camera_col_layout = QVBoxLayout(camera_col)
        camera_col_layout.setContentsMargins(0, 0, 0, 0)
        camera_col_layout.setSpacing(2)
        camera_col_layout.addWidget(self._camera_panel, stretch=1)
        camera_col_layout.addWidget(self._camera_marker_label)

        splitter = QSplitter(Qt.Horizontal)
        splitter.addWidget(midi_col)
        splitter.addWidget(camera_col)
        splitter.setSizes([500, 500])
        layout.addWidget(splitter, stretch=1)

        # Intensity probe: plot of pixel luma vs. frame index for a dropped
        # probe dot. Always visible; displays a placeholder when no dot is
        # active and an error if sampling fails. Lives in its own row between
        # the splitter and the anchor table so the splitter stays symmetric.
        self._intensity_plot = IntensityPlotWidget()
        self._intensity_plot.frame_seek_requested.connect(
            self._on_intensity_plot_frame_seek_requested
        )
        layout.addWidget(self._intensity_plot)
        # Identifies the most-recent dot we're waiting on. Tuple of
        # (center_frame, src_x, src_y) or None. Stale worker results are
        # filtered by exact tuple match so a late sample from an earlier dot
        # (or a previous clip) can't overwrite the current trace.
        self._last_sample_request: tuple[int, int, int] | None = None

        # Intensity worker runs on its own QThread with its own cv2 capture,
        # so display scrubbing stays responsive while a window is sampled.
        self._intensity_thread = QThread(self)
        self._intensity_worker = IntensityWorker()
        self._intensity_worker.moveToThread(self._intensity_thread)
        self._intensity_worker.intensity_ready.connect(self._on_intensity_ready)
        self._intensity_worker.sample_failed.connect(self._on_intensity_failed)
        self._intensity_thread.start()

        # Camera panel → intensity pipeline wiring.
        self._camera_panel.dot_dropped.connect(self._on_camera_dot_dropped)
        self._camera_panel.dot_cleared.connect(self._on_camera_dot_cleared)
        # Playhead in the plot tracks the camera scrubbing in real time.

        # Add Anchor lives with the anchor table it mutates (inserted below).
        self._add_anchor_btn = QPushButton("Add Anchor (A)")
        self._add_anchor_btn.setEnabled(False)
        self._add_anchor_btn.setToolTip("Set markers first: press M on MIDI panel, C on camera panel")
        self._add_anchor_btn.clicked.connect(self._on_add_anchor)

        # Anchor table
        self._anchor_table = AnchorTableWidget()
        self._anchor_table.add_header_action(self._add_anchor_btn)
        self._anchor_table.anchor_activated.connect(self._on_anchor_activated)
        self._anchor_table.anchor_deactivated.connect(self._on_anchor_deactivated)
        self._anchor_table.anchor_deleted.connect(self._on_anchor_deleted)
        self._anchor_table.anchor_label_changed.connect(self._on_anchor_label_changed)
        self._anchor_table.midi_time_jump_requested.connect(self._on_anchor_midi_jump)
        self._anchor_table.camera_frame_jump_requested.connect(self._on_anchor_camera_jump)
        self._anchor_table.probe_jump_requested.connect(self._on_anchor_probe_jump)
        self._anchor_table.setMaximumHeight(200)
        layout.addWidget(self._anchor_table)

        # Connect panel position signals
        self._midi_panel.position_changed.connect(self._on_midi_position_changed)
        self._camera_panel.position_changed.connect(self._on_camera_position_changed)
        self._camera_panel.position_changed.connect(self._intensity_plot.set_playhead_frame)

        # Auto-activate the panel the user is directly interacting with. Only
        # fires from mouse/wheel events, never from programmatic navigation.
        self._midi_panel.user_interacted.connect(lambda: self._set_active_panel("midi"))
        self._camera_panel.user_interacted.connect(lambda: self._set_active_panel("camera"))

        # Keyboard shortcuts (work regardless of which child widget has focus)
        self._setup_shortcuts()

    def reset(self) -> None:
        """Release stale resources from the previous state.

        Called by MainWindow._set_state *before* attach() so the old service
        is still valid for clear_active_anchor().
        """
        if self._service is not None:
            self._service.clear_active_anchor()
        self._camera_panel.clear_dot()
        self._camera_panel.close_video()
        QMetaObject.invokeMethod(
            self._intensity_worker, "close_video", Qt.QueuedConnection,
        )
        self._midi_adapter = None

        self._mode_btn.setChecked(False)
        self._mode_btn.setText("Mode: Independent")
        self._midi_marker_label.setText("MIDI mark: (none)")
        self._camera_marker_label.setText("Camera mark: (none)")
        self._compute_shift_btn.setEnabled(False)
        self._add_anchor_btn.setEnabled(False)

        self._midi_combo.blockSignals(True)
        self._midi_combo.clear()
        self._midi_combo.blockSignals(False)
        self._camera_combo.blockSignals(True)
        self._camera_combo.clear()
        self._camera_combo.blockSignals(False)

        self._midi_index = 0
        self._camera_index = 0

        for timer in self._flash_timers.values():
            timer.stop()
        self._flash_timers.clear()

        self._overlap.clear()
        self._update_status_line()

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
        if self._service is not None:
            self._service.clear_active_anchor()
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
        # Keep the controller's indices aligned with the view and refresh the
        # marker labels (load_pair clears markers). Covers initial drill-down,
        # combo change, and anchor-lock reload in one place.
        if self._controller is not None:
            self._controller.load_pair(self._midi_index, self._camera_index)
            self._update_marker_ui()
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
        if self._controller is not None:
            self._controller.load_pair(self._midi_index, self._camera_index)
            self._update_marker_ui()
        self._camera_panel.load_video(cf)
        self._camera_panel.show_normal()
        # Open the intensity worker on the new clip via a queued invocation so
        # the cv2 capture is created on the worker thread (not the UI thread).
        # _on_camera_dot_cleared (triggered by load_video) also hides the plot.
        QMetaObject.invokeMethod(
            self._intensity_worker,
            "open_video",
            Qt.QueuedConnection,
            Q_ARG(str, cf.mp4_path),
        )
        self._refresh_anchor_table()
        self._anchor_table.set_context(self._state, self._service, self._camera_index)

    def _on_midi_combo_changed(self, index: int):
        if index >= 0:
            if self._service is not None:
                self._service.clear_active_anchor()
            self._load_midi_file(index)
            self._refresh_anchor_table()
            if self._controller is not None and self._controller.mode == Mode.LOCKED:
                self._sync_from_camera()
            self._update_overlap()

    def _on_camera_combo_changed(self, index: int):
        if index >= 0:
            if self._service is not None:
                self._service.clear_active_anchor()
            self._load_camera_file(index)
            if self._controller is not None and self._controller.mode == Mode.LOCKED:
                self._sync_from_camera()
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
            # Sync panels when entering locked mode
            self._sync_from_camera()
            # Rebind overlap widget to current mf/cf/eff; _sync_from_camera
            # only pushes playheads, not bar extents.
            self._update_overlap()
        else:
            # Leaving locked mode: clear any stuck out-of-range display on
            # either panel, since OOR is only meaningful while locked.
            self._reset_panels_to_normal()

    def _reset_panels_to_normal(self):
        self._midi_panel.show_normal()
        self._camera_panel.show_normal()

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
        # User is actively driving MIDI — restore its normal display in case a
        # prior sync left it in OOR. `_apply_sync_output` only restores the
        # mirrored panel, so the driving side needs this explicit call.
        self._midi_panel.show_normal()
        # Always update MIDI indicator (works in both modes)
        self._set_midi_playhead(time_seconds)

        out = self._controller.on_midi_position_changed(time_seconds)
        self._apply_sync_output(out, driven_panel="midi")

    def _on_camera_position_changed(self, frame: int):
        if self._controller is None or self._state is None:
            return
        # Symmetric to `_on_midi_position_changed`: the driving camera panel
        # must clear any stale OOR visual when the user navigates it.
        self._camera_panel.show_normal()
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
            # position_changed is blocked above, so the intensity plot's
            # playhead (normally wired to camera.position_changed) would
            # miss this update. Push it explicitly.
            self._intensity_plot.set_playhead_frame(out.new_camera_frame)
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
        probe_xy = self._camera_panel.current_dot_xy
        probe_x = probe_xy[0] if probe_xy is not None else None
        probe_y = probe_xy[1] if probe_xy is not None else None
        try:
            anchor = self._controller.build_anchor_from_markers(
                label=label, probe_x=probe_x, probe_y=probe_y,
            )
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
        current_midi_filename = None
        if 0 <= self._midi_index < len(self._state.midi_files):
            current_midi_filename = self._state.midi_files[self._midi_index].filename
        self._anchor_table.set_data(
            cf,
            midi_lookup,
            self._state.global_shift_seconds,
            current_midi_filename,
        )

    def _on_anchor_activated(self, index: int):
        if self._controller is not None and self._controller.mode == Mode.LOCKED:
            self._sync_from_camera()
        self._update_overlap()
        self.state_modified.emit()

    def _on_anchor_deactivated(self):
        self._reset_panels_to_normal()
        if self._controller is not None and self._controller.mode == Mode.LOCKED:
            self._sync_from_camera()
        self._update_overlap()
        self.state_modified.emit()

    def _on_anchor_label_changed(self, index: int):
        # Label edits don't affect shifts or geometry, so no panel resync needed.
        # Just mark the state dirty so Save/Ctrl+S / close-prompt pick it up.
        self.state_modified.emit()

    def _on_anchor_deleted(self, index: int):
        cf = self._state.camera_files[self._camera_index]
        if cf.get_active_anchor() is None:
            # Active anchor was just deleted (service clears active_anchor_index
            # when its index matches). Mirror _on_anchor_deactivated cleanup.
            self._reset_panels_to_normal()
            if self._controller is not None and self._controller.mode == Mode.LOCKED:
                self._sync_from_camera()
        self._update_overlap()
        self.state_modified.emit()

    def _on_anchor_midi_jump(self, midi_seconds: float):
        """Double-click on an anchor row's MIDI Time cell."""
        self._set_active_panel("midi")
        self._midi_panel.show_normal()
        self._midi_panel.set_position(midi_seconds)

    def _on_anchor_camera_jump(self, frame: int):
        """Double-click on an anchor row's Camera Frame cell."""
        self._set_active_panel("camera")
        self._camera_panel.show_normal()
        self._camera_panel.set_frame(frame)

    def _on_anchor_probe_jump(self, src_x: int, src_y: int):
        """Double-click on an anchor row's Probe (x,y) cell.

        Re-drops the probe dot at the stored pixel coords on whatever frame
        the camera panel is currently showing. The downstream pipeline
        (camera_panel.dot_dropped → _on_camera_dot_dropped) re-samples the
        intensity window around the current frame.
        """
        self._set_active_panel("camera")
        self._camera_panel.show_normal()
        self._camera_panel.drop_dot(src_x, src_y)

    # --- Overlap navigation bar ---

    def _on_overlap_midi_clicked(self, midi_seconds: float):
        """User clicked/dragged on the MIDI track of the navigation bar."""
        self._set_active_panel("midi")
        self._midi_panel.show_normal()
        self._midi_panel.set_position(midi_seconds)

    def _on_overlap_camera_clicked(self, frame: int):
        """User clicked/dragged on the camera track of the navigation bar."""
        self._set_active_panel("camera")
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
        shortcut(Qt.Key_R, self._resample_intensity_here)
        shortcut(Qt.Key_Left, lambda: self._step_active(-1, False))
        shortcut(Qt.Key_Right, lambda: self._step_active(1, False))
        shortcut(Qt.SHIFT + Qt.Key_Left, lambda: self._step_active(-1, True))
        shortcut(Qt.SHIFT + Qt.Key_Right, lambda: self._step_active(1, True))
        shortcut(Qt.Key_O, self._jump_to_overlap)
        shortcut(Qt.Key_Tab, self._switch_active_panel)
        shortcut(Qt.Key_Escape, self._on_back_requested)

    def _shortcut_add_anchor(self):
        if self._controller is None:
            return
        if self._controller.midi_marker is not None and self._controller.camera_marker is not None:
            self._on_add_anchor()

    def _resample_intensity_here(self):
        """Re-sample the intensity window centered on the current camera frame.

        Reuses the existing dot at its source coords and re-drops it so the
        sample center moves to the current frame. Silent no-op if no dot is set.
        """
        dot = self._camera_panel.current_dot_xy
        if dot is None:
            return
        self._camera_panel.drop_dot(dot[0], dot[1])

    def _step_active(self, direction: int, large: bool):
        if self._active_panel == "midi":
            ticks = (100 if large else 1) * direction
            self._midi_panel.step_ticks(ticks)
        else:
            frames = (10 if large else 1) * direction
            self._camera_panel.step(frames)

    def _switch_active_panel(self):
        self._set_active_panel("camera" if self._active_panel == "midi" else "midi")

    def _set_active_panel(self, name: str) -> None:
        """Single entry point for changing which panel arrow keys drive."""
        if self._active_panel == name:
            return
        self._active_panel = name
        self._update_panel_focus_indicator()

    def _update_panel_focus_indicator(self):
        # Constant border width avoids a 1-px content shift on activation.
        # Object-name selectors scope the rule to each panel, so the border
        # doesn't cascade to child widgets (canvas, labels, counter).
        midi_color = "#4488ff" if self._active_panel == "midi" else "#555"
        cam_color = "#ff8844" if self._active_panel == "camera" else "#555"
        self._midi_panel.setStyleSheet(
            f"QWidget#midiPanel {{ border: 2px solid {midi_color}; }}"
        )
        self._camera_panel.setStyleSheet(
            f"QWidget#cameraPanel {{ border: 2px solid {cam_color}; }}"
        )
        self._update_status_line()

    def _update_status_line(self):
        locked = self._controller is not None and self._controller.mode == Mode.LOCKED
        mode = "Locked" if locked else "Independent"
        active = "MIDI" if self._active_panel == "midi" else "Camera"
        self._status_line.setText(
            f"{mode} Mode  |  Active: {active} (Tab to switch)  |  "
            f"Arrows: navigate  |  L: toggle mode  |  "
            f"M: mark MIDI  |  C: mark camera  |  A: add anchor  |  "
            f"R: re-sample intensity  |  O: jump to overlap"
        )

    def _flash_label(self, label: QLabel):
        """Brief visual flash to confirm marker was set.

        Cancels any pending un-flash timer for this label before starting a new
        flash. The old implementation captured ``label.styleSheet()`` at flash
        time; if called while already flashing, the captured "original" was the
        flash style itself and the timer would "restore" to it, leaving the
        label stuck dark after rapid repeated C/M presses. The marker labels'
        normal state is an empty stylesheet (``_update_marker_ui`` only touches
        text, never style), so we restore unconditionally to ``""``.

        Color-only: no padding / font-weight changes. The labels now sit under
        panels that hold ``stretch=1`` content; any sizeHint change here would
        steal pixels from the panel above and make it repaint twice per flash.
        """
        existing = self._flash_timers.get(label)
        if existing is not None:
            existing.stop()
        label.setStyleSheet("background-color: #446; color: white;")
        timer = QTimer(self)
        timer.setSingleShot(True)

        def _unflash() -> None:
            label.setStyleSheet("")
            self._flash_timers.pop(label, None)

        timer.timeout.connect(_unflash)
        timer.start(400)
        self._flash_timers[label] = timer

    # --- Intensity probe ---

    def _on_back_requested(self) -> None:
        """Exit the pair. Drop the probe dot so returning to any pair starts fresh."""
        if self._service is not None:
            self._service.clear_active_anchor()
        # clear_dot emits dot_cleared → _on_camera_dot_cleared clears the plot
        # and nulls _last_sample_request, so any in-flight sample's late result
        # gets discarded when it arrives.
        self._camera_panel.clear_dot()
        self.back_requested.emit()

    def _on_camera_dot_dropped(self, src_x: int, src_y: int, center_frame: int) -> None:
        """The camera panel just received a right-click. Kick off a sample walk."""
        self._last_sample_request = (center_frame, src_x, src_y)
        self._intensity_plot.show_status(f"Sampling ±{INTENSITY_HALF_WINDOW} frames…")
        self._intensity_plot.set_playhead_frame(self._camera_panel.current_frame)
        QMetaObject.invokeMethod(
            self._intensity_worker,
            "request_window",
            Qt.QueuedConnection,
            Q_ARG(int, center_frame),
            Q_ARG(int, src_x),
            Q_ARG(int, src_y),
            Q_ARG(int, INTENSITY_HALF_WINDOW),
        )

    def _on_camera_dot_cleared(self) -> None:
        """Camera clip was swapped (or dot explicitly cleared). Reset the plot."""
        self._last_sample_request = None
        self._intensity_plot.clear()

    def _on_intensity_ready(
        self,
        center_frame: int,
        src_x: int,
        src_y: int,
        first_frame: int,
        last_frame: int,
        values: object,
    ) -> None:
        # Exact-tuple match: discard any result whose (center_frame, src_x,
        # src_y) is not the latest dropped dot. Covers two races:
        #   1) Clip switch mid-sample — _on_camera_dot_cleared nulled the
        #      tuple, so the late result doesn't match anything.
        #   2) New dot on the same clip mid-sample — the tuple has been
        #      updated to the new dot, and the stale older sample won't match.
        # Worker slots are serialized, so in-flight request_window cannot be
        # cancelled mid-loop; the guard has to live here on the UI side.
        if self._last_sample_request != (center_frame, src_x, src_y):
            return
        # values arrives as a Python list by way of the `object` signal type.
        self._intensity_plot.set_data(first_frame, last_frame, list(values), center_frame)
        self._intensity_plot.set_playhead_frame(self._camera_panel.current_frame)

    def _on_intensity_failed(self, message: str) -> None:
        if self._last_sample_request is None:
            return
        self._intensity_plot.show_status(f"Sampling failed: {message}")

    def _on_intensity_plot_frame_seek_requested(self, frame: int) -> None:
        """User left-clicked the plot — seek the camera playhead there."""
        self._camera_panel.show_normal()
        self._camera_panel.set_frame(int(frame))

    def cleanup(self):
        self._camera_panel.cleanup()
        # Close the intensity capture on the worker thread, then stop the thread.
        QMetaObject.invokeMethod(
            self._intensity_worker, "close_video", Qt.QueuedConnection
        )
        self._intensity_thread.quit()
        self._intensity_thread.wait(2000)
