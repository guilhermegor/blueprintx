"""Unit tests for e-mail signature resolution."""

from pathlib import Path

from src.utils.signatures import resolve_signature, to_html


def test_resolve_signature_prefers_sender_file(tmp_path: Path) -> None:
	"""When ``<sender>.html`` exists it is returned in preference to default.

	Parameters
	----------
	tmp_path : Path
		Pytest temporary directory.
	"""
	(tmp_path / "alice@example.com.html").write_text("<p>Alice</p>", encoding="utf-8")
	(tmp_path / "default.html").write_text("<p>Default</p>", encoding="utf-8")
	assert resolve_signature(tmp_path, "alice@example.com") == "<p>Alice</p>"


def test_resolve_signature_falls_back_to_default(tmp_path: Path) -> None:
	"""With no sender-specific file, ``default.html`` is returned.

	Parameters
	----------
	tmp_path : Path
		Pytest temporary directory.
	"""
	(tmp_path / "default.html").write_text("<p>Default</p>", encoding="utf-8")
	assert resolve_signature(tmp_path, "bob@example.com") == "<p>Default</p>"


def test_resolve_signature_returns_empty_when_none_exist(tmp_path: Path) -> None:
	"""With neither file present the result is the empty string.

	Parameters
	----------
	tmp_path : Path
		Pytest temporary directory.
	"""
	assert resolve_signature(tmp_path, "carol@example.com") == ""


def test_to_html_converts_newlines_to_breaks() -> None:
	"""Plain-text newlines become ``<br>`` tags."""
	assert to_html("line 1\nline 2") == "line 1<br>\nline 2"
