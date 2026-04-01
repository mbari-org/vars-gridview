"""Tabular-text parsing helpers."""

from __future__ import annotations


def parse_tsv(data: str) -> tuple[list[str], list[list[str]]]:
    """Parse a TSV string into ``(header, rows)``."""
    lines = data.split("\n")
    header = lines[0].split("\t")
    rows = [line.split("\t") for line in lines[1:] if line]
    return header, rows


__all__ = ["parse_tsv"]
