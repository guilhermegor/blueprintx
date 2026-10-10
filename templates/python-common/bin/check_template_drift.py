"""Report files this project's template tier ships that this project never received.

Scaffolding is a one-shot copy (blueprintx#109): adding a file to ``templates/<tier>/`` (or
the shared ``templates/python-common/``) protects only projects generated AFTER that commit.
No existing project is ever compared against the template it came from, so a fix landing in
the template silently never reaches a project scaffolded before it — forever, unless someone
remembers to backfill it by hand. Two independent real cases motivated this: a network-block
``conftest.py`` guard and a ``.codespellrc`` skip pattern, both missing from a downstream
project scaffolded before either was added to ``templates/python-common/``.

Shape: PRESENCE-ONLY, deliberately, not a content diff. A project's own legitimate local
changes are not drift — only a file/tool the template ships that the project simply does not
have. This is the cheap, high-signal, low-false-positive half of the drift question; the two
real cases above are both absence. A content-diff check on files a project should never
customise (the shared ``bin/check_*.py`` gates, ``.pre-commit-config.yaml`` hook ids) is a
real follow-on but needs a notion of "not meant to be edited locally" this module does not
attempt — a check that fires on legitimate local edits gets disabled the first week it is
noisy, the same "a number nobody pays is a gate nobody keeps" reasoning that set the ``bin/``
complexity ceiling.

Reporter, not a gate — like ``check_contract_drift.py`` in this same directory (read its
header first; the reasoning is identical). Drift in a downstream project is not that
project's fault on the day it is detected: a template gaining a fix after a project was
scaffolded and a source dropping a column are the same shape, something changed on a
DIFFERENT clock than the one CI is checking. So this always exits 0.

What it needs to run: a BLUEPRINTX CHECKOUT (``--blueprintx-root``, or
``BLUEPRINTX_TEMPLATE_ROOT`` in the environment) — nothing here vendors a second copy of the
template tree. Absent one, it self-skips LOUDLY (prints why, never a silent pass) — the same
contract ``check_actions.sh`` documents for its own missing tool. Absent a provenance stamp
(``.blueprintx-provenance.yaml``, written at scaffold time by
``bin/lib/scaffold_python_templates.sh::scaffold_stamp_provenance``) it also self-skips
loudly: that is the path BlueprintX's OWN tree always takes (not a scaffolded project, no
tier — ``--root .`` here never falls through to a comparison), and the path any project
scaffolded before this feature shipped takes too.

The required-path set is DERIVED, not a hand-maintained second list: parsed straight out of
``bin/lib/scaffold_python_templates.sh`` — the one shared step every service tier's scaffold
calls to copy ``templates/python-common/`` in — rather than duplicated here, so this check
cannot drift from what the scaffold actually copies. That is exactly the failure mode
``check_codespell_sync.sh`` already exists in this repo to police, applied to a new pair.
Deliberately scoped to ``templates/python-common/`` only, not the tier-specific
``templates/<tier>/src/`` (each ``bin/scaffold/python_*.sh`` copies that with its own logic,
currently in flight across several PRs) — a narrower, honest MVP over a wider check that
would risk false positives on conditional tier files it cannot see.
"""

import argparse
import os
import pathlib
import re
import subprocess
import sys


_PROVENANCE_FILENAME = ".blueprintx-provenance.yaml"
_SCAFFOLD_LIB_RELPATH = pathlib.Path("bin/lib/scaffold_python_templates.sh")
_COMMON_TEMPLATE_RELPATH = pathlib.Path("templates/python-common")

# One regex for every `cp [flags] SRC DST` the scaffold lib uses. SRC is rooted at
# `$COMMON_TEMPLATE_ROOT` / `$SHARED_TEMPLATE_ROOT` (braced or not), DST at `$str_project_path`.
# A SRC ending in `/.` is the wholesale directory-contents form.
_RE_CP = re.compile(
    r'cp\s+(?:-[A-Za-z]+\s+)*"\$\{?(COMMON|SHARED)_TEMPLATE_ROOT\}?/([^"]+)"\s+'
    r'"\$\{?str_project_path\}?/([^"]+)"'
)
# A backslash-newline is shell line-splicing: one logical command. Spliced out before the
# cp patterns run, so a wrapped `cp` parses exactly like an unwrapped one.
_RE_LINE_CONTINUATION = re.compile(r"\\\s*\n\s*")
_RE_CHAINED_CP = re.compile(r"(?:&&|\|\|)\s*cp\b")
_RE_ONE_LINE_ESAC = re.compile(r"\besac\s*$")


def read_tier(path_root: pathlib.Path) -> str | None:
    """Return the ``tier:`` value stamped in the project's provenance file, or ``None``.

    Parameters
    ----------
    path_root : pathlib.Path
            The project root to inspect.

    Returns
    -------
    str or None
            The stamped tier name, or ``None`` when there is no provenance stamp at all.
    """
    path_stamp = path_root / _PROVENANCE_FILENAME
    if not path_stamp.exists():
        return None
    for str_line in path_stamp.read_text(encoding="utf-8").splitlines():
        str_stripped = str_line.strip()
        if str_stripped.startswith("tier:"):
            return str_stripped.split(":", 1)[1].strip()
    return None


_RE_ONE_LINE_FI = re.compile(r";\s*fi\s*$")


def _cp_destinations(str_line: str) -> set[str]:
    """Return the project-relative destinations of every ``cp`` found on one source line.

    Parameters
    ----------
    str_line : str
            One line of the shared scaffold lib.

    Returns
    -------
    set of str
            Destinations matched by the single-file ``cp`` pattern.
    """
    return {str_dst for _, _, str_dst in _RE_CP.findall(str_line)}


def conditional_relpaths(str_lib: str, str_flag: str | None = None) -> set[str]:
    """Return destinations copied under a guard, which are NOT unconditionally required.

    ``.review-bots.yaml`` is copied only when ``INCLUDE_REVIEW_BOT_ROSTER`` is true
    (blueprintx#374). Treating it as required made the drift check report a missing file on
    every project that legitimately declined a reviewer bot.

    Guards recognised: ``if``..``fi`` (any nesting, one-line form included), ``case``..``esac``
    and ``cond && cp`` / ``cond || cp`` chains. The condition is never evaluated; that is
    :func:`review_bot_roster_enabled`'s job, from the provenance stamp.

    Parameters
    ----------
    str_lib : str
            The shared scaffold lib source, line-continuations already spliced.
    str_flag : str, optional
            When given, keep only copies under a guard whose line mentions this name.

    Returns
    -------
    set of str
            Project-relative destinations whose ``cp`` sits under a (matching) guard.
    """
    set_conditional: set[str] = set()
    list_guards: list[bool] = []
    for str_line in str_lib.splitlines():
        str_stripped = str_line.strip()
        str_kind = _line_kind(str_stripped)
        bool_match = str_flag is None or str_flag in str_stripped
        if str_kind == "open":
            list_guards.append(bool_match)
        elif str_kind == "close" and list_guards:
            list_guards.pop()
        bool_guarded = (str_kind in ("open", "oneline", "chain") and bool_match) or (
            str_kind == "plain" and any(list_guards)
        )
        if bool_guarded:
            set_conditional.update(_cp_destinations(str_line))
    return set_conditional


def _line_kind(str_stripped: str) -> str:
    """Classify a stripped lib line by its effect on the guard stack.

    Parameters
    ----------
    str_stripped : str
            One lib line, stripped.

    Returns
    -------
    str
            ``open`` (``if``/``case`` block start), ``oneline`` (a self-closing ``if``/``case``;
            counting it as open would mark every later ``cp`` conditional, a false green),
            ``close`` (``fi``/``esac``), ``chain`` (``&& cp`` / ``|| cp``) or ``plain``.
    """
    if str_stripped.startswith(("if ", "if[", "case ")) or str_stripped == "if":
        bool_closed = _RE_ONE_LINE_FI.search(str_stripped) or _RE_ONE_LINE_ESAC.search(
            str_stripped
        )
        return "oneline" if bool_closed else "open"
    if str_stripped == "fi" or str_stripped.startswith(("fi ", "esac")):
        return "close"
    return "chain" if _RE_CHAINED_CP.search(str_stripped) else "plain"


def review_bot_roster_enabled(path_root: pathlib.Path) -> bool | None:
    """Return the ``review_bot_roster:`` choice stamped at scaffold time, or ``None``.

    Provenance recorded only tier/version/commit/timestamp, so the drift checker could not
    recover an opt-out and had to guess. It now records the choice; ``None`` means the
    project predates the stamp, and the caller must not assume either answer.

    Parameters
    ----------
    path_root : pathlib.Path
            The project root to inspect.

    Returns
    -------
    bool or None
            The stamped choice, or ``None`` when the stamp is absent or silent on it.
    """
    path_stamp = path_root / _PROVENANCE_FILENAME
    if not path_stamp.exists():
        return None
    for str_line in path_stamp.read_text(encoding="utf-8").splitlines():
        str_stripped = str_line.strip()
        if str_stripped.startswith("review_bot_roster:"):
            return str_stripped.split(":", 1)[1].strip() == "true"
    return None


def required_relpaths(path_blueprintx_root: pathlib.Path) -> set[str]:
    """Derive every python-common-sourced path a scaffold copies UNCONDITIONALLY.

    Parsed straight out of ``bin/lib/scaffold_python_templates.sh`` rather than hand-listed,
    so this set cannot drift from what actually gets copied. Deliberately excludes anything
    conditional (the docker-compose choice, webhook/storage opt-ins) — those live OUTSIDE the
    shared step this parses, in each individual ``bin/scaffold/python_*.sh``.

    Parameters
    ----------
    path_blueprintx_root : pathlib.Path
            Root of a BlueprintX checkout.

    Returns
    -------
    set of str
            Project-relative paths (POSIX separators) the shared scaffold step always copies.
            Empty when the shared lib file cannot be found — the caller treats that as SKIPPED,
            never as "nothing is required".
    """
    path_lib = path_blueprintx_root / _SCAFFOLD_LIB_RELPATH
    if not path_lib.exists():
        return set()
    # Splice shell line-continuations BEFORE matching. A `cp "$SRC/x" \\<newline> "$DST/x"`
    # is one command to the shell, but the old file regex stopped at the backslash and skipped
    # it — measured on this branch: 23 destinations found, 52 actually copied, so the
    # drift doctor was blind to 29 of the files it exists to police (blueprintx#109).
    str_lib = _RE_LINE_CONTINUATION.sub(" ", path_lib.read_text(encoding="utf-8"))
    path_templates = {
        "COMMON": path_blueprintx_root / _COMMON_TEMPLATE_RELPATH,
        "SHARED": path_blueprintx_root / "templates/common",
    }

    set_conditional = conditional_relpaths(str_lib)
    set_required: set[str] = set()
    for str_root, str_src, str_dst in _RE_CP.findall(str_lib):
        if str_dst in set_conditional:
            continue
        path_src = path_templates[str_root] / str_src.removesuffix("/.")
        if str_src.endswith("/.") or path_src.is_dir():
            for str_rel in _template_files(path_blueprintx_root, path_src):
                set_required.add(f"{str_dst}/{str_rel}")
        else:
            set_required.add(str_dst)
    return set_required


def _template_files(path_blueprintx_root: pathlib.Path, path_dir: pathlib.Path) -> list[str]:
    """List the template files under ``path_dir``, relative to it.

    Tracked files only when the checkout is a git repo: an untracked artifact (a log, an
    editor swap file) is not a template file and would be a permanent false "missing".
    Falls back to a walk that skips ``__pycache__`` when git cannot answer.

    Parameters
    ----------
    path_blueprintx_root : pathlib.Path
            Root of the BlueprintX checkout.
    path_dir : pathlib.Path
            The template directory to list.

    Returns
    -------
    list of str
            POSIX paths relative to ``path_dir``.
    """
    cls_git = subprocess.run(  # noqa: S603
        ["git", "-C", str(path_blueprintx_root), "ls-files", "-z", "--", str(path_dir)],  # noqa: S607
        capture_output=True,
        check=False,
    )
    if cls_git.returncode == 0:
        return [
            pathlib.Path(str_f).relative_to(path_dir.relative_to(path_blueprintx_root)).as_posix()
            for str_f in cls_git.stdout.decode().split("\0")
            if str_f
        ]
    return [
        path_f.relative_to(path_dir).as_posix()
        for path_f in sorted(path_dir.rglob("*"))
        if path_f.is_file() and "__pycache__" not in path_f.parts
    ]


def missing_relpaths(path_root: pathlib.Path, set_required: set[str]) -> list[str]:
    """Return the required paths that do not exist under the project root, sorted.

    Parameters
    ----------
    path_root : pathlib.Path
            The project root to check.
    set_required : set of str
            Project-relative paths the template ships.

    Returns
    -------
    list of str
            Sorted relative paths present in the template but absent from the project.
    """
    return sorted(str_rel for str_rel in set_required if not (path_root / str_rel).exists())


def _parse_args(list_argv: list) -> tuple[pathlib.Path, pathlib.Path | None]:
    """Parse ``--root`` and ``--blueprintx-root`` out of argv, with env-var fallbacks.

    Parameters
    ----------
    list_argv : list of str
            Raw CLI arguments (``sys.argv[1:]``).

    Returns
    -------
    tuple of (pathlib.Path, pathlib.Path or None)
            The project root (defaults to cwd) and the BlueprintX checkout root (defaults to
            ``BLUEPRINTX_TEMPLATE_ROOT`` in the environment, or ``None`` when unset).
    """
    cls_parser = argparse.ArgumentParser(description="Report template drift.")
    cls_parser.add_argument("--root", default=None)
    cls_parser.add_argument(
        "--blueprintx-root", default=os.environ.get("BLUEPRINTX_TEMPLATE_ROOT")
    )
    cls_args = cls_parser.parse_args(list_argv)
    path_root = pathlib.Path(cls_args.root).resolve() if cls_args.root else pathlib.Path.cwd()
    path_blueprintx = (
        pathlib.Path(cls_args.blueprintx_root).resolve() if cls_args.blueprintx_root else None
    )
    return path_root, path_blueprintx


def _report_missing(str_tier: str, list_missing: list, int_total: int) -> None:
    """Print the drift report body for a non-empty ``list_missing``.

    Parameters
    ----------
    str_tier : str
            The project's stamped tier name.
    list_missing : list of str
            Sorted relative paths the template ships that the project lacks.
    int_total : int
            How many paths were required in total (for the trailing summary line).

    Returns
    -------
    None
    """
    print(
        f"Template drift detected for tier '{str_tier}' — the template ships these paths and "
        f"this project does not have them:\n"
    )
    for str_rel in list_missing:
        print(f"➖ {str_rel}")
    print(
        f"\n{len(list_missing)} of {int_total} required path(s) missing. This is a REPORT, not "
        f"a gate — a project may have removed one of these on purpose; a human decides whether "
        f"to backfill it."
    )


def main(list_argv: list) -> int:
    """Report template drift for the project at ``--root``. Always returns 0 (a reporter).

    Parameters
    ----------
    list_argv : list of str
            CLI arguments (``sys.argv[1:]``).

    Returns
    -------
    int
            Always 0 — see the module docstring for why this never gates.
    """
    path_root, path_blueprintx = _parse_args(list_argv)

    str_tier = read_tier(path_root)
    if str_tier is None:
        print(
            f"SKIPPED: no {_PROVENANCE_FILENAME} at {path_root} — nothing to check. Either this "
            f"tree was not scaffolded by BlueprintX (this repo, run over itself, always takes "
            f"this path), or it predates provenance stamping (blueprintx#109). This run proves "
            f"nothing about drift."
        )
        return 0

    if path_blueprintx is None or not path_blueprintx.exists():
        print(
            f"SKIPPED: tier is '{str_tier}' but no BlueprintX checkout is available to compare "
            f"against — pass --blueprintx-root or set BLUEPRINTX_TEMPLATE_ROOT. This run proves "
            f"nothing about drift."
        )
        return 0

    set_required = required_relpaths(path_blueprintx)
    if not set_required:
        print(
            f"SKIPPED: found no required paths under {path_blueprintx} — "
            f"{_SCAFFOLD_LIB_RELPATH} is missing or unparsable there. This run proves nothing "
            f"about drift, and is NOT the same as a clean comparison."
        )
        return 0

    # Add back the conditional copies this project actually opted into. Only when the
    # provenance stamp SAYS so: `None` (a project scaffolded before the stamp recorded the
    # choice) stays excluded, because reporting a file as missing on a project that
    # legitimately declined it is the false positive this whole branch exists to avoid.
    # After the empty-set SKIPPED above on purpose: that is the only case where the lib is
    # absent, and reading it here unguarded raised FileNotFoundError.
    if review_bot_roster_enabled(path_root):
        set_required |= conditional_relpaths(
            _RE_LINE_CONTINUATION.sub(
                " ", (path_blueprintx / _SCAFFOLD_LIB_RELPATH).read_text(encoding="utf-8")
            ),
            "INCLUDE_REVIEW_BOT_ROSTER",
        )

    list_missing = missing_relpaths(path_root, set_required)
    if not list_missing:
        print(f"No template drift detected — {len(set_required)} required path(s) present.")
        return 0

    _report_missing(str_tier, list_missing, len(set_required))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
