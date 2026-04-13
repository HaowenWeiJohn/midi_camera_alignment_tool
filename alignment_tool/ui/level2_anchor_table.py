"""Anchor table widget — displays and manages alignment anchors for a camera clip."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QHeaderView, QAbstractItemView, QLabel,
)

from alignment_tool.core.models import AlignmentState, CameraFileInfo, MidiFileInfo, Anchor
from alignment_tool.core.engine import compute_anchor_shift
from alignment_tool.core.errors import AlignmentToolError
from alignment_tool.services.alignment_service import AlignmentService


class AnchorTableWidget(QWidget):
    """Table showing anchors for the current camera clip."""

    anchor_activated = pyqtSignal(int)  # anchor index
    anchor_deactivated = pyqtSignal()
    anchor_deleted = pyqtSignal(int)  # anchor index

    def __init__(self, parent=None):
        super().__init__(parent)
        self._camera_info: CameraFileInfo | None = None
        self._midi_lookup: dict[str, MidiFileInfo] = {}
        self._global_shift: float = 0.0
        self._state: AlignmentState | None = None
        self._service: AlignmentService | None = None
        self._camera_index: int = 0

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        header_layout = QHBoxLayout()
        header_layout.addWidget(QLabel("Alignment Anchors"))
        header_layout.addStretch()

        self._delete_btn = QPushButton("Delete Selected")
        self._delete_btn.clicked.connect(self._on_delete)
        self._delete_btn.setEnabled(False)
        header_layout.addWidget(self._delete_btn)
        layout.addLayout(header_layout)

        self._table = QTableWidget(0, 7)
        self._table.setHorizontalHeaderLabels([
            "#", "MIDI File", "MIDI Time (s)", "Camera Frame",
            "Derived Shift (s)", "Label", "Active",
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(6, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        self._table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.itemSelectionChanged.connect(
            lambda: self._delete_btn.setEnabled(bool(self._table.selectedItems()))
        )
        layout.addWidget(self._table)

    def set_data(self, camera_info: CameraFileInfo, midi_lookup: dict[str, MidiFileInfo], global_shift: float):
        self._camera_info = camera_info
        self._midi_lookup = midi_lookup
        self._global_shift = global_shift
        self._refresh()

    def set_context(
        self,
        state: AlignmentState | None,
        service: AlignmentService | None,
        camera_index: int,
    ) -> None:
        """Inject the service and camera_index so mutations go through AlignmentService."""
        self._state = state
        self._service = service
        self._camera_index = camera_index

    def refresh(self) -> None:
        """Public re-render hook used by Level2View after external mutations."""
        self._refresh()

    def _refresh(self):
        self._table.setRowCount(0)
        if self._camera_info is None:
            return

        for i, anchor in enumerate(self._camera_info.alignment_anchors):
            self._table.insertRow(i)

            # #
            self._table.setItem(i, 0, QTableWidgetItem(str(i + 1)))

            # MIDI File
            self._table.setItem(i, 1, QTableWidgetItem(anchor.midi_filename))

            # MIDI Time (s)
            self._table.setItem(i, 2, QTableWidgetItem(f"{anchor.midi_timestamp_seconds:.3f}"))

            # Camera Frame
            self._table.setItem(i, 3, QTableWidgetItem(str(anchor.camera_frame)))

            # Derived Shift (s)
            midi = self._midi_lookup.get(anchor.midi_filename)
            if midi:
                shift = compute_anchor_shift(anchor, self._camera_info, midi, self._global_shift)
                self._table.setItem(i, 4, QTableWidgetItem(f"{shift:.4f}"))
            else:
                self._table.setItem(i, 4, QTableWidgetItem("N/A"))

            # Label
            self._table.setItem(i, 5, QTableWidgetItem(anchor.label))

            # Active
            is_active = (i == self._camera_info.active_anchor_index)
            active_item = QTableWidgetItem("*" if is_active else "")
            active_item.setTextAlignment(Qt.AlignCenter)
            if is_active:
                active_item.setBackground(Qt.darkGreen)
                active_item.setForeground(Qt.white)
            self._table.setItem(i, 6, active_item)

    def _on_cell_clicked(self, row: int, col: int):
        if self._camera_info is None or self._service is None:
            return
        if col == 6:  # Active column — toggle
            if self._camera_info.active_anchor_index == row:
                self._service.set_active_anchor(self._camera_index, None)
                self.anchor_deactivated.emit()
            else:
                self._service.set_active_anchor(self._camera_index, row)
                self.anchor_activated.emit(row)
            self._refresh()

    def _on_delete(self):
        if self._camera_info is None or self._service is None:
            return
        rows = self._table.selectionModel().selectedRows()
        if not rows:
            return
        idx = rows[0].row()
        if idx >= len(self._camera_info.alignment_anchors):
            return
        try:
            self._service.delete_anchor(self._camera_index, idx)
        except AlignmentToolError:
            return
        self.anchor_deleted.emit(idx)
        self._refresh()
