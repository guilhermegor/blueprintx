"""Shared rename pairing for the gates that compare a test file against its merge-base."""

import ast
import difflib


FLOAT_RENAME_SIMILARITY = 0.8
FLOAT_BODY_SIMILARITY = 0.6


def _ratio(str_a: str, str_b: str) -> float:
    """Return the ``SequenceMatcher`` ratio of two strings.

    Parameters
    ----------
    str_a : str
        First string.
    str_b : str
        Second string.

    Returns
    -------
    float
        Similarity in ``[0, 1]``.
    """
    return difflib.SequenceMatcher(None, str_a, str_b).ratio()


def _statements(cls_func: ast.FunctionDef) -> list:
    """Return the source text of each body statement, docstring excluded.

    Parameters
    ----------
    cls_func : ast.FunctionDef
        A parsed test function.

    Returns
    -------
    list of str
        One ``ast.unparse`` string per statement, so a changed literal or argument makes the
        statement differ instead of hiding inside shared node boilerplate.
    """
    list_body = cls_func.body
    if ast.get_docstring(cls_func, clean=False) is not None:
        list_body = list_body[1:]
    return [ast.unparse(cls_stmt) for cls_stmt in list_body]


def rename_pairs(dict_removed: dict, dict_added: dict) -> dict:
    """Pair each removed test with the added one that is a plausible rename of it.

    Parameters
    ----------
    dict_removed : dict
        ``{name: ast.FunctionDef}`` present at the merge-base and absent now.
    dict_added : dict
        ``{name: ast.FunctionDef}`` present now and absent at the merge-base.

    Returns
    -------
    dict
        ``{removed_name: added_name}``. A pair needs a similar name AND a similar body, so an
        unrelated test with a near-identical name never absorbs a deletion. Pairs are taken
        best name score first, ties broken by name, so the result never depends on source
        order; each added name is used once.
    """
    dict_stmts = {
        str_n: _statements(cls_node) for str_n, cls_node in (dict_removed | dict_added).items()
    }
    list_scored = sorted(
        (-_ratio(str_old, str_new), str_old, str_new)
        for str_old in dict_removed
        for str_new in dict_added
    )
    dict_pairs = {}
    set_used = set()
    for float_neg, str_old, str_new in list_scored:
        if -float_neg < FLOAT_RENAME_SIMILARITY:
            break
        if str_old in dict_pairs or str_new in set_used:
            continue
        cls_matcher = difflib.SequenceMatcher(
            None, dict_stmts[str_old], dict_stmts[str_new], autojunk=False
        )
        if cls_matcher.ratio() >= FLOAT_BODY_SIMILARITY:
            dict_pairs[str_old] = str_new
            set_used.add(str_new)
    return dict_pairs


def deleted_message(str_shown: str, str_name: str, list_unpaired_added: list) -> str:
    """Return the ``deleted`` finding, naming a likely rename target when one exists.

    Parameters
    ----------
    str_shown : str
        Path to show in the message.
    str_name : str
        The removed test name.
    list_unpaired_added : list of str
        Added test names that no removed test was paired with.

    Returns
    -------
    str
        ``<path>: test '<name>' deleted``, plus ``(possible rename of ...)`` when an unpaired
        added name is at least as similar as a rename needs. It stays a finding: the bodies
        differ too much to prove the rename, so a human judges it.
    """
    list_close = difflib.get_close_matches(
        str_name, list_unpaired_added, n=1, cutoff=FLOAT_RENAME_SIMILARITY
    )
    str_hint = f" (possible rename to {list_close[0]!r}, bodies differ)" if list_close else ""
    return f"{str_shown}: test {str_name!r} deleted{str_hint}"
