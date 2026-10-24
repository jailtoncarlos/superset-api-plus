"""Shared test configuration: loads the test stack .env (tests/integration reads it)."""
import os
from pathlib import Path

ROOT = Path(__file__).parent.parent


def load_env_file(path: Path = ROOT / ".env") -> None:
    """Load the test stack .env into the environment without overriding variables already set."""
    if not path.is_file():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            name, value = line.split("=", 1)
            os.environ.setdefault(name.strip(), value.strip().strip("\"'"))


load_env_file()
