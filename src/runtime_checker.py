"""Load a vendored Colab runtime snapshot and look package versions up in it.

Snapshots come from googlecolab/backend-info and are read straight from data/runtimes/.
No network access at audit time.
"""

import json
import re
from pathlib import Path
from urllib.parse import unquote

from notebook_parser import normalise_name
from models import RuntimeInfo

RUNTIMES_DIR = Path(__file__).resolve().parents[1] / "data" / "runtimes"

# "torch @ https://.../torch-2.11.0+cpu-cp312-cp312-manylinux....whl"
DIRECT_REFERENCE = re.compile(r"^([A-Za-z0-9][A-Za-z0-9._-]*)\s*@\s*(\S+)$")


def list_snapshots(runtimes_dir: Path | None = None) -> list[str]:
    """Snapshot ids available locally, newest first."""
    base = runtimes_dir or RUNTIMES_DIR
    if not base.is_dir():
        return []
    return sorted((item.name for item in base.iterdir() if item.is_dir()), reverse=True)


def _version_from_url(name: str, url: str) -> str | None:
    """Pull a version out of a wheel or sdist filename in a direct reference."""
    filename = unquote(url.split("#", 1)[0]).rstrip("/").split("/")[-1]
    filename = re.sub(r"\.whl$|\.tar\.gz$|\.zip$", "", filename)
    pattern = rf"^{re.escape(name)}[-_]([0-9][^-]*?)(?:-py|-cp|$|\+)"
    match = re.search(pattern, filename, re.IGNORECASE)
    return match.group(1) if match else None


def parse_freeze(text: str) -> dict[str, str]:
    """Parse a pip-freeze listing into {normalised_name: version}.

    Handles "name==1.2.3" and the PEP 440 direct-reference form "name @ url".
    A git reference carries no version, so it is skipped.
    """
    packages: dict[str, str] = {}

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue

        if "==" in line and " @ " not in line:
            name, _, version = line.partition("==")
            packages[normalise_name(name.strip())] = version.strip()
            continue

        match = DIRECT_REFERENCE.match(line)
        if match:
            name, url = match.group(1), match.group(2)
            version = _version_from_url(name, url)
            if version:
                packages[normalise_name(name)] = version

    return packages


def load_snapshot(snapshot: str, runtimes_dir: Path | None = None) -> tuple[dict[str, str], RuntimeInfo]:
    """Return the package index and summary info for one snapshot.

    Raises ValueError if the snapshot is not vendored locally.
    """
    base = (runtimes_dir or RUNTIMES_DIR) / snapshot
    freeze_file = base / "pip-freeze.txt"

    if not freeze_file.is_file():
        available = ", ".join(list_snapshots(runtimes_dir)) or "none"
        raise ValueError(f"Runtime snapshot '{snapshot}' not found. Available: {available}")

    packages = parse_freeze(freeze_file.read_text(encoding="utf-8"))

    info = RuntimeInfo(snapshot=snapshot)

    manifest_file = base / "manifest.json"
    if manifest_file.is_file():
        info.source_commit = json.loads(manifest_file.read_text(encoding="utf-8")).get("commit")

    os_file = base / "os-info.txt"
    if os_file.is_file():
        for line in os_file.read_text(encoding="utf-8").splitlines():
            if line.startswith("Ubuntu"):
                info.os_version = line.strip()
            elif line.startswith("Python "):
                info.python_version = line.removeprefix("Python ").strip()

    return packages, info


def version_in_snapshot(packages: dict[str, str], name: str) -> str | None:
    """Version of a distribution in the snapshot, or None when it is absent."""
    return packages.get(normalise_name(name))


def versions_match(pinned: str, runtime_version: str) -> bool:
    """Compare two versions, ignoring a local build tag such as 2.11.0+cpu."""
    return pinned.split("+")[0].strip() == runtime_version.split("+")[0].strip()