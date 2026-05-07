"""Anchor table widget — displays and manages alignment anchors for a camera clip."""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QBrush
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
    anchor_label_changed = pyqtSignal(int)  # anchor index
    midi_time_jump_requested = pyqtSignal(float)  # seconds into MIDI
    camera_frame_jump_requested = pyqtSignal(int)  # camera frame
    probe_jump_requested = pyqtSignal(int, int)  # (src_x, src_y)

    PROBE_COL = 4
    LABEL_COL = 6
    ACTIVE_COL = 7
    NUM_COLS = 8

    def __init__(self, parent=None):
        super().__init__(parent)
        self._camera_info: CameraFileInfo | None = None
        self._midi_lookup: dict[str, MidiFileInfo] = {}
        self._global_shift: float = 0.0
        self._state: AlignmentState | None = None
        self._service: AlignmentService | None = None
        self._camera_index: int = 0
        self._current_midi_filename: str | None = None
        # Guard against itemChanged firing while _refresh populates cells.
        self._populating: bool = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(2, 2, 2, 2)

        self._header_layout = QHBoxLayout()
        self._header_layout.addWidget(QLabel("Alignment Anchors"))
        self._header_layout.addStretch()

        self._delete_btn = QPushButton("Delete Selected")
        self._delete_btn.clicked.connect(self._on_delete)
        self._delete_btn.setEnabled(False)
        self._header_layout.addWidget(self._delete_btn)
        layout.addLayout(self._header_layout)

        self._table = QTableWidget(0, self.NUM_COLS)
        self._table.setHorizontalHeaderLabels([
            "#", "MIDI File", "MIDI Time (s)", "Camera Frame",
            "Probe (x,y)", "Derived Shift (s)", "Label", "Active",
        ])
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self._table.horizontalHeader().setSectionResizeMode(self.ACTIVE_COL, QHeaderView.ResizeToContents)
        self._table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self._table.setSelectionMode(QAbstractItemView.SingleSelection)
        # Editing is restricted to the Label column via per-item flags in
        # _refresh; keep the table-wide triggers enabled so double-click /
        # edit-key open the editor on that column only.
        self._table.setEditTriggers(
            QAbstractItemView.DoubleClicked | QAbstractItemView.EditKeyPressed
        )
        self._table.cellClicked.connect(self._on_cell_clicked)
        self._table.cellDoubleClicked.connect(self._on_cell_double_clicked)
        self._table.itemChanged.connect(self._on_item_changed)
        self._table.itemSelectionChanged.connect(
            lambda: self._delete_btn.setEnabled(bool(self._table.selectedItems()))
        )
        layout.addWidget(self._table)

    def add_header_action(self, widget: QWidget) -> None:
        """Insert a widget into the header row between the label and the stretch.

        Resulting order: [label, <inserted widgets...>, stretch, Delete Selected].
        """
        insert_index = self._header_layout.count() - 2  # before the stretch
        self._header_layout.insertWidget(insert_index, widget)

    def set_data(
        self,
        camera_info: CameraFileInfo,
        midi_lookup: dict[str, MidiFileInfo],
        global_shift: float,
        current_midi_filename: str | None = None,
    ):
        self._camera_info = camera_info
        self._midi_lookup = midi_lookup
        self._global_shift = global_shift
        self._current_midi_filename = current_midi_filename
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
        # Suppress itemChanged while we repopulate; otherwise every setItem
        # below would round-trip through _on_item_changed and call the service.
        self._populating = True
        try:
            self._table.setRowCount(0)
            if self._camera_info is None:
                return

            for i, anchor in enumerate(self._camera_info.alignment_anchors):
                self._table.insertRow(i)
                matches = (
                    self._current_midi_filename is None
                    or anchor.midi_filename == self._current_midi_filename
                )

                # #
                self._table.setItem(i, 0, self._read_only_item(str(i + 1)))

                # MIDI File
                self._table.setItem(i, 1, self._read_only_item(anchor.midi_filename))

                # MIDI Time (s)
                self._table.setItem(
                    i, 2, self._read_only_item(f"{anchor.midi_timestamp_seconds:.3f}")
                )

                # Camera Frame
                self._table.setItem(i, 3, self._read_only_item(str(anchor.camera_frame)))

                # Probe (x,y) — read-only; "—" when unset.
                if anchor.probe_x is not None and anchor.probe_y is not None:
                    probe_text = f"({anchor.probe_x}, {anchor.probe_y})"
                else:
                    probe_text = "—"
                probe_item = self._read_only_item(probe_text)
                if matches and anchor.probe_x is not None and anchor.probe_y is not None:
                    probe_item.setToolTip("Double-click to drop probe dot at this pixel")
                self._table.setItem(i, self.PROBE_COL, probe_item)

                # Derived Shift (s)
                midi = self._midi_lookup.get(anchor.midi_filename)
                if midi:
                    shift = compute_anchor_shift(anchor, self._camera_info, midi, self._global_shift)
                    self._table.setItem(i, 5, self._read_only_item(f"{shift:.4f}"))
                else:
                    self._table.setItem(i, 5, self._read_only_item("N/A"))

                # Label — editable for rows whose MIDI matches the current pair.
                label_item = QTableWidgetItem(anchor.label)
                if matches:
                    label_item.setFlags(label_item.flags() | Qt.ItemIsEditable)
                    label_item.setToolTip("Double-click to edit label")
                else:
                    label_item.setFlags(label_item.flags() & ~Qt.ItemIsEditable)
                self._table.setItem(i, self.LABEL_COL, label_item)

                # Active — only render * when this row's MIDI matches the displayed one.
                is_active = matches and (i == self._camera_info.active_anchor_index)
                active_item = QTableWidgetItem("*" if is_active else "")
                active_item.setTextAlignment(Qt.AlignCenter)
                active_item.setFlags(active_item.flags() & ~Qt.ItemIsEditable)
                if is_active:
                    active_item.setBackground(Qt.darkGreen)
                    active_item.setForeground(Qt.white)
                self._table.setItem(i, self.ACTIVE_COL, active_item)

                if not matches:
                    gray = QBrush(Qt.gray)
                    for col in range(self.NUM_COLS):
                        item = self._table.item(i, col)
                        if item is None:
                            continue
                        item.setFlags(
                            item.flags() & ~Qt.ItemIsEnabled & ~Qt.ItemIsSelectable
                        )
                        item.setForeground(gray)
        finally:
            self._populating = False

    @staticmethod
    def _read_only_item(text: str) -> QTableWidgetItem:
        item = QTableWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _on_item_changed(self, item: QTableWidgetItem):
        if self._populating:
            return
        if item.column() != self.LABEL_COL:
            return
        if self._camera_info is None or self._service is None:
            return
        row = item.row()
        if not (0 <= row < len(self._camera_info.alignment_anchors)):
            return
        anchor = self._camera_info.alignment_anchors[row]
        # Grayed-out rows are disabled, but block edits defensively anyway.
        if (
            self._current_midi_filename is not None
            and anchor.midi_filename != self._current_midi_filename
        ):
            return
        new_label = item.text()
        if new_label == anchor.label:
            return
        try:
            self._service.set_anchor_label(self._camera_index, row, new_label)
        except AlignmentToolError:
            # Revert the cell to the model value on failure.
            self._populating = True
            try:
                item.setText(anchor.label)
            finally:
                self._populating = False
            return
        self.anchor_label_changed.emit(row)

    def _on_cell_clicked(self, row: int, col: int):
        if self._camera_info is None or self._service is None:
            return
        if col == self.ACTIVE_COL:  # Active column — toggle
            if not (0 <= row < len(self._camera_info.alignment_anchors)):
                return
            anchor = self._camera_info.alignment_anchors[row]
            if (
                self._current_midi_filename is not None
                and anchor.midi_filename != self._current_midi_filename
            ):
                return
            if self._camera_info.active_anchor_index == row:
                self._service.set_active_anchor(self._camera_index, None)
                self.anchor_deactivated.emit()
            else:
                self._service.set_active_anchor(self._camera_index, row)
                self.anchor_activated.emit(row)
            self._refresh()

    def _on_cell_double_clicked(self, row: int, col: int):
        if self._camera_info is None:
            return
        if not (0 <= row < len(self._camera_info.alignment_anchors)):
            return
        anchor = self._camera_info.alignment_anchors[row]
        if (
            self._current_midi_filename is not None
            and anchor.midi_filename != self._current_midi_filename
        ):
            return
        if col == 2:  # MIDI Time (s)
            self.midi_time_jump_requested.emit(anchor.midi_timestamp_seconds)
        elif col == 3:  # Camera Frame
            self.camera_frame_jump_requested.emit(anchor.camera_frame)
        elif col == self.PROBE_COL:
            if anchor.probe_x is not None and anchor.probe_y is not None:
                self.probe_jump_requested.emit(anchor.probe_x, anchor.probe_y)

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
