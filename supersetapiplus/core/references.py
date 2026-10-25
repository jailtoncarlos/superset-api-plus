"""Types of the references to saved objects that the API takes across layers (no HTTP).

The dashboard layer cannot import the chart or dataset models (layer contracts of ``[tool.importlinter]``), so the
methods that place a chart or target a dataset take these structural types: a library ``Chart`` or a
``ChartRef`` satisfies :class:`SavedChart`, and a ``Dataset`` read from Superset satisfies :class:`SavedDataset`.
"""
from typing import Protocol, TypeAlias


class SavedChart(Protocol):
    """A chart saved in Superset: a library ``Chart`` or a ``ChartRef`` (its id and its name)."""

    @property
    def id(self) -> int | None: ...

    @property
    def slice_name(self) -> str: ...


class SavedDataset(Protocol):
    """A dataset saved in Superset, e.g. a ``Dataset`` read with ``client.datasets.get``."""

    @property
    def id(self) -> int | None: ...


#: A dataset given as a saved dataset, its id, or its uuid (the form of the import/export bundles).
DatasetRef: TypeAlias = SavedDataset | int | str
