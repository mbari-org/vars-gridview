"""
M3 querying utilities.
"""

from pydantic.dataclasses import dataclass


@dataclass
class QueryConstraint:
    column: str
    between: list[str] | None = None
    contains: str | None = None
    equals: str | None = None
    in_: list[str] | None = None
    isnull: bool | None = None
    like: str | None = None
    max: float | None = None
    min: float | None = None
    minmax: list[float] | None = None

    def to_dict(self, skip_null: bool = True) -> dict:
        d = {
            "column": self.column,
            "between": self.between,
            "contains": self.contains,
            "equals": self.equals,
            "in": self.in_,
            "isnull": self.isnull,
            "like": self.like,
            "max": self.max,
            "min": self.min,
            "minmax": self.minmax,
        }

        if skip_null:
            for key in list(d.keys()):
                if d[key] is None:
                    del d[key]

        return d


@dataclass
class QueryRequest:
    select: list[str] | None = None
    distinct: bool | None = None
    where: list[QueryConstraint] | None = None
    order_by: list[str] | None = None
    limit: int | None = None
    offset: int | None = None
    concurrent_observations: bool | None = None
    related_associations: bool | None = None
    strict: bool | None = None

    def to_dict(self, skip_null: bool = True) -> dict:
        d = {
            "select": self.select,
            "distinct": self.distinct,
            "where": [
                constraint.to_dict(skip_null=skip_null) for constraint in self.where
            ]
            if self.where
            else None,
            "orderBy": self.order_by,
            "limit": self.limit,
            "offset": self.offset,
            "concurrentObservations": self.concurrent_observations,
            "relatedAssociations": self.related_associations,
            "strict": self.strict,
        }

        if skip_null:
            for key in list(d.keys()):
                if d[key] is None:
                    del d[key]

        return d


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

    def to_constraints(self) -> list[QueryConstraint]:
        return [list_.to_constraint() for list_ in self._lists]

    @classmethod
    def from_dict(cls, d):
        return cls(lists=[ORList(key, values) for key, values in d.items()])
