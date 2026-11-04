"""Derive the Python floor and CI matrix from endoflife.date and sync the templates.

``templates/python-common/.python-version`` is the single source of truth. ``--check`` fails
when any derived place disagrees with it; the default run rewrites ``.python-version`` and
every derived place from the API. Fails closed: bad API data changes nothing and exits 1.

Usage: ``python bin/python_eol_bump.py [--check] [--root DIR] [--fixture FILE]``
"""

import argparse
import json
import pathlib
import re
import sys
import urllib.request


STR_API = "https://endoflife.date/api/v1/products/python/"
STR_VERSION_FILE = "templates/python-common/.python-version"
STR_TESTS_YAML = "templates/python-common/.github/workflows/tests.yaml"

RE_CYCLE = re.compile(r"^3\.(\d+)$")

LIST_RULES = [
    ("templates/*/pyproject.toml", r'(python = ">=)\d+\.\d+(,<4\.0")', "{floor}"),
    ("templates/python-common/ruff.toml", r'(target-version = "py)\d+(")', "{digits}"),
    ("templates/python-common/mypy.ini", r"(python_version = )\d+\.\d+()", "{floor}"),
    (
        "templates/python-common/requirements.txt",
        r'(python_full_version >= ")\d+\.\d+(")',
        "{floor}",
    ),
    ("templates/python-common/README.md", r"(badge/python-)\d+\.\d+(%2B)", "{floor}"),
    ("templates/python-common/README.md", r"(Python )\d+\.\d+(\+ is)", "{floor}"),
    ("templates/common/README.template.md", r"(badge/python-)\d+\.\d+(%2B)", "{floor}"),
    (
        STR_TESTS_YAML,
        r"(python-version: \[)[^\]]*(\])",
        "{matrix}",
    ),
]


def cycle_key(str_cycle: str) -> int:
    """Return the minor number of a ``3.N`` cycle.

    Parameters
    ----------
    str_cycle : str
        Cycle name such as ``"3.11"``.

    Returns
    -------
    int
        The minor number.
    """
    return int(RE_CYCLE.match(str_cycle).group(1))


def derive(dict_payload: dict) -> tuple:
    """Compute the floor and the matrix from an endoflife.date product payload.

    Parameters
    ----------
    dict_payload : dict
        Parsed ``/api/v1/products/python/`` response.

    Returns
    -------
    tuple
        ``(str_floor, list_matrix)``.

    Raises
    ------
    ValueError
        When the payload is malformed or reports no maintained 3.x cycle.
    """
    try:
        list_releases = dict_payload["result"]["releases"]
        list_cycles = [
            str(dict_rel["name"])
            for dict_rel in list_releases
            if dict_rel["isMaintained"] is True and RE_CYCLE.match(str(dict_rel["name"]))
        ]
    except (KeyError, TypeError) as err:
        raise ValueError(f"malformed endoflife.date payload: {err!r}") from err
    if not list_cycles:
        raise ValueError("no maintained Python cycle in payload")
    list_matrix = sorted(list_cycles, key=cycle_key)
    return list_matrix[0], list_matrix


def render(str_template: str, str_floor: str, list_matrix: list) -> str:
    """Fill a rule's replacement placeholder.

    Parameters
    ----------
    str_template : str
        One of ``{floor}``, ``{digits}`` or ``{matrix}``.
    str_floor : str
        Floor cycle, e.g. ``"3.11"``.
    list_matrix : list
        Matrix cycles.

    Returns
    -------
    str
        The text to splice in.
    """
    return str_template.format(
        floor=str_floor,
        digits=str_floor.replace(".", ""),
        matrix=", ".join(f'"{str_c}"' for str_c in list_matrix),
    )


def sync(path_root: pathlib.Path, str_floor: str, list_matrix: list, bool_write: bool) -> list:
    """Rewrite (or only compare) every derived place.

    Parameters
    ----------
    path_root : pathlib.Path
        Repository root.
    str_floor : str
        Floor cycle.
    list_matrix : list
        Matrix cycles.
    bool_write : bool
        Write changes when true, only report drift when false.

    Returns
    -------
    list
        Relative paths whose content differs from the derived value.
    """
    list_drift: list = []
    for str_glob, str_pattern, str_template in LIST_RULES:
        str_new = render(str_template, str_floor, list_matrix)
        for path_file in sorted(path_root.glob(str_glob)):
            str_old = path_file.read_text(encoding="utf-8")
            str_out = re.sub(
                str_pattern, lambda m, s=str_new: m.group(1) + s + m.group(2), str_old
            )
            if str_out != str_old:
                list_drift.append(str(path_file.relative_to(path_root)))
                if bool_write:
                    path_file.write_text(str_out, encoding="utf-8")
    return list_drift


def fetch(str_fixture: str) -> dict:
    """Load the API payload from a fixture file or the network.

    Parameters
    ----------
    str_fixture : str
        Fixture path, or empty to call the API.

    Returns
    -------
    dict
        Parsed JSON.
    """
    if str_fixture:
        return json.loads(pathlib.Path(str_fixture).read_text(encoding="utf-8"))
    with urllib.request.urlopen(STR_API, timeout=30) as cls_resp:  # noqa: S310
        if cls_resp.status != 200:
            raise ValueError(f"endoflife.date returned HTTP {cls_resp.status}")
        return json.loads(cls_resp.read())


def run_check(path_root: pathlib.Path) -> int:
    """Compare every derived place with ``.python-version`` and the tests matrix floor.

    Parameters
    ----------
    path_root : pathlib.Path
        Repository root.

    Returns
    -------
    int
        0 when in sync, 1 on drift.
    """
    str_floor = (path_root / STR_VERSION_FILE).read_text(encoding="utf-8").strip()
    str_matrix = (path_root / STR_TESTS_YAML).read_text(encoding="utf-8")
    re_found = re.search(r"python-version: \[([^\]]*)\]", str_matrix)
    list_matrix = re.findall(r"\d+\.\d+", re_found.group(1)) if re_found else []
    if not list_matrix or list_matrix[0] != str_floor:
        print(f"tests.yaml matrix {list_matrix} does not start at the floor {str_floor}")
        return 1
    list_drift = sync(path_root, str_floor, list_matrix, bool_write=False)
    for str_path in list_drift:
        print(f"{str_path}: out of sync with .python-version ({str_floor})")
    return 1 if list_drift else 0


def run_bump(path_root: pathlib.Path, str_fixture: str) -> int:
    """Derive from the API and rewrite the templates, never lowering a maintained floor.

    Parameters
    ----------
    path_root : pathlib.Path
        Repository root.
    str_fixture : str
        Fixture path, or empty to call the API.

    Returns
    -------
    int
        0 on success (changed or not), 1 on any API or data failure.
    """
    try:
        str_floor, list_matrix = derive(fetch(str_fixture))
    except (ValueError, OSError) as err:
        print(f"fail closed, nothing changed: {err}")
        return 1
    path_version = path_root / STR_VERSION_FILE
    str_current = path_version.read_text(encoding="utf-8").strip()
    if cycle_key(str_floor) < cycle_key(str_current):
        print(f"derived floor {str_floor} is below current {str_current}; refusing to lower it")
        return 1
    path_version.write_text(str_floor + "\n", encoding="utf-8")
    list_drift = sync(path_root, str_floor, list_matrix, bool_write=True)
    print(f"floor {str_floor}, matrix {list_matrix}, changed {len(list_drift)} file(s)")
    return 0


def main(list_argv: list) -> int:
    """Entry point.

    Parameters
    ----------
    list_argv : list
        Arguments after the program name.

    Returns
    -------
    int
        Process exit code.
    """
    cls_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    cls_parser.add_argument("--check", action="store_true")
    cls_parser.add_argument("--root", default=".")
    cls_parser.add_argument("--fixture", default="")
    cls_args = cls_parser.parse_args(list_argv)
    path_root = pathlib.Path(cls_args.root)
    if cls_args.check:
        return run_check(path_root)
    return run_bump(path_root, cls_args.fixture)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
