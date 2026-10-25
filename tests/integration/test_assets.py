"""Assets export and import (/api/v1/assets/) on the real Superset."""
import os
import zipfile

import pytest

from supersetapiplus.exceptions import UnprocessableEntityError

from .conftest import name_filter, new_client


def own_bundle(full_export, target, names: list[str]) -> list[str]:
    """Bundle with only the objects of this test: the full export depends on what the instance holds
    (e.g. the sqlite `examples` database, which Superset refuses to import)."""
    with zipfile.ZipFile(full_export) as source, zipfile.ZipFile(target, "w") as bundle:
        kept = [n for n in source.namelist() if n.endswith("/metadata.yaml") or any(name in n for name in names)]
        for name in kept:
            bundle.writestr(name, source.read(name))
    return kept


def test_assets_export_and_import_from_the_given_path(client, database, dataset, add_chart, cleanup, tmp_path):
    chart = add_chart()
    full, archive = tmp_path / "full.zip", tmp_path / "subdir" / "assets.zip"
    archive.parent.mkdir()

    client.assets.export(full)
    kept = own_bundle(full, archive, [database.database_name, chart.slice_name])
    assert any("/charts/" in n for n in kept) and any("/databases/" in n for n in kept)
    client.charts.delete(chart.id)

    # Exported database URIs have the password masked; the import asks for it per database file.
    database_files = [n.split("/", 1)[1] for n in kept if "/databases/" in n]
    passwords = {name: os.environ.get("POSTGRES_PASSWORD", "") for name in database_files}
    assert client.assets.import_file(archive, passwords=passwords) is True

    imported = client.charts.find(name_filter("slice_name", chart.slice_name), columns=["id"])
    for item in imported:  # the import may assign a new id
        cleanup.chart(item.id)
    assert len(imported) == 1


def test_import_replays_the_archive_after_renewing_credentials(client, add_chart, cleanup, tmp_path):
    chart = add_chart()
    archive = tmp_path / "chart.zip"
    client.charts.export([chart.id], archive)
    client.charts.delete(chart.id)
    importing = new_client(session_mode=False)
    session = importing.session
    statuses = []

    def record(response, *args, **kwargs):
        if "/chart/import/" in response.url:
            statuses.append(response.status_code)

    session.hooks["response"].append(record)
    session.headers["Authorization"] = "Bearer malformed"

    try:
        assert importing.charts.import_file(archive) is True
    finally:
        imported = client.charts.find(name_filter("slice_name", chart.slice_name), columns=["id"])
        for item in imported:
            cleanup.chart(item.id)
    assert len(imported) == 1
    assert statuses == [422, 200]


@pytest.fixture(autouse=True)
def _password_needed():
    if not os.environ.get("POSTGRES_PASSWORD"):
        pytest.skip("needs POSTGRES_PASSWORD of the test database to import it back")


def test_charts_exported_in_batches_and_imported_one_object_at_a_time(client, database, add_chart, cleanup,
                                                                      tmp_path):
    charts = [add_chart() for _ in range(3)]
    archive, checkpoint = tmp_path / "charts.zip", tmp_path / "checkpoint.json"

    client.charts.export([c.id for c in charts], archive, batch_size=2)  # two requests, one bundle
    with zipfile.ZipFile(archive) as bundle:
        files = [n.split("/", 1)[1] for n in bundle.namelist()]
    assert sorted(f for f in files if f.startswith("charts/")) == sorted(
        f for f in files if f.startswith("charts/") and any(c.slice_name in f for c in charts))
    assert len([f for f in files if f.startswith("charts/")]) == 3 and len(files) == len(set(files))
    for chart in charts:
        client.charts.delete(chart.id)

    passwords = {f.split("/")[1][:-len(".yaml")]: os.environ.get("POSTGRES_PASSWORD", "")
                 for f in files if f.startswith("databases/")}
    report = client.bundle_import.import_objects(archive, passwords=passwords, checkpoint=checkpoint)
    for chart in charts:
        for item in client.charts.find(name_filter("slice_name", chart.slice_name), columns=["id"]):
            cleanup.chart(item.id)
    chart_files = sorted(f for f in files if f.startswith("charts/"))
    # The database and dataset were kept: they exist and are not overwritten; the charts are imported.
    assert (sorted(report.imported), sorted(report.existing), report.failed) == (
        chart_files, sorted(f for f in files if f.startswith(("databases/", "datasets/"))), {})

    again = client.bundle_import.import_objects(archive, passwords=passwords, checkpoint=checkpoint)
    assert (again.imported, sorted(again.skipped)) == ([], sorted(report.imported + report.existing))

    # An invalid object fails alone: recorded with continue_on_error, raised without it.
    broken = tmp_path / "broken.zip"
    with zipfile.ZipFile(archive) as source, zipfile.ZipFile(broken, "w") as target:
        for name in source.namelist():
            target.writestr(name, source.read(name))
        target.writestr(source.namelist()[0].split("/")[0] + "/charts/broken.yaml", "slice_name: broken\n")
    result = client.bundle_import.import_objects(broken, passwords=passwords, continue_on_error=True)
    assert list(result.failed) == ["charts/broken.yaml"] and sorted(result.existing) == sorted(
        f for f in files if f != "metadata.yaml")
    with pytest.raises(UnprocessableEntityError):
        client.bundle_import.import_objects(broken, passwords=passwords)
