"""Single entry point for logging through stpstone's ``CreateLog``.

Instead of each model/view instantiating ``CreateLog`` and defining its own
logging helper, this module holds it once: a single ``CreateLog`` instance and a
module-level :func:`log_message` that all callers share. Pass the call site's
``logger`` (or ``None`` to print).
"""

from __future__ import annotations

from logging import Logger
from typing import TYPE_CHECKING

from stpstone.utils.loggs.create_logs import CreateLog


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). mypy reads the single TYPE_CHECKING
# import (no redefinition); at runtime the try/except picks whichever layout shipped.
if TYPE_CHECKING:
	from utils.typing import type_checker
else:
	try:
		from utils.typing import type_checker
	except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
		from chassis.typing import type_checker


_CLS_LOG = CreateLog()


@type_checker
def log_message(logger: Logger | None, str_message: str, str_level: str = "info") -> None:
	"""Log ``str_message`` at ``str_level`` through the shared stpstone logger.

	Parameters
	----------
	logger : logging.Logger | None
		Destination logger; when ``None`` the message is printed with a timestamp.
	str_message : str
		The message to log.
	str_level : str, optional
		One of ``"info"``, ``"warning"``, ``"error"``, ``"critical"``; default
		``"info"``.
	"""
	_CLS_LOG.log_message(logger, str_message, str_level)
