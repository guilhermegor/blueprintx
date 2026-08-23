"""Logging module — self-contained in-repo logging seam.

One home for the project's logging, so no external logging dependency is needed:

- :class:`CreateLog` — configures a file logger (:meth:`CreateLog.basic_conf`) and emits messages
  with caller context (:meth:`CreateLog.log_message`); the message is prefixed with
  ``[ClassName.method_name]``, reconstructed by walking the call stack.
- :func:`log_message` — the shared entry point every model/view/controller calls, holding a
  single ``CreateLog`` instance so callers never instantiate their own.
- :func:`initiate_logging` — bootstraps a run's logging: ensures the log parent directory exists
  and records the run's start datetime (stdlib UTC) and operator.

Layout-agnostic: ships into both MVC (``utils``) and DDD (``chassis``) skeletons.
"""

from datetime import datetime
from getpass import getuser
import inspect
import logging
import os
import time
from typing import TYPE_CHECKING, Literal
from zoneinfo import ZoneInfo


# Runtime type-checking engine — layout-agnostic (utils.typing in MVC, chassis.typing in
# DDD; always injected, just at different paths). mypy reads the single TYPE_CHECKING
# import (no redefinition); at runtime the try/except picks whichever layout shipped.
if TYPE_CHECKING:
	from utils.typing import TypeChecker, type_checker
else:
	try:
		from utils.typing import TypeChecker, type_checker
	except ModuleNotFoundError:  # DDD ships the engine as chassis.typing
		from chassis.typing import TypeChecker, type_checker


# Frame modules skipped when reconstructing the caller context: the stdlib logging and inspect
# machinery, pydantic and typing internals, the project's own runtime type-checker, and the
# logging seam itself (logs, logs emitter, retry) whose wrapper frames would otherwise mask the
# real caller. Matched on the module name's last dotted component (see the walker below), so a
# package-qualified name still matches its final segment where a prefix match would not.
_SET_SKIP_MODULES = frozenset(
	{"pydantic", "typing", "inspect", "logging", "logs", "logs_emitter", "retry"}
)

# The severities a message may carry — shared by ``CreateLog.log_message`` and the module-level
# ``log_message`` seam so the two never drift (mypy checks the forwarded argument against this).
LogLevel = Literal["info", "warning", "error", "critical"]


class CreateLog(metaclass=TypeChecker):
	"""Create and manage log files with a customizable format and caller context."""

	def _validate_path(
		self, path: str
	) -> None:  # complexity-ok: two distinct validation faults, each with its own message
		"""Validate a path string.

		Parameters
		----------
		path : str
			Path to validate.

		Raises
		------
		ValueError
			If ``path`` is empty or not a string.
		"""
		# ⚠️ Type BEFORE emptiness. The other order described a non-string falsy value, such
		# as zero or an empty list, as "cannot be empty" — which sends the reader looking for
		# a blank string that was never there.
		if not isinstance(path, str):
			raise ValueError("Path must be a string")
		if not path:
			raise ValueError("Path cannot be empty")

	def creating_parent_folder(self, new_path: str) -> bool:
		"""Create the parent folder if it does not already exist.

		Parameters
		----------
		new_path : str
			Directory path to create.

		Returns
		-------
		bool
			``True`` if the folder was created, ``False`` if it already existed.
		"""
		self._validate_path(new_path)
		if not os.path.exists(new_path):
			os.makedirs(new_path)
			return True
		return False

	def basic_conf(
		self, complete_path: str, basic_level: Literal["info", "debug"] = "info"
	) -> logging.Logger:
		"""Configure a file logger.

		Parameters
		----------
		complete_path : str
			Full path to the log file.
		basic_level : Literal['info', 'debug']
			Logging level (default: ``"info"``).

		Returns
		-------
		logging.Logger
			The configured logger instance.

		Raises
		------
		ValueError
			If an invalid logging level is provided.
		"""
		self._validate_path(complete_path)

		dict_level_mapping = {"info": logging.INFO, "debug": logging.DEBUG}

		try:
			int_level = dict_level_mapping[basic_level]
		except KeyError as err:
			raise ValueError("Level was not properly defined in basic config of logging") from err

		logger = logging.getLogger(__name__)
		logger.setLevel(int_level)
		handler = logging.FileHandler(complete_path)
		handler.setFormatter(
			logging.Formatter(
				"%(asctime)s.%(msecs)03d %(levelname)s {%(module)s} [%(funcName)s] %(message)s",
				datefmt="%Y-%m-%d,%H:%M:%S",
			)
		)
		logger.handlers.clear()
		logger.addHandler(handler)
		return logger

	def log_message(
		self,
		logger: logging.Logger | None,
		message: str,
		log_level: LogLevel,
	) -> None:
		"""Log a message with reconstructed caller context.

		Parameters
		----------
		logger : logging.Logger | None
			Logger instance, or ``None`` to print to the console.
		message : str
			Message to log.
		log_level : LogLevel
			Logging level — one of ``"info"`` / ``"warning"`` / ``"error"`` / ``"critical"``.

		Raises
		------
		ValueError
			If ``log_level`` is empty or not a valid logger method.
		"""
		if not log_level:
			raise ValueError("log_level cannot be empty")

		str_class_name, str_method_name = self._caller_context()
		self._emit(logger, log_level, message, str_class_name, str_method_name)

	def _caller_context(self) -> tuple[str, str]:  # complexity-ok: a stack walk IS the work here
		"""Walk back up the stack to the first frame outside this logging machinery.

		Its own method because it is a separate job from formatting and emitting: this one
		asks "who called us?", and answering it means inspecting frames, which is inherently
		a search with several exit conditions.

		Returns
		-------
		tuple of (str, str)
			The caller's class name and method name, with placeholder values when the walk
			finds no attributable frame.
		"""
		frame = inspect.currentframe()
		str_class_name = "UnknownClass"
		str_method_name = "unknown_method"

		while frame:
			frame = frame.f_back
			if not frame:
				break
			str_module_name = frame.f_globals.get("__name__", "UnknownModule")
			# Match on the module name's last dotted component so a package-qualified module
			# still matches its final segment. A prefix match silently failed for the nested,
			# distributable layout and misattributed the caller class.
			if str_module_name.rsplit(".", 1)[-1] in _SET_SKIP_MODULES:
				continue
			self_potential_cls = frame.f_locals.get("self")
			if self_potential_cls is not None and not isinstance(
				self_potential_cls, self.__class__
			):
				str_class_name = self_potential_cls.__class__.__name__
				str_method_name = frame.f_code.co_name
				break
			str_method_name = frame.f_code.co_name

		return str_class_name, str_method_name

	def _emit(  # complexity-ok: two sinks and one rejected level, one branch each
		self,
		logger: logging.Logger | None,
		log_level: LogLevel,
		message: str,
		str_class_name: str,
		str_method_name: str,
	) -> None:
		"""Send one already-attributed message to the logger, or to stdout when there is none.

		Parameters
		----------
		logger : logging.Logger or None
			The sink; ``None`` prints a formatted line instead.
		log_level : LogLevel
			The level name, which must name a logger method.
		message : str
			The message body.
		str_class_name : str
			The caller's class, from :meth:`_caller_context`.
		str_method_name : str
			The caller's method, from :meth:`_caller_context`.

		Returns
		-------
		None

		Raises
		------
		ValueError
			If ``log_level`` does not name a method on ``logger``.
		"""
		if logger is None:
			str_timestamp = (
				f"{time.strftime('%Y-%m-%d,%H:%M:%S')}.{int(time.time() * 1000) % 1000:03d}"
			)
			print(
				f"{str_timestamp} {log_level.upper()} {{{str_class_name}}} "
				f"[{str_method_name}] {message}"
			)
			return

		fn_log = getattr(logger, log_level, None)
		if fn_log is None:
			raise ValueError(f"Invalid log level: {log_level}")
		fn_log(f"[{str_class_name}.{str_method_name}] {message}")


_CLS_LOG = CreateLog()


@type_checker
def log_message(
	logger: logging.Logger | None, str_message: str, str_level: LogLevel = "info"
) -> None:
	"""Log ``str_message`` at ``str_level`` through the shared logger.

	Parameters
	----------
	logger : logging.Logger | None
		Destination logger; when ``None`` the message is printed with a timestamp.
	str_message : str
		The message to log.
	str_level : LogLevel, optional
		One of ``"info"``, ``"warning"``, ``"error"``, ``"critical"``; default ``"info"``.
	"""
	_CLS_LOG.log_message(logger, str_message, str_level)


# What each outcome of the parent-folder attempt means, expressed as data. Anything absent
# from this table is an unexpected value and is rejected rather than silently ignored.
_DICT_PARENT_FOLDER_OUTCOME = {
	True: "Logs parent directory created successfully.",
	False: "Logs parent directory could not be created.",
}


@type_checker
def _report_parent_folder(
	cls_create_log: CreateLog, logger: logging.Logger | None, path_log: str
) -> None:
	"""Create the log file's parent directory and report the outcome.

	Parameters
	----------
	cls_create_log : CreateLog
		The logging helper doing the work and the reporting.
	logger : logging.Logger or None
		Destination for the report.
	path_log : str
		The log-file directory to create.

	Returns
	-------
	None

	Raises
	------
	RuntimeError
		If the attempt reports an outcome this module does not recognise.
	"""
	bool_dispatch = cls_create_log.creating_parent_folder(path_log)
	cls_create_log.log_message(logger, f"Logs parent directory: {path_log}", "info")
	# The outcome names a message, so it is a lookup rather than a branch chain — and the
	# table doubles as the set of values considered valid, one source instead of two.
	str_outcome = _DICT_PARENT_FOLDER_OUTCOME.get(bool_dispatch)
	if str_outcome is None:
		raise RuntimeError(f"Unexpected dispatch value: {bool_dispatch}") from None
	cls_create_log.log_message(logger, str_outcome, "info")


@type_checker
def _validate_path_log(path_log: str | None) -> None:
	"""Validate the log path.

	Parameters
	----------
	path_log : str | None
		Path for the log-file directory.

	Raises
	------
	ValueError
		If ``path_log`` is an empty string.
	"""
	if path_log == "":
		raise ValueError("Log path cannot be an empty string")


@type_checker
def initiate_logging(logger: logging.Logger, path_log: str | None = None) -> None:
	"""Initialise logging with directory creation and operator information.

	Parameters
	----------
	logger : logging.Logger
		Logger instance for the run.
	path_log : str | None
		Path for the log-file directory (default: ``None``).

	Raises
	------
	RuntimeError
		If an unexpected dispatch value is returned from directory creation.
	"""
	_validate_path_log(path_log)

	cls_create_log = CreateLog()

	if path_log is not None:
		_report_parent_folder(cls_create_log, logger, path_log)

	dt_now = datetime.now(tz=ZoneInfo("UTC"))
	cls_create_log.log_message(logger, f"Routine started at {dt_now}", "info")
	cls_create_log.log_message(logger, f"Routine operator {getuser()}", "info")
