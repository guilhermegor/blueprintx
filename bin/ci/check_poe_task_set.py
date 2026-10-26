"""Assert a generated project's poe task set is today's set minus what its tier cannot run.

Run from the generated project root: ``python3 check_poe_task_set.py <skeleton>``.
"""

import re
import sys
import tomllib
from pathlib import Path

SET_BOOTSTRAP = {"init", "ensure_env", "venv", "update_venv", "precommit"}
SET_REPO = {
    "enable_pages", "enable_repo_rules", "enable_security", "bump_version", "changelog",
    "get_corporate_ca", "export_context", "export_deps", "template_update",
}
SET_TEST = {
    "unit_tests", "integration_tests", "test_cov", "test_cov_report", "test_cov_serve",
    "test_slowest", "test_urls_docstrings",
}
SET_LINT = {
    "lint", "install_shell_linters", "check_docstrings", "check_readme_structure",
    "check_function_length", "check_fixture_scope", "check_complexity",
    "check_comment_budget", "check_docs_gap", "check_env_docs_sync", "check_secrets",
    "template_drift", "check_commit_msg",
}
SET_DOCS = {"docs_serve", "docs_server"}
SET_DB = {"db_up", "db_backup", "db_restore"}
SET_MIGRATE = {
    "migrate_new", "migrate_up", "migrate_down", "migrate_current", "migrate_history",
    "migrate_sql",
}
SET_SERVICE = {"run", "wheelhouse", "wheelhouse_assemble", "ship", "fix_playwright"}
SET_ALL = (
    SET_BOOTSTRAP | SET_REPO | SET_TEST | SET_LINT | SET_DOCS | SET_DB | SET_MIGRATE
    | SET_SERVICE
)
DICT_CANNOT_RUN = {
    "lib-minimal": SET_DB | SET_MIGRATE | SET_SERVICE,
    "api-service-native-db": SET_MIGRATE,
    "ddd-service-native-db": SET_MIGRATE,
    "mvc-service-native-db": SET_MIGRATE,
    "ddd-service-orm-db": set(),
    "mvc-service-orm-db": set(),
}
RE_SCRIPT = re.compile(r"\b(?:bash|python3?)\s+(bin/[\w./-]+)")


def load_tasks(path_root: Path) -> dict:
    dict_tasks: dict = {}
    pending = [path_root / "poe_tasks.toml"]
    while pending:
        path_file = pending.pop()
        dict_doc = tomllib.loads(path_file.read_text(encoding="utf-8"))
        dict_tasks.update(dict_doc.get("tool", {}).get("poe", {}).get("tasks", {}))
        for str_inc in dict_doc.get("tool", {}).get("poe", {}).get("include", []):
            pending.append(path_root / str_inc)
    return dict_tasks


def task_problems(path_root: Path, dict_tasks: dict) -> list:
    list_problems = []
    for str_name, dict_task in dict_tasks.items():
        list_text = [dict_task.get(k, "") for k in ("cmd", "shell")]
        list_text += [s.get("cmd", "") for s in dict_task.get("sequence", []) if isinstance(s, dict)]
        for str_text in list_text:
            for str_script in RE_SCRIPT.findall(str_text):
                if not (path_root / str_script).is_file():
                    list_problems.append(f"{str_name}: {str_script} is not shipped")
            if "alembic" in str_text and not (path_root / "alembic.ini").is_file():
                list_problems.append(f"{str_name}: alembic.ini is not shipped")
        str_ref = dict_task.get("ref")
        if str_ref and str_ref not in dict_tasks:
            list_problems.append(f"{str_name}: ref {str_ref} is undefined")
    return list_problems


def main() -> int:
    str_skeleton = sys.argv[1]
    path_root = Path.cwd()
    dict_tasks = load_tasks(path_root)
    set_actual = set(dict_tasks)
    set_expected = SET_ALL - DICT_CANNOT_RUN[str_skeleton]
    set_extra = set()
    for str_extra in ("poe_tasks.library.toml", "poe_tasks.offline.toml"):
        path_extra = path_root / str_extra
        if path_extra.is_file():
            set_extra |= set(tomllib.loads(path_extra.read_text(encoding="utf-8"))["tool"]["poe"]["tasks"])
    list_problems = task_problems(path_root, dict_tasks)
    list_problems += [f"missing task: {n}" for n in sorted(set_expected - set_actual)]
    list_problems += [f"unexpected task: {n}" for n in sorted(set_actual - set_expected - set_extra)]
    for str_problem in list_problems:
        print(f"ERROR: [{str_skeleton}] {str_problem}", file=sys.stderr)
    if not list_problems:
        print(f"[{str_skeleton}] {len(set_actual)} poe tasks: set matches the tier, all resolve.")
    return 1 if list_problems else 0


if __name__ == "__main__":
    sys.exit(main())
