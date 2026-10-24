"""Export bundles (merging batches, one bundle per object) and lazy pagination, without HTTP."""
import io
import zipfile

import yaml

from supersetapiplus.datasets import Datasets
from supersetapiplus.resources.repository import merge_bundles
from supersetapiplus.services.bundle_import import _in_import_order, _object_bundle, _read_bundle

DB = {"database_name": "db", "uuid": "u-db"}
DS = {"table_name": "ds", "uuid": "u-ds", "database_uuid": "u-db"}


def chart(n: int) -> dict:
    return {"slice_name": f"c{n}", "uuid": f"u-c{n}", "dataset_uuid": "u-ds"}


def bundle(root: str, files: dict) -> bytes:
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w") as archive:
        archive.writestr(f"{root}/metadata.yaml", yaml.safe_dump({"version": "1.0.0", "type": "Slice"}))
        for path, data in files.items():
            archive.writestr(f"{root}/{path}", yaml.safe_dump(data))
    return content.getvalue()


def names(content: bytes) -> list:
    return sorted(zipfile.ZipFile(io.BytesIO(content)).namelist())


def test_batches_are_merged_under_one_root_with_shared_dependencies_once():
    deps = {"databases/db.yaml": DB, "datasets/db/ds.yaml": DS}
    merged = merge_bundles([bundle("chart_export_1", {**deps, "charts/c1.yaml": chart(1)}),
                            bundle("chart_export_2", {**deps, "charts/c2.yaml": chart(2)})])

    assert names(merged) == ["chart_export_1/charts/c1.yaml", "chart_export_1/charts/c2.yaml",
                             "chart_export_1/databases/db.yaml", "chart_export_1/datasets/db/ds.yaml",
                             "chart_export_1/metadata.yaml"]


def test_each_object_is_imported_in_dependency_order_with_its_dependencies(tmp_path):
    dashboard = {"dashboard_title": "d", "uuid": "u-d",
                 "position": {"CHART-1": {"type": "CHART", "meta": {"uuid": "u-c1"}}, "ROOT_ID": {"type": "ROOT"}}}
    path = tmp_path / "assets.zip"
    path.write_bytes(bundle("assets_export", {"dashboards/d.yaml": dashboard, "charts/c1.yaml": chart(1),
                                              "charts/c2.yaml": chart(2), "datasets/db/ds.yaml": DS,
                                              "databases/db.yaml": DB}))
    files = _read_bundle(path)

    assert _in_import_order(files) == ["databases/db.yaml", "datasets/db/ds.yaml", "charts/c1.yaml",
                                       "charts/c2.yaml", "dashboards/d.yaml"]
    one = _object_bundle("dashboards/d.yaml", files)
    assert names(one) == ["d_export/charts/c1.yaml", "d_export/dashboards/d.yaml", "d_export/databases/db.yaml",
                          "d_export/datasets/db/ds.yaml", "d_export/metadata.yaml"]
    metadata = yaml.safe_load(zipfile.ZipFile(io.BytesIO(one)).read("d_export/metadata.yaml"))
    assert metadata == {"version": "1.0.0", "type": "Dashboard"}
    assert names(_object_bundle("databases/db.yaml", files)) == ["db_export/databases/db.yaml",
                                                                 "db_export/metadata.yaml"]


def test_iter_all_requests_a_page_only_when_the_previous_one_was_consumed(monkeypatch):
    repository = Datasets(client=None)
    requested = []

    def find(filter, columns, page_size, page, *args):
        requested.append(page)
        return list(range(page * page_size, min((page + 1) * page_size, 5)))

    monkeypatch.setattr(repository, "find", find)
    items = repository.iter_all(page_size=2)

    assert next(items) == 0 and requested == [0]
    assert list(items) == [1, 2, 3, 4] and requested == [0, 1, 2]
    assert repository.find_all(page_size=2) == [0, 1, 2, 3, 4]
