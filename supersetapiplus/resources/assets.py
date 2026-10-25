"""Assets."""
import json
from pathlib import Path
from typing import Any


class Assets:
    """Export and import of complete bundles (dashboards, charts, datasets, databases) through /api/v1/assets."""
    endpoint = "assets/"

    def __init__(self, client: Any) -> None:
        self.client = client

    @property
    def base_url(self) -> str:
        """Base url for these objects."""
        url: str = self.client.join_urls(self.client.base_url, self.endpoint)
        return url

    @property
    def import_url(self) -> str:
        url: str = self.client.join_urls(self.base_url, "import/")
        return url

    @property
    def export_url(self) -> str:
        url: str = self.client.join_urls(self.base_url, "export/")
        return url

    def export(self, path: Path | str) -> None:
        """Export object into an importable file"""
        response = self.client.get(self.export_url)

        content_type = response.headers["content-type"].strip()
        if content_type.startswith("application/zip"):
            data = response.content
            with open(path, "wb") as f:
                f.write(data)
            return
        raise ValueError(f"Unknown content type {content_type}")

    def import_file(self, file_path: str | Path, passwords: dict[str, str] | None = None) -> bool:
        """Import a file on remote.

        :param file_path: Path to a JSON or ZIP file containing the import data
        :param passwords: JSON map of passwords for each featured database in
        the file. If the ZIP includes a database config in the path
        databases/MyDatabase.yaml, the password should be provided in the
        following format: {"MyDatabase": "my_password"}
        """
        file_path = Path(file_path)
        if not file_path.exists():
            return False
        file_ext = file_path.suffix.replace(".", "")
        passwords = {f"databases/{db}.yaml": pwd for db, pwd in (passwords or {}).items()}

        with open(file_path, "rb") as bundle:
            files = {
                "bundle": (file_path.name, bundle, f"application/{file_ext}"),
                "passwords": (None, json.dumps(passwords)),
            }
            response = self.client.post(self.import_url, files=files)

        # If import is successful, the following is returned: {'message': 'OK'}
        return bool(response.json().get("message") == "OK")
