import re
from collections.abc import Callable, Iterable
from typing import Any
from uuid import UUID

from PyQt6.QtCore import QAbstractListModel, QModelIndex, QObject, Qt, QTimer, pyqtSlot
from PyQt6.QtGui import QDragEnterEvent, QDropEvent
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QCompleter,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListView,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from vars_gridview.lib.m3.query import QueryConstraint

# BASE CLASSES


class BaseResult:
    """
    Base class for a filter result that can be added to a query. Provides a set of constraints to be applied to the query and a string representation.
    """

    @property
    def constraints(self) -> Iterable[QueryConstraint]:
        """
        Returns an iterable of QueryConstraint objects that represent the constraints to be applied to the query.

        Returns:
            Iterable[QueryConstraint]: An iterable of QueryConstraint objects.
        """
        raise NotImplementedError()

    def __str__(self) -> str:
        """
        Returns a string representation of the result that should encode the constraints in a human-readable form.

        Returns:
            str: A string representation of the result.
        """
        raise NotImplementedError()


class BaseFilter:
    """
    Base class for a filter that can be applied to a query. When called, it should return a Result object or None.
    """

    def __init__(self, parent: QWidget | None, name: str):
        self.parent = parent
        self.name = name

    def __call__(self) -> BaseResult | None:
        """
        When called, this method should display a dialog or interface to the user to gather input for the filter.

        Returns:
            Optional[Result]: A Result object representing the filter constraints, or None if the user canceled or did not provide valid input.
        """
        raise NotImplementedError()


# RESULT IMPLEMENTATIONS

# A list longer than this is shown as its first few values and a count.
SHOWN_VALUES = 8


def _summarise(values: list[Any]) -> str:
    shown = ", ".join(map(str, values[:SHOWN_VALUES]))
    if len(values) > SHOWN_VALUES:
        shown += f", … ({len(values):,} in all)"
    return shown


class EqualityConstraintResult(BaseResult):
    """
    A simple equality constraint result. Creates a single equality constraint for a given key and value.
    """

    def __init__(self, label: str, value: Any, key: str):
        self.label = label
        self.value = value
        self.key = key

    @property
    def constraints(self) -> Iterable[QueryConstraint]:
        yield QueryConstraint(
            column=self.key,
            equals=self.value,
        )

    def __str__(self) -> str:
        return f"{self.label}: {self.value}"


class InConstraintResult(BaseResult):
    """
    A constraint result that creates an IN constraint for a given key and a list of values.
    """

    def __init__(self, label: str, values: list[Any], key: str):
        self.label = label
        self.values = values
        self.key = key

    @property
    def constraints(self) -> Iterable[QueryConstraint]:
        yield QueryConstraint(
            column=self.key,
            in_=self.values,
        )

    def __str__(self) -> str:
        return f"{self.label}: {_summarise(self.values)}"


class UUIDInConstraintResult(InConstraintResult):
    """
    A constraint result that creates an IN constraint for a given key and a list of UUID values.
    """

    def __str__(self) -> str:
        if len(self.values) == 1:
            return f"{self.label}: {self.values[0]}"
        return f"{self.label}: ({len(self.values):,} items)"


class LikeConstraintResult(BaseResult):
    """
    A constraint result that creates a LIKE constraint for a given key and a pattern.
    """

    def __init__(self, label: str, column: str, pattern: str):
        self.label = label
        self.column = column
        self.pattern = pattern

    @property
    def constraints(self) -> Iterable[QueryConstraint]:
        yield QueryConstraint(
            column=self.column,
            like=self.pattern,
        )

    def __str__(self) -> str:
        return f"{self.label} like {self.pattern}"


class VerifierConstraintResult(LikeConstraintResult):
    """
    A constraint result that creates a LIKE constraint for the verifier field.
    """

    def __init__(self, verifier: str):
        super().__init__(
            "Verifier", "link_value", f'%"verifier":%{verifier}%'
        )  # hacky way to check for verifier in JSON
        self.verifier = verifier

    def __str__(self) -> str:
        return f"Verifier: {self.verifier}"


class GeneratorConstraintResult(LikeConstraintResult):
    """
    A constraint result that creates a LIKE constraint for the generator field.
    """

    def __init__(self, generator: str):
        super().__init__(
            "Generator", "link_value", f'%"generator":%{generator}%'
        )  # hacky way to check for generator in JSON
        self.generator = generator

    def __str__(self) -> str:
        return f"Generator: {self.generator}"


class VerifiedConstraintResult(BaseResult):
    """
    A constraint result that creates a constraint to check if the verifier field is present (i.e., verified).
    """

    @property
    def constraints(self) -> Iterable[QueryConstraint]:
        yield QueryConstraint(column="link_value", like='%"verifier":%')

    def __str__(self) -> str:
        return "Verified"


class NotVerifiedConstraintResult(BaseResult):
    """
    A constraint result that creates a constraint to check if the verifier field is NOT present (i.e., not verified).
    """

    @property
    def constraints(self) -> Iterable[QueryConstraint]:
        yield QueryConstraint(column="link_value", notlike='%"verifier":%')

    def __str__(self) -> str:
        return "Not Verified"


class ConceptInConstraintResult(InConstraintResult):
    """
    A constraint result that creates an IN constraint for a list of concepts.
    """

    def __str__(self) -> str:
        if len(self.values) == 1:
            return f"Concept: {self.values[0]}"
        return f"Concepts: {_summarise(self.values)}"


class ConceptDescInConstraintResult(InConstraintResult):
    """
    A constraint result that creates an IN constraint for a concept and its descendants.
    """

    def __init__(self, concept: str, descendants: list[str]):
        super().__init__("Concept (+ descendants)", [concept] + descendants, "concept")
        self._concept = concept
        self._descendants = descendants

    def __str__(self) -> str:
        # Special case: if there are no descendants, just show the concept
        if len(self._descendants) == 0:
            return f"Concept: {self._concept}"

        return "Concept (+ descendants): {} ({})".format(
            self._concept, ", ".join(self._descendants)
        )


class DepthRangeConstraintResult(BaseResult):
    """
    A constraint result that creates min/max constraints for depth range.
    """

    def __init__(self, min_depth: float | None, max_depth: float | None):
        self.min_depth = min_depth
        self.max_depth = max_depth

    @property
    def constraints(self) -> Iterable[QueryConstraint]:
        if self.min_depth is not None and self.max_depth is not None:
            # Both min and max specified - use minmax for between constraint
            yield QueryConstraint(
                column="depth_meters",
                minmax=[self.min_depth, self.max_depth],
            )
        elif self.min_depth is not None:
            # Only min specified - depth >= min
            yield QueryConstraint(
                column="depth_meters",
                min=self.min_depth,
            )
        elif self.max_depth is not None:
            # Only max specified - depth <= max
            yield QueryConstraint(
                column="depth_meters",
                max=self.max_depth,
            )

    def __str__(self) -> str:
        if self.min_depth is not None and self.max_depth is not None:
            return f"Depth: {self.min_depth}m - {self.max_depth}m"
        elif self.min_depth is not None:
            return f"Depth: >= {self.min_depth}m"
        elif self.max_depth is not None:
            return f"Depth: <= {self.max_depth}m"
        return "Depth: (no constraint)"


# FILTER IMPLEMENTATIONS


class FunctionalFilter(BaseFilter):
    """
    A filter that is defined by a callable function. When called, it invokes the function to get the Result.
    """

    def __init__(self, parent, name: str, func):
        super().__init__(parent, name)
        self.func = func

    def __call__(self) -> BaseResult | None:
        return self.func()


class SimpleTextFilter(BaseFilter):
    """
    A simple text input filter that creates an equality constraint.
    """

    def __init__(self, parent, name: str, key: str, prompt: str | None = None):
        super().__init__(parent, name)
        self.key = key
        self.prompt = prompt or name

    def __call__(self) -> EqualityConstraintResult | None:
        text, ok = QInputDialog.getText(
            self.parent, self.name, self.prompt, QLineEdit.EchoMode.Normal, ""
        )
        if ok:
            return EqualityConstraintResult(self.name, text, self.key)


class ItemSelectFilter(BaseFilter):
    """
    A filter that allows the user to select an item from a predefined list.
    """

    def __init__(
        self, parent, name: str, items_getter, key: str, editable: bool = False
    ):
        super().__init__(parent, name)
        self.items_getter = items_getter
        self.key = key
        self.editable = editable

    def __call__(self) -> EqualityConstraintResult | None:
        items = self.items_getter()
        value, ok = QInputDialog.getItem(
            self.parent, self.name, self.name, items, 0, self.editable
        )
        if ok:
            return EqualityConstraintResult(self.name, value, self.key)


class UUIDListFilter(BaseFilter):
    """
    A filter that allows the user to input multiple UUIDs at once.
    """

    def __init__(self, parent, name: str, key: str, title: str | None = None):
        super().__init__(parent, name)
        self.key = key
        self.title = title or name + "s"

    def __call__(self) -> UUIDInConstraintResult | None:
        uuids, ok = BulkUUIDInputDialog.get_uuids(self.title, self.parent)
        if ok:
            if not uuids:
                return None
            return UUIDInConstraintResult(self.name, uuids, self.key)


class BulkValueFilter(BaseFilter):
    """
    A filter that allows the user to input multiple values from a known set at once.
    """

    def __init__(
        self,
        parent,
        name: str,
        values_getter: Callable[[], list[str]],
        key: str,
        item_label: str,
        result_cls: type[InConstraintResult] = InConstraintResult,
    ):
        super().__init__(parent, name)
        self._values_getter = values_getter
        self.key = key
        self.item_label = item_label
        self.result_cls = result_cls

    def __call__(self) -> InConstraintResult | None:
        values, ok = BulkValidatedInputDialog.get_values(
            f"Select {self.name}",
            self.parent,
            values_getter=self._values_getter,
            item_label=self.item_label,
        )
        if ok and values:
            return self.result_cls(self.name, values, self.key)


class ConceptDescFilter(BaseFilter):
    """
    A filter that allows the user to select a concept and includes all its descendants.
    """

    def __init__(
        self,
        parent,
        name: str,
        concepts_getter: Callable[[], list[str]],
        descendants_getter: Callable[[str], list[str]],
    ):
        super().__init__(parent, name)
        self._values_getter = concepts_getter
        self._descendants_getter = descendants_getter

    def __call__(self) -> ConceptDescInConstraintResult | None:
        concept, ok = QInputDialog.getItem(
            self.parent,
            "Concept",
            "Concept",
            self._values_getter(),
            0,
            True,
        )
        if ok:
            # Look up descendants
            descendants = self._descendants_getter(concept)

            # Remove the concept itself if present
            if concept in descendants:
                descendants.remove(concept)

            return ConceptDescInConstraintResult(concept, descendants)


class GeneratorFilter(SimpleTextFilter):
    """
    A filter that allows the user to input a generator string to filter by.
    """

    def __call__(self) -> GeneratorConstraintResult | None:
        result = super().__call__()
        return GeneratorConstraintResult(result.value) if result else None


class VerifierFilter(SimpleTextFilter):
    """
    A filter that allows the user to input a verifier string to filter by.
    """

    def __call__(self) -> VerifierConstraintResult | None:
        result = super().__call__()
        return VerifierConstraintResult(result.value) if result else None


class DepthRangeFilter(BaseFilter):
    """
    A filter that allows the user to specify a depth range constraint.
    """

    def __call__(self) -> DepthRangeConstraintResult | None:
        # Create a custom dialog for depth range input
        dialog = QDialog(self.parent)
        dialog.setWindowTitle("Depth Range")
        layout = QFormLayout(dialog)

        # Min depth input
        min_depth_checkbox = QCheckBox("Set minimum depth")
        min_depth_spinbox = QDoubleSpinBox()
        min_depth_spinbox.setRange(0, 10000)
        min_depth_spinbox.setValue(0)
        min_depth_spinbox.setSuffix(" m")
        min_depth_spinbox.setDecimals(2)
        min_depth_spinbox.setEnabled(False)

        # Max depth input
        max_depth_checkbox = QCheckBox("Set maximum depth")
        max_depth_spinbox = QDoubleSpinBox()
        max_depth_spinbox.setRange(0, 10000)
        max_depth_spinbox.setValue(1000)
        max_depth_spinbox.setSuffix(" m")
        max_depth_spinbox.setDecimals(2)
        max_depth_spinbox.setEnabled(False)

        # Connect checkboxes to enable/disable spinboxes
        min_depth_checkbox.toggled.connect(min_depth_spinbox.setEnabled)
        max_depth_checkbox.toggled.connect(max_depth_spinbox.setEnabled)

        # Add widgets to layout
        layout.addRow(min_depth_checkbox, min_depth_spinbox)
        layout.addRow(max_depth_checkbox, max_depth_spinbox)

        # Dialog buttons
        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        button_box.accepted.connect(dialog.accept)
        button_box.rejected.connect(dialog.reject)
        layout.addWidget(button_box)

        # Show dialog and get result
        if dialog.exec() == QDialog.DialogCode.Accepted:
            min_depth = (
                min_depth_spinbox.value() if min_depth_checkbox.isChecked() else None
            )
            max_depth = (
                max_depth_spinbox.value() if max_depth_checkbox.isChecked() else None
            )

            # Validate that at least one constraint is set
            if min_depth is None and max_depth is None:
                QMessageBox.warning(
                    self.parent,
                    "No Constraint",
                    "Please set at least one depth constraint (minimum or maximum).",
                )
                return None

            # Validate that min <= max if both are set
            if (
                min_depth is not None
                and max_depth is not None
                and min_depth > max_depth
            ):
                QMessageBox.warning(
                    self.parent,
                    "Invalid Range",
                    "Minimum depth cannot be greater than maximum depth.",
                )
                return None

            return DepthRangeConstraintResult(min_depth, max_depth)

        return None


# HELPER DIALOG CLASSES

# A QLineEdit holds 32,767 characters by default, about 880 pasted UUIDs.
# Room for well over 40,000.
MAX_PASTE_CHARS = 4_000_000

# How many rejected values a warning lists before summarising the rest.
SHOWN_REJECTED = 10

_LIST_FILE_FILTER = "Text files (*.txt *.csv *.tsv *.list);;All files (*)"


def read_list_file(path: str) -> str:
    """Read a text file of values, tolerating a byte-order mark."""
    with open(path, encoding="utf-8-sig", errors="replace") as f:
        return f.read()


def _unquote(value: str) -> str:
    return value.strip().strip("\"'").strip()


def _plural(n: int, noun: str) -> str:
    return f"{n:,} {noun}" if n == 1 else f"{n:,} {noun}s"


class BulkInputDialog(QDialog):
    """
    Base dialog that allows the user to input multiple items at once.

    Items are typed or pasted (delimited by commas, spaces, or newlines) or
    read from a text file, and listed in a QListWidget without duplicates.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        placeholder_text: str = "",
        item_label: str = "Item",
    ) -> None:
        super().__init__(parent)
        self._item_label = item_label
        # "UUID" stays as it is; "Concept" reads as "concept" mid-sentence.
        self._noun = item_label if item_label.isupper() else item_label.lower()
        self._present: set[str] = set()
        layout = QVBoxLayout(self)

        # Input field for items
        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder_text)
        self._input.setMaxLength(MAX_PASTE_CHARS)
        layout.addWidget(self._input)

        # Buttons to add and delete items
        button_layout = QHBoxLayout()
        self._add_button = QPushButton("Add")
        self._delete_button = QPushButton("Delete Selected")
        self._open_button = QPushButton("Open File…")
        self._open_button.setToolTip(
            f"Add {self._noun}s from a text file, one per line"
        )
        button_layout.addWidget(self._add_button)
        button_layout.addWidget(self._delete_button)
        button_layout.addWidget(self._open_button)
        layout.addLayout(button_layout)

        # List widget to display items
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self._list.setUniformItemSizes(True)  # fast with tens of thousands
        layout.addWidget(self._list)

        self._count_label = QLabel()
        layout.addWidget(self._count_label)
        self._update_count()

        # Dialog buttons
        self.dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(self.dialog_buttons)

        # Connect signals to slots
        self._add_button.clicked.connect(self.add_items)
        self._delete_button.clicked.connect(self.delete_selected_items)
        self._open_button.clicked.connect(self.open_file)
        self.dialog_buttons.accepted.connect(self.accept)
        self.dialog_buttons.rejected.connect(self.reject)
        self._input.returnPressed.connect(self.add_items)

    # ── Parsing and checking (overridden per kind of value) ───────────────────

    def parse_text(self, text: str) -> list[str]:
        """Split typed or pasted text into values."""
        values = (_unquote(v) for v in re.split(r"[\s,;]+", text))
        return [v for v in values if v]

    def parse_file(self, text: str) -> list[str]:
        """Split a file's text into values."""
        return self.parse_text(text)

    def check_values(self, values: list[str]) -> tuple[list[str], list[str]]:
        """Return ``(accepted, rejected)``; accepted values may be normalised."""
        return values, []

    # ── Adding and removing ───────────────────────────────────────────────────

    def _append(self, values: Iterable[str]) -> int:
        """List the values not already listed; return how many were new."""
        new = []
        for value in values:
            if value and value not in self._present:
                self._present.add(value)
                new.append(value)
        if new:
            self._list.addItems(new)
            self._update_count()
        return len(new)

    def add_values(self, values: list[str]) -> int:
        """Check and list *values*, warning about any that were rejected."""
        accepted, rejected = self.check_values(values)
        added = self._append(accepted)
        if rejected:
            self._warn_rejected(rejected)
        return added

    def add_items(self):
        self.add_values(self.parse_text(self._input.text()))
        self._input.clear()

    @pyqtSlot()
    def open_file(self) -> None:
        """Add the values in a text file the user picks."""
        label = self._noun
        path, _ = QFileDialog.getOpenFileName(
            self, f"Open {label} list", "", _LIST_FILE_FILTER
        )
        if not path:
            return
        try:
            text = read_list_file(path)
        except OSError as exc:
            QMessageBox.warning(self, "Couldn't Open File", f"{path}\n\n{exc}")
            return
        values = self.parse_file(text)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            before = len(self._present)
            accepted, rejected = self.check_values(values)
            added = self._append(accepted)
        finally:
            QApplication.restoreOverrideCursor()
        duplicates = len(accepted) - added
        message = f"Added {_plural(added, label)} from the file"
        if duplicates:
            message += f" ({duplicates:,} already listed or repeated)"
        self._count_label.setText(
            f"{message}. {_plural(before + added, label)} in all."
        )
        if rejected:
            self._warn_rejected(rejected)

    def delete_selected_items(self):
        selected = {index.row() for index in self._list.selectedIndexes()}
        if not selected:
            return
        keep = [
            self._list.item(i).text()
            for i in range(self._list.count())
            if i not in selected
        ]
        self._list.clear()
        self._present = set(keep)
        self._list.addItems(keep)
        self._update_count()

    def items(self) -> list[str]:
        """Return all currently entered items from the list widget."""
        return [self._list.item(i).text() for i in range(self._list.count())]

    def _update_count(self) -> None:
        n = self._list.count()
        self._count_label.setText(_plural(n, self._noun) if n else "")

    def _warn_rejected(self, rejected: list[str]) -> None:
        label = self._noun
        shown = "\n".join(rejected[:SHOWN_REJECTED])
        more = len(rejected) - SHOWN_REJECTED
        if more > 0:
            shown += f"\n… and {more:,} more"
        QMessageBox.warning(
            self,
            f"Invalid {self._item_label}s",
            f"{_plural(len(rejected), 'value')} "
            f"{'was' if len(rejected) == 1 else 'were'} not recognised as "
            f"{label}s and {'was' if len(rejected) == 1 else 'were'} not "
            f"added:\n\n{shown}",
        )

    @classmethod
    def get_items(
        cls,
        title: str = "Enter items",
        parent: QWidget | None = None,
        placeholder_text: str = "",
    ) -> tuple[list[str], bool]:
        dialog = cls(parent, placeholder_text)
        dialog.setWindowTitle(title)
        dialog.resize(450, 300)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.items(), True
        return [], False


class BulkUUIDInputDialog(BulkInputDialog):
    """
    Dialog that allows the user to input multiple UUIDs at once.

    The UUIDs should be delimited by commas, spaces, or newlines, or read from
    a text file. Anything that isn't a UUID (e.g. a column header) is left
    out with a warning.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(
            parent,
            placeholder_text="Enter UUIDs separated by commas, spaces, or newlines",
            item_label="UUID",
        )
        # Rename button
        self._add_button.setText("Add UUIDs")

    def check_values(self, values: list[str]) -> tuple[list[str], list[str]]:
        accepted, rejected = [], []
        for value in values:
            try:
                UUID(value)
            except ValueError:
                rejected.append(value)
            else:
                accepted.append(value)
        return accepted, rejected

    @classmethod
    def get_uuids(
        cls, title: str = "Enter UUIDs", parent: QWidget | None = None
    ) -> tuple[list[str], bool]:
        dialog = cls(parent)
        dialog.setWindowTitle(title)
        dialog.resize(450, 300)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            items = dialog.items()

            # Validate all the UUIDs
            for item in items:
                try:
                    UUID(item)
                except ValueError:
                    QMessageBox.warning(
                        parent, "Invalid UUID", f"The UUID '{item}' is invalid."
                    )
                    return [], False

            return items, True
        return [], False


class BulkValidatedInputDialog(BulkInputDialog):
    """
    Dialog that allows the user to input multiple values from a known set at once.

    Supports autocomplete, selection from a list, drag+drop of newline- or
    comma-delimited text, and text files with one value per line. Dropped or
    file values not in the known set are rejected; a value that differs from
    a known one only in case is taken as that one.
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        values_getter: Callable[[], list[str]] | None = None,
        item_label: str = "Value",
    ) -> None:
        super().__init__(
            parent,
            placeholder_text=f"Enter {item_label.lower()}",
            item_label=item_label,
        )

        # Cache values list
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            getter = values_getter or (list)
            self._values = getter()
        finally:
            QApplication.restoreOverrideCursor()
        self._known = set(self._values)
        self._by_lower: dict[str, str] | None = None  # built on first need

        # Configure the input field with autocomplete
        self._completer = QCompleter(self._values)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._input.setCompleter(self._completer)

        # Configure auto-completion behavior to add values when selected
        self._completer.activated.connect(self._add_current_value)

        # Rename button
        self._add_button.setText(f"Add {item_label}")
        self._add_button.clicked.disconnect()  # Disconnect the parent's implementation
        self._add_button.clicked.connect(self._add_current_value)
        self._input.returnPressed.connect(self._add_current_value)

        # Add a button to select from existing values
        self._select_button = QPushButton("Select from List")
        self.layout().itemAt(1).layout().addWidget(self._select_button)
        self._select_button.clicked.connect(self._select_value)

        # Enable drag and drop
        self.setAcceptDrops(True)

    def parse_text(self, text: str) -> list[str]:
        if "\n" in text:
            # Split by newlines if multi-line (not spaces; names may contain them)
            values = (_unquote(item) for item in text.splitlines())
        else:
            # Split by commas
            values = (_unquote(item) for item in text.split(","))
        return [v for v in values if v]

    def parse_file(self, text: str) -> list[str]:
        values = (_unquote(line) for line in text.splitlines())
        return [v for v in values if v]

    def check_values(self, values: list[str]) -> tuple[list[str], list[str]]:
        accepted, rejected = [], []
        for value in values:
            if value in self._known:
                accepted.append(value)
                continue
            if self._by_lower is None:
                self._by_lower = {v.lower(): v for v in self._values}
            known = self._by_lower.get(value.lower())
            if known is None:
                rejected.append(value)
            else:
                accepted.append(known)
        return accepted, rejected

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        mime_data = event.mimeData()
        if mime_data.hasText():
            self.add_values(self.parse_text(mime_data.text()))
            event.acceptProposedAction()

    def _add_current_value(self):
        value = self._input.text().strip()
        if value:
            self._append([value])
            # Use a zero-timer to clear after the current event is processed
            QTimer.singleShot(0, self._input.clear)

    def _select_value(self):
        value, ok = QInputDialog.getItem(
            self,
            f"Select {self._item_label}",
            self._item_label,
            self._values,
            0,
            True,
        )
        if ok and value:
            self._append([value])

    def add_items(self):
        # This is intentionally empty to prevent splitting by spaces
        # Values are added through _add_current_value method
        pass

    @classmethod
    def get_values(
        cls,
        title: str,
        parent: QWidget | None = None,
        values_getter: Callable[[], list[str]] | None = None,
        item_label: str = "Value",
    ) -> tuple[list[str], bool]:
        dialog = cls(parent, values_getter=values_getter, item_label=item_label)
        dialog.setWindowTitle(title)
        dialog.resize(450, 300)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return dialog.items(), True
        return [], False


class ResultListModel(QAbstractListModel):
    """
    List model to hold the results (constraints) added by the user.
    """

    def __init__(
        self, parent: QObject | None = None, results: list[BaseResult] | None = None
    ):
        super().__init__(parent=parent)

        self.results = results or []

    def rowCount(self, parent: QModelIndex = None) -> int:
        return len(self.results)

    def data(self, index: QModelIndex, role: Qt.ItemDataRole) -> Any:
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole and 0 <= index.row() < len(self.results):
            return str(self.results[index.row()])
        else:
            return None

    def add_result(self, result: BaseResult):
        self.beginInsertRows(QModelIndex(), len(self.results), len(self.results))
        self.results.append(result)
        self.endInsertRows()

    def clear(self):
        self.beginResetModel()
        self.results = []
        self.endResetModel()

    def remove_result(self, index: int):
        self.beginRemoveRows(QModelIndex(), index, index)
        del self.results[index]
        self.endRemoveRows()

    def remove_results(self, indices: list[int]):
        indices.sort(reverse=True)
        for index in indices:
            self.remove_result(index)

    @property
    def constraints(self) -> Iterable[QueryConstraint]:
        for result in self.results:
            yield from result.constraints


class QueryDialog(QDialog):
    """
    Main query dialog that allows the user to add filters, view the resulting constraints, and set limit/offset.
    """

    def __init__(
        self,
        parent,
        filters: list[BaseFilter] | None = None,
        *,
        kb_concepts_getter: Callable[[], list[str]] | None = None,
        kb_descendants_getter: Callable[[str], list[str]] | None = None,
        users_getter: Callable[[], list[dict]] | None = None,
        video_sequence_names_getter: Callable[[], list[str]] | None = None,
    ):
        super().__init__(parent=parent)

        self._kb_concepts_getter = kb_concepts_getter or (list)
        self._kb_descendants_getter = kb_descendants_getter or (lambda _concept: [])
        self._users_getter = users_getter or (list)
        self._video_sequence_names_getter = video_sequence_names_getter or (list)

        self.setWindowTitle("Query")
        self.setLayout(QVBoxLayout())

        # Create filters
        self.filters = filters or self._create_default_filters()

        # Create button bar (add, remove, clear constraints)
        self.button_bar = QWidget()
        self.button_bar.setLayout(QHBoxLayout())
        self.add_constraint_button = QPushButton("Add Constraint")
        self.add_constraint_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogYesButton)
        )
        self.remove_constraint_button = QPushButton("Remove Selected")
        self.remove_constraint_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogNoButton)
        )
        self.clear_filters_button = QPushButton("Clear")
        self.clear_filters_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DialogDiscardButton)
        )

        # Create result list model and view
        self.result_list_model = ResultListModel(parent=self)
        self.result_list_view = QListView()
        self.result_list_view.setModel(self.result_list_model)
        self.result_list_view.setSelectionMode(
            QAbstractItemView.SelectionMode.ExtendedSelection
        )

        # Create limit/offset bar
        self.limit_offset_bar = QWidget()
        self.limit_offset_bar.setLayout(QFormLayout())
        self.limit_edit = QSpinBox()
        self.limit_edit.setRange(1, 100000)
        self.limit_edit.setValue(10000)
        self.offset_edit = QSpinBox()
        self.offset_edit.setRange(0, 1000000000)
        self.offset_edit.setValue(0)
        self.limit_offset_bar.layout().addRow("Limit", self.limit_edit)
        self.limit_offset_bar.layout().addRow("Offset", self.offset_edit)

        # Create dialog button box (just Ok button)
        self.dialog_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)

        # Arrange
        self.layout().addWidget(self.button_bar)
        self.layout().addWidget(self.result_list_view)
        self.layout().addWidget(self.limit_offset_bar)
        self.layout().addWidget(self.dialog_buttons)
        self.button_bar.layout().addWidget(self.add_constraint_button)
        self.button_bar.layout().addWidget(self.remove_constraint_button)
        self.button_bar.layout().addWidget(self.clear_filters_button)

        # Connect signals and slots
        self.dialog_buttons.accepted.connect(self.accept)
        self.add_constraint_button.pressed.connect(self.add_filter)
        self.remove_constraint_button.pressed.connect(self.remove_selected_filters)
        self.clear_filters_button.pressed.connect(self.clear)

    def _create_default_filters(self) -> list[BaseFilter]:
        """
        Create the default set of filters available in the dialog.

        Returns:
            List[BaseFilter]: A list of default filter instances.
        """
        return [
            ItemSelectFilter(
                self,
                "Concept",
                self._kb_concepts_getter,
                "concept",
                editable=True,
            ),
            BulkValueFilter(
                self,
                "Concepts",
                self._kb_concepts_getter,
                "concept",
                "Concept",
                result_cls=ConceptInConstraintResult,
            ),
            ConceptDescFilter(
                self,
                "Concept (+ descendants)",
                self._kb_concepts_getter,
                self._kb_descendants_getter,
            ),
            ItemSelectFilter(
                self,
                "Video sequence name",
                self._video_sequence_names_getter,
                "video_sequence_name",
                editable=True,
            ),
            BulkValueFilter(
                self,
                "Video sequence names",
                self._video_sequence_names_getter,
                "video_sequence_name",
                "Video sequence name",
            ),
            SimpleTextFilter(self, "Chief scientist", "chief_scientist"),
            SimpleTextFilter(self, "Platform", "camera_platform"),
            SimpleTextFilter(self, "Camera ID", "camera_id"),
            ItemSelectFilter(
                self,
                "Observer",
                lambda: sorted([u.get("username", "") for u in self._users_getter()]),
                "observer",
                editable=True,
            ),
            UUIDListFilter(
                self,
                "Imaged moment UUID",
                "imaged_moment_uuid",
                title="Imaged moment UUIDs",
            ),
            UUIDListFilter(
                self, "Observation UUID", "observation_uuid", title="Observation UUIDs"
            ),
            UUIDListFilter(
                self, "Association UUID", "association_uuid", title="Association UUIDs"
            ),
            UUIDListFilter(
                self,
                "Image reference UUID",
                "image_reference_uuid",
                title="Image reference UUIDs",
            ),
            UUIDListFilter(
                self,
                "Video reference UUID",
                "video_reference_uuid",
                title="Video reference UUIDs",
            ),
            SimpleTextFilter(self, "Activity", "activity"),
            SimpleTextFilter(self, "Observation group", "observation_group"),
            DepthRangeFilter(self, "Depth range"),
            GeneratorFilter(self, "Generator", "generator", prompt="Generator"),
            VerifierFilter(self, "Verifier", "verifier", prompt="Verifier"),
            FunctionalFilter(self, "Verified", lambda: VerifiedConstraintResult()),
            FunctionalFilter(
                self, "Not Verified", lambda: NotVerifiedConstraintResult()
            ),
        ]

    @pyqtSlot()
    def add_filter(self):
        """
        Slot to add a filter to the result list by showing a dialog to select from available filters.
        """
        filter_names = [f.name for f in self.filters]
        filter_name, ok = QInputDialog.getItem(
            self, "Filter", "Filter", filter_names, 0, False
        )
        if not ok:
            return

        filter_ = self.filters[filter_names.index(filter_name)]

        result = filter_()

        if result is None:
            return

        self.result_list_model.add_result(result)

    @pyqtSlot()
    def remove_selected_filters(self):
        """
        Slot to remove the selected filters from the result list.
        """
        indices = [index.row() for index in self.result_list_view.selectedIndexes()]
        self.result_list_model.remove_results(indices)

    @pyqtSlot()
    def clear(self):
        """
        Slot to clear all filters from the result list.
        """
        self.result_list_model.clear()

    @property
    def limit(self) -> int:
        """
        The limit value set in the dialog.
        """
        return self.limit_edit.value()

    @property
    def offset(self) -> int:
        """
        The offset value set in the dialog.
        """
        return self.offset_edit.value()

    @property
    def constraints(self) -> list[QueryConstraint]:
        """
        The list of QueryConstraint objects representing the constraints set in the dialog.
        """
        return list(self.result_list_model.constraints)
