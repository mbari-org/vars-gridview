"""
M3 querying utilities.
"""

from typing import List

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


def merge_constraints(constraints: List[QueryConstraint]) -> List[QueryConstraint]:
    """
    Merge constraints on the same column into a single constraint.

    Behavior implemented:

    - Constraints are grouped by `column`.
    - Multiple `equals` and `in_` values are combined into a single `equals` (if one) or
      `in_` (if many) using the union while preserving first-seen order.
    - Other constraint types are preserved as-is.

    Args:
        constraints (List[QueryConstraint]): List of constraints to merge.

    Returns:
        List[QueryConstraint]: Merged list of constraints.
    """
    # group constraints by column
    grouped: dict[str, list[QueryConstraint]] = {}
    for c in constraints:
        grouped.setdefault(c.column, []).append(c)

    merged: list[QueryConstraint] = []

    for column, group in grouped.items():
        # Collect possible values from equals and in_ constraints
        possible_values = set()
        for c in group:
            if c.equals is not None:
                possible_values.add(c.equals)
            elif c.in_ is not None:
                possible_values.update(c.in_)
            else:
                # Maintain other constraints as-is
                merged.append(c)

        # Merge possible values into a single equals or in_ constraint
        if possible_values:
            if len(possible_values) == 1:
                merged.append(
                    QueryConstraint(column=column, equals=possible_values.pop())
                )
            else:
                merged.append(QueryConstraint(column=column, in_=list(possible_values)))

    return merged
