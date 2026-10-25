"""Checks run on each example dashboard shipped with Superset (`superset load_examples`); one module per dashboard.

The examples are public data every Superset instance can load, made with the Superset editor: chart types, layouts
and settings the synthetic payloads of the unit tests do not cover. For each example dashboard:

1. round trip (read only): the dashboard and each chart placed on it, read with the library and re-serialized with
   ``to_json()``, give what Superset stored;
2. chart copies: each chart of a modeled type is copied through the library (read model, new name, query context
   derived from its params) and the copy returns the data the original shows in the UI: the query the UI builds
   from the original params (the library port of the frontend buildQuery) sent to ``/api/v1/chart/data``. The
   examples store no ``query_context``, so ``/chart/{id}/data`` of the original is not available in 6.1.0;
3. dashboard copy: a dashboard created through the library with the original layout and ``json_metadata``, chart
   ids remapped to the copies, reads back like the original, and the copies are associated with it.

Charts of a viz_type the library does not model are reported (NotCoveredWarning) and copied through the raw API, so
the dashboard copy points only to copies and the examples are not changed. Needs the test stack with ``SUPERSET_LOAD_EXAMPLES=1`` (loading takes a few minutes); skipped on an
instance without the example dashboard. The copies use the test prefix and are removed at the end of the module.
"""
import copy
import json
import warnings
from pathlib import Path
from typing import Any, ClassVar

import pytest

from supersetapiplus.dashboards.dashboards import Dashboard
from supersetapiplus.exceptions import UnsupportedTypeError

from ..conftest import Cleanup, unique_name

LAYOUTS = Path(__file__).parents[2] / "fixtures" / "example_layouts_6.1.0.json"
EXAMPLE_TITLES = {layout["dashboard_title"] for layout in json.loads(LAYOUTS.read_text())["layouts"].values()}
CHART_FIELDS = ("params", "query_context")
DASHBOARD_FIELDS = ("position_json", "json_metadata")


class NotCoveredWarning(UserWarning):
    """An example chart of a viz_type the library does not model yet."""


# --- comparison ---------------------------------------------------------------------------------

def parsed(value: Any) -> Any:
    """A JSON field as data: its text parsed (null stays None)."""
    return json.loads(value) if isinstance(value, str) else value


def differences(stored: Any, written: Any, path: str = "") -> list[str]:
    """Paths where `written` differs from `stored`: lost and added keys, changed values (5 and 5.0 differ)."""
    if isinstance(stored, dict) and isinstance(written, dict):
        found = [f"{path}.{key}: lost" for key in stored.keys() - written.keys()]
        found += [f"{path}.{key}: added" for key in written.keys() - stored.keys()]
        for key in stored.keys() & written.keys():
            found += differences(stored[key], written[key], f"{path}.{key}")
        return found
    if isinstance(stored, list) and isinstance(written, list) and len(stored) == len(written):
        return [diff for index, (a, b) in enumerate(zip(stored, written, strict=True))
                for diff in differences(a, b, f"{path}[{index}]")]
    return [] if stored == written and type(stored) is type(written) else [f"{path}: {stored!r} -> {written!r}"]


def field_differences(stored: dict[str, Any], written: dict[str, Any], fields: tuple[str, ...]) -> list[str]:
    """Differences of the JSON `fields` of a resource, per field."""
    found = []
    for field in fields:
        if field not in stored:
            found += [f"{field}: added"] if field in written else []
        elif field not in written:
            found.append(f"{field}: lost")
        else:
            found += [f"{field}{diff}" for diff in differences(parsed(stored[field]), parsed(written[field]))]
    return found


def stored(client, repository, pk: int) -> dict[str, Any]:
    """The object as Superset returns it (GET of the resource)."""
    return client.get(client.join_urls(repository.base_url, pk)).json()["result"]


# --- id remapping (as superset/commands/dashboard/importers/v1/utils.py, 6.1.0) -------------------------------

def remap_ids(ids: list[Any], id_map: dict[int, int]) -> list[Any]:
    return [id_map.get(pk, pk) for pk in ids]


def remap_keys(mapping: dict[str, Any], id_map: dict[int, int]) -> dict[str, Any]:
    return {str(id_map.get(int(key), key)) if key.isdigit() else key: value for key, value in mapping.items()}


def remap_scope(item: dict[str, Any], id_map: dict[int, int]) -> None:
    """`scope.excluded` and `chartsInScope` of a native filter or a cross-filter configuration."""
    scope = item.get("scope")
    if isinstance(scope, dict) and isinstance(scope.get("excluded"), list):
        scope["excluded"] = remap_ids(scope["excluded"], id_map)
    if isinstance(item.get("chartsInScope"), list):
        item["chartsInScope"] = remap_ids(item["chartsInScope"], id_map)


def remap_layout(position: dict[str, Any], id_map: dict[int, int], uuid_map: dict[str, str]) -> dict[str, Any]:
    """The layout with the CHART components pointing to the copies (`chartId` and `uuid`)."""
    position = copy.deepcopy(position)
    for component in position.values():
        if isinstance(component, dict) and component.get("type") == "CHART":
            meta = component["meta"]
            meta["chartId"] = id_map.get(meta.get("chartId"), meta.get("chartId"))
            if meta.get("uuid") in uuid_map:
                meta["uuid"] = uuid_map[meta["uuid"]]
    return position


def remap_metadata(metadata: dict[str, Any], id_map: dict[int, int]) -> dict[str, Any]:
    """The json_metadata with every chart id reference pointing to the copies."""
    metadata = copy.deepcopy(metadata)
    if isinstance(metadata.get("timed_refresh_immune_slices"), list):
        metadata["timed_refresh_immune_slices"] = remap_ids(metadata["timed_refresh_immune_slices"], id_map)
    for key in ("expanded_slices", "filter_scopes"):
        if isinstance(metadata.get(key), dict):
            metadata[key] = remap_keys(metadata[key], id_map)
    if isinstance(metadata.get("default_filters"), str):
        metadata["default_filters"] = json.dumps(remap_keys(json.loads(metadata["default_filters"]), id_map))
    for native_filter in metadata.get("native_filter_configuration") or []:
        remap_scope(native_filter, id_map)
    if isinstance(metadata.get("global_chart_configuration"), dict):
        remap_scope(metadata["global_chart_configuration"], id_map)
    if isinstance(metadata.get("chart_configuration"), dict):
        metadata["chart_configuration"] = remap_keys(metadata["chart_configuration"], id_map)
        for config in metadata["chart_configuration"].values():
            config["id"] = id_map.get(config.get("id"), config.get("id"))
            remap_scope(config.get("crossFilters") or {}, id_map)
    return metadata


# --- the checks ---------------------------------------------------------------------------------

class ExampleDashboardChecks:
    """The checks of one example dashboard; each test module subclasses it with the dashboard TITLE."""

    TITLE: ClassVar[str]

    @pytest.fixture(scope="class")
    @classmethod
    def original(cls, client) -> Dashboard:
        found = [dashboard.id for dashboard in client.dashboards.find_all(columns=["id", "dashboard_title"])
                 if dashboard.dashboard_title == cls.TITLE]
        if not found:
            pytest.skip(f"example dashboard {cls.TITLE!r} not loaded: start the stack with SUPERSET_LOAD_EXAMPLES=1")
        return client.dashboards.get(found[0])

    @pytest.fixture(scope="class")
    @classmethod
    def chart_ids(cls, client, original) -> dict[int, str]:
        """Charts placed on the dashboard: id -> viz_type."""
        url = client.join_urls(client.dashboards.base_url, original.id, "charts")
        return {chart["id"]: chart["form_data"].get("viz_type") for chart in client.get(url).json()["result"]}

    @pytest.fixture(scope="class")
    @classmethod
    def modeled(cls, client, chart_ids) -> dict[int, Any]:
        """The charts of a modeled viz_type, read with the library; the others are reported."""
        charts, not_covered = {}, {}
        for chart_id, viz_type in sorted(chart_ids.items()):
            try:
                charts[chart_id] = client.charts.get(chart_id)
            except UnsupportedTypeError:
                not_covered.setdefault(viz_type, []).append(chart_id)
        if not_covered:
            summary = ", ".join(f"{viz} ({len(ids)})" for viz, ids in sorted(not_covered.items()))
            warnings.warn(NotCoveredWarning(f"{cls.TITLE}: charts of viz_types without a model: {summary}"),
                          stacklevel=1)
        return charts

    @pytest.fixture(scope="class")
    @classmethod
    def removal(cls, client):
        tracker = Cleanup(client)
        yield tracker
        tracker.run()

    @pytest.fixture(scope="class")
    @classmethod
    def chart_copies(cls, client, modeled, removal) -> dict[int, int]:
        """Copies of the modeled charts, made through the library: original id -> copy id."""
        copies = {}
        for chart_id in modeled:
            chart = client.charts.get(chart_id)
            chart.id, chart.slice_name = None, unique_name(f"example-{chart_id}")
            chart.derive_query_context()
            copies[chart_id] = removal.chart(client.charts.add(chart))
        return copies

    @pytest.fixture(scope="class")
    @classmethod
    def unmodeled_copies(cls, client, chart_ids, modeled, removal) -> dict[int, int]:
        """Copies of the charts of unmodeled viz_types, made through the raw API: original id -> copy id."""
        copies = {}
        for chart_id in set(chart_ids) - set(modeled):
            source = stored(client, client.charts, chart_id)
            payload = {key: source[key] for key in ("viz_type", "params", "datasource_id", "datasource_type")}
            payload["slice_name"] = unique_name(f"example-{chart_id}")
            copies[chart_id] = removal.chart(client.post(client.charts.base_url, json=payload).json()["id"])
        return copies

    @pytest.fixture(scope="class")
    @classmethod
    def dashboard_copy(cls, client, original, chart_copies, unmodeled_copies, removal) -> tuple[int, dict[str, Any]]:
        """A dashboard created through the library with the original layout and settings, ids remapped to the
        copies, and the copies associated with it; returns its id and the expected (remapped) JSON fields."""
        id_map = {**chart_copies, **unmodeled_copies}
        uuids = cls.chart_uuids(client, [*id_map, *id_map.values()])
        uuid_map = {uuids[old]: uuids[new] for old, new in id_map.items() if old in uuids and new in uuids}
        source = stored(client, client.dashboards, original.id)
        expected = {"position_json": remap_layout(parsed(source["position_json"]), id_map, uuid_map),
                    "json_metadata": remap_metadata(parsed(source["json_metadata"]), id_map)}
        dashboard = Dashboard.from_json({"dashboard_title": unique_name("example-dashboard"), "css": source.get("css"),
                                         **{key: json.dumps(value) for key, value in expected.items()}})
        copy_id = removal.dashboard(client.dashboards.add(dashboard))
        client.dashboards.attach_charts(client.dashboards.get(copy_id))
        return copy_id, expected

    @staticmethod
    def chart_uuids(client, ids: list[int]) -> dict[int, str]:
        query = f"(columns:!(id,uuid),filters:!((col:id,opr:in,value:!({','.join(map(str, ids))}))),page_size:100)"
        return {item["id"]: item["uuid"] for item in client.get(client.charts.base_url, params={"q": query}).json()["result"]}

    # --- round trip (read only) ---

    def test_dashboard_round_trips_without_loss(self, client, original):
        written = original.to_json()

        assert field_differences(stored(client, client.dashboards, original.id), written, DASHBOARD_FIELDS) == []

    def test_charts_round_trip_without_loss(self, client, modeled):
        found = {}
        for chart_id, chart in modeled.items():
            try:
                diffs = field_differences(stored(client, client.charts, chart_id), chart.to_json(), CHART_FIELDS)
            except Exception as error:  # every chart is reported, not only the first that fails
                diffs = [f"to_json raised {type(error).__name__}: {error}"]
            if diffs:
                found[f"{chart_id} {chart.viz_type} {chart.slice_name!r}"] = diffs

        assert found == {}

    # --- copies built by the library ---

    def test_chart_copies_keep_the_params_and_return_the_data_of_the_original(self, client, modeled, chart_copies):
        found = {}
        for chart_id, copy_id in chart_copies.items():
            diffs = differences(parsed(stored(client, client.charts, chart_id)["params"]),
                                parsed(stored(client, client.charts, copy_id)["params"]))
            shown = client.post(client.join_urls(client.charts.base_url, "data"),
                                json=modeled[chart_id].ui_query_context()).json()["result"]
            if [result["data"] for result in shown] != [result["data"] for result in client.charts.get_chart_data(copy_id)]:
                diffs.append("data differs from the original")
            if diffs:
                found[f"{chart_id} {modeled[chart_id].viz_type}"] = diffs

        assert found == {}

    def test_dashboard_copy_reads_back_like_the_original(self, client, original, chart_copies, unmodeled_copies,
                                                          dashboard_copy):
        copy_id, expected = dashboard_copy

        read = stored(client, client.dashboards, copy_id)

        assert field_differences(expected, read, DASHBOARD_FIELDS) == []
        assert client.dashboards.get(copy_id).position_json.problems() == original.position_json.problems()
        url = client.join_urls(client.dashboards.base_url, copy_id, "charts")
        assert {chart["id"] for chart in client.get(url).json()["result"]} == {*chart_copies.values(),
                                                                              *unmodeled_copies.values()}
