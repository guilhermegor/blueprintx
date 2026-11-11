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
    dict_dump = {
        str_n: "".join(ast.dump(cls_stmt) for cls_stmt in cls_node.body)
        for str_n, cls_node in (dict_removed | dict_added).items()
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
        if _ratio(dict_dump[str_old], dict_dump[str_new]) >= FLOAT_BODY_SIMILARITY:
            dict_pairs[str_old] = str_new
            set_used.add(str_new)
    return dict_pairs
