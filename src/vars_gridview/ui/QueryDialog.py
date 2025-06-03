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


class ConceptFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, concept: str):
            self.concept = concept

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("concept", self.concept)

        def __str__(self) -> str:
            return f"Concept: {self.concept}"

    def __call__(self) -> Optional[Result]:
        concept, ok = QInputDialog.getItem(
            self.parent, "Concept", "Concept", get_kb_concepts(), 0, True
        )
        if ok:
            return ConceptFilter.Result(concept)


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


class DiveNumberFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, dive_number: str):
            self.dive_number = dive_number

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("dive_number", self.dive_number)

        def __str__(self) -> str:
            return "Dive number: {}".format(self.dive_number)

    def __call__(self) -> Optional[Result]:
        dive_number, ok = QInputDialog.getText(
            self.parent, "Dive number", "Dive number", QLineEdit.EchoMode.Normal, ""
        )
        if ok:
            return DiveNumberFilter.Result(dive_number)


class VideoSequenceNameFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, video_sequence_name: str):
            self.video_sequence_name = video_sequence_name

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("video_sequence_name", self.video_sequence_name)

        def __str__(self) -> str:
            return "Video sequence name: {}".format(self.video_sequence_name)

    def __call__(self) -> Optional[Result]:
        video_sequence_name, ok = QInputDialog.getItem(
            self.parent,
            "Video sequence name",
            "Video sequence name",
            get_video_sequence_names(),
            0,
            True,
        )
        if ok:
            return VideoSequenceNameFilter.Result(video_sequence_name)


class ChiefScientistFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, chief_scientist: str):
            self.chief_scientist = chief_scientist

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("chief_scientist", self.chief_scientist)

        def __str__(self) -> str:
            return "Chief scientist: {}".format(self.chief_scientist)

    def __call__(self) -> Optional[Result]:
        chief_scientist, ok = QInputDialog.getText(
            self.parent,
            "Chief scientist",
            "Chief scientist",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if ok:
            return ChiefScientistFilter.Result(chief_scientist)


class PlatformFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, platform: str):
            self.platform = platform

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("camera_platform", self.platform)

        def __str__(self) -> str:
            return "Platform: {}".format(self.platform)

    def __call__(self) -> Optional[Result]:
        platform, ok = QInputDialog.getText(
            self.parent, "Platform", "Platform", QLineEdit.EchoMode.Normal, ""
        )
        if ok:
            return PlatformFilter.Result(platform)


class ObserverFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, observer: str):
            self.observer = observer

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("observer", self.observer)

        def __str__(self) -> str:
            return "Observer: {}".format(self.observer)

    def __call__(self) -> Optional[Result]:
        usernames = sorted([user["username"] for user in get_users()])
        observer, ok = QInputDialog.getItem(
            self.parent, "Observer", "Observer", usernames, 0, True
        )
        if ok:
            return ObserverFilter.Result(observer)


class ImagedMomentUUIDFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, imaged_moment_uuids: List[str]):
            self.imaged_moment_uuids = imaged_moment_uuids

        @property
        def constraints(self) -> Iterable[Constraint]:
            for uuid in self.imaged_moment_uuids:
                yield Constraint("imaged_moment_uuid", uuid)

        def __str__(self) -> str:
            if len(self.imaged_moment_uuids) == 1:
                return "Imaged moment UUID: {}".format(self.imaged_moment_uuids[0])
            return "Imaged moment UUIDs ({} items)".format(
                len(self.imaged_moment_uuids)
            )

    def __call__(self) -> Optional[Result]:
        imaged_moment_uuids, ok = BulkUUIDInputDialog.get_uuids(
            "Imaged moment UUIDs", self.parent
        )
        if ok:
            # If no UUIDs were entered, return None
            if not imaged_moment_uuids:
                return None

            # Validate all the UUIDs
            for imaged_moment_uuid in imaged_moment_uuids:
                try:
                    UUID(imaged_moment_uuid)
                except ValueError:
                    QMessageBox.warning(
                        self.parent,
                        "Invalid UUID",
                        "The UUID '{}' is invalid.".format(imaged_moment_uuid),
                    )
                    return None

            # Return the result
            return ImagedMomentUUIDFilter.Result(imaged_moment_uuids)


class ObservationUUIDFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, observation_uuids: List[str]):
            self.observation_uuids = observation_uuids

        @property
        def constraints(self) -> Iterable[Constraint]:
            for uuid in self.observation_uuids:
                yield Constraint("observation_uuid", uuid)

        def __str__(self) -> str:
            if len(self.observation_uuids) == 1:
                return "Observation UUID: {}".format(self.observation_uuids[0])
            return "Observation UUIDs ({} items)".format(len(self.observation_uuids))

    def __call__(self) -> Optional[Result]:
        observation_uuids, ok = BulkUUIDInputDialog.get_uuids(
            "Observation UUIDs", self.parent
        )
        if ok:
            # If no UUIDs were entered, return None
            if not observation_uuids:
                return None

            # Validate all the UUIDs
            for observation_uuid in observation_uuids:
                try:
                    UUID(observation_uuid)
                except ValueError:
                    QMessageBox.warning(
                        self.parent,
                        "Invalid UUID",
                        "The UUID '{}' is invalid.".format(observation_uuid),
                    )
                    return None

            # Return the result
            return ObservationUUIDFilter.Result(observation_uuids)


class AssociationUUIDFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, association_uuids: List[str]):
            self.association_uuids = association_uuids

        @property
        def constraints(self) -> Iterable[Constraint]:
            for uuid in self.association_uuids:
                yield Constraint("association_uuid", uuid)

        def __str__(self) -> str:
            if len(self.association_uuids) == 1:
                return "Association UUID: {}".format(self.association_uuids[0])
            return "Association UUIDs ({} items)".format(len(self.association_uuids))

    def __call__(self) -> Optional[Result]:
        association_uuids, ok = BulkUUIDInputDialog.get_uuids(
            "Association UUIDs", self.parent
        )
        if ok:
            # If no UUIDs were entered, return None
            if not association_uuids:
                return None

            # Validate all the UUIDs
            for association_uuid in association_uuids:
                try:
                    UUID(association_uuid)
                except ValueError:
                    QMessageBox.warning(
                        self.parent,
                        "Invalid UUID",
                        "The UUID '{}' is invalid.".format(association_uuid),
                    )
                    return None

            # Return the result
            return AssociationUUIDFilter.Result(association_uuids)


class ImageReferenceUUIDFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, image_reference_uuids: List[str]):
            self.image_reference_uuids = image_reference_uuids

        @property
        def constraints(self) -> Iterable[Constraint]:
            for uuid in self.image_reference_uuids:
                yield Constraint("image_reference_uuid", uuid)

        def __str__(self) -> str:
            if len(self.image_reference_uuids) == 1:
                return "Image reference UUID: {}".format(self.image_reference_uuids[0])
            return "Image reference UUIDs ({} items)".format(
                len(self.image_reference_uuids)
            )

    def __call__(self) -> Optional[Result]:
        image_reference_uuids, ok = BulkUUIDInputDialog.get_uuids(
            "Image reference UUIDs", self.parent
        )
        if ok:
            # If no UUIDs were entered, return None
            if not image_reference_uuids:
                return None

            # Validate all the UUIDs
            for image_reference_uuid in image_reference_uuids:
                try:
                    UUID(image_reference_uuid)
                except ValueError:
                    QMessageBox.warning(
                        self.parent,
                        "Invalid UUID",
                        "The UUID '{}' is invalid.".format(image_reference_uuid),
                    )
                    return None

            # Return the result
            return ImageReferenceUUIDFilter.Result(image_reference_uuids)


class VideoReferenceUUIDFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, video_reference_uuids: List[str]):
            self.video_reference_uuids = video_reference_uuids

        @property
        def constraints(self) -> Iterable[Constraint]:
            for uuid in self.video_reference_uuids:
                yield Constraint("video_reference_uuid", uuid)

        def __str__(self) -> str:
            if len(self.video_reference_uuids) == 1:
                return "Video reference UUID: {}".format(self.video_reference_uuids[0])
            return "Video reference UUIDs ({} items)".format(
                len(self.video_reference_uuids)
            )

    def __call__(self) -> Optional[Result]:
        video_reference_uuids, ok = BulkUUIDInputDialog.get_uuids(
            "Video reference UUIDs", self.parent
        )
        if ok:
            # If no UUIDs were entered, return None
            if not video_reference_uuids:
                return None

            # Validate all the UUIDs
            for video_reference_uuid in video_reference_uuids:
                try:
                    UUID(video_reference_uuid)
                except ValueError:
                    QMessageBox.warning(
                        self.parent,
                        "Invalid UUID",
                        "The UUID '{}' is invalid.".format(video_reference_uuid),
                    )
                    return None

            # Return the result
            return VideoReferenceUUIDFilter.Result(video_reference_uuids)


class ActivityFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, activity: str):
            self.activity = activity

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("activity", self.activity)

        def __str__(self) -> str:
            return "Activity: {}".format(self.activity)

    def __call__(self) -> Optional[Result]:
        activity, ok = QInputDialog.getText(
            self.parent,
            "Activity",
            "Activity",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if ok:
            return ActivityFilter.Result(activity)


class ObservationGroupFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, observation_group: str):
            self.observation_group = observation_group

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("observation_group", self.observation_group)

        def __str__(self) -> str:
            return "Observation group: {}".format(self.observation_group)

    def __call__(self) -> Optional[Result]:
        observation_group, ok = QInputDialog.getText(
            self.parent,
            "Observation group",
            "Observation group",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if ok:
            return ObservationGroupFilter.Result(observation_group)


class GeneratorFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, generator: str):
            self.generator = generator

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint(
                "JSON_VALUE(assoc.link_value, '$.generator')", self.generator
            )

        def __str__(self) -> str:
            return "Generator: {}".format(self.generator)

    def __call__(self) -> Optional[Result]:
        generator, ok = QInputDialog.getText(
            self.parent,
            "Generator",
            "Generator",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if ok:
            return GeneratorFilter.Result(generator)


class VerifierFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, verifier: str):
            self.verifier = verifier

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint(
                "JSON_VALUE(assoc.link_value, '$.verifier')", self.verifier
            )

        def __str__(self) -> str:
            return "Verifier: {}".format(self.verifier)

    def __call__(self) -> Optional[Result]:
        verifier, ok = QInputDialog.getText(
            self.parent,
            "Verifier",
            "Verifier",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if ok:
            return VerifierFilter.Result(verifier)


class VerifiedBooleanFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, verified: bool):
            self.verified = verified

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint(
                "CASE WHEN JSON_VALUE(assoc.link_value, '$.verifier') IS NOT NULL THEN 1 ELSE 0 END",
                int(self.verified),
            )

        def __str__(self) -> str:
            return "Verified: {}".format("Yes" if self.verified else "No")

    def __call__(self) -> Optional[Result]:
        verified, ok = QInputDialog.getItem(
            self.parent,
            "Verified",
            "Verified",
            ["Yes", "No"],
            0,
            False,
        )
        if ok:
            return VerifiedBooleanFilter.Result(True if verified == "Yes" else False)


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

        # Create filters
        self.filters = [
            ConceptFilter(self, "Concept"),
            BulkConceptFilter(self, "Concepts"),
            ConceptDescFilter(self, "Concept (+ descendants)"),
            # DiveNumberFilter(self, "Dive number"),
            VideoSequenceNameFilter(self, "Video sequence name"),
            ChiefScientistFilter(self, "Chief scientist"),
            PlatformFilter(self, "Platform"),
            ObserverFilter(self, "Observer"),
            ImagedMomentUUIDFilter(self, "Imaged moment UUID"),
            ObservationUUIDFilter(self, "Observation UUID"),
            AssociationUUIDFilter(self, "Association UUID"),
            ImageReferenceUUIDFilter(self, "Image reference UUID"),
            VideoReferenceUUIDFilter(self, "Video reference UUID"),
            ActivityFilter(self, "Activity"),
            ObservationGroupFilter(self, "Observation group"),
            GeneratorFilter(self, "Generator"),
            VerifierFilter(self, "Verifier"),
            VerifiedBooleanFilter(self, "Verified"),
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
