import importlib.util
import json
from pathlib import Path
import shutil

import pytest


_PATH_REPO = Path(__file__).parents[1]
_SPEC = importlib.util.spec_from_file_location(
    "python_eol_bump", _PATH_REPO / "bin" / "python_eol_bump.py"
)
mod_bump = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(mod_bump)


def _payload(dict_maintained: dict) -> dict:
    return {
        "result": {
            "releases": [
                {
                    "name": str_name,
                    "isMaintained": bool_m,
                    "releaseDate": DICT_DATES.get(str_name, "2020-01-01"),
                }
                for str_name, bool_m in dict_maintained.items()
            ]
        }
    }


STR_LATE = "2028-01-01"
DICT_DATES = {"3.15": "2026-10-01", "3.16": "2027-04-01"}
DICT_TODAY = {"3.15": True, "3.14": True, "3.13": True, "3.12": True, "3.11": True, "3.10": False}


LIST_FILES = [
    "templates/python-common/.python-version",
    "templates/python-common/ruff.toml",
    "templates/python-common/mypy.ini",
    "templates/python-common/requirements.txt",
    "templates/python-common/README.md",
    "templates/python-common/.github/workflows/tests.yaml",
    "templates/common/README.template.md",
    "templates/lib-minimal/pyproject.toml",
]


def _copy_into(path_dst_root: Path, str_rel: str) -> None:
    path_dst = path_dst_root / str_rel
    path_dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(_PATH_REPO / str_rel, path_dst)


@pytest.fixture
def path_tree(tmp_path: Path) -> Path:
    list(map(lambda str_rel: _copy_into(tmp_path, str_rel), LIST_FILES))
    list_base = ["3.11", "3.12", "3.13", "3.14", "3.15"]
    mod_bump.sync(tmp_path, "3.11", list_base, True)
    (tmp_path / mod_bump.STR_VERSION_FILE).write_text("3.11\n", encoding="utf-8")
    return tmp_path


def _write_fixture(path_dir: Path, dict_payload: dict) -> str:
    path_file = path_dir / "api.json"
    path_file.write_text(json.dumps(dict_payload), encoding="utf-8")
    return str(path_file)


def test_derive_floor_is_lowest_maintained_cycle() -> None:
    assert mod_bump.derive(_payload(DICT_TODAY), "2027-06-01") == (
        "3.11",
        ["3.11", "3.12", "3.13", "3.14", "3.15"],
    )


def test_derive_holds_a_new_cycle_until_the_delay_passes() -> None:
    assert mod_bump.derive(_payload(DICT_TODAY), "2026-11-04")[1][-1] == "3.14"


def test_derive_empty_payload_raises() -> None:
    with pytest.raises(ValueError):
        mod_bump.derive(_payload({"3.10": False}))


def test_derive_malformed_payload_raises() -> None:
    with pytest.raises(ValueError):
        mod_bump.derive({"nope": 1})


def test_bump_no_change_when_in_sync(path_tree: Path, tmp_path: Path) -> None:
    str_fixture = _write_fixture(tmp_path, _payload(DICT_TODAY))
    assert mod_bump.run_bump(path_tree, str_fixture, STR_LATE) == 0
    assert mod_bump.run_check(path_tree) == 0


def test_bump_raises_floor_when_cycle_reaches_eol(path_tree: Path, tmp_path: Path) -> None:
    dict_next = {**DICT_TODAY, "3.11": False, "3.16": True}
    str_fixture = _write_fixture(tmp_path, _payload(dict_next))
    assert mod_bump.run_bump(path_tree, str_fixture, STR_LATE) == 0
    assert (path_tree / mod_bump.STR_VERSION_FILE).read_text().strip() == "3.12"
    str_yaml = (path_tree / mod_bump.STR_TESTS_YAML).read_text()
    assert '["3.12", "3.13", "3.14", "3.15", "3.16"]' in str_yaml
    assert 'target-version = "py312"' in (
        path_tree / "templates/python-common/ruff.toml"
    ).read_text()
    assert 'python = ">=3.12,<4.0"' in (
        path_tree / "templates/lib-minimal/pyproject.toml"
    ).read_text()
    assert mod_bump.run_check(path_tree) == 0


def test_bump_new_release_extends_matrix(path_tree: Path, tmp_path: Path) -> None:
    str_fixture = _write_fixture(tmp_path, _payload({**DICT_TODAY, "3.16": True}))
    assert mod_bump.run_bump(path_tree, str_fixture, STR_LATE) == 0
    assert '"3.15", "3.16"]' in (path_tree / mod_bump.STR_TESTS_YAML).read_text()


def test_bump_malformed_data_changes_nothing_and_fails(path_tree: Path, tmp_path: Path) -> None:
    str_fixture = _write_fixture(tmp_path, {"result": {}})
    str_before = (path_tree / mod_bump.STR_TESTS_YAML).read_text()
    assert mod_bump.run_bump(path_tree, str_fixture, STR_LATE) == 1
    assert (path_tree / mod_bump.STR_TESTS_YAML).read_text() == str_before


def test_bump_keeps_a_deliberately_higher_floor_and_still_extends_matrix(
    path_tree: Path, tmp_path: Path
) -> None:
    path_version = path_tree / mod_bump.STR_VERSION_FILE
    path_version.write_text("3.13\n")
    str_fixture = _write_fixture(tmp_path, _payload({**DICT_TODAY, "3.16": True}))
    assert mod_bump.run_bump(path_tree, str_fixture, STR_LATE) == 0
    assert path_version.read_text().strip() == "3.13"
    assert '["3.13", "3.14", "3.15", "3.16"]' in (
        path_tree / mod_bump.STR_TESTS_YAML
    ).read_text()
    assert mod_bump.run_check(path_tree) == 0


def test_check_detects_drift(path_tree: Path) -> None:
    path_ruff = path_tree / "templates/python-common/ruff.toml"
    path_ruff.write_text(path_ruff.read_text().replace("py311", "py310"))
    assert mod_bump.run_check(path_tree) == 1


def test_derive_non_boolean_flag_raises() -> None:
    dict_bad = _payload(DICT_TODAY)
    dict_bad["result"]["releases"][-2]["isMaintained"] = "true"
    with pytest.raises(ValueError):
        mod_bump.derive(dict_bad)


def test_derive_skips_cycle_released_in_the_future() -> None:
    dict_pre = _payload(DICT_TODAY)
    dict_pre["result"]["releases"][0]["releaseDate"] = "2099-10-01"
    assert mod_bump.derive(dict_pre, "2026-11-04")[1][-1] == "3.14"


def test_derive_null_release_date_raises() -> None:
    dict_bad = _payload(DICT_TODAY)
    dict_bad["result"]["releases"][1]["releaseDate"] = None
    with pytest.raises(ValueError):
        mod_bump.derive(dict_bad)


def test_check_fails_when_a_rule_matches_nothing(path_tree: Path) -> None:
    path_toml = path_tree / "templates/lib-minimal/pyproject.toml"
    path_toml.write_text(path_toml.read_text().replace(",<4.0", ",<5.0"))
    assert mod_bump.run_check(path_tree) == 1


def test_check_fails_on_matrix_gap(path_tree: Path) -> None:
    path_yaml = path_tree / mod_bump.STR_TESTS_YAML
    path_yaml.write_text(path_yaml.read_text().replace('"3.12", ', ""))
    assert mod_bump.run_check(path_tree) == 1


def test_check_accepts_full_version_in_floor_file(path_tree: Path) -> None:
    (path_tree / mod_bump.STR_VERSION_FILE).write_text("3.11.4\n")
    assert mod_bump.run_check(path_tree) == 0


def test_check_reports_a_malformed_floor_file_instead_of_crashing(path_tree: Path) -> None:
    (path_tree / mod_bump.STR_VERSION_FILE).write_text("3\n")
    assert mod_bump.run_check(path_tree) == 1


def test_check_reports_a_missing_floor_file_instead_of_crashing(path_tree: Path) -> None:
    (path_tree / mod_bump.STR_VERSION_FILE).unlink()
    assert mod_bump.run_check(path_tree) == 1
