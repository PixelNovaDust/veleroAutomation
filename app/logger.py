import logging
import os
import sys
from datetime import datetime

from colorama import Fore, Style, just_fix_windows_console


just_fix_windows_console()


SUCCESS_LEVEL = 25
SKIPPED_LEVEL = 35

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


def format_context(value):
    return "{:<12}".format(str(value)[:12])


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

        return "{} | {:7} | {}".format(
            timestamp,
            record.levelname,
            record.getMessage()
        )


def setup_logger():

    project_root = os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )

    log_directory = os.path.join(
        project_root,
        "logs"
    )

    os.makedirs(
        log_directory,
        exist_ok=True
    )

    log_file = os.path.join(
        log_directory,
        "velero-automation.log"
    )

    today = datetime.now().date()

    if os.path.exists(log_file):

        modified_date = datetime.fromtimestamp(
            os.path.getmtime(log_file)
        ).date()

        if modified_date != today:

            backup_file = os.path.join(
                log_directory,
                "velero-automation-{}.log".format(
                    modified_date.strftime("%Y-%m-%d")
                )
            )

            if os.path.exists(backup_file):
                os.remove(backup_file)

            os.rename(
                log_file,
                backup_file
            )

    logger = logging.getLogger("velero")

    logger.setLevel(logging.DEBUG)
    logger.propagate = False

    if logger.handlers:
        return logger

    file_handler = logging.FileHandler(
        log_file,
        mode="a",
        encoding="utf-8"
    )

    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(FileFormatter())

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_handler.setFormatter(ConsoleFormatter())

    # Allow detailed file-only messages
    # to remain hidden from console.
    console_handler.addFilter(ConsoleFilter())

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger