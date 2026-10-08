"""Read a .ipynb file as JSON and pull out package references.

The notebook is only ever read as data. No cell is executed, imported, or evaluated.
"""

import json
import re
import shlex
import sys
from pathlib import Path

from models import Requirement

MAX_NOTEBOOK_BYTES = 20 * 1024 * 1024

# pip invocations seen in real notebooks: "!pip install x", "%pip install x",
# "!pip3 install -q x", and the bare "pip install x" that some cells use.
INSTALL_PATTERN = re.compile(r"^[!\s%]*pip3?\s+install\b(.*)$")

IMPORT_PATTERN = re.compile(r"^\s*(?:from|import)\s+([A-Za-z_][A-Za-z0-9_.]*)", re.MULTILINE)

# Import name to distribution name. Only names where the two actually differ.
IMPORT_TO_DISTRIBUTION = {
    "bs4": "beautifulsoup4",
    "cv2": "opencv-python",
    "PIL": "pillow",
    "sklearn": "scikit-learn",
    "yaml": "pyyaml",
    "dotenv": "python-dotenv",
}

FIRST_PARTY = {"google"}


def normalise_name(name: str) -> str:
    """PEP 503 style: lower case, runs of -_. collapse to a single dash."""
    return re.sub(r"[-_.]+", "-", name).strip().lower()


def read_notebook(notebook_path: str | Path) -> dict:
    """Load and sanity-check the notebook JSON. Raises ValueError on bad input."""
    path = Path(notebook_path)

    if not path.is_file():
        raise ValueError(f"Notebook file not found: {path}")
    if path.stat().st_size > MAX_NOTEBOOK_BYTES:
        raise ValueError(f"Notebook is too large to parse safely: {path.stat().st_size} bytes")

    try:
        notebook = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Notebook is not valid JSON: {exc}") from exc

    if not isinstance(notebook, dict) or "cells" not in notebook:
        raise ValueError("File does not look like a Jupyter notebook: no 'cells' key")
    if not isinstance(notebook["cells"], list):
        raise ValueError("Notebook 'cells' must be a list")

    return notebook


def get_code_cells(notebook: dict) -> list[tuple[int, str]]:
    """Return (cell_index, source) for every code cell."""
    cells = []

    for index, cell in enumerate(notebook["cells"]):
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        source = cell.get("source", "")
        if isinstance(source, list):
            source = "".join(source)
        if isinstance(source, str) and source.strip():
            cells.append((index, source))

    return cells


def parse_install_commands(source: str) -> list[str]:
    """Return the argument text of each pip install command found in a cell."""
    commands = []

    for raw_line in source.splitlines():
        match = INSTALL_PATTERN.match(raw_line.strip())
        if match:
            commands.append(match.group(1).strip())

    return commands


def split_requirements(command: str) -> list[str]:
    """Split one install command into individual requirement tokens.

    Unparseable shell text is skipped rather than guessed at.
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        return []

    return [token for token in tokens if token and not token.startswith("-")]


def parse_requirement(token: str, cell: int, origin: str) -> Requirement | None:
    """Turn one requirement token into a Requirement, or None if unusable."""
    raw = token.strip()
    if not raw or raw in {"-e", "."}:
        return None

    name_part = raw.split("[", 1)[0].split("@", 1)[0].split("==", 1)[0]
    name_part = name_part.split(">", 1)[0].split("<", 1)[0].split("!", 1)[0].split("~", 1)[0]
    name_part = name_part.split("=", 1)[0].split(";", 1)[0].strip()

    if not name_part or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*", name_part):
        return None

    if "==" in raw:
        pinned = raw.split("==", 1)[1].strip()
        # Anything that is not one literal version is not an exact pin: a wildcard,
        # a comma-separated constraint list, or a marker clause.
        if not pinned or any(char in pinned for char in "<>~*;,"):
            return None
        return Requirement(
            name=normalise_name(name_part),
            version=pinned,
            raw=raw,
            cell=cell,
            origin=origin,
        )

    # Ranges, bare names and extras all land here: a reference with no exact pin.
    return Requirement(
        name=normalise_name(name_part),
        raw=raw,
        cell=cell,
        origin=origin,
    )


def is_third_party(module_name: str) -> bool:
    """True when an import name looks like an installed package, not stdlib or google.colab."""
    top_level = module_name.split(".")[0]

    return (
        top_level not in sys.stdlib_module_names
        and top_level not in sys.builtin_module_names
        and top_level not in FIRST_PARTY
    )


def resolve_import(module_name: str) -> str:
    """Map an import name to the distribution that provides it."""
    top_level = module_name.split(".")[0]
    return normalise_name(IMPORT_TO_DISTRIBUTION.get(top_level, top_level))


def extract_dependencies(notebook_path: str | Path) -> list[Requirement]:
    """Return every package reference in the notebook, imports and installs merged.

    Imports are only recorded when they are not already covered by a pip install,
    so a notebook installing and then importing the same package lists it once.
    """
    notebook = read_notebook(notebook_path)
    cells = get_code_cells(notebook)
    requirements: list[Requirement] = []
    installed: set[str] = set()

    for cell, source in cells:
        for command in parse_install_commands(source):
            for token in split_requirements(command):
                requirement = parse_requirement(token, cell, "pip_install")
                if requirement:
                    installed.add(requirement.name)
                    requirements.append(requirement)

    for cell, source in cells:
        for module_name in IMPORT_PATTERN.findall(source):
            if not is_third_party(module_name):
                continue
            name = resolve_import(module_name)
            if name in installed:
                continue
            installed.add(name)
            requirements.append(
                Requirement(name=name, raw=module_name, cell=cell, origin="import")
            )

    return requirements


def find_content_paths(notebook_path: str | Path) -> list[tuple[int, str]]:
    """Return (cell_index, path) for every /content/ reference in the notebook."""
    notebook = read_notebook(notebook_path)
    matches = []

    for cell, source in get_code_cells(notebook):
        for found in re.findall(r"/content/[A-Za-z0-9_./\- ]*", source):
            matches.append((cell, found.strip()))

    return matches