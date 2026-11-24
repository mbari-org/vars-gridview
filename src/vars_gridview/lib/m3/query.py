"""M3 querying data structures and utilities.

This module defines the :class:`QueryConstraint` and :class:`QueryRequest`
Pydantic dataclasses that are serialised to JSON and sent to the Annosaurus
``/query/run`` and related endpoints.  It also provides :func:`merge_constraints`
for collapsing duplicate column constraints before dispatch, and
:func:`split_where` / :func:`page_slices` for running a query whose ``in``
list is too long for one database statement.
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


# Annosaurus binds every value of an ``in`` list as its own SQL parameter, and
# SQL Server refuses a statement with more than 2,100. Stay well under that so
# the other constraints, paging and any driver extras still fit.
MAX_QUERY_PARAMETERS = 2000


def _parameter_count(constraint: QueryConstraint) -> int:
    """How many SQL parameters Annosaurus binds for *constraint*."""
    if constraint.in_ is not None:
        return len(constraint.in_)
    if constraint.between is not None or constraint.minmax is not None:
        return 2
    if constraint.isnull is not None:
        return 0
    return 1


def split_where(
    where: list[QueryConstraint],
    max_parameters: int = MAX_QUERY_PARAMETERS,
) -> list[list[QueryConstraint]]:
    """Split *where* into constraint lists that each fit in one statement.

    When the constraints need more than *max_parameters* parameters, the
    longest ``in`` list is sorted and cut into pieces, and each returned list
    holds one piece plus every other constraint unchanged. The rows matching
    *where* are then the rows matching any of the returned lists, with no row
    in two of them.

    Args:
        where: Constraints that are AND-combined.
        max_parameters: Parameter budget for one statement.

    Returns:
        ``[where]`` when it already fits, otherwise one list per piece.

    Raises:
        ValueError: If the constraints other than the longest ``in`` list
            already use the whole budget.
    """
    total = sum(_parameter_count(c) for c in where)
    if total <= max_parameters:
        return [where]
    longest = max(
        (c for c in where if c.in_ is not None),
        key=lambda c: len(c.in_),
        default=None,
    )
    if longest is None:
        raise ValueError("The query has too many constraints for one statement.")
    others = total - len(longest.in_)
    room = max_parameters - others
    if room < 1:
        raise ValueError(
            f"The query's lists add up to {total:,} values, and only the "
            f"longest one can be split. Shorten the other lists to under "
            f"{max_parameters:,} values in all."
        )
    values = sorted(longest.in_)
    pieces = [values[i : i + room] for i in range(0, len(values), room)]
    return [
        [
            QueryConstraint(column=longest.column, in_=piece) if c is longest else c
            for c in where
        ]
        for piece in pieces
    ]


def page_slices(
    counts: list[int], offset: int, limit: int
) -> list[tuple[int, int, int]]:
    """Map one page of the combined results onto the split queries.

    The split queries' results are treated as concatenated in order.

    Args:
        counts: Row count of each split query.
        offset: Offset of the page in the combined results.
        limit: Page length.

    Returns:
        ``(query index, offset, limit)`` for each split query the page
        touches, in order.
    """
    slices: list[tuple[int, int, int]] = []
    start = 0
    end_of_page = offset + limit
    for index, count in enumerate(counts):
        end = start + count
        lo, hi = max(offset, start), min(end_of_page, end)
        if lo < hi:
            slices.append((index, lo - start, hi - lo))
        if end >= end_of_page:
            break
        start = end
    return slices


__all__ = [
    "MAX_QUERY_PARAMETERS",
    "QueryConstraint",
    "QueryRequest",
    "merge_constraints",
    "page_slices",
    "split_where",
]
