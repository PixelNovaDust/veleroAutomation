import logging
import os
import sys
import tempfile
from datetime import datetime, timedelta
from logging.handlers import MemoryHandler

from colorama import Fore, Style, just_fix_windows_console

from app.paths import (
    ensure_directory,
    is_directory_writable,
    resolve_path
)


just_fix_windows_console()


LOGGER_NAME = "velero"

SUCCESS_LEVEL = 25
SKIPPED_LEVEL = 35

BOOTSTRAP_CAPACITY = 500

logging.addLevelName(SUCCESS_LEVEL, "SUCCESS")
logging.addLevelName(SKIPPED_LEVEL, "SKIPPED")


def success(self, message, *args, **kwargs):
    if self.isEnabledFor(SUCCESS_LEVEL):
        self._log(SUCCESS_LEVEL, message, args, **kwargs)


def skipped(self, message, *args, **kwargs):
    if self.isEnabledFor(SKIPPED_LEVEL):
        self._log(SKIPPED_LEVEL, message, args, **kwargs)


logging.Logger.success = success
logging.Logger.skipped = skipped


LABEL_WIDTH = 19


def format_context(value):
    return "{:<12}".format(str(value)[:12])


def format_label(value):
    return "{:<{}}".format(str(value), LABEL_WIDTH)


def file_only():
    """Extra payload keeping a record out of the console."""

    return {
        "console": False
    }


def resolve_level(value, default=logging.DEBUG):

    if isinstance(value, int):
        return value

    if not value:
        return default

    level = logging.getLevelName(
        str(value).strip().upper()
    )

    if isinstance(level, int):
        return level

    return default


class ConsoleFilter(logging.Filter):

    def filter(self, record):
        return getattr(record, "console", True)


class ConsoleFormatter(logging.Formatter):

    def format(self, record):

        timestamp = datetime.fromtimestamp(
            record.created
        ).strftime("%Y-%m-%d %H:%M:%S")

        level = record.levelname
        message = record.getMessage()

        if (
            level == "INFO"
            and message.startswith(
                "Starting Velero Automation"
            )
        ):
            color = Fore.MAGENTA

        elif level == "INFO":
            color = Fore.YELLOW

        elif level == "DEBUG":
            color = Fore.CYAN

        elif level == "SUCCESS":
            color = Fore.GREEN

        elif level == "SKIPPED":
            color = Fore.YELLOW

        elif level == "WARNING":
            color = Fore.YELLOW

        elif level == "ERROR":
            color = Fore.RED

        else:
            color = Fore.WHITE

        return (
            color +
            "{} | {:7} | {}".format(
                timestamp,
                level,
                message
            ) +
            Style.RESET_ALL
        )


class FileFormatter(logging.Formatter):

    def format(self, record):

        timestamp = datetime.fromtimestamp(
            record.created
        ).strftime("%Y-%m-%d %H:%M:%S")

        line = "{} | {:7} | {}".format(
            timestamp,
            record.levelname,
            record.getMessage()
        )

        # Tracebacks are kept in the file only, so the console
        # stays readable while the log stays diagnosable.
        if record.exc_info:

            if not record.exc_text:
                record.exc_text = self.formatException(
                    record.exc_info
                )

            line = "{}\n{}".format(line, record.exc_text)

        return line


def setup_logger():
    """
    Console logger available before the config is read.

    Records are also buffered in memory so the startup lines
    can be replayed into the log file once its location is
    known from the config.
    """

    logger = logging.getLogger(LOGGER_NAME)

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        return logger

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(ConsoleFormatter())

    # Allow detailed file-only messages
    # to remain hidden from console.
    console_handler.addFilter(ConsoleFilter())

    bootstrap_handler = MemoryHandler(
        capacity=BOOTSTRAP_CAPACITY,
        flushLevel=logging.CRITICAL + 1,
        target=None
    )

    bootstrap_handler.setLevel(logging.DEBUG)
    bootstrap_handler.set_name("bootstrap")

    logger.addHandler(console_handler)
    logger.addHandler(bootstrap_handler)

    return logger


def attach_file_logging(logger, config):
    """
    Add the file handler described by the config and replay any
    records emitted before the config was available.

    A log file that cannot be created must never stop a run, so
    the temp directory is used as a fallback and console-only
    logging as a last resort.
    """

    settings = config.get("logging", {})

    base_directory = (
        config
        .get("runtime", {})
        .get("base_directory")
    )

    console_level = resolve_level(
        settings.get("console_level"),
        logging.DEBUG
    )

    file_level = resolve_level(
        settings.get("level"),
        logging.DEBUG
    )

    for handler in logger.handlers:

        if isinstance(handler, logging.StreamHandler) and not isinstance(
            handler,
            logging.FileHandler
        ):
            handler.setLevel(console_level)

    # Keep the call idempotent so a second configuration pass
    # cannot write every line to the log twice.
    for handler in list(logger.handlers):

        if isinstance(handler, logging.FileHandler):

            logger.removeHandler(handler)
            handler.close()

    log_directory = _prepare_log_directory(
        settings,
        base_directory,
        logger
    )

    log_file = None

    if log_directory:

        file_name = (
            settings.get("file_name")
            or "velero-automation.log"
        )

        log_file = os.path.join(
            log_directory,
            file_name
        )

        _rotate_daily(log_file, logger)

        _apply_retention(
            log_directory,
            file_name,
            settings.get("retention_days"),
            logger
        )

        try:

            file_handler = logging.FileHandler(
                log_file,
                mode="a",
                encoding="utf-8"
            )

            file_handler.setLevel(file_level)
            file_handler.setFormatter(FileFormatter())

            logger.addHandler(file_handler)

        except OSError as error:

            log_file = None

            logger.warning(
                "Log file could not be opened, "
                "continuing on console only: %s",
                error
            )

    _flush_bootstrap(logger)

    return log_file


def _prepare_log_directory(settings, base_directory, logger):

    configured = resolve_path(
        settings.get("directory") or "logs",
        base_directory
    )

    candidates = [configured]

    fallback = os.path.join(
        tempfile.gettempdir(),
        "velero-automation-logs"
    )

    if fallback != configured:
        candidates.append(fallback)

    for index, candidate in enumerate(candidates):

        try:
            ensure_directory(candidate)

        except OSError:
            continue

        if not is_directory_writable(candidate):
            continue

        if index > 0:

            logger.warning(
                "Log directory %s is not writable, using %s",
                configured,
                candidate
            )

        return candidate

    logger.warning(
        "No writable log directory found, "
        "continuing on console only."
    )

    return None


def _rotate_daily(log_file, logger):
    """
    Keep one file per calendar day. The active file is renamed
    only when it was last written on an earlier day.
    """

    if not os.path.exists(log_file):
        return

    try:

        modified_date = datetime.fromtimestamp(
            os.path.getmtime(log_file)
        ).date()

    except OSError:
        return

    if modified_date == datetime.now().date():
        return

    directory, file_name = os.path.split(log_file)
    stem, extension = os.path.splitext(file_name)

    backup_file = os.path.join(
        directory,
        "{}-{}{}".format(
            stem,
            modified_date.strftime("%Y-%m-%d"),
            extension
        )
    )

    try:

        if os.path.exists(backup_file):
            os.remove(backup_file)

        os.rename(log_file, backup_file)

    except OSError as error:

        # Another engineer's session may still hold the file on
        # a synced folder. Appending is better than failing.
        logger.debug(
            "Log file could not be rotated: %s",
            error,
            extra=file_only()
        )


def _apply_retention(log_directory, file_name, retention_days, logger):

    try:
        retention_days = int(retention_days)

    except (TypeError, ValueError):
        return

    if retention_days <= 0:
        return

    stem, extension = os.path.splitext(file_name)

    cutoff = (
        datetime.now() - timedelta(days=retention_days)
    ).date()

    try:
        entries = os.listdir(log_directory)

    except OSError:
        return

    for entry in entries:

        if entry == file_name:
            continue

        if not entry.startswith(stem + "-"):
            continue

        if not entry.endswith(extension):
            continue

        stamp = entry[len(stem) + 1:len(entry) - len(extension)]

        try:
            stamp_date = datetime.strptime(
                stamp,
                "%Y-%m-%d"
            ).date()

        except ValueError:
            continue

        if stamp_date >= cutoff:
            continue

        try:
            os.remove(
                os.path.join(log_directory, entry)
            )

        except OSError as error:

            logger.debug(
                "Old log %s could not be removed: %s",
                entry,
                error,
                extra=file_only()
            )


def _flush_bootstrap(logger):
    """Replay buffered startup records into the file handler."""

    bootstrap_handler = None

    for handler in logger.handlers:

        if isinstance(handler, MemoryHandler):
            bootstrap_handler = handler
            break

    if not bootstrap_handler:
        return

    targets = [
        handler
        for handler in logger.handlers
        if isinstance(handler, logging.FileHandler)
    ]

    for record in bootstrap_handler.buffer:

        for handler in targets:

            if record.levelno >= handler.level:
                handler.handle(record)

    bootstrap_handler.buffer = []

    logger.removeHandler(bootstrap_handler)

    bootstrap_handler.close()
