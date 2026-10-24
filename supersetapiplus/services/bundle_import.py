"""Import of an export bundle one object at a time, in dependency order, with a checkpoint.

``client.assets.import_file`` sends a whole bundle in one request: one failing object fails all of them.
``client.bundle_import.import_objects`` splits the bundle (an export of /assets/, /dashboard/, /chart/...)
into one bundle per object, with the files of its dependencies, and sends each one to the import endpoint
of its type: databases, then datasets, charts and dashboards. A dependency already in Superset is reused
(Superset imports dependencies without overwriting them); `overwrite` applies to the object itself, and an
object that exists when `overwrite` is false is reported as existing, not as a failure.
"""
from __future__ import annotations

import io
import json
import tempfile
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

import yaml

from supersetapiplus.exceptions import BadRequestError
from supersetapiplus.resources.repository import ApiModelFactories

# Bundle folder -> `type` of metadata.yaml in a bundle of that resource (superset/commands/*/export.py).
BUNDLE_TYPES = {"databases": "Database", "datasets": "SqlaTable", "charts": "Slice", "dashboards": "Dashboard"}
IMPORT_ORDER = ("databases", "datasets", "charts", "dashboards")
# Error of ImportModelsCommand (superset/commands/importers/v1/__init__.py) for an object that exists.
ALREADY_EXISTS = "already exists and `overwrite=true` was not passed"


class _Client(Protocol):
    """What the service needs from SupersetClient (services must not import the client layer)."""

    @property
    def databases(self) -> ApiModelFactories: ...

    @property
    def datasets(self) -> ApiModelFactories: ...

    @property
    def charts(self) -> ApiModelFactories: ...

    @property
    def dashboards(self) -> ApiModelFactories: ...


@dataclass
class ImportReport:
    """Bundle files imported, already in Superset (not overwritten), skipped (imported by an earlier run, per
    the checkpoint) and failed (with the error)."""
    imported: list[str] = field(default_factory=list)
    existing: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: dict[str, str] = field(default_factory=dict)


class BundleImport:
    """Import of a bundle one object at a time (available as `client.bundle_import`)."""

    def __init__(self, client: _Client) -> None:
        self.client = client

    def import_objects(self, bundle: str | Path, overwrite: bool = False, passwords: dict[str, str] | None = None,
                       continue_on_error: bool = False, checkpoint: str | Path | None = None) -> ImportReport:
        """
        Imports each object of `bundle` with its dependencies, in the order databases, datasets, charts,
        dashboards.

        Args:
            bundle: export ZIP (assets or a resource export).
            overwrite: replace objects that already exist (their dependencies are never overwritten).
            passwords: database passwords by database name, as in ``import_file``.
            continue_on_error: record a failed object in the report and go on; otherwise raise its error.
            checkpoint: JSON file with the files already imported; they are skipped, and each import is
                added to it, so a run can be resumed.
        """
        files = _read_bundle(bundle)
        done = set(json.loads(Path(checkpoint).read_text())) if checkpoint and Path(checkpoint).exists() else set()
        report = ImportReport()
        for name in _in_import_order(files):
            if name in done:
                report.skipped.append(name)
                continue
            try:
                self._import_one(name, files, overwrite, passwords)
                report.imported.append(name)
            except BadRequestError as error:
                if ALREADY_EXISTS not in str(error):
                    if not continue_on_error:
                        raise
                    report.failed[name] = str(error)
                    continue
                report.existing.append(name)
            done.add(name)
            if checkpoint:
                Path(checkpoint).write_text(json.dumps(sorted(done), indent=1))
        return report

    def _import_one(self, name: str, files: dict[str, bytes], overwrite: bool,
                    passwords: dict[str, str] | None) -> None:
        folder = name.split("/", 1)[0]
        repository: ApiModelFactories = getattr(self.client, folder)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / f"{Path(name).stem}.zip"
            path.write_bytes(_object_bundle(name, files))
            repository.import_file(path, overwrite=overwrite, passwords=passwords)


def _read_bundle(bundle: str | Path) -> dict[str, bytes]:
    """Files of the bundle by path relative to its root folder (``databases/x.yaml``...)."""
    with zipfile.ZipFile(bundle) as archive:
        return {name.partition("/")[2]: archive.read(name) for name in archive.namelist() if name.partition("/")[2]}


def _in_import_order(files: dict[str, bytes]) -> list[str]:
    return [name for folder in IMPORT_ORDER for name in sorted(files) if name.startswith(f"{folder}/")]


def _object_bundle(name: str, files: dict[str, bytes]) -> bytes:
    """Bundle of one object: its file, the files of its dependencies and a metadata.yaml of its type."""
    by_uuid = {str(_yaml(content).get("uuid")): path for path, content in files.items()
               if path.endswith(".yaml") and path != "metadata.yaml"}
    included = _with_dependencies(name, files, by_uuid)
    metadata = {**_yaml(files.get("metadata.yaml", b"{}")), "type": BUNDLE_TYPES[name.split("/", 1)[0]]}
    root = f"{Path(name).stem}_export"
    content = io.BytesIO()
    with zipfile.ZipFile(content, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(f"{root}/metadata.yaml", yaml.safe_dump(metadata, sort_keys=False))
        for path in sorted(included):
            archive.writestr(f"{root}/{path}", files[path])
    return content.getvalue()


def _with_dependencies(name: str, files: dict[str, bytes], by_uuid: dict[str, str]) -> set[str]:
    """`name` and, transitively, the files it refers to (database_uuid, dataset_uuid, chart uuids)."""
    included: set[str] = set()
    pending = [name]
    while pending:
        path = pending.pop()
        if path in included:
            continue
        included.add(path)
        pending.extend(by_uuid[uuid] for uuid in _referenced_uuids(_yaml(files[path])) if uuid in by_uuid)
    return included


def _referenced_uuids(config: dict[str, Any]) -> list[str]:
    uuids = [str(config[key]) for key in ("database_uuid", "dataset_uuid") if config.get(key)]
    for component in (config.get("position") or {}).values():
        if isinstance(component, dict) and component.get("type") == "CHART":
            uuids.append(str((component.get("meta") or {}).get("uuid")))
    return uuids


def _yaml(content: bytes) -> dict[str, Any]:
    data = yaml.safe_load(content)
    return data if isinstance(data, dict) else {}
