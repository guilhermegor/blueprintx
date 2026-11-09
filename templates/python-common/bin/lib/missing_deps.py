"""Print the direct dependencies in pyproject.toml that the running interpreter cannot see."""

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
import re
import sys
import tomllib


_RE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*")
_TUPLE_GROUPS = ("main", "dev")


def _is_required(spec: object) -> bool:
    """Return whether a Poetry dependency spec is unconditional.

    Parameters
    ----------
    spec : object
        The right-hand side of a dependency entry.

    Returns
    -------
    bool
        False for optional or marker-gated entries; for a list of alternative constraints,
        True when at least one of them is unconditional.
    """
    if isinstance(spec, list):
        return any(_is_required(spec_item) for spec_item in spec)
    return not isinstance(spec, dict) or not (
        spec.get("optional") or spec.get("markers") or spec.get("python")
    )


def declared_names(dict_toml: dict) -> list[str]:
    """Collect unconditional direct dependency names from the main and dev groups.

    Parameters
    ----------
    dict_toml : dict
        Parsed pyproject.toml.

    Returns
    -------
    list of str
        Distribution names.
    """
    dict_poetry = dict_toml.get("tool", {}).get("poetry", {})
    list_tables = [dict_poetry.get("dependencies", {})]
    list_tables += [
        dict_poetry.get("group", {}).get(str_group, {}).get("dependencies", {})
        for str_group in _TUPLE_GROUPS
    ]
    list_names = [
        str_name
        for dict_t in list_tables
        for str_name, spec in dict_t.items()
        if _is_required(spec)
    ]
    list_pep621 = [
        _RE_NAME.match(str_req).group(0)
        for str_req in dict_toml.get("project", {}).get("dependencies", [])
        if ";" not in str_req and _RE_NAME.match(str_req)
    ]
    return [str_name for str_name in list_names + list_pep621 if str_name.lower() != "python"]


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


if __name__ == "__main__":
    path_toml = Path(sys.argv[1])
    print("\n".join(missing(declared_names(tomllib.loads(path_toml.read_text(encoding="utf-8"))))))
