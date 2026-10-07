"""Path-confinement tests for ``JoblibHandler`` (blueprintx#645).

``read``, ``delete`` and ``_verify`` used to build ``self._dir / f"{record_id}.joblib"`` from
an unvalidated ``record_id``. The SHA-256 check only compares the id's last segment to the
file's bytes, and the caller picks that segment, so ``../../x_<date>_<time>_<sha8>`` passed it.
Without a ``secret_key`` that reached ``joblib.load`` on a file outside the store (arbitrary
pickle execution); ``delete`` unlinked outside it; ``create`` wrote outside it through ``_name``.

Every test builds a VALID artifact outside the store first, so the traversal id points at a
file the old code would have accepted. Only the id shape is wrong, which is what makes each
witness red before the fix and green after it.
"""

from __future__ import annotations

import contextlib
from pathlib import Path

import pytest

from chassis.db_wschema.infrastructure.joblib_handler import JoblibHandler


# zlib, not the handler's default lz4: lz4 is not a declared dependency of any tier, and these
# tests are about the id, not the codec.
TUPLE_COMPRESS = ("zlib", 3)

LIST_BAD_ID_SUFFIXES = [
    "../{valid}",
    "../../{valid}",
    "sub/dir/{valid}",
    "..\\{valid}",
    "{valid}/../{valid}",
]


@pytest.fixture
def str_outside_id(tmp_path: Path) -> str:
    """Create a valid artifact directly in ``tmp_path``, outside the store.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest's per-test temporary directory.

    Returns
    -------
    str
        Identifier of an artifact that sits one level above ``tmp_path / "store"``.
    """
    return JoblibHandler(tmp_path, compress=TUPLE_COMPRESS).create(
        {"_name": "payload", "value": 1}
    )


@pytest.fixture
def cls_store(tmp_path: Path) -> JoblibHandler:
    """Return a handler whose store directory is ``tmp_path / "store"``.

    Parameters
    ----------
    tmp_path : pathlib.Path
        Pytest's per-test temporary directory.

    Returns
    -------
    JoblibHandler
        Handler under test, without a ``secret_key``.
    """
    return JoblibHandler(tmp_path / "store", compress=TUPLE_COMPRESS)


@pytest.mark.parametrize("str_template", LIST_BAD_ID_SUFFIXES)
def test_read_rejects_a_path_like_record_id(
    cls_store: JoblibHandler, str_outside_id: str, str_template: str
) -> None:
    """A traversal id is refused instead of loading the artifact it points at."""
    with pytest.raises(ValueError, match="record_id"):
        cls_store.read(str_template.format(valid=str_outside_id))


@pytest.mark.parametrize("str_template", LIST_BAD_ID_SUFFIXES)
def test_delete_rejects_a_path_like_record_id(
    cls_store: JoblibHandler, str_outside_id: str, str_template: str
) -> None:
    """A traversal id is refused instead of unlinking the artifact it points at."""
    with pytest.raises(ValueError, match="record_id"):
        cls_store.delete(str_template.format(valid=str_outside_id))


def test_delete_leaves_the_file_outside_the_store(
    cls_store: JoblibHandler, str_outside_id: str, tmp_path: Path
) -> None:
    """The outside artifact survives a delete attempt through ``../``."""
    with contextlib.suppress(ValueError):
        cls_store.delete(f"../{str_outside_id}")

    assert (tmp_path / f"{str_outside_id}.joblib").exists()


def test_read_rejects_an_absolute_record_id(
    cls_store: JoblibHandler, str_outside_id: str, tmp_path: Path
) -> None:
    """``Path('store') / '/abs/x'`` discards the store, so an absolute id must be refused."""
    with pytest.raises(ValueError, match="record_id"):
        cls_store.read(str(tmp_path / str_outside_id))


def test_delete_rejects_an_absolute_record_id(
    cls_store: JoblibHandler, str_outside_id: str, tmp_path: Path
) -> None:
    """An absolute id is refused by ``delete`` as well."""
    with pytest.raises(ValueError, match="record_id"):
        cls_store.delete(str(tmp_path / str_outside_id))


@pytest.mark.parametrize("str_bad_id", ["", "no-shape", "Upper_20260101_000000_deadbeef"])
def test_read_rejects_an_id_off_the_documented_shape(
    cls_store: JoblibHandler, str_bad_id: str
) -> None:
    """Only ``{kebab-name}_{YYYYMMDD}_{HHMMSS}_{sha8}`` is a record id."""
    with pytest.raises(ValueError, match="record_id"):
        cls_store.read(str_bad_id)


def test_read_rejects_a_symlink_that_leaves_the_store(
    cls_store: JoblibHandler, str_outside_id: str, tmp_path: Path
) -> None:
    """A well-formed id whose file is a symlink out of the store is caught by the resolve check."""
    (tmp_path / "store" / f"{str_outside_id}.joblib").symlink_to(
        tmp_path / f"{str_outside_id}.joblib"
    )

    with pytest.raises(ValueError, match="escapes"):
        cls_store.read(str_outside_id)


@pytest.fixture
def str_stored_id_with_escaping_sig(cls_store: JoblibHandler, tmp_path: Path) -> str:
    """Store an artifact whose ``.sig`` sidecar is a symlink out of the store.

    Parameters
    ----------
    cls_store : JoblibHandler
        Handler under test.
    tmp_path : pathlib.Path
        Pytest's per-test temporary directory.

    Returns
    -------
    str
        Identifier of the stored artifact.
    """
    str_record_id = cls_store.create({"_name": "half", "value": 1})
    (tmp_path / "victim.sig").write_bytes(b"outside")
    (tmp_path / "store" / f"{str_record_id}.sig").symlink_to(tmp_path / "victim.sig")
    return str_record_id


def test_delete_rejects_a_signature_that_leaves_the_store(
    cls_store: JoblibHandler, str_stored_id_with_escaping_sig: str
) -> None:
    """A ``.sig`` symlinked out of the store is refused, not followed."""
    with pytest.raises(ValueError, match="escapes"):
        cls_store.delete(str_stored_id_with_escaping_sig)


def test_delete_leaves_the_artifact_when_its_signature_is_refused(
    cls_store: JoblibHandler, str_stored_id_with_escaping_sig: str, tmp_path: Path
) -> None:
    """Both paths are checked before anything is unlinked, so a refusal deletes nothing."""
    with contextlib.suppress(ValueError):
        cls_store.delete(str_stored_id_with_escaping_sig)

    assert (tmp_path / "store" / f"{str_stored_id_with_escaping_sig}.joblib").exists()


@pytest.mark.parametrize("str_name", ["../evil", "a/b", "..", "a\\b", "/abs", ""])
def test_create_rejects_a_name_outside_the_kebab_charset(
    cls_store: JoblibHandler, str_name: str
) -> None:
    """A ``_name`` carrying a separator or ``..`` is refused before anything is written."""
    with pytest.raises(ValueError, match="_name"):
        cls_store.create({"_name": str_name})


def test_create_writes_nothing_outside_the_store_for_a_traversal_name(
    cls_store: JoblibHandler, tmp_path: Path
) -> None:
    """The rejected ``_name`` leaves no artifact next to the store."""
    with contextlib.suppress(ValueError):
        cls_store.create({"_name": "../evil"})

    assert list(tmp_path.glob("*.joblib")) == []


def test_a_created_record_reads_back(cls_store: JoblibHandler) -> None:
    """The check does not reject the ids ``create`` itself produces (underscores in a name)."""
    str_record_id = cls_store.create({"_name": "my_model", "value": 7})

    assert cls_store.read(str_record_id)["value"] == 7


def test_a_record_without_a_name_reads_back(cls_store: JoblibHandler) -> None:
    """The uuid-hex fallback name is inside the allowed charset."""
    str_record_id = cls_store.create({"value": 3})

    assert cls_store.read(str_record_id)["value"] == 3


def test_a_created_record_can_be_deleted(cls_store: JoblibHandler) -> None:
    """A well-formed id still deletes."""
    str_record_id = cls_store.create({"_name": "gone", "value": 1})

    assert cls_store.delete(str_record_id) is True


def test_update_raises_because_artifacts_are_immutable(cls_store: JoblibHandler) -> None:
    """``update()`` is part of the port but not of this backend (see the factory docstring)."""
    with pytest.raises(NotImplementedError):
        cls_store.update("any_20260101_000000_deadbeef", {"value": 2})
