"""Derive the Python floor and CI matrix from endoflife.date and sync the templates.

``templates/python-common/.python-version`` is the single source of truth. ``--check`` fails
when any derived place disagrees with it; the default run rewrites ``.python-version`` and
every derived place from the API. Fails closed: bad API data changes nothing and exits 1.

Usage: ``python bin/python_eol_bump.py [--check] [--root DIR] [--fixture FILE]``
"""

import argparse
import datetime
import http.client
import json
import pathlib
import re
import sys
import urllib.request


STR_API = "https://endoflife.date/api/v1/products/python/"
STR_VERSION_FILE = "templates/python-common/.python-version"
STR_TESTS_YAML = "templates/python-common/.github/workflows/tests.yaml"

INT_MATRIX_DELAY_DAYS = 180

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
    re_match = RE_CYCLE.match(str_cycle)
    if re_match is None:
        raise ValueError(f"not a 3.N cycle: {str_cycle!r}")
    return int(re_match.group(1))


def settled(dict_rel: dict, str_today: str) -> bool:
    """Tell whether a release is old enough to enter the matrix.

    Parameters
    ----------
    dict_rel : dict
        One release record with a string ``releaseDate``.
    str_today : str
        ISO date.

    Returns
    -------
    bool
        True once ``INT_MATRIX_DELAY_DAYS`` have passed since the release.
    """
    dt_release = datetime.date.fromisoformat(dict_rel["releaseDate"])
    dt_today = datetime.date.fromisoformat(str_today)
    return dt_release + datetime.timedelta(days=INT_MATRIX_DELAY_DAYS) <= dt_today


def derive(dict_payload: dict, str_today: str = "9999-12-31") -> tuple:
    """Compute the floor and the matrix from an endoflife.date product payload.

    Parameters
    ----------
    dict_payload : dict
        Parsed ``/api/v1/products/python/`` response.
    str_today : str
        ISO date; a cycle whose ``releaseDate`` is later is a pre-release and is skipped.

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
        list_releases = [
            dict_rel
            for dict_rel in dict_payload["result"]["releases"]
            if RE_CYCLE.match(str(dict_rel["name"]))
        ]
        if not all(isinstance(dict_rel["isMaintained"], bool) for dict_rel in list_releases):
            raise ValueError("isMaintained is not a boolean on every Python 3 cycle")
        if not all(isinstance(dict_rel["releaseDate"], str) for dict_rel in list_releases):
            raise ValueError("releaseDate is not a string on every Python 3 cycle")
        list_cycles = [
            str(dict_rel["name"])
            for dict_rel in list_releases
            if dict_rel["isMaintained"] and settled(dict_rel, str_today)
        ]
    except (KeyError, TypeError, AttributeError) as cls_err:
        raise ValueError(f"malformed endoflife.date payload: {cls_err!r}") from cls_err
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
        list_files = sorted(path_root.glob(str_glob))
        if not list_files:
            raise ValueError(f"rule matched no file: {str_glob}")
        for path_file in list_files:
            str_old = path_file.read_text(encoding="utf-8")
            str_out, int_hits = re.subn(
                str_pattern, lambda m, s=str_new: m.group(1) + s + m.group(2), str_old
            )
            if int_hits == 0:
                raise ValueError(f"{path_file.relative_to(path_root)}: no match for {str_pattern}")
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
    cls_request = urllib.request.Request(  # noqa: S310
        STR_API, headers={"User-Agent": "blueprintx-python-eol-bump"}
    )
    with urllib.request.urlopen(cls_request, timeout=30) as cls_resp:  # noqa: S310
        if cls_resp.status != 200:
            raise ValueError(f"endoflife.date returned HTTP {cls_resp.status}")
        return json.loads(cls_resp.read())


def matrix_problem(str_floor: str, list_matrix: list) -> str:
    """Return why a tests.yaml matrix is not a contiguous run from the floor, or ``""``.

    Parameters
    ----------
    str_floor : str
        Floor cycle.
    list_matrix : list
        Cycles read from ``tests.yaml``.

    Returns
    -------
    str
        A finding message, empty when the matrix is valid.
    """
    if not list_matrix:
        return "tests.yaml has no python-version matrix"
    int_last = cycle_key(list_matrix[-1])
    list_expected = [f"3.{int_n}" for int_n in range(cycle_key(str_floor), int_last + 1)]
    if list_matrix != list_expected:
        return f"tests.yaml matrix {list_matrix} is not contiguous from {str_floor}"
    return ""


def read_floor(path_root: pathlib.Path) -> str:
    """Read ``.python-version`` as a ``MAJOR.MINOR`` cycle.

    Parameters
    ----------
    path_root : pathlib.Path
        Repository root.

    Returns
    -------
    str
        The floor, truncated to two components.
    """
    str_raw = (path_root / STR_VERSION_FILE).read_text(encoding="utf-8").strip()
    return ".".join(str_raw.split(".")[:2])


def run_check(path_root: pathlib.Path) -> int:
    """Compare every derived place with ``.python-version`` and the tests matrix.

    Parameters
    ----------
    path_root : pathlib.Path
        Repository root.

    Returns
    -------
    int
        0 when in sync, 1 on drift or when a rule cannot be verified.
    """
    try:
        str_floor = read_floor(path_root)
        str_yaml = (path_root / STR_TESTS_YAML).read_text(encoding="utf-8")
        re_found = re.search(r"python-version: \[([^\]]*)\]", str_yaml)
        list_matrix = re.findall(r"\d+\.\d+", re_found.group(1)) if re_found else []
        str_problem = matrix_problem(str_floor, list_matrix)
        list_drift = [str_problem] if str_problem else []
        list_drift += sync(path_root, str_floor, list_matrix, bool_write=False)
    except (ValueError, OSError) as cls_err:
        print(f"drift gate cannot verify: {cls_err}")
        return 1
    for str_item in list_drift:
        print(f"drift ({str_floor}): {str_item}")
    return 1 if list_drift else 0


def run_bump(path_root: pathlib.Path, str_fixture: str, str_today: str = "") -> int:
    """Derive from the API and rewrite the templates, never lowering the floor.

    Parameters
    ----------
    path_root : pathlib.Path
        Repository root.
    str_fixture : str
        Fixture path, or empty to call the API.
    str_today : str
        ISO date for the settling delay; empty means today.

    Returns
    -------
    int
        0 on success (changed or not), 1 on any API, data or rule failure.
    """
    try:
        str_derived, list_derived = derive(
            fetch(str_fixture), str_today or datetime.date.today().isoformat()
        )
        str_floor = max(str_derived, read_floor(path_root), key=cycle_key)
        list_matrix = [str_c for str_c in list_derived if cycle_key(str_c) >= cycle_key(str_floor)]
        if not list_matrix:
            raise ValueError(f"no settled cycle at or above the floor {str_floor}")
        sync(path_root, str_floor, list_matrix, bool_write=False)
    except (ValueError, OSError, http.client.HTTPException) as cls_err:
        print(f"fail closed, nothing changed: {cls_err}")
        return 1
    if str_floor != read_floor(path_root):
        (path_root / STR_VERSION_FILE).write_text(str_floor + "\n", encoding="utf-8")
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
