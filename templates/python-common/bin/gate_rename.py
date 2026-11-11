"""Shared rename pairing for the gates that compare a test file against its merge-base."""

import difflib


FLOAT_RENAME_SIMILARITY = 0.8


def rename_pairs(list_removed: list, list_added: list) -> dict:
    """Pair each removed test name with the most similar newly added one.

    Parameters
    ----------
    list_removed : list of str
        Names present at the merge-base and absent now.
    list_added : list of str
        Names present now and absent at the merge-base.

    Returns
    -------
    dict
        ``{removed_name: added_name}``. Pairs are taken best-score first, ties broken by
        name, so the result never depends on source order; each added name is used once.
        A pair is a rename candidate only, so the caller still compares the two bodies.
    """
    list_scored = sorted(
        (-difflib.SequenceMatcher(None, str_old, str_new).ratio(), str_old, str_new)
        for str_old in list_removed
        for str_new in list_added
    )
    dict_pairs = {}
    set_used = set()
    for float_neg, str_old, str_new in list_scored:
        if -float_neg < FLOAT_RENAME_SIMILARITY:
            break
        if str_old not in dict_pairs and str_new not in set_used:
            dict_pairs[str_old] = str_new
            set_used.add(str_new)
    return dict_pairs
