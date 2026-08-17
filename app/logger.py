import logging
import os
from datetime import datetime


def setup_logger():

    project_root = os.path.dirname(
        os.path.dirname(os.path.abspath(__file__))
    )

    log_directory = os.path.join(
        project_root,
        "logs"
    )

    os.makedirs(log_directory, exist_ok=True)

    log_file = os.path.join(
        log_directory,
        "velero-automation.log"
    )

    today = datetime.now().date()

    # Check whether the current log already belongs to today.
    needs_new_log = True

    if os.path.exists(log_file):

        modified_date = datetime.fromtimestamp(
            os.path.getmtime(log_file)
        ).date()

        if modified_date == today:
            needs_new_log = False

        else:
            backup_name = (
                "velero-automation-{}.log"
                .format(
                    modified_date.strftime("%Y-%m-%d")
                )
            )

            backup_file = os.path.join(
                log_directory,
                backup_name
            )

            # If a backup for that date already exists,
            # don't overwrite it.
            if not os.path.exists(backup_file):

                os.rename(
                    log_file,
                    backup_file
                )

            else:

                # Backup already exists.
                # Remove the current log so today's
                # execution can start fresh.
                os.remove(log_file)

    # Create a fresh log file when required.
    if needs_new_log and not os.path.exists(log_file):

        open(
            log_file,
            "w",
            encoding="utf-8"
        ).close()

    logger = logging.getLogger("velero")
    logger.setLevel(logging.INFO)

    # Prevent duplicate handlers if setup_logger()
    # is called more than once.
    if logger.handlers:
        return logger

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(message)s"
    )

    file_handler = logging.FileHandler(
        log_file,
        mode="a",
        encoding="utf-8"
    )

    file_handler.setFormatter(formatter)

    logger.addHandler(file_handler)

    return logger