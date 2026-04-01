"""M3 querying data structures and utilities.

This module defines the :class:`QueryConstraint` and :class:`QueryRequest`
Pydantic dataclasses that are serialised to JSON and sent to the Annosaurus
``/query/run`` and related endpoints.  It also provides :func:`merge_constraints`
for collapsing duplicate column constraints before dispatch.
"""

from __future__ import annotations

from pydantic.dataclasses import dataclass


@dataclass
class QueryConstraint:
    """A single filtering constraint applied to one column.

    Attributes:
        column: The column name to filter on.
        between: Inclusive range expressed as ``[low, high]`` strings.
        contains: Substring match (case-sensitive).
        equals: Exact equality match.
        in_: Membership test — serialised as ``"in"`` in the wire format.
        isnull: If ``True``, matches rows where the column is ``NULL``.
        like: SQL ``LIKE`` pattern.
        notlike: SQL ``NOT LIKE`` pattern.
        max: Upper bound (inclusive) for numeric columns.
        min: Lower bound (inclusive) for numeric columns.
        minmax: Two-element ``[min, max]`` numeric range shorthand.
    """

    column: str
    between: list[str] | None = None
    contains: str | None = None
    equals: str | None = None
    in_: list[str] | None = None
    isnull: bool | None = None
    like: str | None = None
    notlike: str | None = None
    max: float | None = None
    min: float | None = None
    minmax: list[float] | None = None

    def to_dict(self, skip_null: bool = True) -> dict:
        """Serialise this constraint to a wire-format dictionary.

        Note that the ``in_`` attribute is serialised as ``"in"`` to match
        the Annosaurus API.

        Args:
            skip_null: When ``True`` (default), ``None``-valued keys are
                omitted from the result.

        Returns:
            dict: Wire-format representation of this constraint.
        """
        d: dict = {
            "column": self.column,
            "between": self.between,
            "contains": self.contains,
            "equals": self.equals,
            "in": self.in_,
            "isnull": self.isnull,
            "like": self.like,
            "notlike": self.notlike,
            "max": self.max,
            "min": self.min,
            "minmax": self.minmax,
        }
        if skip_null:
            d = {k: v for k, v in d.items() if v is not None}
        return d


@dataclass
class QueryRequest:
    """A complete Annosaurus query request.

    Attributes:
        select: Columns to return; ``None`` means all columns.
        distinct: If ``True``, deduplicate result rows.
        where: List of :class:`QueryConstraint` conditions (AND-combined).
        order_by: Column names to sort by.
        limit: Maximum rows to return.
        offset: Row offset for pagination.
        concurrent_observations: Include concurrent observations.
        related_associations: Include related associations.
        strict: Strict mode flag.
    """

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
        """Serialise this request to a wire-format dictionary.

        Args:
            skip_null: When ``True`` (default), ``None``-valued keys are
                omitted from the result.

        Returns:
            dict: Wire-format representation of this request.
        """
        d: dict = {
            "select": self.select,
            "distinct": self.distinct,
            "where": (
                [c.to_dict(skip_null=skip_null) for c in self.where]
                if self.where
                else None
            ),
            "orderBy": self.order_by,
            "limit": self.limit,
            "offset": self.offset,
            "concurrentObservations": self.concurrent_observations,
            "relatedAssociations": self.related_associations,
            "strict": self.strict,
        }
        if skip_null:
            d = {k: v for k, v in d.items() if v is not None}
        return d


def merge_constraints(constraints: list[QueryConstraint]) -> list[QueryConstraint]:
    """Merge constraints on the same column into a single constraint.

    Groups constraints by ``column``.  ``equals`` and ``in_`` values for the
    same column are unioned into a single ``equals`` (when one unique value
    results) or ``in_`` (when many).  All other constraint types are kept
    verbatim.

    Args:
        constraints: List of constraints to merge.

    Returns:
        Merged list of constraints with at most one equality constraint per
        column.
    """
    grouped: dict[str, list[QueryConstraint]] = {}
    for c in constraints:
        grouped.setdefault(c.column, []).append(c)

    merged: list[QueryConstraint] = []
    for column, group in grouped.items():
        possible_values: set[str] = set()
        for c in group:
            if c.equals is not None:
                possible_values.add(c.equals)
            elif c.in_ is not None:
                possible_values.update(c.in_)
            else:
                merged.append(c)

        if possible_values:
            if len(possible_values) == 1:
                merged.append(
                    QueryConstraint(column=column, equals=possible_values.pop())
                )
            else:
                merged.append(QueryConstraint(column=column, in_=list(possible_values)))

    return merged


__all__ = ["QueryConstraint", "QueryRequest", "merge_constraints"]
