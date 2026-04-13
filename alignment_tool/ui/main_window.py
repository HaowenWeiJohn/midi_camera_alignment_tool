import logging

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QMainWindow, QStackedWidget, QAction, QFileDialog,
    QMessageBox, QLabel, QApplication,
)

from alignment_tool.core import persistence
from alignment_tool.core.errors import (
    AlignmentToolError, InvariantError, MediaLoadError, PersistenceError,
)
from alignment_tool.core.models import AlignmentState
from alignment_tool.io.participant_loader import ParticipantLoader
from alignment_tool.services.alignment_service import AlignmentService
from alignment_tool.services.level2_controller import Level2Controller
from alignment_tool.ui.level1_timeline import Level1Widget
from alignment_tool.ui.level2_view import Level2View

logger = logging.getLogger(__name__)


class MainWindow(QMainWindow):

    state_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MIDI-Camera Alignment Tool")
        self.resize(1400, 800)

        self._state: AlignmentState | None = None
        self._service: AlignmentService | None = None
        self._controller: Level2Controller | None = None

        # Central stacked widget (Level 1 / Level 2)
        self._stack = QStackedWidget()
        self.setCentralWidget(self._stack)

        # Placeholder for when no participant is loaded
        self._placeholder = QLabel("No participant loaded.\n\nUse File > Open Participant to load data,\nor File > Load Alignment to resume a saved session.")
        self._placeholder.setAlignment(Qt.AlignCenter)
        self._stack.addWidget(self._placeholder)

        # Level 1: Timeline overview
        self._level1 = Level1Widget()
        self._level1.pair_selected.connect(self._on_pair_selected)
        self._stack.addWidget(self._level1)

        # Level 2: Alignment detail view
        self._level2 = Level2View()
        self._level2.back_requested.connect(self._on_back_to_level1)
        self._level2.state_modified.connect(self._on_state_modified)
        self._stack.addWidget(self._level2)

        self._setup_menu()
        self._setup_statusbar()

    def _setup_menu(self):
        menu_bar = self.menuBar()
        file_menu = menu_bar.addMenu("&File")

        open_action = QAction("&Open Participant...", self)
        open_action.setShortcut("Ctrl+O")
        open_action.triggered.connect(self._on_open_participant)
        file_menu.addAction(open_action)

        file_menu.addSeparator()

        save_action = QAction("&Save Alignment...", self)
        save_action.setShortcut("Ctrl+S")
        save_action.triggered.connect(self._on_save)
        save_action.setEnabled(False)
        self._save_action = save_action
        file_menu.addAction(save_action)

        load_action = QAction("&Load Alignment...", self)
        load_action.setShortcut("Ctrl+L")
        load_action.triggered.connect(self._on_load)
        file_menu.addAction(load_action)

        file_menu.addSeparator()

        exit_action = QAction("E&xit", self)
        exit_action.setShortcut("Ctrl+Q")
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

    def _setup_statusbar(self):
        self._status_label = QLabel("No participant loaded")
        self.statusBar().addWidget(self._status_label)

    @property
    def state(self) -> AlignmentState | None:
        return self._state

    def _set_state(self, state: AlignmentState, warnings: list[str] | None = None):
        self._state = state
        self._service = AlignmentService(state)
        self._controller = Level2Controller(state, self._service)
        self._save_action.setEnabled(True)
        self.setWindowTitle(f"MIDI-Camera Alignment Tool \u2014 Participant {state.participant_id}")
        self._update_status()
        self._level1.set_state(state, self._service)
        self._level2.attach(state, self._service, self._controller)
        self._stack.setCurrentWidget(self._level1)
        if warnings:
            self._show_warnings(warnings)
        self.state_changed.emit()

    def _on_pair_selected(self, midi_index: int, camera_index: int):
        """Handle drill-down from Level 1 to Level 2."""
        if self._state is None:
            return
        self._level2.load_pair(self._state, midi_index, camera_index)
        self._stack.setCurrentWidget(self._level2)
        self._level2.setFocus()
        mf = self._state.midi_files[midi_index]
        cf = self._state.camera_files[camera_index]
        self._status_label.setText(f"Level 2: {mf.filename} + {cf.filename}")

    def _on_back_to_level1(self):
        """Return from Level 2 to Level 1."""
        self._level1.refresh()
        self._stack.setCurrentWidget(self._level1)
        self._update_status()

    def _on_state_modified(self):
        """Handle state changes from Level 2 (anchors, global shift)."""
        self._update_status()

    def _update_status(self):
        if self._state is None:
            return
        self._status_label.setText(
            f"Participant {self._state.participant_id} | "
            f"{len(self._state.midi_files)} MIDI files | "
            f"{len(self._state.camera_files)} camera clips | "
            f"Global shift: {self._state.global_shift_seconds:.3f}s | "
            f"Anchors: {self._state.total_anchor_count()}"
        )

    def _on_open_participant(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Participant Folder")
        if not folder:
            return
        QApplication.setOverrideCursor(Qt.WaitCursor)
        try:
            result = ParticipantLoader.load(folder)
        except AlignmentToolError as e:
            QApplication.restoreOverrideCursor()
            self._show_exception(e)
            return
        except Exception as e:
            QApplication.restoreOverrideCursor()
            logger.exception("Unexpected error loading participant")
            QMessageBox.critical(self, "Error Loading Participant", str(e))
            return
        QApplication.restoreOverrideCursor()

        if not result.state.midi_files and not result.state.camera_files:
            QMessageBox.warning(
                self, "No Files Found",
                f"No .mid or .MP4 files found in:\n{folder}\n\n"
                "Expected subdirectories: disklavier/ and overhead camera/"
            )
            return
        self._set_state(result.state, warnings=result.warnings)

    def _on_save(self):
        if self._state is None:
            return
        filepath, _ = QFileDialog.getSaveFileName(
            self, "Save Alignment", "", "JSON Files (*.json)"
        )
        if not filepath:
            return
        try:
            persistence.save_alignment(self._state, filepath)
            self._status_label.setText(f"Saved: {filepath}")
        except AlignmentToolError as e:
            self._show_exception(e)
        except Exception as e:
            logger.exception("Unexpected error saving alignment")
            QMessageBox.critical(self, "Error Saving", str(e))

    def _on_load(self):
        filepath, _ = QFileDialog.getOpenFileName(
            self, "Load Alignment", "", "JSON Files (*.json)"
        )
        if not filepath:
            return
        try:
            state = persistence.load_alignment(filepath)
            self._set_state(state)
        except AlignmentToolError as e:
            self._show_exception(e)
        except Exception as e:
            logger.exception("Unexpected error loading alignment")
            QMessageBox.critical(self, "Error Loading", str(e))

    def _show_exception(self, exc: AlignmentToolError) -> None:
        if isinstance(exc, (MediaLoadError, PersistenceError)):
            QMessageBox.critical(self, type(exc).__name__, str(exc))
        elif isinstance(exc, InvariantError):
            QMessageBox.warning(self, type(exc).__name__, str(exc))
        else:
            QMessageBox.critical(self, "Error", str(exc))

    def _show_warnings(self, warnings: list[str]) -> None:
        if not warnings:
            return
        msg = "\n".join(f"\u2022 {w}" for w in warnings)
        QMessageBox.warning(
            self, "Some files could not be loaded",
            f"{len(warnings)} file(s) were skipped:\n\n{msg}",
        )
