from vars_gridview.lib.m3.query import QueryConstraint


class ORList:
    @staticmethod
    def typestr(value):
        if isinstance(value, str):
            return f"'{value}'"
        elif isinstance(value, int):
            return f"{value}"
        else:
            raise ValueError("Unsupported type: {}".format(type(value)))

    def __init__(self, key: str, values=None):
        self._key = key
        self._values = values or []

    def __iadd__(self, value):
        self._values.append(value)
        return self

    @property
    def form(self):
        return (
            "("
            + " OR ".join(
                [
                    "{} = {}".format(self._key, ORList.typestr(value))
                    for value in self._values
                ]
            )
            + ")"
        )

    @property
    def values(self):
        return self._values

    def to_constraint(self) -> QueryConstraint:
        constraint = QueryConstraint(
            column=self._key,
        )
        if len(self._values) == 1:
            constraint.equals = self._values[0]
        else:
            constraint.in_ = self._values
        return constraint


class ConstraintSpec:
    def __init__(self, lists: list[ORList] = None):
        self._lists = lists or []

    @property
    def form(self):
        if len(self._lists) == 0:
            return "1=1"  # Accept anything
        return " AND ".join(
            [list_.form for list_ in self._lists]
        )  # AND together all forms

    @property
    def values(self):
        return [
            value for list_ in self._lists for value in list_.values
        ]  # Flatten all values

    def to_constraints(self) -> list[QueryConstraint]:
        return [list_.to_constraint() for list_ in self._lists]

    @classmethod
    def from_dict(cls, d):
        return cls(lists=[ORList(key, values) for key, values in d.items()])
