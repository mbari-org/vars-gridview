from typing import Any, Iterable, List, Optional
from uuid import UUID

from PyQt6.QtCore import QAbstractListModel, QModelIndex, QObject, Qt, pyqtSlot
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QInputDialog,
    QLineEdit,
    QListView,
    QMessageBox,
    QPushButton,
    QStyle,
    QVBoxLayout,
    QWidget,
)

from vars_gridview.lib.m3.operations import (
    get_kb_concepts,
    get_kb_descendants,
    get_users,
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


class ConceptFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, concept: str):
            self.concept = concept

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("concept", self.concept)

        def __str__(self) -> str:
            return "Concept: {}".format(self.concept)

    def __call__(self) -> Optional[Result]:
        concept, ok = QInputDialog.getItem(
            self.parent, "Concept", "Concept", get_kb_concepts(), 0, True
        )
        if ok:
            return ConceptFilter.Result(concept)


class ConceptDescFilter(Filter):
    class Result(ConceptFilter.Result):
        def __init__(self, concept: str):
            super().__init__(concept)
            self.descendants = get_kb_descendants(concept)

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield from super().constraints
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
            yield Constraint("platform", self.platform)

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
        def __init__(self, imaged_moment_uuid: str):
            self.imaged_moment_uuid = imaged_moment_uuid

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("imaged_moment_uuid", self.imaged_moment_uuid)

        def __str__(self) -> str:
            return "Imaged moment UUID: {}".format(self.imaged_moment_uuid)

    def __call__(self) -> Optional[Result]:
        imaged_moment_uuid, ok = QInputDialog.getText(
            self.parent,
            "Imaged moment UUID",
            "Imaged moment UUID",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if ok:
            # Ensure that the UUID is valid
            try:
                UUID(imaged_moment_uuid)
            except ValueError:
                QMessageBox.warning(self.parent, "Invalid UUID", "The UUID is invalid.")
                return None
            return ImagedMomentUUIDFilter.Result(imaged_moment_uuid.lower())


class ObservationUUIDFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, observation_uuid: str):
            self.observation_uuid = observation_uuid

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("observation_uuid", self.observation_uuid)

        def __str__(self) -> str:
            return "Observation UUID: {}".format(self.observation_uuid)

    def __call__(self) -> Optional[Result]:
        observation_uuid, ok = QInputDialog.getText(
            self.parent,
            "Observation UUID",
            "Observation UUID",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if ok:
            # Ensure that the UUID is valid
            try:
                UUID(observation_uuid)
            except ValueError:
                QMessageBox.warning(self.parent, "Invalid UUID", "The UUID is invalid.")
                return None
            return ObservationUUIDFilter.Result(observation_uuid.lower())


class AssociationUUIDFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, association_uuid: str):
            self.association_uuid = association_uuid

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("assoc.uuid", self.association_uuid)

        def __str__(self) -> str:
            return "Association UUID: {}".format(self.association_uuid)

    def __call__(self) -> Optional[Result]:
        association_uuid, ok = QInputDialog.getText(
            self.parent,
            "Association UUID",
            "Association UUID",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if ok:
            # Ensure that the UUID is valid
            try:
                UUID(association_uuid)
            except ValueError:
                QMessageBox.warning(self.parent, "Invalid UUID", "The UUID is invalid.")
                return None
            return AssociationUUIDFilter.Result(association_uuid.lower())


class ImageReferenceUUIDFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, image_reference_uuid: str):
            self.image_reference_uuid = image_reference_uuid

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("image_reference_uuid", self.image_reference_uuid)

        def __str__(self) -> str:
            return "Image reference UUID: {}".format(self.image_reference_uuid)

    def __call__(self) -> Optional[Result]:
        image_reference_uuid, ok = QInputDialog.getText(
            self.parent,
            "Image reference UUID",
            "Image reference UUID",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if ok:
            # Ensure that the UUID is valid
            try:
                UUID(image_reference_uuid)
            except ValueError:
                QMessageBox.warning(self.parent, "Invalid UUID", "The UUID is invalid.")
                return None
            return ImageReferenceUUIDFilter.Result(image_reference_uuid.lower())


class VideoReferenceUUIDFilter(Filter):
    class Result(Filter.Result):
        def __init__(self, video_reference_uuid: str):
            self.video_reference_uuid = video_reference_uuid

        @property
        def constraints(self) -> Iterable[Constraint]:
            yield Constraint("video_reference_uuid", self.video_reference_uuid)

        def __str__(self) -> str:
            return "Video reference UUID: {}".format(self.video_reference_uuid)

    def __call__(self) -> Optional[Result]:
        video_reference_uuid, ok = QInputDialog.getText(
            self.parent,
            "Video reference UUID",
            "Video reference UUID",
            QLineEdit.EchoMode.Normal,
            "",
        )
        if ok:
            # Ensure that the UUID is valid
            try:
                UUID(video_reference_uuid)
            except ValueError:
                QMessageBox.warning(self.parent, "Invalid UUID", "The UUID is invalid.")
                return None
            return VideoReferenceUUIDFilter.Result(video_reference_uuid.lower())


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
            ConceptDescFilter(self, "Concept (+ descendants)"),
            DiveNumberFilter(self, "Dive number"),
            ChiefScientistFilter(self, "Chief scientist"),
            PlatformFilter(self, "Platform"),
            ObserverFilter(self, "Observer"),
            ImagedMomentUUIDFilter(self, "Imaged moment UUID"),
            ObservationUUIDFilter(self, "Observation UUID"),
            AssociationUUIDFilter(self, "Association UUID"),
            ImageReferenceUUIDFilter(self, "Image reference UUID"),
            VideoReferenceUUIDFilter(self, "Video reference UUID"),
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

        # Create dialog button box (just Ok button)
        self.dialog_buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok)

        # Arrange
        self.layout().addWidget(self.button_bar)
        self.layout().addWidget(self.result_list_view)
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

    def constraints_dict(self):
        d = {}
        for constraint in self.result_list_model.constraints:
            if constraint.key not in d:
                d[constraint.key] = []
            d[constraint.key].append(constraint.value)
        return d
