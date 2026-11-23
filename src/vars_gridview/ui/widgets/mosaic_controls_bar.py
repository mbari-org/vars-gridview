"""Filter and view controls shown above the mosaic.

Two rows:

* **Filter** -- a label dropdown (every label in the loaded results, with
  counts; "All labels" shows everything) and a confidence range slider. Both
  only hide tiles: nothing is re-queried, and clearing them brings every tile
  back. A line underneath says how many tiles the confidence range is hiding,
  with a per-label breakdown in its tooltip.
* **View** -- display-only adjustments: colour correction for underwater
  images (with optional local contrast), fix colour fringes, sharpen,
  brightness and contrast. These change how tiles and the image view are
  drawn, never the stored images, boxes or embeddings.

Slider movement is coalesced (debounced) so dragging stays smooth on large
pages.
"""

from __future__ import annotations

from PyQt6 import QtCore, QtWidgets

from vars_gridview.lib.vision.display_adjust import DisplayAdjustment
from vars_gridview.ui.widgets.flow_layout import FlowLayout
from vars_gridview.ui.widgets.range_slider import RangeSlider

ALL_LABELS = "All labels"
FILTER_DEBOUNCE_MS = 120
VIEW_DEBOUNCE_MS = 120
# Local contrast (CLAHE clip limit) in steps of 0.5; 0 is off.
LOCAL_CONTRAST_MAX_STEPS = 6
BRIGHTNESS_RANGE = (-100, 100)
CONTRAST_RANGE = (25, 300)  # percent; 100 is neutral


def _elide_without_widening(label: QtWidgets.QLabel) -> None:
    """Let a status label shrink instead of widening its panel: a growing
    label in the grid's panel used to widen it, change the column count, and
    make the grid jump."""
    label.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred
    )
    label.setMinimumWidth(0)


def _group(*widgets: QtWidgets.QWidget) -> QtWidgets.QWidget:
    """Keep a caption and its control together when the bar wraps."""
    box = QtWidgets.QWidget()
    row = QtWidgets.QHBoxLayout(box)
    row.setContentsMargins(0, 0, 0, 0)
    row.setSpacing(4)
    for widget in widgets:
        row.addWidget(widget)
    return box


def _flow_row(*widgets: QtWidgets.QWidget) -> QtWidgets.QWidget:
    """A row that wraps onto more lines when the pane is narrow, instead of
    forcing the grid's pane to be at least as wide as all of its controls."""
    row = QtWidgets.QWidget()
    flow = FlowLayout(row, spacing=10)
    flow.setContentsMargins(0, 0, 0, 0)
    for widget in widgets:
        flow.addWidget(widget)
    row.setSizePolicy(
        QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred
    )
    return row


class MosaicControlsBar(QtWidgets.QWidget):
    """Label/confidence filter and view adjustments for the mosaic."""

    # label (None = all), min confidence, max confidence
    filtersChanged = QtCore.pyqtSignal(object, float, float)
    displayChanged = QtCore.pyqtSignal(object)  # DisplayAdjustment

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._updating_labels = False

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 2)
        layout.setSpacing(2)
        # Never widen the grid's pane (see _flow_row).
        self.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred
        )

        # -- filter row ------------------------------------------------------
        self.label_combo = QtWidgets.QComboBox()
        self.label_combo.setEditable(True)
        self.label_combo.setInsertPolicy(QtWidgets.QComboBox.InsertPolicy.NoInsert)
        self.label_combo.setSizeAdjustPolicy(
            QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.label_combo.setMinimumContentsLength(18)
        self.label_combo.setToolTip(
            "Show only tiles with this label. Type to search; "
            "'All labels' shows everything."
        )
        completer = self.label_combo.completer()
        if completer is not None:
            completer.setFilterMode(QtCore.Qt.MatchFlag.MatchContains)
            completer.setCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)
            completer.setCompletionMode(
                QtWidgets.QCompleter.CompletionMode.PopupCompletion
            )
        self.label_combo.addItem(ALL_LABELS, None)
        self.label_combo.activated.connect(self._on_label_activated)
        line_edit = self.label_combo.lineEdit()
        if line_edit is not None:
            line_edit.editingFinished.connect(self._on_label_text_entered)

        self.confidence_slider = RangeSlider(0, 100)  # 0-100 -> 0.00-1.00
        self.confidence_slider.setToolTip(
            "Show only tiles whose ML confidence is in this range (drag either "
            "handle; arrow keys nudge). While narrowed, boxes with no confidence "
            "-- usually drawn by a person -- are hidden too."
        )
        self.confidence_slider.valuesChanged.connect(self._on_confidence_moved)
        self.confidence_slider.setFixedWidth(200)
        self.confidence_value = QtWidgets.QLabel(self._confidence_text(0, 100))
        self.confidence_value.setMinimumWidth(
            self.confidence_value.fontMetrics().horizontalAdvance("0.00 - 1.00") + 6
        )

        self.clear_filters_button = QtWidgets.QPushButton("Clear filters")
        self.clear_filters_button.setToolTip("Show all labels and the full 0-1 range.")
        self.clear_filters_button.clicked.connect(self.clear_filters)
        self.clear_filters_button.setEnabled(False)
        layout.addWidget(
            _flow_row(
                _group(QtWidgets.QLabel("Label:"), self.label_combo),
                _group(
                    QtWidgets.QLabel("Confidence:"),
                    self.confidence_slider,
                    self.confidence_value,
                ),
                self.clear_filters_button,
            )
        )

        self.filter_status = QtWidgets.QLabel("")
        _elide_without_widening(self.filter_status)
        layout.addWidget(self.filter_status)

        # -- view row --------------------------------------------------------
        self.colour_box = QtWidgets.QCheckBox("Color-correct")
        self.colour_box.setToolTip(
            "Remove the water's colour cast and restore contrast and colour in "
            "what you see. Display only: labels, boxes and embeddings use the "
            "original pixels. Tiles are corrected from their own crop until the "
            "full frame has been shown (click a tile); then every tile from "
            "that frame uses the frame's correction."
        )
        self.colour_box.toggled.connect(self._on_colour_toggled)

        self.local_contrast_label = QtWidgets.QLabel("Local contrast")
        self.local_contrast_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.local_contrast_slider.setRange(0, LOCAL_CONTRAST_MAX_STEPS)
        self.local_contrast_slider.setFixedWidth(90)
        self.local_contrast_slider.setToolTip(
            "CLAHE on the colour-corrected display: brings out faint, "
            "low-contrast detail, but also grain. Off at the far left."
        )
        self.local_contrast_slider.valueChanged.connect(self._schedule_display)
        self._set_local_contrast_enabled(False)

        self.fringes_box = QtWidgets.QCheckBox("Fix color fringes")
        self.fringes_box.setToolTip(
            "Shift red and blue back onto green and soften rainbow edges on "
            "bright animals. ~10-25 ms per tile, so tiles redraw a little slower."
        )
        self.fringes_box.toggled.connect(self._schedule_display)

        self.sharpen_box = QtWidgets.QCheckBox("Sharpen")
        self.sharpen_box.setToolTip(
            "Adaptive sharpening of the enlarged tiles; leaves flat sediment and "
            "dark water alone so noise isn't amplified."
        )
        self.sharpen_box.toggled.connect(self._schedule_display)

        self.brightness_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.brightness_slider.setRange(*BRIGHTNESS_RANGE)
        self.brightness_slider.setValue(0)
        self.brightness_slider.setFixedWidth(110)
        self.brightness_slider.valueChanged.connect(self._schedule_display)
        self.contrast_slider = QtWidgets.QSlider(QtCore.Qt.Orientation.Horizontal)
        self.contrast_slider.setRange(*CONTRAST_RANGE)
        self.contrast_slider.setValue(100)
        self.contrast_slider.setFixedWidth(110)
        self.contrast_slider.valueChanged.connect(self._schedule_display)

        self.reset_view_button = QtWidgets.QPushButton("Reset view")
        self.reset_view_button.setToolTip("Turn every view adjustment off.")
        self.reset_view_button.clicked.connect(self.reset_view)
        layout.addWidget(
            _flow_row(
                self.colour_box,
                _group(self.local_contrast_label, self.local_contrast_slider),
                self.fringes_box,
                self.sharpen_box,
                _group(QtWidgets.QLabel("Brightness"), self.brightness_slider),
                _group(QtWidgets.QLabel("Contrast"), self.contrast_slider),
                self.reset_view_button,
            )
        )

        self._filter_timer = QtCore.QTimer(self)
        self._filter_timer.setSingleShot(True)
        self._filter_timer.setInterval(FILTER_DEBOUNCE_MS)
        self._filter_timer.timeout.connect(self._emit_filters)
        self._display_timer = QtCore.QTimer(self)
        self._display_timer.setSingleShot(True)
        self._display_timer.setInterval(VIEW_DEBOUNCE_MS)
        self._display_timer.timeout.connect(self._emit_display)

        self._label: str | None = None

    # -- filter ---------------------------------------------------------------

    @staticmethod
    def _confidence_text(low: int, high: int) -> str:
        return f"{low / 100:.2f} - {high / 100:.2f}"

    @property
    def label(self) -> str | None:
        return self._label

    @property
    def confidence_range(self) -> tuple[float, float]:
        low, high = self.confidence_slider.values()
        return low / 100.0, high / 100.0

    def set_labels(self, counts: dict[str, int]) -> None:
        """Offer *counts* (label -> tiles) in the dropdown, most common first.
        Keeps the current choice when it's still present."""
        self._updating_labels = True
        try:
            self.label_combo.clear()
            total = sum(counts.values())
            self.label_combo.addItem(f"{ALL_LABELS} ({total})", None)
            for label, count in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])):
                self.label_combo.addItem(f"{label} ({count})", label)
            index = 0
            if self._label is not None:
                found = self.label_combo.findData(self._label)
                if found >= 0:
                    index = found
                else:
                    self.label_combo.addItem(f"{self._label} (0)", self._label)
                    index = self.label_combo.count() - 1
            self.label_combo.setCurrentIndex(index)
        finally:
            self._updating_labels = False

    def _on_label_activated(self, index: int) -> None:
        if self._updating_labels:
            return
        self._set_label(self.label_combo.itemData(index))

    def _on_label_text_entered(self) -> None:
        """Typed text: match a label exactly (case-insensitive), with or
        without its "(count)"; anything else snaps back to the current choice."""
        if self._updating_labels:
            return
        text = self.label_combo.currentText().strip()
        if not text or text.lower().startswith(ALL_LABELS.lower()):
            self._set_label(None)
            return
        for i in range(self.label_combo.count()):
            data = self.label_combo.itemData(i)
            if data is None:
                continue
            if text.lower() in (
                str(data).lower(),
                self.label_combo.itemText(i).lower(),
            ):
                self.label_combo.setCurrentIndex(i)
                self._set_label(data)
                return
        current = self.label_combo.findData(self._label)
        self.label_combo.setCurrentIndex(max(current, 0))

    def _set_label(self, label: str | None) -> None:
        if label == self._label:
            return
        self._label = label
        self._filter_timer.start()

    def _on_confidence_moved(self, low: int, high: int) -> None:
        self.confidence_value.setText(self._confidence_text(low, high))
        self._filter_timer.start()

    def _emit_filters(self) -> None:
        low, high = self.confidence_range
        self.clear_filters_button.setEnabled(
            self._label is not None or low > 0.0 or high < 1.0
        )
        self.filtersChanged.emit(self._label, low, high)

    def clear_filters(self) -> None:
        self._label = None
        self._updating_labels = True
        try:
            self.label_combo.setCurrentIndex(0)
        finally:
            self._updating_labels = False
        self.confidence_slider.setValues(0, 100)
        self._filter_timer.stop()
        self._emit_filters()

    def set_filter_status(
        self, shown: int, total: int, hidden_by_confidence: dict[str, int]
    ) -> None:
        """'Showing N of M', plus what the confidence range hides."""
        parts = [f"Showing {shown:,} of {total:,} tiles"]
        tooltip = ""
        hidden = sum(hidden_by_confidence.values())
        if hidden:
            parts.append(f"{hidden:,} hidden by the confidence range")
            lines = [
                f"{count:,}  {label}"
                for label, count in sorted(
                    hidden_by_confidence.items(), key=lambda kv: (-kv[1], kv[0])
                )
            ]
            shown_lines = lines[:25]
            if len(lines) > len(shown_lines):
                shown_lines.append(
                    f"... and {len(lines) - len(shown_lines)} more labels"
                )
            tooltip = "Hidden by the confidence range, per label:\n" + "\n".join(
                shown_lines
            )
        self.filter_status.setText(" · ".join(parts))
        self.filter_status.setToolTip(tooltip)

    # -- view -----------------------------------------------------------------

    def _set_local_contrast_enabled(self, enabled: bool) -> None:
        self.local_contrast_label.setEnabled(enabled)
        self.local_contrast_slider.setEnabled(enabled)

    def _on_colour_toggled(self, checked: bool) -> None:
        self._set_local_contrast_enabled(checked)
        self._schedule_display()

    def _schedule_display(self, *_args) -> None:
        self._display_timer.start()

    @property
    def display_adjustment(self) -> DisplayAdjustment:
        return DisplayAdjustment(
            colour_correct=self.colour_box.isChecked(),
            local_contrast=0.5 * self.local_contrast_slider.value(),
            fix_fringes=self.fringes_box.isChecked(),
            brightness=int(self.brightness_slider.value()),
            contrast=self.contrast_slider.value() / 100.0,
            sharpen=self.sharpen_box.isChecked(),
        )

    def _emit_display(self) -> None:
        self.displayChanged.emit(self.display_adjustment)

    def reset_view(self) -> None:
        for widget, value in (
            (self.colour_box, False),
            (self.fringes_box, False),
            (self.sharpen_box, False),
        ):
            widget.setChecked(value)
        self.local_contrast_slider.setValue(0)
        self.brightness_slider.setValue(0)
        self.contrast_slider.setValue(100)
        self._display_timer.stop()
        self._emit_display()


__all__ = ["ALL_LABELS", "MosaicControlsBar"]
