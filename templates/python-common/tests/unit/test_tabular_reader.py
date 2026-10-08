"""Unit tests for the tabular reading seam (contract + dtype enforcement)."""

import csv
from pathlib import Path

import pytest

from src.utils.tabular_reader import (
    ContractError,
    FileContract,
    ProblemReport,
    find_file_problems,
    read_table,
)


def _write_csv(path_dir: Path) -> Path:
    """Write a small ``;``-separated CSV and return its path.

    Parameters
    ----------
    path_dir : pathlib.Path
            Directory in which to create the file.

    Returns
    -------
    pathlib.Path
            Path to the created CSV.
    """
    path_csv = path_dir / "data.csv"
    path_csv.write_text("code;amount\nABC;10\nDEF;20\n", encoding="utf-8")
    return path_csv


@pytest.fixture
def df_typed_read(tmp_path: Path) -> object:
    """Read a valid file through its contract with declared dtypes.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.

    Returns
    -------
    object
        The typed frame.
    """
    pytest.importorskip("pandas")
    path_csv = _write_csv(tmp_path)
    cls_contract = FileContract("data", "data", ("code", "amount"), ())
    return read_table(path_csv, "", {"code": "str", "amount": "int64"}, cls_contract)


def test_read_table_keeps_the_contract_columns(df_typed_read: object) -> None:
    """A valid file passes its contract and keeps its columns.

    Parameters
    ----------
    df_typed_read : object
        The typed frame.
    """
    assert list(df_typed_read.columns) == ["code", "amount"]


def test_read_table_types_the_code_column_as_string(df_typed_read: object) -> None:
    """The declared ``str`` dtype is applied to ``code``.

    Parameters
    ----------
    df_typed_read : object
        The typed frame.
    """
    pd = pytest.importorskip("pandas")
    assert pd.api.types.is_string_dtype(df_typed_read["code"])


def test_read_table_types_the_amount_column_as_int64(df_typed_read: object) -> None:
    """The declared ``int64`` dtype is applied to ``amount``.

    Parameters
    ----------
    df_typed_read : object
        The typed frame.
    """
    assert str(df_typed_read["amount"].dtype) == "int64"


def test_read_table_keeps_the_first_code_value(df_typed_read: object) -> None:
    """The first row's code survives typing.

    Parameters
    ----------
    df_typed_read : object
        The typed frame.
    """
    assert df_typed_read["code"].iloc[0] == "ABC"


@pytest.fixture
def df_padded_read(tmp_path: Path) -> object:
    """Read a zero-padded code and a money decimal as text.

    The regression this guards: reading with pandas' inference (``dtype=None``) parses ``007``
    to the int ``7`` and ``1000.50`` to the float ``1000.5`` *before* typing, and a later
    ``astype`` cannot recover the dropped leading/trailing zeros. Reading as raw text keeps the
    exact source characters, so the declared dtype coerces from ``"007"`` / ``"1000.50"``.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.

    Returns
    -------
    object
        The frame read as text.
    """
    path_csv = tmp_path / "padded.csv"
    path_csv.write_text("code;amount\n007;1000.50\n042;0.10\n", encoding="utf-8")
    cls_contract = FileContract("data", "data", ("code", "amount"), ())
    return read_table(path_csv, "", {"code": "str", "amount": "str"}, cls_contract)


def test_read_table_reads_as_text_preserving_zero_padding(df_padded_read: object) -> None:
    """Leading zeros survive the read.

    Parameters
    ----------
    df_padded_read : object
        The frame read as text.
    """
    assert df_padded_read["code"].tolist() == ["007", "042"]


def test_read_table_reads_as_text_preserving_decimals(df_padded_read: object) -> None:
    """Trailing zeros survive the read.

    Parameters
    ----------
    df_padded_read : object
        The frame read as text.
    """
    assert df_padded_read["amount"].tolist() == ["1000.50", "0.10"]


def test_read_table_raises_on_missing_required_column(tmp_path: Path) -> None:
    """A missing required column raises ContractError before typing."""
    path_csv = _write_csv(tmp_path)
    cls_contract = FileContract("data", "data", ("code", "missing_col"), ())
    with pytest.raises(ContractError, match="missing_col"):
        read_table(path_csv, "", {"code": "str"}, cls_contract)


def test_find_file_problems_reports_without_raising(tmp_path: Path) -> None:
    """find_file_problems returns a ProblemReport instead of raising."""
    path_csv = _write_csv(tmp_path)
    cls_contract = FileContract("data", "data", ("code", "absent"), ())
    cls_report = find_file_problems(cls_contract, path_csv, "")
    assert any("absent" in p for p in cls_report.list_fatal)


def test_find_file_problems_reports_a_missing_file_as_fatal(tmp_path: Path) -> None:
    """A missing file is a FATAL finding, not a FileNotFoundError (the "never raises" half)."""
    cls_contract = FileContract("t", "t", (), ())
    cls_report = find_file_problems(cls_contract, tmp_path / "nope.csv", "")
    assert "not found" in " ".join(cls_report.list_fatal)


def test_find_file_problems_missing_column_is_fatal_never_a_warning(tmp_path: Path) -> None:
    """A missing required column lands in ``list_fatal``, never in ``list_warnings``.

    Should-fail witness for blueprintx#162: under the OLD flat-list shape, a caller wanting to
    "proceed with a note" on cosmetic problems had to string-match messages — e.g. skip
    anything mentioning "CNPJ" — and nothing stopped it from ALSO matching a missing-column
    message by accident, silently swallowing a fatal problem as a warning. Under the new
    shape that mistake is unrepresentable: a caller reading only ``list_warnings`` (its
    "proceed" branch) cannot see this finding at all, because it is never placed there.
    """
    path_csv = _write_csv(tmp_path)
    cls_contract = FileContract("data", "data", ("code", "absent"), ())
    cls_report = find_file_problems(cls_contract, path_csv, "")
    assert any("absent" in p for p in cls_report.list_fatal)


def test_find_file_problems_missing_column_leaves_warnings_empty(tmp_path: Path) -> None:
    """A missing required column is not duplicated into ``list_warnings``."""
    path_csv = _write_csv(tmp_path)
    cls_contract = FileContract("data", "data", ("code", "absent"), ())
    cls_report = find_file_problems(cls_contract, path_csv, "")
    assert cls_report.list_warnings == []


def test_header_only_file_passes_its_cnpj_contract(tmp_path: Path) -> None:
    """A source reporting "nothing today" by shipping its header alone is not a broken file.

    Negative control for the ``any()``-over-an-empty-series trap: ``any()`` of an empty series
    is ``False``, the same answer a column of garbage gives, so the pre-fix code reproved a
    well-formed header-only file as "holds no valid CNPJ" and killed the run.
    """
    path_csv = tmp_path / "empty.csv"
    path_csv.write_text("cnpj;amount\n", encoding="utf-8")
    cls_contract = FileContract("data", "data", ("cnpj", "amount"), ("cnpj",))
    cls_report = find_file_problems(cls_contract, path_csv, "")
    assert cls_report == ProblemReport(list_fatal=[], list_warnings=[])


def test_populated_cnpj_column_with_no_valid_value_is_a_warning_not_fatal(
    tmp_path: Path,
) -> None:
    """A populated-but-invalid CNPJ column is reported, but as a WARNING, never fatal.

    The other half of the control above: skipping an empty column is right, skipping a
    populated-but-invalid one would delete the check entirely — it must still be reported.
    It is content-quality, not structural (the column is present, the shape is sound), which
    is why it belongs in ``list_warnings`` rather than ``list_fatal`` — see the should-fail
    witness in ``test_find_file_problems_missing_column_is_fatal_never_a_warning``.
    """
    path_csv = tmp_path / "garbage.csv"
    path_csv.write_text("cnpj;amount\nnot-a-cnpj;10\nalso-not;20\n", encoding="utf-8")
    cls_contract = FileContract("data", "data", ("cnpj", "amount"), ("cnpj",))
    cls_report = find_file_problems(cls_contract, path_csv, "")
    assert any("holds no valid CNPJ" in p for p in cls_report.list_warnings)


def test_populated_cnpj_column_with_no_valid_value_is_never_fatal(tmp_path: Path) -> None:
    """The populated-but-invalid CNPJ column adds nothing to ``list_fatal``."""
    path_csv = tmp_path / "garbage.csv"
    path_csv.write_text("cnpj;amount\nnot-a-cnpj;10\nalso-not;20\n", encoding="utf-8")
    cls_contract = FileContract("data", "data", ("cnpj", "amount"), ("cnpj",))
    cls_report = find_file_problems(cls_contract, path_csv, "")
    assert cls_report.list_fatal == []


def test_missing_cnpj_value_is_not_stringified_to_nan(tmp_path: Path) -> None:
    """A blank cell must not reach the validator as the literal string ``"nan"``.

    ``.astype(str)`` is not NA-safe below pandas 3: it renders a missing value as ``"nan"``,
    which then fails validation for the wrong reason. ``safe_str`` yields ``""``. A valid
    sibling row keeps the column passing, proving the blank was skipped rather than counted.
    """
    path_csv = tmp_path / "blank.csv"
    path_csv.write_text("cnpj;amount\n;10\n11.222.333/0001-81;20\n", encoding="utf-8")
    cls_contract = FileContract("data", "data", ("cnpj", "amount"), ("cnpj",))
    cls_report = find_file_problems(cls_contract, path_csv, "")
    assert cls_report == ProblemReport(list_fatal=[], list_warnings=[])


def test_empty_contract_constrains_nothing(tmp_path: Path) -> None:
    """An empty contract still declares intent and passes any well-formed file."""
    path_csv = _write_csv(tmp_path)
    cls_contract = FileContract("data", "data", (), ())
    df_out = read_table(path_csv, "", {"code": "str", "amount": "int64"}, cls_contract)
    assert len(df_out) == 2


def _write_malformed_quote_csv(path_dir: Path) -> Path:
    """Write a ``;``-CSV whose middle row has an unclosed ``"`` in a free-text field.

    Mirrors real CVM open data: an upstream submitter leaves a stray double quote in a
    deliberation field that also contains ``;``. The default reader treats the ``"`` as a
    field wrapper and swallows the delimiter (and following rows); ``QUOTE_NONE`` does not.

    Parameters
    ----------
    path_dir : pathlib.Path
            Directory in which to create the file.

    Returns
    -------
    pathlib.Path
            Path to the created CSV.
    """
    # The stray quote opens a free-text MIDDLE column, so the delimiter after it is the real
    # separator before amount. Under default quoting the open quote swallows that separator plus
    # the trailing rows, whereas QUOTE_NONE keeps the row's three real fields intact.
    path_csv = path_dir / "malformed.csv"
    path_csv.write_text(
        'code;note;amount\nABC;ok;10\nDEF;"parecer aprovado;20\nGHI;fine;30\n',
        encoding="utf-8",
    )
    return path_csv


@pytest.fixture
def df_quote_none_read(tmp_path: Path) -> object:
    """Read a ``;``-dump whose free-text field has a stray quote, with ``QUOTE_NONE``.

    Were the ``quoting`` argument not threaded through to the reader, the default
    ``QUOTE_MINIMAL`` would treat the stray ``"`` as a field wrapper and either drop rows or
    raise a tokenizing error — so this positive read passing is itself the proof it is passed
    through (default-quoting corruption is pandas-version dependent, hence not asserted here).

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.

    Returns
    -------
    object
        The frame read with ``QUOTE_NONE``.
    """
    path_csv = _write_malformed_quote_csv(tmp_path)
    cls_contract = FileContract("data", "data", (), ())
    dict_dtypes = {"code": "str", "amount": "str", "note": "str"}
    return read_table(path_csv, "", dict_dtypes, cls_contract, int_csv_quoting=csv.QUOTE_NONE)


def test_read_table_quote_none_keeps_every_row(df_quote_none_read: object) -> None:
    """All rows survive; the stray quote is literal text.

    Parameters
    ----------
    df_quote_none_read : object
        The frame read with ``QUOTE_NONE``.
    """
    assert len(df_quote_none_read) == 3


def test_read_table_quote_none_keeps_the_stray_quote_literal(df_quote_none_read: object) -> None:
    """The row with the stray quote carries it as text.

    Parameters
    ----------
    df_quote_none_read : object
        The frame read with ``QUOTE_NONE``.
    """
    assert df_quote_none_read["note"].iloc[1] == '"parecer aprovado'


def test_read_table_quote_none_reads_the_amounts_after_the_stray_quote(
    df_quote_none_read: object,
) -> None:
    """The columns after the stray quote are read intact.

    Parameters
    ----------
    df_quote_none_read : object
        The frame read with ``QUOTE_NONE``.
    """
    assert df_quote_none_read["amount"].tolist() == ["10", "20", "30"]


@pytest.fixture
def df_json_read(tmp_path: Path) -> object:
    """Read a JSON document holding a padded code and a money value as text.

    ``read_table``'s docstring promises the file is *always* read as text, never with pandas'
    inference — but the JSON branch used ``pd.read_json``, which infers regardless. Measured:
    it returns ``1000.5`` for a document that literally contains the STRING ``"1000.50"``, and
    ``7`` for ``"007"``. The scale is unrecoverable afterwards, so a money column ingested from
    an API silently lost its cents.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.

    Returns
    -------
    object
        The frame read as text.
    """
    path_json = tmp_path / "money.json"
    path_json.write_text(
        '[{"code": "007", "amount": "1000.50"}, {"code": "042", "amount": 0.10}]',
        encoding="utf-8",
    )
    cls_contract = FileContract("data", "data", ("code", "amount"), ())
    return read_table(path_json, "", {"code": "str", "amount": "str"}, cls_contract)


def test_read_table_json_preserves_zero_padding(df_json_read: object) -> None:
    """The JSON branch keeps leading zeros, as the CSV branch does.

    Parameters
    ----------
    df_json_read : object
        The frame read as text.
    """
    assert df_json_read["code"].tolist() == ["007", "042"]


def test_read_table_json_preserves_decimal_scale(df_json_read: object) -> None:
    """The JSON branch keeps the decimal scale, even for a bare JSON number token.

    Parameters
    ----------
    df_json_read : object
        The frame read as text.
    """
    assert df_json_read["amount"].tolist() == ["1000.50", "0.10"]


def test_padded_column_name_is_stripped_at_the_read_boundary(tmp_path: Path) -> None:
    """A header cell with a trailing space must not produce an unreachable column.

    The nasty part is that it does not look like a defect: the column PRINTS as ``amount``
    while only ``df["amount "]`` reaches it, so the contract reports a required column missing
    and every lookup raises KeyError on a name plainly visible in ``df.columns``. It is
    per-dataset, never per-format — a sibling table from the same publisher is usually clean.
    """
    path_csv = tmp_path / "padded_header.csv"
    path_csv.write_text("code ;amount \nABC;10\n", encoding="utf-8")
    cls_contract = FileContract("data", "data", ("code", "amount"), ())
    df_out = read_table(path_csv, "", {"code": "str", "amount": "str"}, cls_contract)
    assert list(df_out.columns) == ["code", "amount"]


@pytest.fixture
def df_wide_read(tmp_path: Path) -> object:
    """Read a positional payload whose rows are wider than the header, surplus empty.

    Parameters
    ----------
    tmp_path : pathlib.Path
        A throwaway directory pytest provides per test.

    Returns
    -------
    object
        The frame read.
    """
    path_json = tmp_path / "wide.json"
    path_json.write_text(
        '{"columns": ["code", "amount"], "rows": [["ABC", "10", null], ["DEF", "20", null]]}',
        encoding="utf-8",
    )
    cls_contract = FileContract("data", "data", ("code", "amount"), ())
    return read_table(path_json, "", {"code": "str", "amount": "str"}, cls_contract)


def test_positional_payload_drops_a_surplus_position_that_is_empty_everywhere(
    df_wide_read: object,
) -> None:
    """A row wider than its header is tolerated only when the surplus is empty on every row.

    Parameters
    ----------
    df_wide_read : object
        The frame read.
    """
    assert list(df_wide_read.columns) == ["code", "amount"]


def test_positional_payload_keeps_the_declared_values_when_dropping_the_surplus(
    df_wide_read: object,
) -> None:
    """Dropping the empty surplus position leaves the declared columns' values intact.

    Parameters
    ----------
    df_wide_read : object
        The frame read.
    """
    assert df_wide_read["amount"].tolist() == ["10", "20"]


def test_positional_payload_raises_when_the_surplus_holds_a_value(tmp_path: Path) -> None:
    """A surplus position carrying data must raise, never be trimmed away.

    The payload is positional, so a surplus value cannot be named — and blind trimming is
    exactly how a source column stops arriving with nothing going red: a contract validates
    column PRESENCE, not payload WIDTH.
    """
    path_json = tmp_path / "wide_valued.json"
    path_json.write_text(
        '{"columns": ["code", "amount"], "rows": [["ABC", "10", "surprise"]]}',
        encoding="utf-8",
    )
    cls_contract = FileContract("data", "data", ("code", "amount"), ())
    with pytest.raises(ContractError, match="surplus position"):
        read_table(path_json, "", {"code": "str", "amount": "str"}, cls_contract)


def test_positional_payload_raises_on_a_row_narrower_than_its_header(tmp_path: Path) -> None:
    """A short row is a defect too — padding it would invent data."""
    path_json = tmp_path / "narrow.json"
    path_json.write_text('{"columns": ["code", "amount"], "rows": [["ABC"]]}', encoding="utf-8")
    cls_contract = FileContract("data", "data", ("code", "amount"), ())
    with pytest.raises(ContractError, match="narrower"):
        read_table(path_json, "", {"code": "str", "amount": "str"}, cls_contract)


def test_column_names_colliding_after_trimming_are_rejected(tmp_path: Path) -> None:
    """Two names that differ only by surrounding spaces must not silently become one.

    Stripping is the fix for an unreachable padded column, but it can collide: a source
    shipping both ``code`` and ``code `` yields two columns named ``code``. The contract's
    required-column check still passes — the name IS present — while every later lookup
    returns a DataFrame instead of a Series and ``apply_dtypes`` types an ambiguous schema.
    """
    path_csv = tmp_path / "collide.csv"
    path_csv.write_text("code;code ;amount\nABC;DEF;10\n", encoding="utf-8")
    cls_contract = FileContract("data", "data", ("code",), ())
    with pytest.raises(ContractError, match="collide after trimming"):
        read_table(path_csv, "", {"code": "str", "amount": "str"}, cls_contract)
