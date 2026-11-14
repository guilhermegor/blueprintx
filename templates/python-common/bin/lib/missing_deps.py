"""Print the direct dependencies in pyproject.toml that the running interpreter cannot see."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import re
import sys
import tomllib


_RE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")
_RE_SEPARATORS = re.compile(r"[-_.]+")
_STR_PREFIX = "missing: "


def _is_required(obj_spec: object) -> bool:
    """Return whether a Poetry dependency spec is unconditional.

    Parameters
    ----------
    obj_spec : object
        The right-hand side of a dependency entry.

    Returns
    -------
    bool
        False for optional or marker-gated entries; for a list of alternative constraints,
        True when at least one of them is unconditional.
    """
    if isinstance(obj_spec, list):
        return any(_is_required(obj_item) for obj_item in obj_spec)
    return not isinstance(obj_spec, dict) or not (
        obj_spec.get("optional") or obj_spec.get("markers") or obj_spec.get("python")
    )


def _pep508_name(str_req: str) -> str | None:
    """Return the distribution name of an unconditional PEP 508 requirement.

    Parameters
    ----------
    str_req : str
        One requirement string.

    Returns
    -------
    str or None
        The name, or None for a marker-gated entry or one that does not start with a name.
    """
    cls_match = _RE_NAME.match(str_req.strip())
    return None if ";" in str_req or cls_match is None else cls_match.group(0)


def _poetry_names(dict_poetry: dict) -> list[str]:
    """Collect unconditional names from the main table and every non-optional group.

    Parameters
    ----------
    dict_poetry : dict
        The ``[tool.poetry]`` table.

    Returns
    -------
    list of str
        Distribution names, which ``poetry install`` installs by default.
    """
    list_tables = [dict_poetry.get("dependencies", {})]
    list_tables += [
        dict_group.get("dependencies", {})
        for dict_group in dict_poetry.get("group", {}).values()
        if not dict_group.get("optional")
    ]
    return [
        str_name
        for dict_table in list_tables
        for str_name, obj_spec in dict_table.items()
        if _is_required(obj_spec)
    ]


def declared_names(dict_toml: dict) -> list[str]:
    """Collect unconditional direct dependency names, de-duplicated by normalised name.

    Parameters
    ----------
    dict_toml : dict
        Parsed pyproject.toml.

    Returns
    -------
    list of str
        Distribution names, first spelling kept.
    """
    list_pep621 = list(dict_toml.get("project", {}).get("dependencies", []))
    for list_group in dict_toml.get("dependency-groups", {}).values():
        list_pep621 += [obj for obj in list_group if isinstance(obj, str)]
    list_names = _poetry_names(dict_toml.get("tool", {}).get("poetry", {})) + [
        str_name for str_name in map(_pep508_name, list_pep621) if str_name
    ]
    dict_unique: dict[str, str] = {}
    for str_name in list_names:
        dict_unique.setdefault(_RE_SEPARATORS.sub("-", str_name).lower(), str_name)
    return [str_name for str_name in dict_unique.values() if str_name.lower() != "python"]


def missing(list_names: list[str]) -> list[str]:
    """Return the names the interpreter has no installed distribution for.

    Parameters
    ----------
    list_names : list of str
        Distribution names.

    Returns
    -------
    list of str
        Those not installed.
    """
    list_out = []
    for str_name in list_names:
        try:
            version(str_name)
        except PackageNotFoundError:
            list_out.append(str_name)
    return list_out


def main(list_argv: list[str]) -> int:
    """Print one ``missing: <name>`` line per absent dependency.

    Parameters
    ----------
    list_argv : list of str
        Command line without the program name; the single argument is the pyproject path.

    Returns
    -------
    int
        2 on a usage error, otherwise 0.
    """
    if len(list_argv) != 1:
        print("usage: missing_deps.py <pyproject.toml>", file=sys.stderr)
        return 2
    dict_toml = tomllib.loads(Path(list_argv[0]).read_text(encoding="utf-8"))
    for str_name in missing(declared_names(dict_toml)):
        print(f"{_STR_PREFIX}{str_name}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
