from typing import Any, Iterable, List, Optional, Tuple
from uuid import UUID

from PyQt6.QtCore import QAbstractListModel, QModelIndex, QObject, Qt, pyqtSlot, QTimer
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListView,
    QListWidget,
    QMessageBox,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
    QSpinBox,
    QFormLayout,
    QCompleter,
)
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from vars_gridview.lib.m3.operations import (
    get_kb_concepts,
    get_kb_descendants,
    get_users,
    get_video_sequence_names,
)


class Constraint:
    def __init__(self, key, value):
        self.key = key
        self.value = value


class Filter:
    class Result:
        @property
        def constraints(self) -> Iterable[Constraint]:
            raise NotImplementedError()

        def __str__(self) -> str:
            raise NotImplementedError()

    def __init__(self, parent, name: str):
        self.parent = parent
        self.name = name

    def __call__(self) -> Optional[Result]:
        raise NotImplementedError()


class BulkInputDialog(QDialog):
    """
    Base dialog that allows the user to input multiple items at once.

    The items should be delimited by commas, spaces, or newlines.
    The parsed items should be rendered in a QListWidget.
    """

    def __init__(
        self, parent: QWidget | None = ..., placeholder_text: str = ""
    ) -> None:
        super().__init__(parent)
        layout = QVBoxLayout(self)

        # Input field for items
        self._input = QLineEdit()
        self._input.setPlaceholderText(placeholder_text)
        layout.addWidget(self._input)

        # Buttons to add and delete items
        button_layout = QHBoxLayout()
        self._add_button = QPushButton("Add")
        self._delete_button = QPushButton("Delete Selected")
        button_layout.addWidget(self._add_button)
        button_layout.addWidget(self._delete_button)
        layout.addLayout(button_layout)

        # List widget to display items
        self._list = QListWidget()
        self._list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        layout.addWidget(self._list)

        # Dialog buttons
        self.dialog_buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        layout.addWidget(self.dialog_buttons)

        # Connect signals to slots
        self._add_button.clicked.connect(self.add_items)
        self._delete_button.clicked.connect(self.delete_selected_items)
        self.dialog_buttons.accepted.connect(self.accept)
        self.dialog_buttons.rejected.connect(self.reject)

    def add_items(self):
        input_text = self._input.text()
        items = [item.strip() for item in input_text.replace(",", " ").split()]
        for item in items:
            if item and not self._list.findItems(item, Qt.MatchFlag.MatchExactly):
                self._list.addItem(item)
        self._input.clear()

    def delete_selected_items(self):
        selected_items = self._list.selectedItems()
        for item in selected_items:
            self._list.takeItem(self._list.row(item))

    @classmethod
    def get_items(
        cls,
        title: str = "Enter items",
        parent: QWidget | None = ...,
        placeholder_text: str = "",
    ) -> Tuple[List[str], bool]:
        dialog = cls(parent, placeholder_text)
        dialog.setWindowTitle(title)
        dialog.resize(450, 300)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return [
                dialog._list.item(i).text() for i in range(dialog._list.count())
            ], True
        return [], False


class BulkUUIDInputDialog(BulkInputDialog):
    """
    Dialog that allows the user to input multiple UUIDs at once.

    The UUIDs should be delimited by commas, spaces, or newlines.

    The parsed UUIDs should be rendered in a QListWidget.
    """

    def __init__(self, parent: QWidget | None = ...) -> None:
        super().__init__(
            parent,
            placeholder_text="Enter UUIDs separated by commas, spaces, or newlines",
        )
        # Rename button
        self._add_button.setText("Add UUIDs")

    @classmethod
    def get_uuids(
        cls, title: str = "Enter UUIDs", parent: QWidget | None = ...
    ) -> Tuple[List[str], bool]:
        dialog = cls(parent)
        dialog.setWindowTitle(title)
        dialog.resize(450, 300)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            items = [dialog._list.item(i).text() for i in range(dialog._list.count())]

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


class BulkConceptInputDialog(BulkInputDialog):
    """
    Dialog that allows the user to input multiple concepts at once.
    """

    def __init__(self, parent: QWidget | None = ...) -> None:
        super().__init__(
            parent,
            placeholder_text="Enter concept",
        )
        # Cache concepts list
        self._concepts = get_kb_concepts()

        # Configure the input field with autocomplete
        self._completer = QCompleter(self._concepts)
        self._completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self._input.setCompleter(self._completer)

        # Configure auto-completion behavior to add concepts when selected
        self._completer.activated.connect(self._add_current_concept)

        # Rename button
        self._add_button.setText("Add Concept")
        self._add_button.clicked.disconnect()  # Disconnect the parent's implementation
        self._add_button.clicked.connect(self._add_current_concept)

        # Add a button to select from existing concepts
        self._select_button = QPushButton("Select from List")
        self.layout().itemAt(1).layout().addWidget(self._select_button)
        self._select_button.clicked.connect(self._select_concept)

        # Enable drag and drop
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasText():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        mime_data = event.mimeData()
        if mime_data.hasText():
            text = mime_data.text()
            if "\n" in text:
                # Split by newlines if the text contains multiple lines
                concepts = [item.strip() for item in text.splitlines() if item.strip()]
            else:
                # Split by commas
                concepts = [item.strip() for item in text.split(",") if item.strip()]
            invalid_concepts = []
            for concept in concepts:
                # Guard against invalid concepts
                if concept not in self._concepts:
                    invalid_concepts.append(concept)
                    continue

                # Add the concept if it does not already exist in the list
                if concept and not self._list.findItems(
                    concept, Qt.MatchFlag.MatchExactly
                ):
                    self._list.addItem(concept)

            # Show a warning for any invalid concepts
            if invalid_concepts:
                QMessageBox.warning(
                    self,
                    "Invalid Concepts",
                    "The following concepts were not recognized and were not added:\n"
                    + ", ".join(invalid_concepts),
                )

            event.acceptProposedAction()

    def _add_current_concept(self):
        concept = self._input.text().strip()
        if concept and not self._list.findItems(concept, Qt.MatchFlag.MatchExactly):
            self._list.addItem(concept)
            # Use a zero-timer to clear after the current event is processed
            QTimer.singleShot(0, self._input.clear)

    def _select_concept(self):
        concept, ok = QInputDialog.getItem(
            self, "Select Concept", "Concept", self._concepts, 0, True
        )
        if ok and concept:
            if not self._list.findItems(concept, Qt.MatchFlag.MatchExactly):
                self._list.addItem(concept)

    def add_items(self):
        # This is intentionally empty to prevent splitting by spaces
        # Concepts are added through _add_current_concept method
        pass

    @classmethod
    def get_concepts(
        cls, title: str = "Enter Concepts", parent: QWidget | None = ...
    ) -> Tuple[List[str], bool]:
        dialog = cls(parent)
        dialog.setWindowTitle(title)
        dialog.resize(450, 300)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            return [
                dialog._list.item(i).text() for i in range(dialog._list.count())
            ], True
        return [], False


class SimpleTextFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, label: str, value: str, key: str):
            self.label = label
            self.value = value
            self.key = key

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint(self.key, self.value)

        def __str__(self) -> str:
            return f"{self.label}: {self.value}"

    def __init__(self, parent, name: str, key: str, prompt: Optional[str] = None):
        super().__init__(parent, name)
        self.key = key
        self.prompt = prompt or name

    def __call__(self) -> Optional[Result]:
        text, ok = QInputDialog.getText(
            self.parent, self.name, self.prompt, QLineEdit.EchoMode.Normal, ""
        )
        if ok:
            return SimpleTextFilter.Result(self.name, text, self.key)


class ItemSelectFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, label: str, value: str, key: str):
            self.label = label
            self.value = value
            self.key = key

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint(self.key, self.value)

        def __str__(self) -> str:
            return f"{self.label}: {self.value}"

    def __init__(
        self, parent, name: str, items_getter, key: str, editable: bool = False
    ):
        super().__init__(parent, name)
        self.items_getter = items_getter
        self.key = key
        self.editable = editable

    def __call__(self) -> Optional[Result]:
        items = self.items_getter()
        value, ok = QInputDialog.getItem(
            self.parent, self.name, self.name, items, 0, self.editable
        )
        if ok:
            return ItemSelectFilter.Result(self.name, value, self.key)


class UUIDListFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, label: str, uuids: List[str], key: str):
            self.label = label
            self.uuids = uuids
            self.key = key

        @property
        def constraints(self) -> Iterable[Constraint]:
            for u in self.uuids:
                yield Constraint(self.key, u)

        def __str__(self) -> str:
            if len(self.uuids) == 1:
                return f"{self.label}: {self.uuids[0]}"
            return f"{self.label}s ({len(self.uuids)} items)"

    def __init__(self, parent, name: str, key: str, title: Optional[str] = None):
        super().__init__(parent, name)
        self.key = key
        self.title = title or name + "s"

    def __call__(self) -> Optional[Result]:
        uuids, ok = BulkUUIDInputDialog.get_uuids(self.title, self.parent)
        if ok:
            if not uuids:
                return None
            # Validate
            for u in uuids:
                try:
                    UUID(u)
                except ValueError:
                    QMessageBox.warning(
                        self.parent, "Invalid UUID", f"The UUID '{u}' is invalid."
                    )
                    return None
            return UUIDListFilter.Result(self.name, uuids, self.key)


class BooleanSQLFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, label: str, value: bool, expr: str):
            self.label = label
            self.value = value
            self.expr = expr

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint(self.expr, int(self.value))

        def __str__(self) -> str:
            return f"{self.label}: {'Yes' if self.value else 'No'}"

    def __init__(self, parent, name: str, expr: str):
        super().__init__(parent, name)
        self.expr = expr

    def __call__(self) -> Optional[Result]:
        choice, ok = QInputDialog.getItem(
            self.parent, self.name, self.name, ["Yes", "No"], 0, False
        )
        if ok:
            return BooleanSQLFilter.Result(
                self.name, True if choice == "Yes" else False, self.expr
            )


# Small adapters for concepts since they have special dialogs/behaviour
class BulkConceptFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, concepts: List[str]):
            self.concepts = concepts

        @property
        def constraints(self) -> Iterable[Constraint]:
            for concept in self.concepts:
                yield Constraint("concept", concept)

        def __str__(self) -> str:
            if len(self.concepts) == 1:
                return f"Concept: {self.concepts[0]}"
            return f"Concepts: {', '.join(self.concepts)}"

    def __call__(self) -> Optional[Result]:
        concepts, ok = BulkConceptInputDialog.get_concepts(
            "Select Concepts", self.parent
        )
        if ok and concepts:
            return BulkConceptFilter.Result(concepts)


class ConceptDescFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, concept: str):
            self.concept = concept
            self.descendants = get_kb_descendants(concept)

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("concept", self.concept)
            for descendant in self.descendants:
                yield Constraint("concept", descendant)

        def __str__(self) -> str:
            return "Concept (+ descendants): {} ({})".format(
                self.concept, ", ".join(self.descendants)
            )

    def __call__(self) -> Optional[Result]:
        concept, ok = QInputDialog.getItem(
            self.parent, "Concept", "Concept", get_kb_concepts(), 0, True
        )
        if ok:
            return ConceptDescFilter.Result(concept)


class ResultListModel(QAbstractListModel):
    def __init__(self, parent: QObject = None, results: List[Filter.Result] = None):
        super().__init__(parent=parent)

        self.results = results or []

    def rowCount(self, parent: QModelIndex = None) -> int:
        return len(self.results)

    def data(self, index: QModelIndex, role: Qt.ItemDataRole) -> Any:
        if not index.isValid():
            return None

        if role == Qt.ItemDataRole.DisplayRole:
            return str(self.results[index.row()])
        else:
            return None

    def add_result(self, result: Filter.Result):
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

    def remove_results(self, indices: List[int]):
        indices.sort(reverse=True)
        for index in indices:
            self.remove_result(index)

    @property
    def constraints(self) -> Iterable[Constraint]:
        for result in self.results:
            yield from result.constraints


class QueryDialog(QDialog):
    def __init__(self, parent):
        super().__init__(parent=parent)

        self.setWindowTitle("Query")
        self.setLayout(QVBoxLayout())

        # Create filters (using generic filter classes to reduce duplication)
        self.filters = [
            ItemSelectFilter(
                self, "Concept", get_kb_concepts, "concept", editable=True
            ),
            BulkConceptFilter(self, "Concepts"),
            ConceptDescFilter(self, "Concept (+ descendants)"),
            # DiveNumberFilter(self, "Dive number"),
            ItemSelectFilter(
                self,
                "Video sequence name",
                get_video_sequence_names,
                "video_sequence_name",
                editable=True,
            ),
            SimpleTextFilter(self, "Chief scientist", "chief_scientist"),
            SimpleTextFilter(self, "Platform", "camera_platform"),
            SimpleTextFilter(self, "Camera ID", "camera_id"),
            ItemSelectFilter(
                self,
                "Observer",
                lambda: sorted([u["username"] for u in get_users()]),
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
            # SimpleTextFilter(self, "Generator", "JSON_VALUE(assoc.link_value, '$.generator')"),
            # SimpleTextFilter(self, "Verifier", "JSON_VALUE(assoc.link_value, '$.verifier')"),
            # BooleanSQLFilter(self, "Verified", "CASE WHEN JSON_VALUE(assoc.link_value, '$.verifier') IS NOT NULL THEN 1 ELSE 0 END"),
        ]

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
        self.limit_edit.setRange(0, 100000)
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
        self.clear_filters_button.pressed.connect(self.result_list_model.clear)

    @pyqtSlot()
    def add_filter(self):
        filter_names = [f.name for f in self.filters]
        filter_name, ok = QInputDialog.getItem(
            self, "Filter", "Filter", filter_names, 0, False
        )
        if not ok:
            return

        filter = self.filters[filter_names.index(filter_name)]

        result = filter()

        if result is None:
            return

        self.result_list_model.add_result(result)

    @pyqtSlot()
    def remove_selected_filters(self):
        indices = [index.row() for index in self.result_list_view.selectedIndexes()]
        self.result_list_model.remove_results(indices)

    @pyqtSlot()
    def clear(self):
        self.result_list_model.clear()

    @property
    def limit(self) -> int:
        return self.limit_edit.value()

    @property
    def offset(self) -> int:
        return self.offset_edit.value()

    def constraints_dict(self):
        d = {}
        for constraint in self.result_list_model.constraints:
            if constraint.key not in d:
                d[constraint.key] = []
            d[constraint.key].append(constraint.value)
        return d
