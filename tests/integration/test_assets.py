"""Assets export and import (/api/v1/assets/) on the real Superset."""
import os
import zipfile

import pytest

from .conftest import name_filter


def own_bundle(full_export, target, names: list[str]) -> list[str]:
    """Bundle with only the objects of this test: the full export depends on what the instance holds
    (e.g. the sqlite `examples` database, which Superset refuses to import)."""
    with zipfile.ZipFile(full_export) as source, zipfile.ZipFile(target, "w") as bundle:
        kept = [n for n in source.namelist() if n.endswith("/metadata.yaml") or any(name in n for name in names)]
        for name in kept:
            bundle.writestr(name, source.read(name))
    return kept


def test_assets_export_and_import_from_the_given_path(client, database, dataset, add_chart, tmp_path):
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

    imported = client.charts.find_one(name_filter("slice_name", chart.slice_name))
    try:
        assert imported.slice_name == chart.slice_name
    finally:
        client.charts.delete(imported.id)


@pytest.fixture(autouse=True)
def _password_needed():
    if not os.environ.get("POSTGRES_PASSWORD"):
        pytest.skip("needs POSTGRES_PASSWORD of the test database to import it back")
