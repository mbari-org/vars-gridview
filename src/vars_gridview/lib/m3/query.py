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


def parse_tsv(data: str) -> tuple[list[str], list[list[str]]]:
    """
    Parse a TSV string into a header and rows.

    Args:
        data (str): TSV data.

    Returns:
        tuple[list[str], list[list[str]]]: Header and rows.
    """
    lines = data.split("\n")
    header = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:] if line]
    return header, rows
