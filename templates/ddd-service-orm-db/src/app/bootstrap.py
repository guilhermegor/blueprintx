"""Service bootstrap: environment loading, logging setup, and timing."""

from __future__ import annotations

import warnings
from time import time

from dotenv import load_dotenv
from stpstone.utils.calendars.calendar_br import DatesBRAnbima
from stpstone.utils.loggs.create_logs import CreateLog
from stpstone.utils.loggs.init_setup import initiate_logging

from src.config.startup import DIR_PARENT, LOGGER


cls_create_log = CreateLog()
cls_dates = DatesBRAnbima()


def init() -> float:
	"""Load environment, configure logging, suppress warnings.

	Returns
	-------
	float
		Monotonic start timestamp for elapsed-time tracking.
	"""
	load_dotenv()
	warnings.simplefilter(action="ignore", category=FutureWarning)
	initiate_logging(LOGGER, DIR_PARENT)
	return time()


def teardown(start_time: float) -> None:
	"""Log elapsed time and routine end datetime.

	Parameters
	----------
	start_time : float
		Timestamp returned by :func:`init`.
	"""
	elapsed = time() - start_time
	hours, remainder = divmod(elapsed, 3600)
	minutes, seconds = divmod(remainder, 60)
	cls_create_log.log_message(
		logger=LOGGER,
		message=f"Time elapsed(HH:MM:SS): {int(hours)}:{int(minutes)}:{seconds:.2f}",
		log_level="info",
	)
	cls_create_log.log_message(
		logger=LOGGER,
		message=f"Routine ended in {cls_dates.curr_datetime()}",
		log_level="info",
	)
