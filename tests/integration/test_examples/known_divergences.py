"""Example charts whose copy returns other data than Explore shows for the original, each with its GitHub issues.

The reference is the query Explore sends (``example_query_contexts_6.1.0.json``). Keyed by the chart UUID of the
examples (stable across stacks). The data check reports these charts as KnownDivergenceWarning instead of failing,
and fails when one of them returns the data of the original: remove it from here when its issues are fixed.

Empty since issues #23-#26 (the params normalized as Explore does, supersetapiplus/charts/explore.py) removed the
32 charts listed when the reference became the Explore capture.
"""
KNOWN_DATA_DIVERGENCES: dict[str, tuple[int, ...]] = {}
